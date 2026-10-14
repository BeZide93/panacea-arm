"""DroidDeck setup operations. Importing this module does not modify the machine.

Steam metadata is parsed locally, never evaluated as shell code. Changes to VDF
files replace only the selected value; unknown fields/comments stay byte-identical.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import tempfile

APPID = '2552430'
DLL_SHA256 = 'c7d29191d69f5e132f5ca4a0a21d9ae75cd5f803a198ffa3f5f0220dc67f6360'
WINETRICKS_SHA256 = '672a1ff4442e8691a3ffc0e6860137e201a1d1227e9b3044245f1731e9e9837e'
KIT = Path(__file__).resolve().parents[1]


class SetupError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def host_env():
    """The manual setup's user-local tools, also for direct Python/desktop starts."""
    env = os.environ.copy()
    local_bin = str(Path.home()/'.local/bin')
    entries = env.get('PATH', os.defpath).split(os.pathsep)
    env['PATH'] = os.pathsep.join([local_bin] + [p for p in entries if p != local_bin])
    return env


@dataclasses.dataclass
class Node:
    key: str
    value: object
    start: int = 0
    end: int = 0
    close: int = 0


def child(nodes, key):
    matches = [n for n in nodes if n.key.lower() == key.lower()]
    if len(matches) > 1:
        raise SetupError(f'Ambiguous Steam field: {key}')
    return matches[0] if matches else None


def descend(nodes, keys):
    for index, key in enumerate(keys):
        n = child(nodes, key)
        if n is None:
            return None
        nodes = n.value
        if index < len(keys)-1 and not isinstance(nodes, list):
            raise SetupError(f'Expected Steam object: {key}')
    return n


def unquote(s):
    return re.sub(r'\\([\\"nt])', lambda m: {'n': '\n', 't': '\t'}.get(m[1], m[1]), s[1:-1])


def quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t') + '"'


def text_vdf(text):
    tokens = list(re.finditer(r'\s+|//[^\r\n]*|"(?:\\.|[^"\\])*"|[{}]', text))
    pos = 0
    useful = []
    for m in tokens:
        if m.start() != pos:
            raise SetupError('Unsupported Steam VDF syntax; file left unchanged.')
        pos = m.end()
        if not m[0].isspace() and not m[0].startswith('//'):
            useful.append(m)
    if pos != len(text):
        raise SetupError('Incomplete Steam VDF.')
    i = 0

    def obj(nested=False):
        nonlocal i
        result = []
        while i < len(useful):
            k = useful[i]; i += 1
            if k[0] == '}':
                if not nested:
                    raise SetupError('Unexpected VDF brace.')
                return result, k.start()
            if not k[0].startswith('"') or i == len(useful):
                raise SetupError('Invalid VDF key.')
            v = useful[i]; i += 1
            if v[0] == '{':
                value, close = obj(True)
                result.append(Node(unquote(k[0]), value, v.start(), useful[i-1].end(), close))
            elif v[0].startswith('"'):
                result.append(Node(unquote(k[0]), unquote(v[0]), v.start(), v.end()))
            else:
                raise SetupError('Invalid VDF value.')
        if nested:
            raise SetupError('Missing VDF closing brace.')
        return result, len(text)
    return obj()[0]


def set_text_value(raw, keys, value):
    text = raw.decode('utf-8')
    nodes = text_vdf(text)
    parent = None
    for index, key in enumerate(keys):
        n = child(nodes, key)
        if n is None:
            if parent is None:
                raise SetupError('Unexpected Steam config root; file left unchanged.')
            tail = quote(keys[-1]) + '\t' + quote(value)
            for missing in reversed(keys[index:-1]):
                tail = quote(missing) + '\n{\n' + tail + '\n}'
            return (text[:parent.close] + '\n' + tail + '\n' + text[parent.close:]).encode()
        if index == len(keys)-1:
            if not isinstance(n.value, str):
                raise SetupError('LaunchOptions is not a string.')
            return (text[:n.start] + quote(value) + text[n.end:]).encode()
        if not isinstance(n.value, list):
            raise SetupError('Unexpected Steam config value.')
        parent, nodes = n, n.value
    raise SetupError('Empty VDF path.')


def binary_vdf(raw):
    pos = 0

    def take(n):
        nonlocal pos
        if n < 0 or pos+n > len(raw):
            raise SetupError('Truncated shortcuts.vdf.')
        b = raw[pos:pos+n]; pos += n
        return b

    def string():
        nonlocal pos
        end = raw.find(b'\0', pos)
        if end < 0:
            raise SetupError('Unterminated shortcut string.')
        b = take(end-pos+1)
        return b[:-1].decode('utf-8')

    def obj(depth=0):
        nonlocal pos
        if depth > 32:
            raise SetupError('Shortcut nesting too deep.')
        result = []
        while True:
            kind = take(1)[0]
            if kind == 8:
                return result, pos-1
            key = string(); start = pos; close = 0
            if kind == 0:
                value, close = obj(depth+1)
            elif kind == 1:
                value = string()
            elif kind in (2, 3, 4, 6):
                b = take(4)
                value = struct.unpack('<I', b)[0] if kind == 2 else b
            elif kind in (7, 10):
                value = take(8)
            else:
                raise SetupError(f'Unsupported shortcut type {kind}; file left unchanged.')
            result.append(Node(key, value, start, pos, close))
    nodes, _ = obj()
    if pos != len(raw):
        raise SetupError('Unexpected trailing shortcuts.vdf data.')
    return nodes


@dataclasses.dataclass
class Shortcut:
    appid: str
    name: str
    exe: str
    options: str
    record: Node


def shortcuts(raw):
    root = child(binary_vdf(raw), 'shortcuts')
    if root is None or not isinstance(root.value, list):
        raise SetupError('No shortcuts object found.')
    result = []
    for record in root.value:
        if not isinstance(record.value, list):
            continue
        def field(key, default=''):
            n = child(record.value, key)
            return n.value if n else default
        appid = field('appid', 0)
        if not isinstance(appid, int) or not 0 < appid <= 0xffffffff:
            continue
        result.append(Shortcut(str(appid), field('AppName'), field('Exe'), field('LaunchOptions'), record))
    return result


def set_shortcut_options(raw, appid, value):
    matches = [s for s in shortcuts(raw) if s.appid == appid]
    if len(matches) != 1:
        raise SetupError('OpenKH shortcut is missing or ambiguous.')
    record = matches[0].record
    n = child(record.value, 'LaunchOptions')
    b = value.encode() + b'\0'
    if n:
        if not isinstance(n.value, str):
            raise SetupError('Invalid shortcut LaunchOptions type.')
        return raw[:n.start] + b + raw[n.end:]
    return raw[:record.close] + b'\x01LaunchOptions\0' + b + raw[record.close:]


def merge_options(options, variable, value):
    """Preserve wrappers/arguments; refuse dynamic shell expressions instead of guessing."""
    if '\n' in options or '\r' in options or '$' in options or '`' in options:
        raise SetupError('Dynamic Steam launch options need manual editing; no changes made.')
    lexer = shlex.shlex(options, posix=True, punctuation_chars=';&|<>()')
    lexer.whitespace_split = True; lexer.commenters = ''
    try:
        parts = list(lexer)
    except ValueError as e:
        raise SetupError(f'Invalid launch options: {e}') from e
    if any(p and all(c in ';&|<>()' for c in p) for p in parts):
        raise SetupError('Compound Steam launch commands need manual editing.')
    if any(p.startswith(('WINEPREFIX=', 'STEAM_COMPAT_DATA_PATH=')) for p in parts):
        raise SetupError('Launch options redirect the Wine prefix; use the manual setup for that custom prefix.')
    count = options.count('%command%')
    if count > 1:
        raise SetupError('More than one %command% in launch options.')
    assignment = re.compile(r'(?<!\S)' + re.escape(variable) + r'=(?:"([^"\\]*)"|\x27([^\x27\\]*)\x27|([^\s\x27"\\]+))')
    found = list(assignment.finditer(options))
    assignments = [p for p in parts if p.startswith(variable+'=')]
    if len(found) != len(assignments) or len(found) > 1:
        raise SetupError(f'Unsupported or repeated {variable} assignment.')
    if found and count and found[0].start() > options.index('%command%'):
        raise SetupError(f'{variable} occurs after %command%; please edit manually.')
    old = next((g for g in found[0].groups() if g is not None), '') if found else ''
    if variable == 'WINEDLLOVERRIDES':
        overrides = []
        required = dict(item.split('=', 1) for item in value.split(';'))
        # Separate grouped overrides (e.g. version,foo=b) without losing foo.
        for item in old.split(';'):
            if not item:
                continue
            if '=' not in item:
                raise SetupError('Cannot merge malformed DLL overrides.')
            names, mode = item.split('=', 1)
            keep = [n for n in names.split(',') if n.lower().lstrip('*') not in {k.lower() for k in required}]
            if keep:
                overrides.append(','.join(keep)+'='+mode)
        value = ';'.join(overrides + [k+'='+v for k, v in required.items()])
    new = variable + '=' + shlex.quote(value)
    if found:
        m = found[0]
        updated = options[:m.start()] + new + options[m.end():]
        if count:
            return updated
        # Without %command%, Steam treats options as game arguments. Do not
        # reinterpret an apparent assignment as an environment command.
        raise SetupError('Environment assignment without %command%; edit manually.')
    if count:
        return options.replace('%command%', 'env '+new+' %command%')
    return 'env '+new+' %command%' + (' '+options if options.strip() else '')


def unique_paths(paths):
    return list(dict.fromkeys(p.expanduser().resolve() for p in paths if p.exists()))


def steam_roots(home):
    return unique_paths(p for p in [home/'.local/share/Steam', home/'.steam/steam', home/'.steam/root'] if (p/'steamapps').is_dir())


def libraries(steam, home):
    paths = [steam, home/'Games/Windows', Path('/mnt/droiddeck'), Path('/mnt/droiddeck-sd')]
    path = steam/'steamapps/libraryfolders.vdf'
    if path.exists():
        root = child(text_vdf(path.read_text()), 'libraryfolders')
        if root and isinstance(root.value, list):
            for item in root.value:
                n = child(item.value, 'path') if isinstance(item.value, list) else None
                if n and isinstance(n.value, str):
                    paths.append(Path(n.value))
                elif item.key.isdigit() and isinstance(item.value, str):
                    paths.append(Path(item.value))
    return unique_paths(paths)


def game_dirs(libs):
    result = []
    for lib in libs:
        acf = lib/f'steamapps/appmanifest_{APPID}.acf'
        if acf.exists():
            n = descend(text_vdf(acf.read_text()), ['AppState', 'installdir'])
            if n and isinstance(n.value, str) and Path(n.value).name == n.value:
                p = lib/'steamapps/common'/n.value
                if p.is_dir():
                    result.append(p)
    return unique_paths(result)


def prefixes(libs, appid):
    if not re.fullmatch(r'[1-9][0-9]{0,9}', appid) or int(appid) > 0xffffffff:
        raise SetupError('Invalid Steam AppID.')
    return unique_paths(lib/f'steamapps/compatdata/{appid}' for lib in libs
                        if (lib/f'steamapps/compatdata/{appid}/pfx/system.reg').is_file())


def proton_candidates(home, libs, steam):
    paths = list((home/'.local/share/droiddeck-esync/dist').glob('*'))
    paths += list((steam/'compatibilitytools.d').glob('*'))
    for lib in libs:
        paths += list((lib/'steamapps/common').glob('*'))
    return unique_paths(p for p in paths if valid_proton(p))


def valid_proton(p):
    return all((p/'files/bin-arm64'/n).is_file() and os.access(p/'files/bin-arm64'/n, os.X_OK)
               for n in ['wine', 'wineserver'])


def accounts(steam):
    return sorted(p.name for p in (steam/'userdata').glob('*')
                  if p.name.isdigit() and (p/'config/localconfig.vdf').is_file())


def dotnet_hosts(prefix):
    drive = prefix/'drive_c'
    return [p for p in [drive/'Program Files/dotnet/dotnet.exe',
                       drive/'Program Files/dotnet/x64/dotnet.exe',
                       drive/'Program Files (x86)/dotnet/dotnet.exe',
                       drive/'Program Files/dotnet/x86/dotnet.exe'] if p.is_file()]


def pe_machine(path):
    try:
        with path.open('rb') as f:
            if f.read(2) != b'MZ': return None
            f.seek(0x3c); offset = struct.unpack('<I', f.read(4))[0]
            if offset > path.stat().st_size-6: return None
            f.seek(offset)
            if f.read(4) != b'PE\0\0': return None
            return struct.unpack('<H', f.read(2))[0]
    except (OSError, struct.error):
        return None


def runtime_ready(reports, runtime):
    # Require working x86 and x64 Windows hosts, not an ARM64/Linux dotnet.
    return all(any(machine == arch and re.search(r'^'+re.escape(runtime)+r'\s+8\.[0-9.]+\s+\[', out, re.M)
                   for machine, out in reports) for arch in (0x14c, 0x8664))


def wine_env(target, steam):
    env = host_env()
    files = target.proton/'files'
    env.update(WINEPREFIX=str(target.compat/'pfx'), WINE=str(files/'bin-arm64/wine'),
               WINESERVER=str(files/'bin-arm64/wineserver'),
               STEAM_COMPAT_DATA_PATH=str(target.compat), STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
               SteamAppId=target.appid, SteamGameId=target.appid)
    env['PATH'] = str(files/'bin-arm64')+':'+env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = ':'.join(str(files/'lib'/a) for a in ['x86_64-linux-gnu','aarch64-linux-gnu','i386-linux-gnu']) + (':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    env['WINEDLLPATH'] = str(files/'lib/vkd3d')+':'+str(files/'lib/wine') + (':'+env['WINEDLLPATH'] if env.get('WINEDLLPATH') else '')
    env.pop('WINEARCH', None)
    return env


def running_clients(proc=Path('/proc')):
    """Conservative check: don't back up a prefix while Steam/Wine is active."""
    found = []
    for p in proc.glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip().lower()
            if name in ('steam', 'steamwebhelper', 'wineserver', 'wine', 'wine64', 'wineserver64') or name.endswith('.exe'):
                found.append(f'{name} (PID {p.name})')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Other users' processes cannot use this user's private prefix.
            if p.stat().st_uid == os.getuid():
                raise SetupError('Cannot inspect your processes. Close Steam/Wine and check /proc access.')
    return found


def require_stopped():
    active = running_clients()
    if active:
        raise SetupError('Close Steam, games and Windows applications first:\n'+'\n'.join(active[:12]))


@dataclasses.dataclass
class Target:
    label: str
    appid: str
    compat: Path
    proton: Path
    game: bool = False


@dataclasses.dataclass
class Plan:
    steam: Path
    account: str
    game_dir: Path
    backup_root: Path
    targets: list[Target]
    runtimes: bool = True
    install_dll: bool = True
    launch_options: bool = True
    registry_batch: Path | None = None
    registry_appid: str = APPID

    def validate(self):
        if not self.targets or not (self.steam/'steamapps').is_dir():
            raise SetupError('Select an existing Steam installation and prefix.')
        if len({t.appid for t in self.targets}) != len(self.targets):
            raise SetupError('Each target AppID must be unique.')
        for t in self.targets:
            if not t.compat.is_absolute() or t.compat.name != t.appid or not t.appid.isdigit() or not 0 < int(t.appid) <= 0xffffffff:
                raise SetupError(f'{t.label}: select compatdata/{t.appid}, without /pfx.')
            if not (t.compat/'pfx/system.reg').is_file() or not (t.compat/'pfx/drive_c').is_dir():
                raise SetupError(f'{t.label}: start this program once through Steam to create its prefix.')
            if not t.proton.is_absolute() or not valid_proton(t.proton):
                raise SetupError(f'{t.label}: select the active ARM64 Proton folder.')
            if self.backup_root.resolve().is_relative_to(t.compat.resolve()):
                raise SetupError('Backup directory must be outside every selected compatdata folder.')
        if self.install_dll:
            if not self.game_dir.is_dir() or not any(p.name.lower() == 'kingdom hearts ii final mix.exe' for p in self.game_dir.iterdir()):
                raise SetupError('Select the game folder containing KINGDOM HEARTS II FINAL MIX.exe.')
            if any(p.name.lower() == 'version.dll' and p.name != 'version.dll' for p in self.game_dir.iterdir()):
                raise SetupError('A differently capitalized VERSION.DLL exists. Back it up and rename it to version.dll first.')
            if not any(t.game and t.appid == APPID for t in self.targets):
                raise SetupError('The game prefix must be selected to install Panacea.')
        if self.launch_options and (not self.account.isdigit() or not (self.steam/'userdata'/self.account/'config/localconfig.vdf').is_file()):
            raise SetupError('Select the Steam account whose launch options should be changed.')
        if self.registry_batch:
            if not self.registry_batch.is_file() or self.registry_batch.name.lower() != 'add_registry.bat':
                raise SetupError('Select your original OpenKH add_registry.bat.')
            if self.registry_appid not in [t.appid for t in self.targets]:
                raise SetupError('Registry target prefix is not selected.')


def launch_edits(plan):
    edits = []
    cfg = plan.steam/'userdata'/plan.account/'config'
    for t in plan.targets:
        if t.game:
            path = cfg/'localconfig.vdf'
            raw = path.read_bytes()
            keys = ['UserLocalConfigStore','Software','Valve','Steam','apps',APPID,'LaunchOptions']
            n = descend(text_vdf(raw.decode()), keys)
            options = n.value if n else ''
            new = merge_options(options, 'WINEDLLOVERRIDES', 'version=n,b;dinput8=n,b;LuaBackend=n,b')
            after = set_text_value(raw, keys, new)
        else:
            path = cfg/'shortcuts.vdf'
            raw = path.read_bytes()
            matches = [s for s in shortcuts(raw) if s.appid == t.appid]
            if len(matches) != 1 or 'openkh' not in (matches[0].name+' '+matches[0].exe).lower():
                raise SetupError('Selected shortcut is not an identifiable OpenKH shortcut.')
            new = merge_options(matches[0].options, 'PROTON_USE_WINED3D', '1')
            after = set_shortcut_options(raw, t.appid, new)
        if raw != after:
            edits.append((path, raw, after))
    return edits


def atomic_replace(path, data, expected):
    """Compare before replacing. Preserve file mode and avoid following a DLL symlink."""
    if path.is_symlink():
        raise SetupError(f'Refusing to overwrite a symlink: {path}')
    current = path.read_bytes() if path.exists() else None
    if current != expected:
        raise SetupError(f'File changed since review; not overwritten: {path}')
    fd, temp = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        # Recheck after staging to catch Steam starting during installation.
        if (path.read_bytes() if path.exists() else None) != expected:
            raise SetupError(f'File changed during installation: {path}')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def dll_payload():
    for p in [KIT/'payload/version.dll', KIT.parent/'version.dll']:
        if p.is_file() and digest(p.read_bytes()) == DLL_SHA256 and pe_machine(p) == 0x8664:
            return p.read_bytes()
    raise SetupError('Verified main version.dll is missing. Use the complete setup ZIP.')


class Runner:
    def __init__(self, emit, logfile):
        self.emit = emit
        self.logfile = logfile

    def log(self, text):
        self.logfile.write(text+'\n'); self.logfile.flush(); self.emit(text)

    def run(self, args, env=None, cwd=None, timeout=1800):
        self.log('$ '+shlex.join(str(x) for x in args))
        # All commands use argv arrays; no paths or Steam values are executed as shell text.
        try:
            result = subprocess.run([str(x) for x in args], env=host_env() if env is None else env, cwd=cwd,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise SetupError('Command timed out. Close any remaining Windows installer before retrying. Backup is retained.') from e
        self.log(result.stdout[-100000:])
        if result.returncode:
            raise SetupError(f'Command failed ({result.returncode}): {Path(str(args[0])).name}. See setup.log.')
        return result.stdout


def tree_bytes(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())


def backup(plan, edits, runner):
    root = plan.backup_root
    root.mkdir(parents=True, exist_ok=True)
    need = sum(tree_bytes(t.compat/'pfx') for t in plan.targets) + 128*1024*1024
    if shutil.disk_usage(root).free < need:
        raise SetupError(f'Not enough backup space: need at least {need//(1024*1024)} MiB.')
    folder = Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=root))
    runner.log('BACKUP: '+str(folder))
    metadata = {'complete': False, 'prefixes': [], 'files': []}
    manifest = folder/'backup.json'
    manifest.write_text(json.dumps(metadata, indent=2))
    for t in plan.targets:
        dest = folder/t.appid
        dest.mkdir()
        runner.run(['cp','-a','--reflink=auto','--',t.compat/'pfx',dest/'pfx'])
        metadata['prefixes'].append({'original':str(t.compat/'pfx'),'backup':str(dest/'pfx'),'proton':str(t.proton)})
    paths = [e[0] for e in edits]
    if plan.install_dll:
        paths.append(plan.game_dir/'version.dll')
    for index, path in enumerate(dict.fromkeys(paths)):
        if path.is_symlink():
            raise SetupError(f'Cannot safely replace symlink: {path}')
        dest = folder/f'file-{index}-{path.name}'
        existed = path.exists()
        if existed:
            shutil.copy2(path, dest)
        metadata['files'].append({'original':str(path),'backup':str(dest) if existed else None})
    metadata['complete'] = True
    manifest.write_text(json.dumps(metadata, indent=2))
    (folder/'RESTORE.txt').write_text(
        'Close Steam and every Wine application before restoring.\n'
        'backup.json maps every backup to its original location.\n'
        'For a prefix: rename the current pfx to pfx-after-setup, then COPY the backed-up pfx to the original location.\n'
        'A full prefix restore also reverts saves/settings added since this backup. Keep the renamed copy.\n'
        'For a file: copy its backup over the original; backup=null means the installer added the file.\n'
        'Restoring a Steam config also reverts later edits to that file.\n')
    return folder


def reports(target, plan, runner):
    result = []
    env = wine_env(target, plan.steam)
    for host in dotnet_hosts(target.compat/'pfx'):
        machine = pe_machine(host)
        if machine in (0x14c, 0x8664):
            try:
                out = runner.run([env['WINE'], host, '--list-runtimes'], env=env, timeout=120)
                result.append((machine, out))
            except SetupError as e:
                runner.log('Runtime probe failed: '+str(e))
    return result


def check_wine(env, runner):
    out = runner.run([env['WINE'], 'cmd.exe', '/c', 'echo WINE_TEST_OK'], env=env, timeout=120)
    if 'WINE_TEST_OK' not in [line.strip() for line in out.splitlines()]:
        raise SetupError('Wine exited without the expected WINE_TEST_OK marker.')


def installed_verbs(prefix):
    log = prefix/'winetricks.log'
    return set(log.read_text().splitlines()) if log.exists() else set()


def install_runtimes(target, plan, runner):
    env = wine_env(target, plan.steam)
    check_wine(env, runner)
    current = reports(target, plan, runner)
    wants = [('dotnet8','Microsoft.NETCore.App'), ('dotnetdesktop8','Microsoft.WindowsDesktop.App')]
    if target.game:
        wants += [('vcrun6', None), ('xaudio29', None)]
    for verb, runtime in wants:
        records = installed_verbs(target.compat/'pfx')
        ready = runtime_ready(current, runtime) if runtime else verb in records
        if ready:
            runner.log(f'{target.label}: {verb} already installed; skipped.')
            continue
        if verb in records:
            raise SetupError(f'{target.label}: {verb} is recorded but its Windows runtimes do not pass the checks. No forced reinstall; inspect setup.log.')
        runner.run(['bash', KIT/'tools/winetricks','-q',verb], env=env)
        check_wine(env, runner)
        if runtime:
            current = reports(target, plan, runner)
            if not runtime_ready(current, runtime):
                raise SetupError(f'{target.label}: {runtime} 8.x is not working in both Windows architectures after installation.')
        elif verb not in installed_verbs(target.compat/'pfx'):
            raise SetupError(f'{target.label}: Winetricks did not record successful installation of {verb}.')


def execute(plan, runner):
    plan.validate()
    require_stopped()
    # Resolve every edit/payload before modifying prefixes; malformed launch
    # options stop here and can be handled by deselecting automatic editing.
    edits = launch_edits(plan) if plan.launch_options else []
    dll = dll_payload() if plan.install_dll else None
    dll_before = (plan.game_dir/'version.dll').read_bytes() if dll and (plan.game_dir/'version.dll').exists() else None
    if plan.runtimes:
        wt = KIT/'tools/winetricks'
        search_path = host_env()['PATH']
        missing = [n for n in ['python3','curl','cabextract','unzip','file'] if not shutil.which(n, path=search_path)]
        if not missing:
            runner.log('Using cabextract: '+str(shutil.which('cabextract', path=search_path)))
        if missing or not wt.is_file():
            runner.log('Preparing missing Linux helper tools and verified Winetricks.')
            if missing and os.geteuid() != 0:
                if not shutil.which('sudo'):
                    raise SetupError('Missing Linux tools: '+', '.join(missing)+
                                     '. This session has no sudo. Install these tools using your Linux environment’s package installation facility, then retry. No prefix changed.')
                runner.log('Please confirm sudo in the terminal window opened with this assistant.')
                # Inherit the terminal so sudo's password prompt stays visible.
                if subprocess.run(['sudo','-v']).returncode:
                    raise SetupError('Administrator authentication cancelled; no prefix changed.')
            runner.run(['bash',KIT/'00-host-tools.sh','--install'])
        if not wt.is_file() or digest(wt.read_bytes()) != WINETRICKS_SHA256:
            raise SetupError('Winetricks checksum mismatch; no prefix changed.')
    require_stopped()
    folder = backup(plan, edits, runner)
    runner.log('BACKUP COMPLETE. '+str(folder))
    require_stopped()
    for target in plan.targets:
        env = wine_env(target, plan.steam)
        if plan.runtimes:
            install_runtimes(target, plan, runner)
        else:
            check_wine(env, runner)
        if plan.registry_batch and target.appid == plan.registry_appid:
            batch = plan.registry_batch
            winpath = runner.run([env['WINE'],'winepath.exe','-w',batch], env=env, timeout=60).strip().splitlines()[-1]
            if '"' in winpath or '\n' in winpath or not re.match(r'^[A-Za-z]:\\', winpath):
                raise SetupError('Invalid Windows path for registry batch.')
            runner.run([env['WINE'],'cmd.exe','/d','/s','/c','"'+winpath+'"'],env=env,cwd=batch.parent)
            check_wine(env, runner)
        # Wait for this prefix's Wine services to exit before the final Steam check.
        runner.run([env['WINESERVER'],'-w'],env=env,timeout=120)
    require_stopped()
    # Check ALL files before committing any file changes.
    for path, before, _ in edits:
        if path.is_symlink() or path.read_bytes() != before:
            raise SetupError(f'Steam config changed during setup: {path}; edits were not applied.')
    if dll:
        atomic_replace(plan.game_dir/'version.dll',dll,dll_before)
        runner.log('Installed verified main version.dll (custom logging disabled).')
    for path, before, after in edits:
        atomic_replace(path,after,before)
        runner.log('Updated launch options: '+str(path))
    runner.log('SETUP COMPLETE. Backup: '+str(folder))
    return folder


@contextlib.contextmanager
def setup_lock(state):
    state.mkdir(parents=True, exist_ok=True)
    with (state/'setup.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise SetupError('Another setup assistant is already running.') from e
        yield


def plan_summary(plan):
    lines=[]
    for t in plan.targets:lines.append(f'{t.label} ({t.appid})\nPrefix: {t.compat}/pfx\nProton: {t.proton}')
    lines.append('Backup: '+str(plan.backup_root))
    if plan.runtimes:lines.append('Runtimes prüfen; fehlende .NET-8-Runtimes (x86/x64), für KH zusätzlich vcrun6 und xaudio29 installieren.\nDas Paket nutzt die dokumentierten Winetricks-Versionen (.NET 8.0.12); vorhandene funktionierende 8.x-Versionen bleiben erhalten.')
    if plan.install_dll:lines.append('Main version.dll ersetzen: '+str(plan.game_dir))
    if plan.registry_batch:lines.append(f'Registry-Batch AUSFÜHREN: {plan.registry_batch}\nIm Prefix für AppID {plan.registry_appid}.')
    if plan.launch_options:
        edits=launch_edits(plan)
        if not edits:lines.append('Steam-Startoptionen sind bereits gesetzt.')
        for path, before, after in edits:
            if path.name == 'localconfig.vdf':
                value=descend(text_vdf(after.decode()),['UserLocalConfigStore','Software','Valve','Steam','apps',APPID,'LaunchOptions']).value
                lines.append('Kingdom Hearts Startoptionen:\n'+value)
            else:
                ids={t.appid for t in plan.targets if not t.game}
                lines.extend('OpenKH Startoptionen:\n'+s.options for s in shortcuts(after) if s.appid in ids)
    return '\n\n'.join(lines)
