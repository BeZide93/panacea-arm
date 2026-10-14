"""Install missing DroidDeck helpers in the user's home, never into the Linux rootfs.

pacman is used only for dependency resolution (--print) against private repository
metadata. Packages are downloaded over HTTPS, checked against the repository SHA256,
and unpacked without executing package scripts or changing pacman's installed DB.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import venv

from core import SetupError, host_env

TOOLS = {'curl': ['--version'], 'cabextract': ['--version'], 'unzip': ['-v'], 'file': ['--version']}
MIRRORS = ('https://ca.us.mirror.archlinuxarm.org', 'https://de3.mirror.archlinuxarm.org')
MAX_DOWNLOAD = 256 * 1024 * 1024


def working(name, env=None):
    env = env or host_env()
    path = shutil.which(name, path=env['PATH'])
    if not path:
        return False
    try:
        return subprocess.run([path, *TOOLS[name]], env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def missing_tools():
    return [name for name in TOOLS if not working(name)]


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise SetupError('Refusing a non-HTTPS download redirect.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, dest, checksum=None):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise SetupError('Downloads require HTTPS.')
    opener = urllib.request.build_opener(HTTPSOnly())
    digest = hashlib.sha256()
    try:
        with opener.open(url, timeout=45) as source, dest.open('wb') as target:
            total = 0
            while block := source.read(1024 * 1024):
                total += len(block)
                if total > MAX_DOWNLOAD:
                    raise SetupError('Helper download exceeds the size limit.')
                digest.update(block); target.write(block)
        if checksum and digest.hexdigest() != checksum:
            raise SetupError('Helper package checksum mismatch: '+dest.name)
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def package_records(text):
    records = []
    for line in text.splitlines():
        fields = line.split('|')
        if len(fields) != 4:
            raise SetupError('Unexpected pacman package metadata.')
        name, arch, checksum, url = fields
        parsed = urllib.parse.urlsplit(url)
        if (not re.fullmatch(r'[a-zA-Z0-9@+_.-]+', name) or arch not in ('aarch64','any')
                or not re.fullmatch(r'[0-9a-f]{64}', checksum)
                or parsed.scheme != 'https' or parsed.username or parsed.password
                or parsed.hostname not in {urllib.parse.urlsplit(m).hostname for m in MIRRORS}
                or not re.fullmatch(r'/aarch64/(core|extra)/[a-zA-Z0-9@+_.:-]+\.pkg\.tar\.(xz|zst|gz)', parsed.path)
                or parsed.query or parsed.fragment):
            raise SetupError('Invalid helper package metadata: '+name)
        records.append(dict(name=name, sha256=checksum, url=url))
    if not records or len(records) > 80:
        raise SetupError('Unexpected number of helper packages.')
    return records


def resolve_packages(names, work, log):
    pacman = shutil.which('pacman', path=host_env()['PATH'])
    if not pacman:
        raise SetupError('DroidDeck base tool pacman is missing. Restore the DroidDeck Linux environment; no prefix changed.')
    db = work/'db';(db/'sync').mkdir(parents=True)
    # Only read the installed package records. --print does not update them.
    installed = Path('/var/lib/pacman/local')
    if installed.is_dir():
        (db/'local').symlink_to(installed, target_is_directory=True)
    last = None
    for mirror in MIRRORS:
        try:
            log('Reading Arch Linux ARM package metadata: '+mirror)
            for repo in ('core','extra'):
                download(f'{mirror}/aarch64/{repo}/{repo}.db', db/'sync'/f'{repo}.db')
            config = work/'pacman.conf'
            config.write_text('[options]\nArchitecture = aarch64\n'+''.join(
                f'[{repo}]\nServer = {mirror}/aarch64/{repo}\n' for repo in ('core','extra')))
            command = [pacman,'--config',str(config),'--dbpath',str(db),'-Sp',
                       '--print-format','%n|%a|%h|%l','--noconfirm','--',*names]
            result = subprocess.run(command, env=host_env(), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            if result.returncode:
                raise SetupError('Cannot resolve helper dependencies: '+result.stderr[-2000:])
            records = package_records(result.stdout)
            if not set(names).issubset({r['name'] for r in records}):
                raise SetupError('Dependency plan omits requested helpers.')
            return records
        except (OSError, ValueError, SetupError, subprocess.TimeoutExpired) as error:
            last = error
    raise SetupError('Cannot obtain helper packages: '+str(last))


def safe_unpack(archive, root):
    """Extract only regular files and contained links, with no package install scripts."""
    try:
        source = tarfile.open(archive, 'r:*')
    except tarfile.ReadError:
        # Arch packages may use zstd. DroidDeck's bsdtar supports it natively.
        bsdtar = shutil.which('bsdtar', path=host_env()['PATH'])
        if not bsdtar:
            raise SetupError('This package requires DroidDeck’s bsdtar for zstd decompression.')
        plain = archive.with_suffix('.plain.tar')
        with plain.open('wb') as output:
            # Convert the archive; Python performs the actual path-checked extraction.
            result = subprocess.run([bsdtar,'-cf','-','--format=ustar','@'+str(archive)],
                                    stdout=output, stderr=subprocess.PIPE, timeout=120, env=host_env())
        if result.returncode:
            raise SetupError('Cannot decompress helper package: '+result.stderr.decode(errors='replace')[-1000:])
        source = tarfile.open(plain, 'r:')
    with source:
        members = source.getmembers()
        if sum(m.size for m in members) > 512 * 1024 * 1024:
            raise SetupError('Unpacked helper package is too large.')
        links = []
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise SetupError('Unsafe package path: '+member.name)
            # Keep licenses/data too; never touch /etc, /var or execute .INSTALL.
            if not path.parts or path.parts[0] != 'usr':
                continue
            target = root.joinpath(*path.parts)
            if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != root.parent):
                raise SetupError('Package path crosses a symbolic link.')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as data, target.open('wb') as out:
                    shutil.copyfileobj(data,out)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym() or member.islnk():
                links.append((member,target))
            else:
                raise SetupError('Unsupported helper package entry.')
        for member,target in links:
            link = PurePosixPath(member.linkname)
            if link.is_absolute():
                raise SetupError('Absolute package link is not allowed.')
            dest = (target.parent/str(link) if member.issym() else root/str(link)).resolve()
            if not dest.is_relative_to(root.resolve()/'usr'):
                raise SetupError('Package link escapes helper directory.')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() or target.is_symlink():
                if target.is_symlink() and target.resolve() == dest: continue
                raise SetupError('Conflicting helper package link.')
            if member.issym(): target.symlink_to(member.linkname)
            else: shutil.copyfile(dest,target)


def wrapper(root, name):
    binary = root/'usr/bin'/name
    lib = root/'usr/lib'
    lines = ['#!/bin/sh', '# Managed by Panacea ARM setup.']
    # A private glibc, if requested by dependency resolution, needs its own loader.
    loader = lib/'ld-linux-aarch64.so.1'
    command = [str(binary)]
    if loader.exists():
        command = [str(loader),'--library-path',str(lib),str(binary)]
    else:
        lines.append('export LD_LIBRARY_PATH='+shlex.quote(str(lib))+'${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}')
    if name == 'file':
        magic = next((p for p in (root/'usr/share').rglob('magic.mgc') if p.is_file()), None)
        if magic:
            lines.append('export MAGIC='+shlex.quote(str(magic)))
    lines.append('exec '+shlex.join(command)+' "$@"')
    return '\n'.join(lines)+'\n'


def install_local(names, log=print, home=None):
    home = home or Path.home()
    if platform.machine().lower() not in ('aarch64','arm64'):
        raise SetupError('Local helper packages require DroidDeck ARM64 Linux.')
    if not names or any(n not in TOOLS for n in names):
        raise SetupError('Invalid helper selection.')
    base = home/'.local/share/panacea-arm/host-tools';base.mkdir(parents=True,exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='install-',dir=base))
    published = False
    try:
        with tempfile.TemporaryDirectory(prefix='download-',dir=base) as temp:
            work = Path(temp)
            records = resolve_packages(names,work,log)
            for rec in records:
                archive = work/Path(urllib.parse.urlsplit(rec['url']).path).name
                log('Downloading/verifying Linux helper package: '+rec['name'])
                error = None
                path = urllib.parse.urlsplit(rec['url']).path
                urls = list(dict.fromkeys([rec['url'], *(m+path for m in MIRRORS)]))
                for url in urls:
                    try:
                        download(url,archive,rec['sha256'])
                        error = None
                        break
                    except OSError as failure:
                        error = failure
                if error:
                    raise SetupError('Cannot download '+rec['name']+': '+str(error))
                safe_unpack(archive,root)
            (root/'packages.json').write_text(json.dumps(records,indent=2)+'\n')
        scripts = root/'launchers';scripts.mkdir()
        for name in names:
            if not (root/'usr/bin'/name).is_file():
                raise SetupError('Helper binary missing from package: '+name)
            script = scripts/name;script.write_text(wrapper(root,name));script.chmod(0o755)
            env = host_env();env['PATH'] = str(scripts)+':'+env['PATH']
            if not working(name,env):
                raise SetupError('Downloaded helper does not run in this DroidDeck environment: '+name)
        local = home/'.local/bin';local.mkdir(parents=True,exist_ok=True)
        old = root/'previous';old.mkdir()
        installed = []
        try:
            for name in names:
                dest = local/name
                if dest.exists() or dest.is_symlink():
                    shutil.copy2(dest,old/name,follow_symlinks=False)
                fd, temporary = tempfile.mkstemp(prefix='.panacea-'+name+'-',dir=local)
                temp = Path(temporary)
                try:
                    with os.fdopen(fd,'w') as output:
                        output.write((scripts/name).read_text())
                        os.fchmod(output.fileno(),0o755)
                    os.replace(temp,dest);installed.append(name)
                finally:
                    temp.unlink(missing_ok=True)
            published = True
        except Exception:
            for name in reversed(installed):
                (local/name).unlink(missing_ok=True)
                if (old/name).exists() or (old/name).is_symlink(): os.replace(old/name,local/name)
            raise
        log('Local Linux helpers ready: '+', '.join(str(local/n) for n in names))
        log('Helper files and prior launcher backups: '+str(root))
    finally:
        if not published: shutil.rmtree(root)


def prepare(log=print):
    names = missing_tools()
    if names:
        install_local(names,log)
    for name in TOOLS:
        if not working(name):
            raise SetupError('Linux helper is still unavailable: '+name)
        log('Using '+name+': '+str(shutil.which(name,path=host_env()['PATH'])))


def optional_protontricks(folder):
    """The historical optional tool, isolated from the system Python and pip."""
    venv.EnvBuilder(with_pip=False).create(folder)
    python = folder/'bin/python'
    with tempfile.TemporaryDirectory(prefix='pip-',dir=folder) as temp:
        work = Path(temp)
        metadata = work/'pip.json'
        download('https://pypi.org/pypi/pip/26.2.1/json',metadata)
        wheels = [r for r in json.loads(metadata.read_text())['urls']
                  if r['filename'] == 'pip-26.2.1-py3-none-any.whl']
        if len(wheels) != 1:
            raise SetupError('Pinned pip wheel not found.')
        record = wheels[0]
        if urllib.parse.urlsplit(record['url']).hostname != 'files.pythonhosted.org':
            raise SetupError('Unexpected pip download host.')
        wheel = work/record['filename']
        download(record['url'],wheel,record['digests']['sha256'])
        bootstrap = 'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("pip",run_name="__main__")'
        commands = [[str(python),'-c',bootstrap,str(wheel),'install','--no-index',str(wheel)],
                    [str(python),'-m','pip','install','--index-url','https://pypi.org/simple','protontricks==1.15.0']]
        for command in commands:
            if subprocess.run(command,env=host_env(),timeout=600).returncode:
                raise SetupError('Optional Protontricks installation failed.')


if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--protontricks':
            optional_protontricks(Path(sys.argv[2]).resolve())
        elif len(sys.argv) == 1:
            prepare()
        else:
            raise SetupError('Usage: host_tools.py [--protontricks VENV]')
    except (SetupError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise SystemExit('ERROR: '+str(error))
