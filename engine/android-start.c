/*
 * The engine's entry point on arm64, before glibc's own _start.
 *
 * Android's app sandbox (seccomp) does not allow some system calls glibc makes, among them set_robust_list and rseq
 * while it sets up the first thread, before any other code of ours can run. Where the kernel lacks a call, glibc
 * gets ENOSYS and carries on without it; Android's filter instead raises SIGSYS, which kills the process. This entry
 * point installs a SIGSYS handler that answers ENOSYS, then jumps to _start. It uses no libc and no thread-local
 * storage (neither exists yet). android-location.c replaces it later with one that also logs each refused call.
 * Linked with -Wl,-e,pandy_start (engine.cmake). On a machine without the filter it never runs.
 */
#if defined(__aarch64__)
#include <signal.h>
#include <ucontext.h>

#define PANDY_ENOSYS 38

__attribute__((no_stack_protector)) static void early_sigsys(int sig, siginfo_t *info, void *context) {
    (void)sig; (void)info;
    ((ucontext_t *)context)->uc_mcontext.regs[0] = (unsigned long long)(-PANDY_ENOSYS);
}

/* The kernel's struct sigaction on arm64. Without SA_RESTORER the kernel returns through the vDSO trampoline. */
struct pandy_kernel_sigaction { void (*handler)(int, siginfo_t *, void *); unsigned long flags; void (*restorer)(void); unsigned long mask; };

__attribute__((no_stack_protector, used)) void pandy_early_setup(void) {
    struct pandy_kernel_sigaction sa = { early_sigsys, 4 /* SA_SIGINFO */, 0, 0 };
    register long x8 __asm__("x8") = 134; /* rt_sigaction */
    register long x0 __asm__("x0") = 31;  /* SIGSYS */
    register long x1 __asm__("x1") = (long)&sa;
    register long x2 __asm__("x2") = 0;
    register long x3 __asm__("x3") = 8;   /* sizeof(sigset) */
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory");
}

/* Entry: keep x0 (the kernel's atexit argument) and the stack exactly as _start expects them. */
__asm__(".text\n.globl pandy_start\n.type pandy_start, %function\npandy_start:\n"
        "  mov x19, x0\n  mov x20, sp\n  bl pandy_early_setup\n  mov sp, x20\n  mov x0, x19\n  mov x29, #0\n  mov x30, #0\n  b _start\n");
#endif
