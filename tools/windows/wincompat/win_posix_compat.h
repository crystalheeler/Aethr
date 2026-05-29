/* wincompat: POSIX function/macro shims for the mingw acarsdec/dumpvdl2 builds.
 *
 * Force-included (gcc -include) ahead of each source so the decoders' Linux
 * assumptions compile under mingw without editing upstream. Everything is
 * guarded by _WIN32 and is either a macro, a type, or a `static` function, so
 * it's safe to pull into every translation unit. Each function the build
 * flagged as "implicit declaration" is genuinely absent from mingw, so these
 * definitions can't clash with a system one.
 *
 * Not used by the INTERCEPT Python app at all.
 */
#ifndef WIN_POSIX_COMPAT_H
#define WIN_POSIX_COMPAT_H

#ifdef _WIN32

#include <winsock2.h>	/* gethostname; must precede windows.h */
#include <ws2tcpip.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* POSIX hostname cap — mingw <limits.h> doesn't define it. */
#ifndef HOST_NAME_MAX
#define HOST_NAME_MAX 255
#endif

/* strsep(3) — BSD, absent from mingw. */
static __attribute__((unused)) char *strsep(char **stringp, const char *delim)
{
	char *start = *stringp;
	char *p;

	if (start == NULL)
		return NULL;

	p = start + strcspn(start, delim);
	if (*p != '\0') {
		*p = '\0';
		*stringp = p + 1;
	} else {
		*stringp = NULL;
	}
	return start;
}

/* strsignal(3) — absent from mingw; a generic label is enough here. */
static __attribute__((unused)) char *strsignal(int sig)
{
	(void)sig;
	return (char *)"signal";
}

/* gmtime_r(3) — POSIX reentrant variant; mingw only ships gmtime_s (swapped
 * argument order and a different return convention).
 *
 * acarsdec calls this as gmtime_r(&tv.tv_sec, ...) where tv is a
 * struct timeval. On mingw/Winsock, timeval.tv_sec is a 32-bit `long`, but
 * time_t is 64-bit — so we take `const long *` to match the caller exactly
 * and widen to time_t before handing off to gmtime_s. (Declaring time_t*
 * here would both fail to compile AND, if forced, make gmtime_s read 8 bytes
 * from a 4-byte field — i.e. garbage timestamps.) */
static __attribute__((unused)) struct tm *gmtime_r(const long *timep, struct tm *result)
{
	time_t t = (time_t)(*timep);

	if (gmtime_s(result, &t) != 0)
		return NULL;
	return result;
}

/* Minimal POSIX signal shim. Windows lacks sigaction()/sigemptyset()/SIGQUIT.
 * acarsdec only uses these to install a clean-shutdown handler; INTERCEPT
 * terminates the child process directly, so mapping to the C-standard
 * signal() (and ignoring SIGQUIT, which Windows never raises) is sufficient. */
#ifndef SIGQUIT
#define SIGQUIT 3
#endif

struct sigaction {
	void (*sa_handler)(int);
	int sa_mask;
	int sa_flags;
};

static __attribute__((unused)) int sigemptyset(int *set)
{
	if (set)
		*set = 0;
	return 0;
}

static __attribute__((unused)) int sigaction(int signum, const struct sigaction *act,
					     struct sigaction *oldact)
{
	(void)oldact;
	if (act && act->sa_handler)
		signal(signum, act->sa_handler);
	return 0;
}

#endif /* _WIN32 */

#endif /* WIN_POSIX_COMPAT_H */
