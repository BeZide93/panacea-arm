#!/usr/bin/env python3
"""Package a CI-built ARM64 onedir runtime inside a shared-storage-safe ZIP."""
import hashlib
import shutil
from pathlib import Path
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
runtime=DIST/'Panacea-Setup'
if not (runtime/'Panacea-Setup').is_file():raise SystemExit('Build the ARM64 runtime first.')
# Runtime symlinks stay inside tar, never unpacked by an Android ZIP extractor.
archive=DIST/'runtime.tar.gz'
def runtime_member(member):
    # No image assets are used by the wizard; omit bundled Tk demo logos.
    if Path(member.name).suffix.lower() in {'.png','.gif','.jpg','.jpeg','.ico','.bmp','.webp','.bmd'}:
        return None
    return member
with tarfile.open(archive,'w:gz') as out:out.add(runtime,arcname='Panacea-Setup',filter=runtime_member)
files={}
with zipfile.ZipFile(DIST/'Panacea-ARM-Linux-Setup.zip') as source:
    for entry in source.infolist():files[entry.filename.split('/',1)[1]]=source.read(entry)
for name in ('start-native.sh','Panacea-Setup.desktop'):
    files[name]=(ROOT/'linux-setup/native'/name).read_bytes()
files['runtime.tar.gz']=archive.read_bytes()
files['runtime.sha256']=(hashlib.sha256(files['runtime.tar.gz']).hexdigest()+'  runtime.tar.gz\n').encode()
files['NATIVE-README.txt']=('Panacea DroidDeck native setup\n\nExtract this entire ZIP in the DroidDeck Linux desktop.\n'
    'Close Steam and Windows applications, then open Panacea-Setup.desktop.\n'
    'No browser or host Tk is needed. Python/Tcl/Tk are bundled for the window.\n'
    'DroidDeck base tools (including python3 for the desktop launcher/manual scripts) remain required.\n'
    'The runtime is temporarily extracted under ~/.local/share/panacea-arm/native.\n'
    'Keep config.env beside Panacea-Setup.desktop. See README.md / README-DE.md.\n'
    'If startup fails, see ~/.local/state/panacea-arm/native-start.log.\n').encode()
files['SHA256SUMS.txt']=''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name,data in sorted(files.items()) if name!='SHA256SUMS.txt').encode()
# Upload this directory to Actions, not the release ZIP below: Actions adds
# the one user-facing ZIP itself. Keep the folder and manifest together.
staging=DIST/'native-artifact'
if staging.exists():shutil.rmtree(staging)
package=staging/'Panacea-DroidDeck-Native-Setup'
for name,data in files.items():
    target=package/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o755 if name.endswith(('.sh','.desktop')) else 0o644)
output=DIST/'Panacea-DroidDeck-Native-Setup.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,data in sorted(files.items()):
        item=zipfile.ZipInfo('Panacea-DroidDeck-Native-Setup/'+name)
        item.external_attr=(0o100755 if name.endswith(('.sh','.desktop')) else 0o100644)<<16
        item.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(item,data)
(DIST/'Panacea-DroidDeck-Native-Setup.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(output.name,output.stat().st_size)
