"""Read-only Steam routing hints and current Wine process evidence.

Never execute tool manifests, launch options or DroidDeck scripts. A Steam tool
name/config_info is not proof of the final Wine path: DroidDeck can redirect it.
Only keep the selected identifiers and sync flags, never the full environment.
"""
from __future__ import annotations
import dataclasses
import json
import os
from pathlib import Path
import time

from core import APPID, SetupError, child, descend, digest, shortcuts, text_vdf, valid_proton

SYNC_KEYS = ('WINEESYNC', 'WINEFSYNC', 'PROTON_NO_ESYNC', 'PROTON_NO_FSYNC',
             'PROTON_NO_NTSYNC', 'BL_SYNC', 'BL_FSYNC', 'BL_SYNC_PACK')
WINE_NAMES = ('wine', 'wine64', 'wine-preloader', 'wine64-preloader')
DROIDDECK_SCRIPTS = tuple(Path('/usr/local/bin')/name for name in
                         ('steam-compatibility', 'droiddeck-game-env', 'droiddeck-esync'))


def mapping_choice(steam, appid):
    path = steam/'config/config.vdf'
    if not path.is_file():
        return '', 'Keine gespeicherte Steam-Zuordnung'
    block = descend(text_vdf(path.read_text()),
                    ['InstallConfigStore', 'Software', 'Valve', 'Steam', 'CompatToolMapping'])
    if block is not None:
        if not isinstance(block.value, list):
            raise SetupError('Invalid Steam CompatToolMapping.')
        for key, label in ((appid, 'Steam-Zuordnung für diese App'), ('0', 'Steam-Standard')):
            entry = child(block.value, key)
            if entry is not None:
                name = child(entry.value, 'name') if isinstance(entry.value, list) else None
                if name and isinstance(name.value, str) and name.value:
                    return name.value, label
    return '', 'Keine gespeicherte Steam-Zuordnung'


def tool_files(steam, libs, name):
    """Resolve internal tool IDs using their manifests, not display names."""
    if not name:
        return []
    bases = [steam/'compatibilitytools.d', Path('/usr/share/steam/compatibilitytools.d')]
    bases += [lib/'steamapps/common' for lib in libs]
    found = []
    for base in bases:
        for folder in sorted(base.glob('*')):
            vdf = folder/'compatibilitytool.vdf'
            if not vdf.is_file():
                continue
            try:
                block = descend(text_vdf(vdf.read_text()), ['compatibilitytools', 'compat_tools'])
                matched = block and isinstance(block.value, list) and child(block.value, name)
            except (SetupError, UnicodeError):
                # Unknown manifests cannot be used to claim a configuration match.
                continue
            if matched:
                found += [vdf, folder/'toolmanifest.vdf']
                # Observe wrapper changes too; do not run arbitrary command lines.
                found += [folder/n for n in ('proton', 'droiddeck-proton', 'bannerlator-proton',
                                             'droiddeck-proton-wrap', 'bannerlator-proton-wrap')]
    return sorted(set(p.resolve() for p in found if p.is_file()))


def options_and_identity(steam, account, appid):
    cfg = steam/'userdata'/account/'config'
    if appid == APPID:
        path = cfg/'localconfig.vdf'
        if not path.is_file():
            raise SetupError('Steam-Konto für die Zuordnungsprüfung auswählen.')
        n = descend(text_vdf(path.read_text()), ['UserLocalConfigStore','Software','Valve','Steam','apps',appid,'LaunchOptions'])
        return {'options': n.value if n else ''}
    path = cfg/'shortcuts.vdf'
    matches = [s for s in shortcuts(path.read_bytes()) if s.appid == appid]
    if len(matches) != 1:
        raise SetupError('OpenKH-Verknüpfung nicht eindeutig.')
    return {'options': matches[0].options, 'exe': matches[0].exe, 'name': matches[0].name}


def configuration(steam, account, appid, libs):
    name, source = mapping_choice(steam, appid)
    files = tool_files(steam, libs, name) + [p for p in DROIDDECK_SCRIPTS if p.is_file()]
    identity = options_and_identity(steam, account, appid)
    stamp = digest(json.dumps({'tool': name, 'source': source, 'shortcut': identity,
                              'scripts': {str(p): digest(p.read_bytes()) for p in files}},
                             sort_keys=True).encode())
    note = f'{source}: {name or "unbekannt"}. '
    note += 'DroidDeck kann auf eine esync-Kopie umleiten; config_info ist nur Historie.'
    return stamp, note


def file_stamp(path):
    st = path.stat()
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def runtime_stamp(proton):
    paths = [proton/'files/bin-arm64'/n for n in (*WINE_NAMES, 'wineserver')]
    paths += [proton/'version', proton/'proton', proton/'.droiddeck-esync.json']
    return {str(p): file_stamp(p) for p in paths if p.is_file()}


@dataclasses.dataclass
class Evidence:
    steam: Path
    account: str
    appid: str
    compat: Path
    proton: Path
    libs: list[Path]
    config_stamp: str
    runtime: dict
    captured: float
    pid: str
    sync: dict
    note: str

    def validate(self, steam, account, target):
        if (steam.resolve(), account, target.appid, target.compat.resolve(), target.proton.resolve()) != (
                self.steam, self.account, self.appid, self.compat, self.proton):
            raise SetupError(f'{target.label}: Auswahl stimmt nicht mit dem beobachteten Start überein. Erneut erkennen.')
        if not 0 <= time.time()-self.captured <= 1800:
            raise SetupError(f'{target.label}: Startnachweis älter als 30 Minuten. Erneut erkennen.')
        current, _ = configuration(self.steam, self.account, self.appid, self.libs)
        if current != self.config_stamp or runtime_stamp(self.proton) != self.runtime:
            raise SetupError(f'{target.label}: Steam-Zuordnung, Startoptionen oder Proton wurden seit der Erkennung geändert. Erneut starten und erkennen.')


def process_ids(env):
    ids = {env[k] for k in ('SteamAppId', 'STEAM_COMPAT_APP_ID')
           if env.get(k, '').isdigit() and env[k] != '0'}
    # Steam shortcuts may set SteamAppId=0, but encode their unsigned AppID here.
    for key in ('SteamGameId', 'SteamOverlayGameId'):
        raw = env.get(key, '')
        if raw.isdigit():
            value = int(raw)
            if value > 0xffffffff:
                ids.add(str(value >> 32))
            elif value:
                ids.add(str(value))
    return ids


def wine_root(process, candidates):
    """Match both the live executable's inode and path; reject hardlink ambiguity."""
    try:
        live = (process/'exe').stat()
        link = os.readlink(process/'exe')
    except (OSError, ValueError):
        return None
    matches = []
    for candidate in candidates:
        for name in WINE_NAMES:
            p = candidate/'files/bin-arm64'/name
            try:
                st = p.stat()
            except OSError:
                continue
            # PRoot may expose the Android host path in /proc; the entire guest
            # path must be its suffix, with the inode providing a second check.
            if (st.st_dev, st.st_ino) == (live.st_dev, live.st_ino) and (
                    link == str(p) or link.endswith(str(p)) or link == str(p.resolve()) or link.endswith(str(p.resolve()))):
                matches.append(candidate.resolve())
    matches = list(dict.fromkeys(matches))
    return matches[0] if len(matches) == 1 else None


def observe(steam, account, appid, libs, candidates, proc=Path('/proc')):
    """Read current Wine processes. No cached log or former config_info can pass."""
    before, note = configuration(steam, account, appid, libs)
    tool_name, _ = mapping_choice(steam, appid)
    mapped_roots = {p.parent for p in tool_files(steam, libs, tool_name) if p.name == 'compatibilitytool.vdf'}
    results = {}
    for process in proc.glob('[0-9]*'):
        try:
            raw = (process/'environ').read_bytes()
            env = dict(item.split('=', 1) for item in raw.decode('utf-8', 'surrogateescape').split('\0') if '=' in item)
            if appid not in process_ids(env):
                continue
            if process_ids(env) != {appid}:
                raise SetupError('Widersprüchliche Steam-AppIDs im laufenden Prozess; Erkennung abgebrochen.')
            client = env.get('STEAM_COMPAT_CLIENT_INSTALL_PATH', '')
            data = env.get('STEAM_COMPAT_DATA_PATH', '')
            prefix = env.get('WINEPREFIX', '')
            if not all(x.startswith('/') for x in (client, data, prefix)):
                continue
            if Path(client).resolve() != steam.resolve():
                continue
            compat = Path(data).resolve()
            if compat.name != appid or Path(prefix).resolve() != (compat/'pfx').resolve():
                raise SetupError('WINEPREFIX und Steam-compatdata widersprechen sich. Keine automatische Auswahl.')
            proton = wine_root(process, candidates)
            if proton is None:
                continue
            launched_tools = {Path(p).resolve() for p in env.get('STEAM_COMPAT_TOOL_PATHS', '').split(':') if p.startswith('/')}
            if mapped_roots and not mapped_roots.intersection(launched_tools):
                raise SetupError('Gespeicherte Steam-Zuordnung und laufender Start widersprechen sich oder lassen sich nicht abgleichen. Programm schließen, Steam-Einstellung prüfen und neu starten.')
            if not valid_proton(proton) or not (compat/'pfx/system.reg').is_file():
                continue
            server = env.get('WINESERVER', '')
            if server and (not server.startswith('/') or Path(server).resolve() != (proton/'files/bin-arm64/wineserver').resolve()):
                raise SetupError('Wine und WINESERVER stammen nicht eindeutig aus demselben Build. Keine Installation.')
            # Recheck the process identity after reading its executable (PID exit/reuse).
            if (process/'environ').read_bytes() != raw:
                continue
            sync = {k:env[k] for k in SYNC_KEYS if k in env}
            key = (compat, proton, tuple(sorted(sync.items())))
            results[key] = (process.name, sync)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    if len(results) != 1:
        raise SetupError('Kein eindeutiger laufender Wine-Prozess für diese App erkannt. '
                         'Das richtige Spiel/OpenKH über Steam starten und geöffnet lassen; dann erneut erkennen. '
                         'Mehrere Instanzen schließen. Ein alter Log oder config_info reicht nicht aus.')
    after, _ = configuration(steam, account, appid, libs)
    if after != before:
        raise SetupError('Steam-Konfiguration wurde während der Erkennung geändert. Bitte erneut erkennen.')
    (compat, proton, _), (pid, sync) = next(iter(results.items()))
    return Evidence(steam.resolve(), account, appid, compat, proton, list(libs), before,
                    runtime_stamp(proton), time.time(), pid, sync, note)


def validate_targets(plan):
    for target in plan.targets:
        if not isinstance(target.evidence, Evidence):
            raise SetupError(f'{target.label}: Prefix und Proton noch nicht durch einen laufenden Start bestätigt. '
                             'Programm über Steam öffnen und im Assistenten erkennen.')
        target.evidence.validate(plan.steam, plan.account, target)
