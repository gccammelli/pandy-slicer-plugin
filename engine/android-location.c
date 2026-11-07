/*
 * Where the engine thinks it is installed, on Android.
 *
 * Bambu Studio's CLI finds its resources/ next to its own executable: it reads the /proc/self/exe link
 * (boost::dll::program_location) and goes up from there. Android installs the engine read-only in the app's native
 * library folder, with nowhere to put resources/ beside it. When PANDY_ENGINE_HOME is set, this answer to
 * readlink("/proc/self/exe") is "$PANDY_ENGINE_HOME/bin/pandy-engine" (a placeholder file the app creates next to the
 * unpacked resources/), so the CLI uses $PANDY_ENGINE_HOME/resources. Every other readlink is the real one.
 * Linked with -Wl,--wrap=readlink (engine.cmake): nothing else in the slicer changes.
 */
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

ssize_t __real_readlink(const char *path, char *buf, size_t size);

ssize_t __wrap_readlink(const char *path, char *buf, size_t size) {
    const char *home = getenv("PANDY_ENGINE_HOME");
    if (home && path && strcmp(path, "/proc/self/exe") == 0) {
        static const char suffix[] = "/bin/pandy-engine";
        size_t n = strlen(home), total = n + sizeof(suffix) - 1;
        if (total > size) total = size;
        memcpy(buf, home, n < total ? n : total);
        if (total > n) memcpy(buf + n, suffix, total - n);
        return (ssize_t)total;
    }
    return __real_readlink(path, buf, size);
}

/*
 * Android's app sandbox (seccomp) kills a process that makes a system call outside its allow-list, with SIGSYS.
 * glibc tries some newer calls first (rseq, clone3, ...) and falls back when the kernel answers ENOSYS. This handler
 * gives that answer instead of dying, and logs each refused call once, so a call the engine cannot do without still
 * fails visibly. Only installed when PANDY_ENGINE_HOME is set (inside the app). aarch64 only.
 */
#if defined(__aarch64__)
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <ucontext.h>
#include <unistd.h>

static void on_sigsys(int sig, siginfo_t *info, void *context) {
    (void)sig;
    static unsigned char logged[1024];
    int nr = info->si_syscall;
    if (nr >= 0 && nr < 1024 && !logged[nr]) {
        logged[nr] = 1;
        char msg[96];
        int n = snprintf(msg, sizeof msg, "pandy-engine: system call %d refused by the Android sandbox, answered ENOSYS\n", nr);
        if (n > 0) (void)!write(2, msg, (size_t)n);
    }
    ((ucontext_t *)context)->uc_mcontext.regs[0] = (unsigned long long)(-ENOSYS);
}

__attribute__((constructor)) static void pandy_install_sigsys(void) {
    if (!getenv("PANDY_ENGINE_HOME")) return;
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_sigsys;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSYS, &sa, NULL);
}
#endif

/*
 * Threads. glibc creates them with clone3 and falls back to clone when the kernel answers ENOSYS. Android's sandbox
 * refuses clone3, and glibc makes that call with every signal blocked, so the SIGSYS handler above cannot answer
 * for it: the process would be killed. Linked with -Wl,--wrap=__clone3 (engine.cmake), clone3 reports ENOSYS
 * without being called, and glibc uses clone, which the sandbox allows. Same threads, same results.
 */
#include <errno.h>
struct clone_args;
int __wrap___clone3(struct clone_args *args, size_t size, int (*func)(void *), void *arg) {
    (void)args; (void)size; (void)func; (void)arg;
    errno = ENOSYS;
    return -1;
}
