/* Executes actual shipped Windows x64 PE code with MS ABI WinAPI test doubles.
 * This is not a Proton/FEX/game integration test. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <pthread.h>
#include "harness_generated.h"
#define MS __attribute__((ms_abi))
static _Thread_local unsigned error_code=321;
static uint64_t clock_now=1000000;
static unsigned writes,opens,closes,threads,deny,thread_fail,partial;
static char output[4000000];static size_t outlen;
static void *state;static uint8_t *im;
static unsigned MS geterr(void){return error_code;}
static void MS seterr(unsigned x){error_code=x;}
static int MS qpc(int64_t *t){*t=(int64_t)__atomic_fetch_add(&clock_now,100,__ATOMIC_RELAXED);error_code=888;return 1;}
static int MS frequency(int64_t *t){*t=1000000;return 1;}
static void MS sleep_(unsigned x){(void)x;}
static void *MS alloc_(void *p,size_t n,unsigned mode,unsigned prot){assert(!p&&n>1000000&&mode==0x3000&&prot==4);state=calloc(1,n);assert(state);return state;}
static void *MS module(const uint16_t *n){assert(!n||*n=='k');return (void *)1;}
static void *MS create_thread(void *sec,size_t size,void *fn,void *arg,unsigned flags,unsigned *id){assert(!sec&&!size&&fn&&arg==state&&!flags&&!id);threads++;return thread_fail?NULL:(void *)3;}
static void *MS proc(void *mod,const char *n){assert(mod==(void *)1);if(!strcmp(n,"VirtualAlloc"))return alloc_;if(!strcmp(n,"QueryPerformanceFrequency"))return frequency;if(!strcmp(n,"Sleep"))return sleep_;if(!strcmp(n,"CreateThread"))return create_thread;abort();}
static void *MS create_file(const uint16_t *n,unsigned a,unsigned sh,void *sec,unsigned d,unsigned attr,void *t){assert(*n=='p'&&a==4&&sh==3&&!sec&&d==4&&attr==0x80&&!t);opens++;error_code=444;return deny?(void *)(intptr_t)-1:(void *)2;}
static int MS write_(void *h,const void *b,unsigned n,unsigned *out,void *ov){assert(h==(void *)2&&!ov);if(partial&&n>31)n=31;assert(outlen+n<sizeof(output));memcpy(output+outlen,b,n);outlen+=n;output[outlen]=0;*out=n;writes++;return 1;}
static int MS close_(void *h){assert(h==(void *)2||h==(void *)3);closes++;return 1;}
static void *ctx=(void *)0x12345678,*buf=(void *)0x98765432;
static const char name[]="obj/P_EX080.a.fm",alt[]="alternate";
static void check(void *s,const char *n){assert(s==ctx&&n==name&&error_code==321);error_code=777;}
static int MS load(void *s,const char *n,void *b,uint8_t hd){check(s,n);assert(b==buf&&hd==1);return -23;}
static int MS load_size(void *s,const char *n,void *b,int z,uint8_t hd){check(s,n);assert(b==buf&&z==0x12345&&hd==1);return 77;}
static void *MS load_malloc(void *s,const char *n,int *z,uint8_t hd,const char *a){check(s,n);assert(hd==1&&a==alt);*z=54321;return buf;}
static uint8_t MS open_(void *s,const char *n,const char *a){check(s,n);assert(a==alt);return 0;}
static int MS size_(void *s,const char *n){check(s,n);return 0;}
static void jump(uint8_t *p,void *fn){p[0]=0xff;p[1]=0x25;memset(p+2,0,4);memcpy(p+6,&fn,8);}
static void reset_output(void){outlen=0;output[0]=0;}
static void flush(void){((void(MS *)(void *))(im+RVA_perf_flush))(state);}
static void record(unsigned k,const char *p,int64_t r,uint64_t start,uint64_t end,uint64_t caller){((void(MS *)(unsigned,const char *,int64_t,uint64_t,uint64_t,uint64_t))(im+RVA_perf_record))(k,p,r,start,end,caller);}
static void *runner(void *v){(void)v;for(unsigned i=0;i<20000;i++)record(4,"OBJ\\RIKU.A.FM",0,100,125,0x140000123);return 0;}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);im=mmap(0,IMAGE_SIZE,7,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(im!=MAP_FAILED);
 for(unsigned i=0;i<sizeof(chunks)/sizeof(*chunks);i++){assert(!fseek(f,chunks[i].offset,SEEK_SET));assert(fread(im+chunks[i].rva,1,chunks[i].size,f)==chunks[i].size);}fclose(f);
#define BIND(n,fn) *(void **)(im+IAT_##n)=(void *)(fn)
 BIND(GetLastError,geterr);BIND(SetLastError,seterr);BIND(QueryPerformanceCounter,qpc);BIND(GetModuleHandleW,module);BIND(GetProcAddress,proc);BIND(CreateFileW,create_file);BIND(WriteFile,write_);BIND(CloseHandle,close_);
 jump(im+0xfeb0,load);jump(im+0x103c0,load_size);jump(im+0x10900,load_malloc);jump(im+0xfe20,open_);jump(im+0x10e60,size_);
 /* Enforce shipped section permissions after installing the test doubles. */
 for(unsigned i=0;i<sizeof(chunks)/sizeof(*chunks);i++){unsigned flags=chunks[i].flags;int prot=PROT_READ;if(flags&0x80000000U)prot|=PROT_WRITE;if(flags&0x20000000U)prot|=PROT_EXEC;assert(!mprotect(im+chunks[i].rva,(chunks[i].size+4095)&~4095U,prot));}
 ((void(MS *)(void))(im+RVA_perf_init))();assert(threads==1&&*(void **)(im+PERF_STATE_RVA)==state);
 ((void(MS *)(void))(im+RVA_perf_init))();assert(threads==1);
 struct Hook {void *original,*replacement,*patch,*saved;int length;};
 const unsigned originals[]={0xfeb0,0x103c0,0x10900,0xfe20,0x10e60};
 const unsigned replacements[]={RVA_trace_load,RVA_trace_load_size,RVA_trace_load_malloc,RVA_trace_open,RVA_trace_size};
 for(unsigned i=0;i<5;i++){uint8_t patch[14]={0};struct Hook h={(void *)(uintptr_t)(0x140000000ULL+i*256),im+originals[i],patch,0,14};error_code=321;((void(MS *)(struct Hook *))(im+RVA_trace_attach))(&h);assert(h.replacement==im+replacements[i]&&patch[0]==0xff&&patch[1]==0x25&&*(void **)(patch+6)==h.replacement&&error_code==321);}
 unsigned oldwrites=writes,oldopens=opens;
 error_code=321;assert(((int(MS *)(void *,const char *,void *,uint8_t))(im+RVA_trace_load))(ctx,name,buf,1)==-23);assert(error_code==777);
 error_code=321;assert(((int(MS *)(void *,const char *,void *,int,uint8_t))(im+RVA_trace_load_size))(ctx,name,buf,0x12345,1)==77);assert(error_code==777);
 error_code=321;int z=0;assert(((void *(MS *)(void *,const char *,int *,uint8_t,const char *))(im+RVA_trace_load_malloc))(ctx,name,&z,1,alt)==buf&&z==54321);assert(error_code==777);
 error_code=321;assert(((uint8_t(MS *)(void *,const char *,const char *))(im+RVA_trace_open))(ctx,name,alt)==0);assert(error_code==777);
 error_code=321;assert(((int(MS *)(void *,const char *))(im+RVA_trace_size))(ctx,name)==0);assert(error_code==777);
 assert(writes==oldwrites&&opens==oldopens);reset_output();flush();
 assert(strstr(output,"\tLoadFile\t1\t0\t1\t100\t100\t"));assert(strstr(output,"\tGetFileSize\t1\t1\t0\t100\t100\t"));assert(strstr(output,"\tLoadFileWithSize\t1\t0\t0\t"));assert(strstr(output,"\tLoadFileWithMalloc\t1\t0\t0\t"));assert(strstr(output,"\tOpenFileImpl\t1\t1\t0\t"));
 puts("PASS: five actual PE wrappers; register/stack arguments, return values, output size and LastError preserved; no per-call file I/O; exact timed aggregates.");
 reset_output();flush();assert(!strstr(output,"ROW\t"));
 pthread_t t[8];for(unsigned i=0;i<8;i++)assert(!pthread_create(&t[i],0,runner,0));for(unsigned i=0;i<8;i++)assert(!pthread_join(t[i],0));reset_output();flush();
 unsigned long long seq,start,end,elapsed,dropped,overflow,bad,clk,we,mask;
 assert(sscanf(output,"BUCKET\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu",&seq,&start,&end,&elapsed,&dropped,&overflow,&bad,&clk,&we,&mask)==10);
 char *row=strstr(output,"\tGetFileSize\t");assert(row);unsigned long long count,zeros,neg,ticks,max;
 assert(sscanf(row,"\tGetFileSize\t%llu\t%llu\t%llu\t%llu\t%llu",&count,&zeros,&neg,&ticks,&max)==5);assert(mask==31);assert(count+dropped==160000&&zeros==count&&neg==0&&ticks==count*25&&max==25&&!overflow&&!bad&&!clk);assert(strstr(output,"obj/riku.a.fm"));
 printf("PASS: 160,000 calls on eight threads: %llu collected + %llu explicitly dropped; exact count/timing conservation.\n",count,dropped);
 *(unsigned *)state=1;record(4,"locked",0,100,125,1);*(unsigned *)state=0;
 char longpath[300];memset(longpath,'x',sizeof(longpath));longpath[299]=0;record(4,longpath,0,100,125,1);record(4,"clock",0,0,125,1);
 for(unsigned i=0;i<2200;i++){char p[64];snprintf(p,sizeof(p),"obj/unique_%u.a.fm",i);record(4,p,0,100,125,1);}
 partial=1;reset_output();flush();partial=0;
 assert(sscanf(output,"BUCKET\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu",&seq,&start,&end,&elapsed,&dropped,&overflow,&bad,&clk,&we,&mask)==10);assert(dropped==1&&overflow>0&&bad==1&&clk==1);assert(strstr(output,"ROW\t"));
 deny=1;flush();deny=0;reset_output();flush();assert(sscanf(output,"BUCKET\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu",&seq,&start,&end,&elapsed,&dropped,&overflow,&bad,&clk,&we,&mask)==10);assert(we==1);
 puts("PASS: bucket reset, path normalization, lock contention, table overflow, long paths, clock failure, short writes and unwritable-log recovery.");
 free(state);state=0;*(void **)(im+PERF_STATE_RVA)=0;thread_fail=1;((void(MS *)(void))(im+RVA_perf_init))();oldwrites=writes;oldopens=opens;error_code=321;
 assert(((int(MS *)(void *,const char *))(im+RVA_trace_size))(ctx,name)==0&&error_code==777);assert(writes==oldwrites&&opens==oldopens);
 puts("PASS: worker-creation failure disables measurement and preserves original function behavior.");
 free(state);munmap(im,IMAGE_SIZE);return 0;
}
