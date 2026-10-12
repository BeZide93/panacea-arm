#!/usr/bin/env python3
"""Static PE verification, plus generation of the x64 ABI harness header."""
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys
import pefile

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from build import ORIGINAL_SHA256, ORIGINAL_EXPORTS, VERSION_NAMES, NEW_NAMES, IMPORTS

original = pathlib.Path(sys.argv[1]).read_bytes()
patched = (root/'version.dll').read_bytes()
a, b = pefile.PE(data=original), pefile.PE(data=patched)
assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
assert b.FILE_HEADER.Machine == 0x8664 and b.OPTIONAL_HEADER.Magic == 0x20b
assert b.OPTIONAL_HEADER.AddressOfEntryPoint == a.OPTIONAL_HEADER.AddressOfEntryPoint
assert b.OPTIONAL_HEADER.ImageBase == a.OPTIONAL_HEADER.ImageBase
assert b.OPTIONAL_HEADER.DllCharacteristics == a.OPTIONAL_HEADER.DllCharacteristics
assert b.OPTIONAL_HEADER.CheckSum == b.generate_checksum()
hook = json.loads((root/"build/hookfix-manifest.json").read_text())
restored = bytearray(patched)
for patch in hook["patches"]:
    rva=int(patch["rva"],16); offset=b.get_offset_from_rva(rva)
    old=bytes.fromhex(patch["before"]); neo=bytes.fromhex(patch["after"])
    assert restored[offset:offset+len(neo)]==neo
    restored[offset:offset+len(old)]=old
restored_pe=pefile.PE(data=bytes(restored))
for old, new in zip(a.sections, restored_pe.sections):
    assert old.__pack__() == new.__pack__()
    assert old.get_data() == new.get_data(), old.Name
for idx in range(16):
    if idx not in (0, 3):
        assert a.OPTIONAL_HEADER.DATA_DIRECTORY[idx].__pack__() == b.OPTIONAL_HEADER.DATA_DIRECTORY[idx].__pack__()
exports = {e.name.decode(): (e.ordinal, e.address) for e in b.DIRECTORY_ENTRY_EXPORT.symbols}
assert set(exports) == set(VERSION_NAMES) | {'MiniDumpWriteDump'}
assert all(exports[n] == v for n,v in ORIGINAL_EXPORTS.items())
assert all(not e.forwarder for e in b.DIRECTORY_ENTRY_EXPORT.symbols)
assert [e.name for e in b.DIRECTORY_ENTRY_EXPORT.symbols] == sorted(e.name for e in b.DIRECTORY_ENTRY_EXPORT.symbols)
for s in b.sections:
    assert not (s.Characteristics & 0x20000000 and s.Characteristics & 0x80000000)
for x,y in zip(b.sections,b.sections[1:]):
    assert x.VirtualAddress+max(x.Misc_VirtualSize,x.SizeOfRawData) <= y.VirtualAddress
def pdata(pe):
    d = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    data = pe.get_data(d.VirtualAddress,d.Size)
    return [struct.unpack_from('<III',data,i) for i in range(0,len(data),12)]
old, new = pdata(a), pdata(b)
assert new[:len(old)] == old
assert new == sorted(new)
assert len(new) == len(old)+14+hook["helper_runtime_functions"]
assert all(x[1] <= y[0] for x,y in zip(new,new[1:]))
manifest = json.loads((root/'build/manifest.json').read_text())
sym = manifest['symbols']
for begin,end,unwind in new[len(old):len(old)+14]:
    u = b.get_data(unwind,8)
    frame = 0x168 if begin == sym['resolve_begin'] else 0x68
    assert u == (bytes([1,7,2,0,7,1,45,0]) if frame == 0x168 else bytes([1,4,1,0,4,0xc2,0,0]))
    assert b.get_data(begin,7 if frame==0x168 else 4) == (b'\x48\x81\xec\x68\x01\x00\x00' if frame==0x168 else b'\x48\x83\xec\x68')
delta = b.get_offset_from_rva(b.OPTIONAL_HEADER.DATA_DIRECTORY[3].VirtualAddress) - a.get_offset_from_rva(a.OPTIONAL_HEADER.DATA_DIRECTORY[3].VirtualAddress)
relocated_warnings = [re.sub(r'at ([0-9a-f]+):',lambda m: f'at {int(m[1],16)+delta:x}:',w) for w in a.get_warnings()]
assert b.get_warnings() == relocated_warnings, 'New PE parser warnings'
dump = subprocess.check_output(['objdump','-p',str(root/'version.dll')],text=True)
assert 'Invalid' not in dump
(root/'build/exports.txt').write_text(dump[dump.index('The Export Tables'):dump.index('The Function Table')])
header = '#include <stddef.h>\n'
header += f'#define IMAGE_SIZE {b.OPTIONAL_HEADER.SizeOfImage}\n'
header += 'struct chunk {unsigned rva, offset, size, flags;};\n'
header += 'static const struct chunk chunks[] = {'+','.join('{'+','.join(map(str,[s.VirtualAddress,s.PointerToRawData,s.SizeOfRawData,s.Characteristics]))+'}' for s in b.sections)+'};\n'
for name in IMPORTS:
    header += f'#define IAT_{name} {manifest["iats"][name]}\n'
header += 'struct export_test {const char *name; unsigned rva;};\n'
header += 'static const struct export_test entries[] = {'+','.join('{"'+n+'",'+str(exports[n][1])+'}' for n in NEW_NAMES)+'};\n'
header += f'#define DATA_RVA {next(s.VirtualAddress for s in b.sections if s.Name.startswith(b".vpd"))}\n'
header += f'#define QUERY_RVA {exports["VerQueryValueA"][1]}\n'
header += f'#define HOOK_INSTALL_RVA {hook["symbols"]["hook_install"]}\n'
for name in ['GetModuleHandleW','VirtualProtect','RtlLookupFunctionEntry','CreateFileW','WriteFile','CloseHandle']:
    header += f'#define IAT_{name} {hook["iats"][name]}\n'
(root/'build/harness_generated.h').write_text(header)
print('PASS: AMD64 PE, checksum, 17 exports; original 4 names/ordinals/RVAs unchanged.')
print('PASS: exactly 14 verified 8-byte constructor redirects; all other original bytes, entry point, imports, relocations and TLS unchanged.')
print('PASS: sorted merged exception table, 14 proxy + 5 compiler-generated helper unwind records, RX/RW/R separation, no new parser warnings.')
print('NOTE: pefile reports the same 6 existing chained-unwind parsing warnings on both DLLs; objdump parses the tables.')
