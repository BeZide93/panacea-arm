/* SPDX-License-Identifier: Apache-2.0
 * Windows AMD64 VERSION forwards, built with GNU as/ld.
 * Existing Panacea code and entry point are NOT replaced.
 * All APIs here have integer/pointer parameters; tail jumps preserve stack args.
 * Import addresses are obtained by build.py from the verified original PE.
 * Only RIP-relative references: no new image-base relocations required.
 */
.text
.p2align 4
.global resolve_begin, resolve_end, resolve_prolog_end
resolve_begin:
    subq $0x168, %rsp
resolve_prolog_end:
    movq %rcx, 0x20(%rsp)       /* export name */
    movq %rdx, 0x28(%rsp)       /* aligned cache slot */
    movq (%rdx), %rax
    testq %rax, %rax
    jnz resolve_return
    call *iat_GetLastError(%rip)
    movl %eax, 0x30(%rsp)
    movq system_module(%rip), %rcx
    testq %rcx, %rcx
    jnz resolve_proc

    leaq 0x40(%rsp), %rcx
    movl $248, %edx            /* leaves space for 12 chars + NUL */
    call *iat_GetSystemDirectoryA(%rip)
    testl %eax, %eax
    jz resolve_fail
    cmpl $248, %eax
    jae resolve_fail
    leaq 0x40(%rsp,%rax), %r8
    leaq version_suffix(%rip), %r9
    xorl %edx, %edx
resolve_copy:
    movb (%r9,%rdx), %al
    movb %al, (%r8,%rdx)
    incq %rdx
    testb %al, %al
    jnz resolve_copy
    leaq 0x40(%rsp), %rcx
    call *iat_LoadLibraryA(%rip)
    testq %rax, %rax
    jz resolve_fail
    movq %rax, %r10
    leaq image_base(%rip), %rdx
    cmpq %rdx, %rax
    je resolve_fail            /* never forward back to this DLL */

    xorl %eax, %eax
    lock cmpxchgq %r10, system_module(%rip)
    jz resolve_published
    movq %rax, 0x38(%rsp)      /* another thread won publication */
    movq %r10, %rcx
    call *iat_FreeLibrary(%rip) /* balance only OUR redundant ref */
    movq 0x38(%rsp), %rcx
    jmp resolve_proc
resolve_published:
    movq %r10, %rcx            /* retain one ref for cached pointers */
resolve_proc:
    movq 0x20(%rsp), %rdx
    call *iat_GetProcAddress(%rip)
    testq %rax, %rax
    jz resolve_fail
    leaq image_base(%rip), %rdx
    cmpq %rdx, %rax
    jb resolve_store
    leaq proxy_code_end(%rip), %rdx
    cmpq %rdx, %rax
    jb resolve_fail            /* reject a recursive forward */
resolve_store:
    movq 0x28(%rsp), %rdx
    movq %rax, (%rdx)          /* aligned AMD64 store; same target in races */
    movq %rax, 0x38(%rsp)
    movl 0x30(%rsp), %ecx
    call *iat_SetLastError(%rip)
    movq 0x38(%rsp), %rax
resolve_return:
    addq $0x168, %rsp
    ret
resolve_fail:
    movl $0xc0000139, %ecx     /* STATUS_ENTRYPOINT_NOT_FOUND */
    movl $1, %edx              /* EXCEPTION_NONCONTINUABLE */
    xorl %r8d, %r8d
    xorl %r9d, %r9d
    call *iat_RaiseException(%rip)
    movl $127, %ecx
    call *iat_ExitProcess(%rip)
    ud2
resolve_end:

.macro FORWARD name
.text
.p2align 4
.global proxy_\name, end_\name, prolog_\name
proxy_\name:
    subq $0x68, %rsp
prolog_\name:
    movq %rcx, 0x20(%rsp)
    movq %rdx, 0x28(%rsp)
    movq %r8, 0x30(%rsp)
    movq %r9, 0x38(%rsp)
    leaq name_\name(%rip), %rcx
    leaq slot_\name(%rip), %rdx
    call resolve_begin
    movq 0x20(%rsp), %rcx
    movq 0x28(%rsp), %rdx
    movq 0x30(%rsp), %r8
    movq 0x38(%rsp), %r9
    addq $0x68, %rsp
    jmp *slot_\name(%rip)      /* valid x64 epilog, stack args untouched */
end_\name:
.section .rodata
name_\name: .asciz "\name"
.data
.p2align 3
slot_\name: .quad 0
.endm

FORWARD GetFileVersionInfoA
FORWARD GetFileVersionInfoExA
FORWARD GetFileVersionInfoExW
FORWARD GetFileVersionInfoSizeA
FORWARD GetFileVersionInfoSizeExA
FORWARD GetFileVersionInfoSizeExW
FORWARD VerFindFileA
FORWARD VerFindFileW
FORWARD VerInstallFileA
FORWARD VerInstallFileW
FORWARD VerLanguageNameA
FORWARD VerLanguageNameW
FORWARD VerQueryValueA

.text
.global proxy_code_end
proxy_code_end:
.section .rodata
version_suffix: .asciz "\\version.dll"
patch_notice: .asciz "Modified OpenKH Panacea: VERSION export completion, 2026-10-12. Original Panacea code preserved. Unofficial build; see ANLEITUNG.txt and NOTICE.txt."
.data
.p2align 3
system_module: .quad 0
.section .note.GNU-stack,"",@progbits
