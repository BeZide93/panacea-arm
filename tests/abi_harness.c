/* Executes the shipped AMD64 forwarders under Linux using GCC ms_abi mocks.
 * This is NOT a Wine/Proton/game test; the original DllMain is never run.
 */
#define _GNU_SOURCE
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#include "harness_generated.h"
#define MS __attribute__((ms_abi))
static unsigned char *image;
static _Thread_local unsigned last_error;
static atomic_int loads, frees, lookups;
static int fault_mode, query_mode;
static pthread_barrier_t barrier;
typedef uint64_t (MS *forward8)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);

static uint64_t MS target8(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,uint64_t g,uint64_t h) {
    assert(a==0x1111222233334444ULL && b==0x5555666677778888ULL);
    assert(c==0x1234567887654321ULL && d==0xffffeeeeddddccccULL);
    assert(e==0x100000005ULL && f==0x200000006ULL && g==0x300000007ULL && h==0x400000008ULL);
    assert(last_error==0x1234);
    last_error=0x5678;
    return 0xfedcba9876543210ULL;
}
static const char query_block[]="opaque version data";
static int MS query_target(const void *block,const char *sub,void **buffer,unsigned *length) {
    assert(block==query_block && !strcmp(sub,"\\"));
    assert(last_error==0x1234);
    *buffer=(void *)(query_block+7);
    *length=13;
    last_error=0x5678;
    return 1;
}
static unsigned MS mock_GetLastError(void) { return last_error; }
static void MS mock_SetLastError(unsigned n) { last_error=n; }
static unsigned MS mock_GetSystemDirectoryA(char *p,unsigned n) {
    assert(n==248);
    last_error=91;
    if(fault_mode==1) return 248;
    if(fault_mode==6) return 0;
    strcpy(p,"C:\\windows\\system32");
    return (unsigned)strlen(p);
}
static void *MS mock_LoadLibraryA(const char *p) {
    assert(!strcmp(p,"C:\\windows\\system32\\version.dll"));
    atomic_fetch_add(&loads,1);
    usleep(2000); /* provoke concurrent first-call publication */
    last_error=92;
    if(fault_mode==2) return NULL;
    if(fault_mode==3) return image;
    return (void *)0x123000;
}
static int MS mock_FreeLibrary(void *h) {
    assert(h==(void *)0x123000);
    atomic_fetch_add(&frees,1);
    last_error=93;
    return 1;
}
static void *MS mock_GetProcAddress(void *h,const char *name) {
    assert(h==(void *)0x123000);
    int found=0;
    for(size_t i=0;i<sizeof(entries)/sizeof(*entries);i++) if(!strcmp(name,entries[i].name)) found=1;
    assert(found);
    atomic_fetch_add(&lookups,1);
    last_error=94;
    if(fault_mode==4) return NULL;
    if(fault_mode==5) return image+QUERY_RVA;
    return query_mode ? (void *)query_target : (void *)target8;
}
static void MS mock_RaiseException(unsigned code,unsigned flags,unsigned count,const void *args) {
    assert(code==0xc0000139 && flags==1 && count==0 && args==NULL);
    _Exit(73);
}
static void MS mock_ExitProcess(unsigned code) { _Exit(code); }
static void reset(void) {
    memset(image+DATA_RVA,0,4096);
    atomic_store(&loads,0); atomic_store(&frees,0); atomic_store(&lookups,0);
}
static void call_one(size_t i) {
    last_error=0x1234;
    forward8 fn=(forward8)(image+entries[i].rva);
    assert(fn(0x1111222233334444ULL,0x5555666677778888ULL,0x1234567887654321ULL,
        0xffffeeeeddddccccULL,0x100000005ULL,0x200000006ULL,0x300000007ULL,0x400000008ULL)==0xfedcba9876543210ULL);
    assert(last_error==0x5678);
}
static void *thread_main(void *unused) {
    (void)unused;
    pthread_barrier_wait(&barrier);
    for(int j=0;j<50;j++) for(size_t i=0;i<sizeof(entries)/sizeof(*entries);i++) call_one(i);
    return NULL;
}
int main(int argc,char **argv) {
    assert(argc==2);
    FILE *f=fopen(argv[1],"rb"); assert(f);
    image=mmap(NULL,IMAGE_SIZE,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(image!=MAP_FAILED);
    for(size_t i=0;i<sizeof(chunks)/sizeof(*chunks);i++) {
        assert(!fseek(f,chunks[i].offset,SEEK_SET));
        assert(fread(image+chunks[i].rva,1,chunks[i].size,f)==chunks[i].size);
    }
    fclose(f);
#define BIND(n) (*(void **)(image+IAT_##n)=(void *)mock_##n)
    BIND(GetLastError); BIND(SetLastError); BIND(GetSystemDirectoryA); BIND(LoadLibraryA);
    BIND(FreeLibrary); BIND(GetProcAddress); BIND(RaiseException); BIND(ExitProcess);
    for(size_t i=0;i<sizeof(chunks)/sizeof(*chunks);i++) {
        unsigned flags=chunks[i].flags;
        int prot=PROT_READ|((flags&0x80000000)?PROT_WRITE:0)|((flags&0x20000000)?PROT_EXEC:0);
        assert(!mprotect(image+chunks[i].rva,(chunks[i].size+4095)&~4095,prot));
    }
    reset();
    for(size_t i=0;i<sizeof(entries)/sizeof(*entries);i++) {call_one(i); call_one(i);}
    assert(atomic_load(&loads)==1 && atomic_load(&frees)==0 && atomic_load(&lookups)==13);
    puts("PASS: all 13 compiled forwards, cold/hot cache, 8 full-width arguments, result and LastError preservation.");
    reset();
    query_mode=1;
    typedef int (MS *query_fn)(const void *,const char *,void **,unsigned *);
    void *buffer=NULL; unsigned length=0; last_error=0x1234;
    assert(((query_fn)(image+QUERY_RVA))(query_block,"\\",&buffer,&length)==1);
    assert(buffer==query_block+7 && length==13 && last_error==0x5678);
    query_mode=0;
    puts("PASS: VerQueryValueA pointer/output-length ABI using an opaque-buffer mock.");
    reset();
    pthread_t threads[16];
    assert(!pthread_barrier_init(&barrier,NULL,16));
    for(int i=0;i<16;i++) assert(!pthread_create(&threads[i],NULL,thread_main,NULL));
    for(int i=0;i<16;i++) assert(!pthread_join(threads[i],NULL));
    assert(atomic_load(&loads)-atomic_load(&frees)==1);
    printf("PASS: 10,400 forwarded calls across 16 threads; %d loads, %d duplicate references released.\n",atomic_load(&loads),atomic_load(&frees));
    for(int mode=1;mode<=6;mode++) {
        reset(); fault_mode=mode;
        pid_t pid=fork(); assert(pid>=0);
        if(!pid) {call_one(0); _Exit(99);}
        int status; assert(waitpid(pid,&status,0)==pid);
        assert(WIFEXITED(status) && WEXITSTATUS(status)==73);
    }
    puts("PASS: 6 error cases fail explicitly: long/failed system path, failed/self load, missing/recursive proc.");
    puts("LIMIT: mocked Win32 APIs on Linux x86-64; no Panacea DllMain, real VERSION resources, Wine or ARM64 game run.");
    return 0;
}
