#!/usr/bin/env python3
"""Reproduce v1 VERSION forwarders, then compile and append the v2 hook engine.
No GitHub operations. Input is locked to the original user-supplied SHA256.
"""
import pathlib, subprocess, sys, struct, json, hashlib
import pefile
from build import align
ROOT=pathlib.Path(__file__).resolve().parents[1]
CONSTRUCTORS=[0xc355,0xc4bc,0xc5fe,0xc73d,0xc87f,0xc9ba,0xcaf9,
              0xcc3f,0xcd85,0xcecb,0xd011,0xd156,0xd2bd,0x1223d]
IMPORTS=['GetModuleHandleW','GetProcAddress','VirtualProtect','RtlLookupFunctionEntry',
         'ExitProcess','CreateFileW','WriteFile','CloseHandle']
def run(*args):return subprocess.check_output(list(map(str,args)),text=True)
def main():
    work=ROOT/'build';work.mkdir(exist_ok=True)
    original=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'original/version.dll'
    run(sys.executable,ROOT/'src/build.py',original,ROOT/'version.dll')
    image=bytearray((ROOT/'version.dll').read_bytes());p=pefile.PE(data=bytes(image))
    rva=align(p.OPTIONAL_HEADER.SizeOfImage,0x1000)
    for src,name in [('hookfix.c','hookfix'),('hde/hde64.c','hde64')]:
        run(sys.executable,'-m','ziglang','cc','-target','x86_64-windows-gnu','-Os',
            '-ffreestanding','-fno-builtin','-fno-stack-protector','-mno-stack-arg-probe',
            '-funwind-tables','-c',ROOT/'src'/src,'-o',work/(name+'.o'))
    iat={i.name.decode():i.address-p.OPTIONAL_HEADER.ImageBase for d in p.DIRECTORY_ENTRY_IMPORT
         if d.dll.lower()==b'kernel32.dll' for i in d.imports if i.name}
    script=''.join(f'__imp_{n} = 0x{iat[n]:x};\n' for n in IMPORTS)
    script+=f'''SECTIONS {{
    .text 0x{rva:x} : {{ *(.text) *(.rdata*) *(.data) *(.xdata*)
        . = ALIGN(4); helper_pdata_begin = .; *(.pdata*) helper_pdata_end = .; }}
    /DISCARD/ : {{ *(.debug*) *(.llvm*) *(.drectve) }}
    }}\n'''
    (work/'hookfix.ld').write_text(script)
    run('ld','-m','i386pep','--image-base','0','--entry','hook_install','--disable-reloc-section',
        '--no-insert-timestamp','-T',work/'hookfix.ld','-o',work/'hookfix.exe',work/'hookfix.o',work/'hde64.o')
    h=pefile.PE(str(work/'hookfix.exe'))
    assert len(h.sections)==1 and h.sections[0].VirtualAddress==rva
    assert not h.OPTIONAL_HEADER.DATA_DIRECTORY[5].Size
    # All object fixups must be PC-relative or image-relative, never absolute VA.
    for obj in ['hookfix.o','hde64.o']:
        for line in run('objdump','-r',work/obj).splitlines():
            if 'IMAGE_REL_' in line:assert 'IMAGE_REL_AMD64_REL32' in line or 'IMAGE_REL_AMD64_ADDR32NB' in line,line
    syms={}
    for line in run('nm','-n',work/'hookfix.exe').splitlines():
        parts=line.split()
        if len(parts)==3:syms[parts[2]]=int(parts[0],16)
    payload=bytearray(h.sections[0].get_data()[:h.sections[0].Misc_VirtualSize])
    pd=p.OPTIONAL_HEADER.DATA_DIRECTORY[3];oldpd=p.get_data(pd.VirtualAddress,pd.Size)
    hp=h.get_data(syms['helper_pdata_begin'],syms['helper_pdata_end']-syms['helper_pdata_begin'])
    entries=[struct.unpack_from('<III',oldpd+hp,i) for i in range(0,len(oldpd+hp),12)]
    entries.sort();assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:]))
    payload.extend(b'\0'*(align(len(payload),4)-len(payload)))
    pd_rva=rva+len(payload);payload.extend(b''.join(struct.pack('<III',*e) for e in entries))
    patches=[]
    for call in CONSTRUCTORS:
        off=p.get_offset_from_rva(call)
        assert image[off:off+5]==b'\xe8'+struct.pack('<i',0x42be0-call-5)
        previous=bytes(image[off-3:off]);assert previous in [b'\x48\x8b\x0f',b'\x48\x8b\x0b']
        # mov rcx,[rdi/rbx] -> mov rcx,rdi/rbx. The new callee takes Hook*.
        reg=b'\x48\x89\xf9' if previous[-1]==0x0f else b'\x48\x89\xd9'
        before=bytes(image[off-3:off+5]);after=reg+b'\xe8'+struct.pack('<i',syms['hook_install']-call-5)
        image[off-3:off+5]=after
        patches.append({'rva':hex(call-3),'before':before.hex(),'after':after.hex()})
    header=p.sections[-1].get_file_offset()+40
    assert header+40<=p.OPTIONAL_HEADER.SizeOfHeaders and not any(image[header:header+40])
    raw=align(len(image),p.OPTIONAL_HEADER.FileAlignment);rawsize=align(len(payload),p.OPTIONAL_HEADER.FileAlignment)
    image.extend(b'\0'*(raw-len(image)));image.extend(payload);image.extend(b'\0'*(rawsize-len(payload)))
    struct.pack_into('<8sIIIIIIHHI',image,header,b'.hfx',len(payload),rva,rawsize,raw,0,0,0,0,0x60000020)
    def put(obj,field,value,fmt='<I'):struct.pack_into(fmt,image,obj.get_field_absolute_offset(field),value)
    put(p.FILE_HEADER,'NumberOfSections',len(p.sections)+1,'<H')
    put(p.OPTIONAL_HEADER,'SizeOfImage',align(rva+len(payload),0x1000))
    put(p.OPTIONAL_HEADER,'SizeOfCode',p.OPTIONAL_HEADER.SizeOfCode+rawsize)
    put(pd,'VirtualAddress',pd_rva);put(pd,'Size',len(entries)*12)
    put(p.OPTIONAL_HEADER,'CheckSum',0)
    put(p.OPTIONAL_HEADER,'CheckSum',pefile.PE(data=bytes(image)).generate_checksum())
    (ROOT/'version.dll').write_bytes(image)
    manifest={'sha256':hashlib.sha256(image).hexdigest(),'patches':patches,'symbols':syms,
              'helper_runtime_functions':len(hp)//12,'iats':iat,'hookfix_source':'hookfix.c',
              'original_entry_unchanged':hex(p.OPTIONAL_HEADER.AddressOfEntryPoint)}
    (work/'hookfix-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['sha256','helper_runtime_functions','original_entry_unchanged']},indent=2))
if __name__=='__main__':main()
