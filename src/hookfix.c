/* Panacea stable-trampoline retrofit, 2026-10-12. No CRT or external helper DLL.
 * Loaded through 14 verified constructor call sites in the supplied binary.
 * Existing Hook layout: original, replacement, patch, saved, length.
 * After publication original is the trampoline and length=0. All inlined
 * Patch/Unpatch calls therefore perform zero-byte copies, including tail calls.
 * Installation happens in Panacea::Initialize, before mod DLLs are loaded.
 * DLL unloading / concurrent installation during gameplay is not supported.
 */
#include <stdint.h>
#include <stddef.h>
#include "hde/hde64.h"
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef struct {u32 begin,end,unwind;} RF;
typedef struct {u8 *original,*replacement,*patch,*saved; int length;} Hook;
#define IMP __declspec(dllimport)
IMP void *GetModuleHandleW(const uint16_t *);
IMP void *GetProcAddress(void *,const char *);
IMP int VirtualProtect(void *,size_t,u32,u32 *);
IMP RF *RtlLookupFunctionEntry(u64,u64 *,void *);
IMP void ExitProcess(u32);
IMP void *CreateFileW(const uint16_t *,u32,u32,void *,u32,u32,void *);
IMP int WriteFile(void *,const void *,u32,u32 *,void *);
IMP int CloseHandle(void *);
void *memset(void *v,int c,size_t n) {u8 *p=v; for(size_t i=0;i<n;i++)p[i]=(u8)c;return v;}
static void copy(void *d,const void *s,size_t n) {u8 *a=d;const u8 *b=s;for(size_t i=0;i<n;i++)a[i]=b[i];}
static const uint16_t kernel_name[]={'k','e','r','n','e','l','3','2','.','d','l','l',0};
static const uint16_t log_name[]={'p','a','n','a','c','e','a','_','h','o','o','k','f','i','x','.','l','o','g',0};
static void log_line(const char *s,u64 address) {
    char b[160];u32 n=0,written;while(*s && n<120)b[n++]=*s++;
    b[n++]=' ';b[n++]='0';b[n++]='x';
    const char hex[]="0123456789abcdef";
    for(int i=15;i>=0;i--)b[n++]=hex[(address>>(i*4))&15];b[n++]='\r';b[n++]='\n';
    void *f=CreateFileW(log_name,4,3,0,4,0x80,0); /* append, shared R/W, OPEN_ALWAYS */
    if(f!=(void *)(intptr_t)-1) {WriteFile(f,b,n,&written,0);CloseHandle(f);}
}
__attribute__((noreturn)) static void fail(const char *why,u64 target) {
    log_line(why,target);ExitProcess(0xE04B4802);for(;;){}
}
static int fits32(int64_t v) {return v>=INT32_MIN && v<=INT32_MAX;}
static unsigned imm_size(hde64s *h) {
    if(h->flags&F_IMM64)return 8;if(h->flags&F_IMM32)return 4;
    if(h->flags&F_IMM16)return 2;if(h->flags&F_IMM8)return 1;return 0;
}
static void absjump(u8 *p,const void *to) {p[0]=0xff;p[1]=0x25;memset(p+2,0,4);*(u64 *)(p+6)=(u64)to;}
/* Each relocated instruction retains its length except short Jcc, which is
 * expanded to 0F 8x rel32. Internal branch targets are remapped in pass 2. */
typedef struct {hde64s h;u8 old,newpos,nlen;} Insn;
static unsigned map_offset(Insn *a,unsigned count,unsigned old,unsigned copied,unsigned emitted) {
    if(old==copied)return emitted;
    for(unsigned i=0;i<count;i++)if(a[i].old==old)return a[i].newpos;
    return 0xFFFFFFFF;
}
/* Clone only completed original unwind operations. SAVE offsets refer to the
 * final RSP; removing later PUSH/ALLOC operations requires subtracting their
 * total stack delta. This also handles spills before the stack allocation. */
static int make_unwind(u8 *out,u8 *target,Insn *a,unsigned count,unsigned copied,unsigned emitted) {
    u64 base=0;RF *r=RtlLookupFunctionEntry((u64)target,&base,0);
    memset(out,0,512);out[0]=1;out[1]=(u8)emitted;
    if(!r) {
        for(unsigned i=0;i<count;i++) {
            hde64s *h=&a[i].h;
            if((h->opcode>=0x50&&h->opcode<=0x57)||
               ((h->opcode==0x81||h->opcode==0x83)&&h->modrm==0xec))return 0;
        }
        return 1;
    }
    if(base+r->begin!=(u64)target)return 0;
    const u8 *u=(const u8 *)(base+r->unwind);
    if((u[0]&7)!=1 || (u[0]>>3)&4 || u[3])return 0; /* no chained/frame-register functions */
    unsigned cnt=u[2],omitted=0,kept=0;
    for(unsigned pass=0;pass<2;pass++)for(unsigned i=0;i<cnt;) {
        const u8 *c=u+4+2*i;unsigned off=c[0],op=c[1]&15,info=c[1]>>4,slots=1,delta=0;
        if(op==0)delta=8;
        else if(op==1) {if(info>1)return 0;slots=info?3:2;}
        else if(op==2)delta=info*8+8;
        else if(op==4||op==8)slots=2;
        else if(op==5||op==9)slots=3;
        else return 0;
        if(i+slots>cnt)return 0;
        if(op==1)delta=info?*(const u32 *)(c+2):*(const uint16_t *)(c+2)*8;
        if(!pass) {if(off>copied)omitted+=delta;}
        else if(off<=copied) {
            unsigned neo=map_offset(a,count,off,copied,emitted);
            if(neo==0xFFFFFFFF || kept+slots>250)return 0;
            u8 *d=out+4+2*kept;copy(d,c,2*slots);d[0]=(u8)neo;
            if(op==4||op==5||op==8||op==9) {
                unsigned scale=(op==8)?16:8;
                u64 save=(slots==2)?(u64)*(const uint16_t *)(c+2)*scale:*(const u32 *)(c+2);
                if(save<omitted)return 0;save-=omitted;
                if(slots==2) {if(save%scale || save/scale>65535)return 0;*(uint16_t *)(d+2)=(uint16_t)(save/scale);}
                else *(u32 *)(d+2)=(u32)save;
            }
            kept+=slots;
        }
        i+=slots;
    }
    out[2]=(u8)kept;return 1;
}
void *hook_install(Hook *hook) {
    typedef void *(*Alloc)(void *,size_t,u32,u32);
    typedef int (*Flush)(void *,const void *,size_t);
    typedef u8 (*Add)(RF *,u32,u64);
    u8 *target=hook->original;
    if(hook->length!=14 || !target || !hook->replacement)fail("FAIL invalid Hook layout",(u64)target);
    for(unsigned i=0;i<14;i++)if(target[i]!=hook->saved[i])fail("FAIL entry changed before install",(u64)target);
    void *k=GetModuleHandleW(kernel_name);
    Alloc alloc=(Alloc)GetProcAddress(k,"VirtualAlloc");
    Flush flush=(Flush)GetProcAddress(k,"FlushInstructionCache");
    Add add=(Add)GetProcAddress(k,"RtlAddFunctionTable");
    if(!k||!alloc||!flush||!add)fail("FAIL required WinAPI missing",(u64)target);
    Insn a[16];unsigned count=0,copied=0,emitted=0;
    while(copied<14) {
        if(count>=16)fail("FAIL too many prologue instructions",(u64)target);
        Insn *in=&a[count++];hde64_disasm(target+copied,&in->h);hde64s *h=&in->h;
        if(!h->len || h->flags&F_ERROR || h->p_67)fail("FAIL unsupported instruction",(u64)target);
        /* A trampoline prologue must not contain a call or return. */
        if(h->opcode==0xe8 || h->opcode==0xc2 || h->opcode==0xc3 ||
          (h->opcode==0xff&&(h->modrm_reg==2||h->modrm_reg==3)) ||
          (h->opcode>=0xe0&&h->opcode<=0xe3))fail("FAIL unsupported prologue control flow",(u64)target);
        in->old=(u8)copied;in->newpos=(u8)emitted;in->nlen=h->len;
        if(h->opcode>=0x70&&h->opcode<=0x7f)in->nlen=6;
        if(h->opcode==0xeb)in->nlen=5;
        if((h->flags&F_RELATIVE) && !(h->opcode==0xeb||h->opcode==0xe9||
            (h->opcode>=0x70&&h->opcode<=0x7f)||(h->opcode==0x0f&&h->opcode2>=0x80&&h->opcode2<=0x8f)))
            fail("FAIL unsupported relative instruction",(u64)target);
        copied+=h->len;emitted+=in->nlen;
    }
    u8 *page=0;u64 origin=(u64)target&~(u64)65535;
    /* 64 KiB allocation granularity; nearest candidates first, within 1 GiB. */
    for(u64 distance=65536;distance<0x40000000 && !page;distance+=65536) {
        if(origin>distance+65536)page=alloc((void *)(origin-distance),4096,0x3000,4);
        if(!page && origin+distance<0x00007fff00000000ULL)page=alloc((void *)(origin+distance),4096,0x3000,4);
    }
    if(!page)fail("FAIL cannot allocate nearby trampoline",(u64)target);
    for(unsigned i=0;i<count;i++) {
        Insn *in=&a[i];hde64s *h=&in->h;u8 *src=target+in->old,*dst=page+in->newpos;
        copy(dst,src,h->len);
        if(h->flags&F_RELATIVE) {
            int64_t rel=(h->flags&F_IMM8)?(int8_t)h->imm.imm8:(int32_t)h->imm.imm32;
            u8 *dest=src+h->len+rel;
            if(dest>=target && dest<target+copied) {
                unsigned off=map_offset(a,count,(unsigned)(dest-target),copied,emitted);
                if(off==0xFFFFFFFF)fail("FAIL branch into instruction",(u64)target);
                dest=page+off;
            }
            unsigned disp;
            if(h->opcode>=0x70&&h->opcode<=0x7f){dst[0]=0x0f;dst[1]=0x80|(h->opcode&15);disp=2;}
            else if(h->opcode==0xeb){dst[0]=0xe9;disp=1;}
            else disp=h->len-4;
            int64_t d=(int64_t)(dest-(dst+in->nlen));
            if(!fits32(d))fail("FAIL branch out of rel32 range",(u64)target);
            *(int32_t *)(dst+disp)=(int32_t)d;
        } else if((h->flags&F_MODRM)&&h->modrm_mod==0&&h->modrm_rm==5) {
            unsigned pos=h->len-imm_size(h)-4;
            int64_t d=(int64_t)((src+h->len+(int32_t)h->disp.disp32)-(dst+h->len));
            if(!fits32(d))fail("FAIL RIP operand out of range",(u64)target);
            *(int32_t *)(dst+pos)=(int32_t)d;
        }
    }
    absjump(page+emitted,target+copied);
    if(!make_unwind(page+256,target,a,count,copied,emitted))fail("FAIL unsupported unwind metadata",(u64)target);
    RF *rf=(RF *)(page+1024);rf->begin=0;rf->end=emitted+14;rf->unwind=256;
    u32 old;
    if(!VirtualProtect(page,4096,0x20,&old))fail("FAIL trampoline RX protection",(u64)target);
    if(!flush((void *)(intptr_t)-1,page,emitted+14))fail("FAIL trampoline cache flush",(u64)target);
    if(!add(rf,1,(u64)page))fail("FAIL trampoline unwind registration",(u64)target);
    /* Publish completed RX trampoline, disable EVERY existing Patch/Unpatch. */
    hook->original=page;hook->length=0;
    if(!VirtualProtect(target,14,0x40,&old))fail("FAIL entry protection",(u64)target);
    copy(target,hook->patch,14);
    if(!flush((void *)(intptr_t)-1,target,14))fail("FAIL entry cache flush",(u64)target);
    u32 ignored;if(!VirtualProtect(target,14,old,&ignored))fail("FAIL entry protection restore",(u64)target);
    log_line("HookFix v2 installed stable trampoline for",(u64)target);
    return target;
}
