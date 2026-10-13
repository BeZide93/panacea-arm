/* Aggregated diagnostics only. No result substitution or resource caching.
 * One worker writes five-second buckets. Game threads never do file I/O here.
 * Nonblocking collector: lost measurements are counted instead of spinning.
 * Supported lifetime: installed before gameplay; no hot FreeLibrary/unload.
 */
IMP u32 GetLastError(void);
IMP void SetLastError(u32);
IMP int QueryPerformanceCounter(int64_t *);
extern int panacea_load(void *,const char *,void *,u8);
extern int panacea_load_size(void *,const char *,void *,int,u8);
extern void *panacea_load_malloc(void *,const char *,int *,u8,const char *);
extern u8 panacea_open(void *,const char *,const char *);
extern int panacea_size(void *,const char *);
#define PERF_SLOTS 2048
#define PERF_PATH 256
#define PERF_KINDS 5
/* Windows x64 long is 32 bit. All duration values are QPC ticks. */
typedef struct {u64 calls,zero,negative,ticks,max_ticks,first_caller,last_caller;} PerfCounts;
typedef struct {u32 used,kind,hash;char path[PERF_PATH];PerfCounts c;} PerfRow;
typedef void (*PerfSleep)(u32);
typedef struct {
    u32 lock,enabled,attached,pad;
    u64 dropped,overflow,badpath,clock_errors;
    u64 origin,last,freq,seq,write_errors;
    PerfSleep sleep;
    PerfRow rows[PERF_SLOTS],snapshot[PERF_SLOTS];
    char output[65536];
} PerfState;
/* The linker supplies this address in a separate RW, non-executable section. */
static PerfState *perf_state __attribute__((section(".perfdata")));
static const uint16_t perf_name[]={'p','a','n','a','c','e','a','_','r','i','k','u','_','p','e','r','f','.','l','o','g',0};
static int perf_lock(PerfState *s){return !__atomic_exchange_n(&s->lock,1,__ATOMIC_ACQUIRE);}
static void perf_unlock(PerfState *s){__atomic_store_n(&s->lock,0,__ATOMIC_RELEASE);}
static u64 perf_clock(void){int64_t t=0;return QueryPerformanceCounter(&t)?(u64)t:0;}
static u64 perf_begin(void){u32 e=GetLastError();PerfState *s=__atomic_load_n(&perf_state,__ATOMIC_ACQUIRE);u64 t=(s&&__atomic_load_n(&s->enabled,__ATOMIC_RELAXED))?perf_clock():0;SetLastError(e);return t;}
static __attribute__((noinline)) void perf_record(u32 kind,const char *path,int64_t result,u64 start,u64 end,u64 caller){
    PerfState *s=__atomic_load_n(&perf_state,__ATOMIC_ACQUIRE);
    if(!s||!__atomic_load_n(&s->enabled,__ATOMIC_RELAXED))return;
    if(!start||!end||end<start){__atomic_fetch_add(&s->clock_errors,1,__ATOMIC_RELAXED);return;}
    char key[PERF_PATH];u32 h=2166136261U,n=0;
    if(!path)path="(null)";
    for(;n<PERF_PATH-1 && path[n];n++){
        unsigned char c=(unsigned char)path[n];if(c>='A'&&c<='Z')c+=32;if(c=='\\')c='/';if(c<' '||c==127)c='?';
        key[n]=(char)c;h=(h^c)*16777619U;
    }
    if(n==PERF_PATH-1 && path[n]){__atomic_fetch_add(&s->badpath,1,__ATOMIC_RELAXED);return;}key[n]=0;
    h=(h^kind)*16777619U;
    if(!perf_lock(s)){__atomic_fetch_add(&s->dropped,1,__ATOMIC_RELAXED);return;}
    PerfRow *r=0;
    for(u32 j=0;j<PERF_SLOTS;j++){
        PerfRow *q=&s->rows[(h+j)&(PERF_SLOTS-1)];
        if(!q->used){q->used=1;q->kind=kind;q->hash=h;copy(q->path,key,n+1);r=q;break;}
        if(q->hash==h&&q->kind==kind){u32 k=0;while(k<=n&&q->path[k]==key[k])k++;if(k==n+1){r=q;break;}}
    }
    if(r){PerfCounts *c=&r->c;u64 dt=end-start;if(!c->calls)c->first_caller=caller;c->last_caller=caller;c->calls++;c->zero+=result==0;c->negative+=result<0;c->ticks+=dt;if(dt>c->max_ticks)c->max_ticks=dt;}
    else __atomic_fetch_add(&s->overflow,1,__ATOMIC_RELAXED);
    perf_unlock(s);
}
static void perf_end(u32 kind,const char *path,int64_t r,u64 start,u64 caller){u32 e=GetLastError();u64 end=start?perf_clock():0;perf_record(kind,path,r,start,end,caller);SetLastError(e);}
static unsigned perf_text(char *b,unsigned n,const char *s){while(*s)b[n++]=*s++;return n;}
static unsigned perf_num(char *b,unsigned n,u64 v){char d[24];unsigned i=0;do{d[i++]=(char)('0'+v%10);v/=10;}while(v);while(i)b[n++]=d[--i];return n;}
static unsigned perf_hex(char *b,unsigned n,u64 v){const char x[]="0123456789abcdef";b[n++]='0';b[n++]='x';for(int i=15;i>=0;i--)b[n++]=x[(v>>(i*4))&15];return n;}
static unsigned perf_field(char *b,unsigned n,u64 v){b[n++]='\t';return perf_num(b,n,v);}
static int perf_write(void *f,const char *b,unsigned n){while(n){u32 w=0;if(!WriteFile(f,b,n,&w,0)||!w||w>n)return 0;b+=w;n-=w;}return 1;}
static const char *perf_kind(u32 k){switch(k){case 0:return "LoadFile";case 1:return "LoadFileWithSize";case 2:return "LoadFileWithMalloc";case 3:return "OpenFileImpl";default:return "GetFileSize";}}
/* The worker is the sole writer. Snapshot rows retain names; active counts reset.
 * Durations are inclusive (nested OpenFile time is also inside LoadFile time).
 * Calls belong to the bucket in which they finish, not the one they start in.
 */
static __attribute__((noinline)) void perf_flush(PerfState *s){
    while(!perf_lock(s))s->sleep(1);
    u64 now=perf_clock(),prev=s->last;s->last=now;s->seq++;
    copy(s->snapshot,s->rows,sizeof(s->rows));
    for(u32 i=0;i<PERF_SLOTS;i++)memset(&s->rows[i].c,0,sizeof(PerfCounts));
    u64 drop=__atomic_exchange_n(&s->dropped,0,__ATOMIC_RELAXED),over=__atomic_exchange_n(&s->overflow,0,__ATOMIC_RELAXED),bad=__atomic_exchange_n(&s->badpath,0,__ATOMIC_RELAXED),clk=__atomic_exchange_n(&s->clock_errors,0,__ATOMIC_RELAXED);
    perf_unlock(s);
    void *f=CreateFileW(perf_name,4,3,0,4,0x80,0);
    if(f==(void *)(intptr_t)-1){s->write_errors++;return;}
    char *b=s->output;unsigned n=0;
    n=perf_text(b,n,"BUCKET\t");n=perf_num(b,n,s->seq);n=perf_field(b,n,prev-s->origin);n=perf_field(b,n,now-s->origin);n=perf_field(b,n,now-prev);n=perf_field(b,n,drop);n=perf_field(b,n,over);n=perf_field(b,n,bad);n=perf_field(b,n,clk);n=perf_field(b,n,s->write_errors);n=perf_field(b,n,__atomic_load_n(&s->attached,__ATOMIC_RELAXED));b[n++]='\n';
    int good=1;
    for(u32 i=0;i<PERF_SLOTS;i++){
        PerfRow *r=&s->snapshot[i];PerfCounts *c=&r->c;if(!c->calls)continue;
        if(n>sizeof(s->output)-1024){if(!perf_write(f,b,n)){good=0;break;}n=0;}
        n=perf_text(b,n,"ROW\t");n=perf_num(b,n,s->seq);b[n++]='\t';n=perf_text(b,n,perf_kind(r->kind));n=perf_field(b,n,c->calls);n=perf_field(b,n,c->zero);n=perf_field(b,n,c->negative);n=perf_field(b,n,c->ticks);n=perf_field(b,n,c->max_ticks);b[n++]='\t';n=perf_hex(b,n,c->first_caller);b[n++]='\t';n=perf_hex(b,n,c->last_caller);b[n++]='\t';n=perf_text(b,n,r->path);b[n++]='\n';
    }
    if(good){n=perf_text(b,n,"END\t");n=perf_num(b,n,s->seq);b[n++]='\n';good=perf_write(f,b,n);}if(!good)s->write_errors++;CloseHandle(f);
}
static u32 perf_worker(void *arg){
    PerfState *s=arg;void *f=CreateFileW(perf_name,4,3,0,4,0x80,0);
    if(f!=(void *)(intptr_t)-1){char b[1600];unsigned n=0;n=perf_text(b,n,"RIKU-PERF-v1\tqpc_frequency=");n=perf_num(b,n,s->freq);n=perf_text(b,n,"\tgame_base=");n=perf_hex(b,n,(u64)GetModuleHandleW(0));n=perf_text(b,n,"\torigin_qpc=");n=perf_num(b,n,s->origin);n=perf_text(b,n,"\nBUCKET columns: id,start_ticks,end_ticks,elapsed_ticks,dropped,table_full,path_too_long,clock_errors,write_errors_total,attached_mask\nROW columns: bucket,kind,calls,zero,negative,inclusive_ticks,max_ticks,first_caller,last_caller,path\nAll times are QPC ticks; divide by qpc_frequency for seconds. Nested kinds MUST NOT be summed. Counts are completed calls, not disk reads. Expected attached_mask=31. Paths ASCII-casefolded. Final <5 seconds can be absent.\n");if(!perf_write(f,b,n))s->write_errors++;CloseHandle(f);}else s->write_errors++;
    for(;;){s->sleep(5000);perf_flush(s);}return 0;
}
static __attribute__((noinline)) void perf_init(void){
    if(perf_state)return;
    typedef void *(*Alloc)(void *,size_t,u32,u32);
    typedef int (*Frequency)(int64_t *);
    typedef void *(*Thread)(void *,size_t,u32 (*)(void *),void *,u32,u32 *);
    void *k=GetModuleHandleW(kernel_name);Alloc alloc=(Alloc)GetProcAddress(k,"VirtualAlloc");Frequency freq=(Frequency)GetProcAddress(k,"QueryPerformanceFrequency");PerfSleep sleep=(PerfSleep)GetProcAddress(k,"Sleep");Thread create=(Thread)GetProcAddress(k,"CreateThread");
    if(!alloc||!freq||!sleep||!create){log_line("PERF DISABLED missing API",0);return;}
    int64_t hz=0;if(!freq(&hz)||hz<=0){log_line("PERF DISABLED QPC frequency",0);return;}
    PerfState *s=alloc(0,sizeof(*s),0x3000,4);if(!s){log_line("PERF DISABLED allocation",0);return;}
    s->freq=(u64)hz;s->sleep=sleep;s->origin=s->last=perf_clock();if(!s->origin){log_line("PERF DISABLED QPC",0);return;}
    s->enabled=1;__atomic_store_n(&perf_state,s,__ATOMIC_RELEASE);
    void *t=create(0,0,perf_worker,s,0,0);if(!t){__atomic_store_n(&s->enabled,0,__ATOMIC_RELAXED);log_line("PERF DISABLED worker",0);return;}
    CloseHandle(t);log_line("PERF v1 enabled; interval ms",5000);
}
static int trace_load(void *self,const char *name,void *addr,u8 hd){u64 t=perf_begin();int r=panacea_load(self,name,addr,hd);perf_end(0,name,r,t,(u64)__builtin_return_address(0));return r;}
static int trace_load_size(void *self,const char *name,void *addr,int size,u8 hd){u64 t=perf_begin();int r=panacea_load_size(self,name,addr,size,hd);perf_end(1,name,r,t,(u64)__builtin_return_address(0));return r;}
static void *trace_load_malloc(void *self,const char *name,int *size,u8 hd,const char *alt){u64 t=perf_begin();void *r=panacea_load_malloc(self,name,size,hd,alt);perf_end(2,name,r?1:0,t,(u64)__builtin_return_address(0));return r;}
static u8 trace_open(void *self,const char *name,const char *alt){u64 t=perf_begin();u8 r=panacea_open(self,name,alt);perf_end(3,name,r,t,(u64)__builtin_return_address(0));return r;}
static int trace_size(void *self,const char *name){u64 t=perf_begin();int r=panacea_size(self,name);perf_end(4,name,r,t,(u64)__builtin_return_address(0));return r;}
static __attribute__((noinline)) void trace_attach(Hook *h){
    void *neo=0;u32 mask=0;
    if(h->replacement==(void *)panacea_load){neo=(void *)trace_load;mask=1;}
    else if(h->replacement==(void *)panacea_load_size){neo=(void *)trace_load_size;mask=2;}
    else if(h->replacement==(void *)panacea_load_malloc){neo=(void *)trace_load_malloc;mask=4;}
    else if(h->replacement==(void *)panacea_open){neo=(void *)trace_open;mask=8;}
    else if(h->replacement==(void *)panacea_size){neo=(void *)trace_size;mask=16;}
    if(neo){u32 e=GetLastError();perf_init();if(perf_state&&perf_state->enabled){h->replacement=neo;absjump(h->patch,neo);__atomic_fetch_or(&perf_state->attached,mask,__ATOMIC_RELAXED);log_line("PERF ATTACH",(u64)h->original);}SetLastError(e);}
}
