#!/usr/bin/env python3
"""Build a deterministic setup ZIP with sources and the pinned main DLL."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['README.md', 'README-DE.md', 'config.example.env', 'common.sh',
         '00-host-tools.sh', '01-check.sh', '02-install-runtimes.sh',
         '03-add-registry.sh', '04-launch-options.sh', 'start-setup.sh',
         'Panacea-Setup.desktop', 'assistant/core.py', 'assistant/gui.py']


def main():
    files = {name: (ROOT / 'linux-setup' / name).read_bytes() for name in NAMES}
    checksums = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                        for name, data in sorted(files.items())).encode()
    if (ROOT / 'linux-setup/SHA256SUMS.txt').read_bytes() != checksums:
        raise SystemExit('Update linux-setup/SHA256SUMS.txt before packaging.')
    # Bundle the verified main DLL so setup does not fetch a moving branch.
    for name in ['version.dll', 'LICENSE-OpenKH.txt', 'LICENSE-HDE.txt', 'NOTICE.txt']:
        files['payload/' + name] = (ROOT / name).read_bytes()
    import sys
    sys.path.insert(0, str(ROOT / 'linux-setup/assistant'))
    from core import DLL_SHA256
    if hashlib.sha256(files['payload/version.dll']).hexdigest() != DLL_SHA256:
        raise SystemExit('Update the assistant DLL pin when intentionally changing version.dll.')
    files['SHA256SUMS.txt'] = ''.join(
        f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(files.items())).encode()
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / 'Panacea-ARM-Linux-Setup.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo('Panacea-ARM-Linux-Setup/' + name, (2026, 10, 12, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith(('.sh', '.desktop')) else 0o100644) << 16
            z.writestr(entry, data)
    (dist / 'Panacea-ARM-Linux-Setup.sha256').write_text(
        f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
    print(f'Packaged {len(files)} files: {archive.name}')


if __name__ == '__main__':
    main()
