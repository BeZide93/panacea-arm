#!/usr/bin/env python3
"""Compile AMD64 forwards and append them to this exact supplied Panacea DLL.
Requires Python 3, pefile, GNU binutils (as, ld, nm, objcopy).
No proprietary SDK, external DLL, network download or repository change.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import pefile

ORIGINAL_SHA256 = 'ea8eb87b45194927898e3084aecb5f36d3b4c1e2bfd7262b85c11d3e603b52ea'
ORIGINAL_EXPORTS = {
    'GetFileVersionInfoSizeW': (1, 0x3870),
    'GetFileVersionInfoW': (2, 0x3810),
    'MiniDumpWriteDump': (3, 0x37b0),
    'VerQueryValueW': (4, 0x38b0),
}
VERSION_NAMES = sorted([
    'GetFileVersionInfoA', 'GetFileVersionInfoW',
    'GetFileVersionInfoExA', 'GetFileVersionInfoExW',
    'GetFileVersionInfoSizeA', 'GetFileVersionInfoSizeW',
    'GetFileVersionInfoSizeExA', 'GetFileVersionInfoSizeExW',
    'VerFindFileA', 'VerFindFileW', 'VerInstallFileA', 'VerInstallFileW',
    'VerLanguageNameA', 'VerLanguageNameW', 'VerQueryValueA', 'VerQueryValueW',
])
NEW_NAMES = [n for n in VERSION_NAMES if n not in ORIGINAL_EXPORTS]
IMPORTS = ['GetSystemDirectoryA', 'LoadLibraryA', 'GetProcAddress',
           'GetLastError', 'SetLastError', 'FreeLibrary', 'RaiseException', 'ExitProcess']

def align(n, a):
    return (n + a - 1) // a * a

def run(*args):
    return subprocess.check_output(args, text=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    original = args.original.read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256, 'Wrong original DLL; refusing to patch.'
    assert args.original.resolve() != args.output.resolve(), 'Do not overwrite the original.'
    pe = pefile.PE(data=original)
    assert pe.FILE_HEADER.Machine == 0x8664 and pe.OPTIONAL_HEADER.Magic == 0x20b
    old_exports = {e.name.decode(): (e.ordinal, e.address) for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    assert old_exports == ORIGINAL_EXPORTS
    assert not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size, 'Signed image is not supported.'
    iats = {i.name.decode(): i.address - pe.OPTIONAL_HEADER.ImageBase
            for d in pe.DIRECTORY_ENTRY_IMPORT if d.dll.lower() == b'kernel32.dll'
            for i in d.imports if i.name}
    assert all(n in iats for n in IMPORTS)
    work = args.output.parent / 'build'
    work.mkdir(parents=True, exist_ok=True)
    src = pathlib.Path(__file__).with_name('proxy.S')
    run('as', '--64', '-o', str(work/'proxy.o'), str(src))
    assert all(s.PointerToRawData+s.SizeOfRawData <= len(original) for s in pe.sections)
    sect_align, file_align = pe.OPTIONAL_HEADER.SectionAlignment, pe.OPTIONAL_HEADER.FileAlignment
    code_rva = align(pe.OPTIONAL_HEADER.SizeOfImage, sect_align)
    # One page for compiled forwards and names; this build checks both limits.
    data_rva = code_rva + sect_align
    ro_rva = data_rva + sect_align
    script = 'image_base = 0;\n' + ''.join(f'iat_{n} = 0x{iats[n]:x};\n' for n in IMPORTS)
    script += f'''SECTIONS {{
      .text 0x{code_rva:x} : {{ *(.text) }}
      .data 0x{data_rva:x} : {{ *(.data) }}
      .rodata 0x{ro_rva:x} : {{ *(.rodata) }}
      /DISCARD/ : {{ *(.note*) *(.comment*) }}
    }}\n'''
    (work/'proxy.ld').write_text(script)
    run('ld', '-m', 'elf_x86_64', '--build-id=none', '-T', str(work/'proxy.ld'), '-o', str(work/'proxy.elf'), str(work/'proxy.o'))
    assert 'There are no relocations' in run('readelf', '-r', str(work/'proxy.elf'))
    symbols = {}
    for line in run('nm', '-n', str(work/'proxy.elf')).splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    chunks = {}
    for section, key in [('.text', 'code'), ('.data', 'data'), ('.rodata', 'ro')]:
        file = work/(key+'.bin')
        run('objcopy', '-O', 'binary', '--only-section='+section, str(work/'proxy.elf'), str(file))
        chunks[key] = file.read_bytes()
    assert len(chunks['code']) <= sect_align and len(chunks['data']) <= sect_align
    ro = bytearray(chunks['ro'])
    def append(data, alignment=1):
        ro.extend(b'\0' * (align(len(ro), alignment)-len(ro)))
        rva = ro_rva + len(ro)
        ro.extend(data)
        return rva

    # Add valid UNWIND_INFO for every new non-leaf function and merge the
    # sorted RUNTIME_FUNCTION array; original entries and xdata stay intact.
    old_pdata = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    pdata = pe.get_data(old_pdata.VirtualAddress, old_pdata.Size)
    entries = [struct.unpack_from('<III', pdata, n) for n in range(0, len(pdata), 12)]
    rp = symbols['resolve_prolog_end'] - symbols['resolve_begin']
    assert rp == 7
    unwind = append(bytes([1, rp, 2, 0, rp, 1, 0x168//8, 0]), 4)
    entries.append((symbols['resolve_begin'], symbols['resolve_end'], unwind))
    for name in NEW_NAMES:
        prolog = symbols['prolog_'+name] - symbols['proxy_'+name]
        assert prolog == 4
        unwind = append(bytes([1, prolog, 1, 0, prolog, 0xc2, 0, 0]), 4)
        entries.append((symbols['proxy_'+name], symbols['end_'+name], unwind))
    entries.sort()
    new_pdata = append(b''.join(struct.pack('<III', *v) for v in entries), 4)

    # Preserve existing ordinals 1..4 AND their original RVAs. New APIs 5..17.
    exports = dict(ORIGINAL_EXPORTS)
    for ordinal, name in enumerate(NEW_NAMES, 5):
        exports[name] = (ordinal, symbols['proxy_'+name])
    export_begin = append(b'\0'*40, 4)
    dll_name = append(b'version.dll\0')
    names = sorted(exports)
    name_rvas = {n: append(n.encode()+b'\0') for n in names}
    by_ordinal = sorted(exports.values())
    eat = append(struct.pack('<'+'I'*len(exports), *(v[1] for v in by_ordinal)), 4)
    eot = append(struct.pack('<'+'H'*len(exports), *(exports[n][0]-1 for n in names)), 2)
    ent = append(struct.pack('<'+'I'*len(exports), *(name_rvas[n] for n in names)), 4)
    struct.pack_into('<IIHHIIIIIII', ro, export_begin-ro_rva,
                     0, 0, 0, 0, dll_name, 1, len(exports), len(exports), eat, ent, eot)
    # Leave padding after the tables (also accommodates conservative PE readers).
    ro.extend(b'\0' * 128)
    export_size = ro_rva + len(ro) - export_begin

    out = bytearray(original)
    header_start = pe.sections[-1].get_file_offset()+40
    assert header_start + 3*40 <= pe.OPTIONAL_HEADER.SizeOfHeaders
    assert not any(out[header_start:header_start+3*40]), 'Section header slack not empty.'
    sections = [('.vpx', chunks['code'], code_rva, 0x60000020),
                ('.vpd', chunks['data'], data_rva, 0xc0000040),
                ('.vpr', bytes(ro), ro_rva, 0x40000040)]
    for index, (name, payload, rva, flags) in enumerate(sections):
        raw = align(len(out), file_align)
        rawsize = align(len(payload), file_align)
        out.extend(b'\0' * (raw-len(out)))
        out.extend(payload)
        out.extend(b'\0' * (rawsize-len(payload)))
        struct.pack_into('<8sIIIIIIHHI', out, header_start+40*index,
                         name.encode(), len(payload), rva, rawsize, raw, 0, 0, 0, 0, flags)
    def put(field, value, fmt='<I'):
        struct.pack_into(fmt, out, field, value)
    put(pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'), len(pe.sections)+3, '<H')
    oh = pe.OPTIONAL_HEADER
    put(oh.get_field_absolute_offset('SizeOfImage'), align(ro_rva+len(ro), sect_align))
    put(oh.get_field_absolute_offset('SizeOfCode'), oh.SizeOfCode+align(len(chunks['code']), file_align))
    put(oh.get_field_absolute_offset('SizeOfInitializedData'), oh.SizeOfInitializedData+
        align(len(chunks['data']), file_align)+align(len(ro), file_align))
    for idx, rva, size in [(0, export_begin, export_size), (3, new_pdata, len(entries)*12)]:
        directory = oh.DATA_DIRECTORY[idx]
        put(directory.get_field_absolute_offset('VirtualAddress'), rva)
        put(directory.get_field_absolute_offset('Size'), size)
    put(oh.get_field_absolute_offset('CheckSum'), 0)
    put(oh.get_field_absolute_offset('CheckSum'), pefile.PE(data=bytes(out)).generate_checksum())
    args.output.write_bytes(out)
    report = {
        'original_sha256': ORIGINAL_SHA256,
        'output_sha256': hashlib.sha256(out).hexdigest(),
        'architecture': 'PE32+ AMD64 (0x8664)',
        'entry_point_rva': hex(oh.AddressOfEntryPoint),
        'exports': [{'name': n, 'ordinal': v[0], 'rva': hex(v[1]),
                     'preserved': n in ORIGINAL_EXPORTS} for n,v in sorted(exports.items())],
        'new_unwind_functions': 1+len(NEW_NAMES),
        'symbols': symbols,
        'iats': iats,
    }
    (work/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['output_sha256','architecture','entry_point_rva','new_unwind_functions']}, indent=2))

if __name__ == '__main__':
    main()
