/* Runs the actual shipped Windows AMD64 engine and original Panacea wrappers
 * on Linux x86-64. Win32 memory/unwind/file services are narrow test doubles.
 * Does NOT claim Proton/FEX execution or a game integration test. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#include <pthread.h>
#include "harness_generated.h"
#define MS __attribute__((ms_abi))
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
typedef struct {u32 begin,end,unwind;} RF;
typedef struct {u8 *original,*replacement,*patch,*saved;int length;} Hook;
typedef u64 (MS *Fn)(u64,u64,u64,u64);
static u8 *image,*game,*tramp;
static Hook current;
static RF rf;
static int has_unwind,fail_mode,flushes,registrations;
static u8 original_unwind[128];
static char lastlog[200];
static u32 MS last_error_(void){return 123;}
static void MS set_error_(u32 x){assert(x==123);}
static u32 MS tid_(void){return 1;}
static void *MS module(const uint16_t *name){assert(name[0]=='k');return (void *)1;}
static void *MS alloc_(void *want,size_t size,u32 mode,u32 prot){
    assert(size==4096&&mode==0x3000&&prot==4);if(fail_mode==1)return NULL;
    void *p=mmap(want,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    if(p==MAP_FAILED)return NULL;
    tramp=p;return p;
}
static int MS flush_(void *process,const void *addr,size_t size){
    assert(process==(void *)(intptr_t)-1);assert(addr==game||addr==tramp);assert(size>=14);
    flushes++;return fail_mode!=2;
}
static u8 MS add_(RF *r,u32 count,u64 base){
    assert(count==1&&base==(u64)tramp&&r->begin==0&&r->unwind==256&&r->end>=28);
    assert(tramp[256]==1);registrations++;return fail_mode!=3;
}
static void *MS proc(void *mod,const char *name){
    assert(mod==(void *)1);
    if(!strcmp(name,"VirtualAlloc"))return alloc_;
    if(!strcmp(name,"FlushInstructionCache"))return flush_;
    if(!strcmp(name,"RtlAddFunctionTable"))return add_;
    if(!strcmp(name,"QueryPerformanceFrequency")||!strcmp(name,"Sleep")||!strcmp(name,"CreateThread"))return NULL;
    abort();
}
static int MS protect(void *p,size_t n,u32 prot,u32 *old){
    uintptr_t a=(uintptr_t)p&~(uintptr_t)4095;
    int perms=PROT_READ|PROT_EXEC;if(prot==0x40)perms|=PROT_WRITE;
    *old=0x20;return mprotect((void *)a,(((uintptr_t)p+n+4095)&~(uintptr_t)4095)-a,perms)==0;
}
static RF *MS lookup(u64 pc,u64 *base,void *history){
    assert(pc==(u64)game&&!history);*base=(u64)game;return has_unwind?&rf:NULL;
}
static void MS exit_(u32 code){if(!fail_mode)fprintf(stderr,"UNEXPECTED: %s",lastlog);assert(code==0xe04b4802);assert(!strncmp(lastlog,"FAIL",4));_Exit(73);}
static void *MS file_(const uint16_t *n,u32 access,u32 share,void *s,u32 disposition,u32 attrs,void *t){
    assert(n[0]=='p'&&access==4&&share==3&&!s&&disposition==4&&attrs==0x80&&!t);return (void *)2;
}
static int MS write_(void *h,const void *buf,u32 len,u32 *out,void *over){
    assert(h==(void *)2&&!over&&len<sizeof(lastlog));memcpy(lastlog,buf,len);lastlog[len]=0;*out=len;return 1;
}
static int MS close_(void *h){assert(h==(void *)2);return 1;}
static u64 MS replacement(u64 a,u64 b,u64 c,u64 d){return ((Fn)current.original)(a,b,c,d)+1;}
static void start(const u8 *code,size_t n,const u8 *unwind,size_t un){
    game=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(game!=MAP_FAILED);
    memset(game,0x90,256);memcpy(game,code,n);memset(original_unwind,0,sizeof(original_unwind));
    has_unwind=un!=0;if(un)memcpy(original_unwind,unwind,un);memcpy(game+1024,original_unwind,sizeof(original_unwind));
    rf=(RF){0,256,1024};tramp=NULL;flushes=registrations=0;lastlog[0]=0;
    current=(Hook){game,(u8 *)replacement,malloc(14),malloc(14),14};
    memcpy(current.saved,game,14);current.patch[0]=0xff;current.patch[1]=0x25;memset(current.patch+2,0,4);
    *(u64 *)(current.patch+6)=(u64)current.replacement;
}
static void install(void){
    assert(!mprotect(game,4096,PROT_READ|PROT_EXEC));
    ((void *(MS *)(Hook *))(image+HOOK_INSTALL_RVA))(&current);
    assert(current.original==tramp&&current.length==0&&flushes==2&&registrations==1);
    assert(!memcmp(game,current.patch,14));assert(!strncmp(lastlog,"HookFix v2 installed",20));
}
static void done(void){free(current.patch);free(current.saved);if(tramp)munmap(tramp,4096);munmap(game,65536);}
static void *thread_(void *unused){(void)unused;for(int j=0;j<10000;j++)assert(((Fn)game)(0,0,0,0)==0);return NULL;}
static void test_openfile(void){
    const u8 code[]={0x40,0x53,0x55,0x56,0x57,0x41,0x57,0x48,0x81,0xec,0x90,1,0,0,
       0x48,0x81,0xc4,0x90,1,0,0,0x41,0x5f,0x5f,0x5e,0x5d,0x5b,0x48,0x89,0xc8,0xc3};
    const u8 unwind[]={1,14,7,0,14,1,50,0,7,0xf0,5,0x70,4,0x60,3,0x50,2,0x30,0,0};
    start(code,sizeof(code),unwind,sizeof(unwind));install();
    assert(((Fn)game)(0xabcdef123456ULL,2,3,4)==0xabcdef123457ULL);
    assert(!memcmp(tramp+256,unwind,18));done();
    /* Execute the REAL original OpenFileImpl wrapper (including its two
     * zero-length memcpy calls), not just our replacement test double. */
    start(code,sizeof(code),unwind,sizeof(unwind));current.replacement=image+0xfe20;
    *(u64 *)(current.patch+6)=(u64)current.replacement;*(Hook **)(image+0x5fe18)=&current;
    install();u8 stable[64];memcpy(stable,tramp,64);
    pthread_t threads[16];for(int i=0;i<16;i++)assert(!pthread_create(&threads[i],NULL,thread_,NULL));
    for(int i=0;i<16;i++)assert(!pthread_join(threads[i],NULL));
    assert(!memcmp(game,current.patch,14)&&!memcmp(tramp,stable,64));
    puts("PASS: actual OpenFileImpl wrapper, 160,000 calls on 16 threads; entry and trampoline unchanged.");done();
}
static void test_spills(void){
    const u8 code[]={0x48,0x89,0x5c,0x24,8,0x48,0x89,0x6c,0x24,16,0x48,0x89,0x74,0x24,24,
      0x48,0x89,0x7c,0x24,32,0x41,0x56,0x48,0x83,0xec,32,
      0x48,0x83,0xc4,32,0x41,0x5e,0x48,0x8b,0x5c,0x24,8,0x48,0x8b,0x6c,0x24,16,
      0x48,0x8b,0x74,0x24,24,0x48,0x8b,0x7c,0x24,32,0x48,0x89,0xc8,0xc3};
    const u8 unwind[]={1,26,10,0,26,0x32,22,0xe0,20,0x74,9,0,15,0x64,8,0,10,0x54,7,0,5,0x34,6,0};
    const u8 expect[]={1,15,6,0,15,0x64,3,0,10,0x54,2,0,5,0x34,1,0};
    start(code,sizeof(code),unwind,sizeof(unwind));install();
    assert(!memcmp(tramp+256,expect,sizeof(expect)));assert(((Fn)game)(777,2,3,4)==778);
    puts("PASS: 15-byte instruction boundary; partial-prologue unwind adjusts three saved-register offsets.");done();
}
static void test_rip_and_branch(void){
    const u8 code[]={0x44,0x8b,0xc1,0x48,0x8b,0x0d,0,0,0,0,0x48,0x85,0xc9,0x74,8,
      0x4c,0x89,0xc0,0xc3,0x90,0x90,0x90,0x90,0xb8,123,0,0,0,0xc3};
    start(code,sizeof(code),NULL,0);*(int32_t *)(game+6)=2048-10;*(u64 *)(game+2048)=1;memcpy(current.saved,game,14);install();
    assert(tramp[13]==0x0f&&tramp[14]==0x84);assert(((Fn)game)(555,0,0,0)==556);
    assert(!mprotect(game,4096,PROT_READ|PROT_WRITE|PROT_EXEC));*(u64 *)(game+2048)=0;
    assert(!mprotect(game,4096,PROT_READ|PROT_EXEC));assert(((Fn)game)(555,0,0,0)==124);
    puts("PASS: RIP-relative operand relocated; short conditional branch expanded, both paths execute correctly.");done();
}
static void failures(void){
    const u8 code[]={0x40,0x53,0x55,0x56,0x57,0x41,0x57,0x48,0x81,0xec,0x90,1,0,0,0xc3};
    const u8 unwind[]={1,14,7,0,14,1,50,0,7,0xf0,5,0x70,4,0x60,3,0x50,2,0x30,0,0};
    for(int mode=1;mode<=7;mode++){
        pid_t child=fork();assert(child>=0);
        if(!child){start(code,sizeof(code),unwind,sizeof(unwind));fail_mode=mode;
            if(mode==4)current.saved[0]^=1;
            if(mode==5)game[0]=current.saved[0]=0xc3;
            if(mode==6)game[1024]=0x21; /* chained */
            if(mode==7)has_unwind=0;
            ((void *(MS *)(Hook *))(image+HOOK_INSTALL_RVA))(&current);_Exit(99);
        }
        int status;assert(waitpid(child,&status,0)==child);assert(WIFEXITED(status)&&WEXITSTATUS(status)==73);
    }
    puts("PASS: 7 failure paths stop explicitly (allocation, flush, registration, modified entry, return, chained/missing unwind).");
}
int main(int argc,char **argv){
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
    image=mmap(NULL,IMAGE_SIZE,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(image!=MAP_FAILED);
    for(size_t i=0;i<sizeof(chunks)/sizeof(*chunks);i++){assert(!fseek(f,chunks[i].offset,SEEK_SET));assert(fread(image+chunks[i].rva,1,chunks[i].size,f)==chunks[i].size);}fclose(f);
#define BIND(n,fn) *(void **)(image+IAT_##n)=(void *)(fn)
    BIND(GetCurrentThreadId,tid_);BIND(GetLastError,last_error_);BIND(SetLastError,set_error_);BIND(GetModuleHandleW,module);BIND(GetProcAddress,proc);BIND(VirtualProtect,protect);
    BIND(RtlLookupFunctionEntry,lookup);BIND(ExitProcess,exit_);BIND(CreateFileW,file_);BIND(WriteFile,write_);BIND(CloseHandle,close_);
    for(size_t i=0;i<sizeof(chunks)/sizeof(*chunks);i++){
        int prot=PROT_READ;if(chunks[i].flags&0x80000000)prot|=PROT_WRITE;if(chunks[i].flags&0x20000000)prot|=PROT_EXEC;
        assert(!mprotect(image+chunks[i].rva,(chunks[i].size+4095)&~4095,prot));
    }
    test_openfile();test_spills();test_rip_and_branch();failures();
    puts("LIMIT: actual AMD64 DLL code, mocked Win32 services; no ARM64/FEX/Proton game run.");return 0;
}
