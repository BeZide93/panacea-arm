#!/usr/bin/env python3
"""Package the current verified build, without logs or local intermediate files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable, str(ROOT / 'tests/verify.py'),
                    str(ROOT / 'original/version.dll')], check=True)
    proxy = json.loads((ROOT / 'build/manifest.json').read_text())
    hook = json.loads((ROOT / 'build/hookfix-manifest.json').read_text())
    dll = (ROOT / 'version.dll').read_bytes()
    if hashlib.sha256(dll).hexdigest() != hook['sha256']:
        raise SystemExit('Build manifest does not match version.dll')
    manifest = {'version': 'HookFix v2', 'variant': 'main', 'custom_logging': False, 'version_proxy': proxy, 'hookfix': hook}
    files = {
        name: (ROOT / name).read_bytes() for name in [
            'version.dll', 'README.md', 'ANLEITUNG.txt', 'NOTICE.txt', 'LICENSE',
            'LICENSE-OpenKH.txt', 'LICENSE-HDE.txt', 'requirements.txt',
            'original/version.dll', 'rollback/version-v1.dll',
        ]
    }
    for folder in ['src', 'tests', 'scripts', '.github/workflows', 'linux-setup']:
        for path in sorted((ROOT / folder).rglob('*')):
            if folder == 'linux-setup' and (path.parent != ROOT / folder or path.name == 'config.env'):
                continue
            if path.is_file() and path.suffix in {'.py', '.c', '.h', '.S', '.yml', '.sh', '.md', '.env', '.txt'}:
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    files['BUILD-MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    files['EXPORTS.txt'] = (ROOT / 'build/exports.txt').read_bytes()
    files['SHA256SUMS.txt'] = ''.join(
        f'{hashlib.sha256(data).hexdigest()}  {name}\n'
        for name, data in sorted(files.items())
    ).encode()
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / 'Panacea-ARM-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 10, 12, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    for name in ['BUILD-MANIFEST.json', 'EXPORTS.txt']:
        (dist / name).write_bytes(files[name])
    (dist / 'SHA256SUMS.txt').write_text(
        f'{hashlib.sha256(dll).hexdigest()}  version.dll\n'
        f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n'
    )
    print(f'Packaged {len(files)} files: {archive.name}')


if __name__ == '__main__':
    main()
