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

/* strndup(3) — mingw <string.h> declares it only in non-strict mode, so
 * strict-ANSI builds (dumpvdl2's) get an implicit-declaration error while a
 * default build sees the real declaration. A plain `static strndup` collides
 * with that declaration (and broke even cmake's compiler test). Provide a
 * privately-named impl and macro-rename — works whether or not mingw's
 * declaration is visible, since <string.h> was already included above. */
static __attribute__((unused)) char *_wincompat_strndup(const char *s, size_t n)
{
	size_t len = strnlen(s, n);
	char *p = (char *)malloc(len + 1);

	if (p) {
		memcpy(p, s, len);
		p[len] = '\0';
	}
	return p;
}
#define strndup _wincompat_strndup

/* strsignal(3) — absent from mingw; a generic label is enough here. */
static __attribute__((unused)) char *strsignal(int sig)
{
	(void)sig;
	return (char *)"signal";
}

/* gmtime_r(3) — POSIX reentrant variant; mingw only ships gmtime_s (swapped
 * argument order and a different return convention).
 *
 * Callers pass different pointer types: fileout.c uses &(time_t) (64-bit),
 * while output.c uses &tv.tv_sec which on Winsock's struct timeval is a
 * 32-bit long. No single fixed pointer-type signature matches both (GCC 14
 * makes the mismatch a hard error). So gmtime_r is a macro that dereferences
 * the argument and widens the value to time_t — type-agnostic and always
 * correct (no over-reading a 4-byte field as 8 bytes). */
static __attribute__((unused)) struct tm *_wincompat_gmtime_r(time_t t, struct tm *result)
{
	if (gmtime_s(result, &t) != 0)
		return NULL;
	return result;
}
#define gmtime_r(timep, result) _wincompat_gmtime_r((time_t)(*(timep)), (result))

/* localtime_r(3) — same story as gmtime_r; mingw only has localtime_s. */
static __attribute__((unused)) struct tm *_wincompat_localtime_r(time_t t, struct tm *result)
{
	if (localtime_s(result, &t) != 0)
		return NULL;
	return result;
}
#define localtime_r(timep, result) _wincompat_localtime_r((time_t)(*(timep)), (result))

/* gmtime(3) / localtime(3) — dumpvdl2 passes &tv.tv_sec (Winsock 32-bit long)
 * to these, mismatching the const time_t* (64-bit) prototype (hard error under
 * GCC 14). Wrap as macros that widen the value to time_t and use the reentrant
 * *_s variants into a per-translation-unit static buffer (matching the
 * static-storage semantics of the originals). <time.h> is already included
 * above, so the real prototypes were processed before these macros. */
static __attribute__((unused)) struct tm _wincompat_tm_buf;
static __attribute__((unused)) struct tm *_wincompat_gmtime(time_t t)
{
	return (gmtime_s(&_wincompat_tm_buf, &t) == 0) ? &_wincompat_tm_buf : NULL;
}
static __attribute__((unused)) struct tm *_wincompat_localtime(time_t t)
{
	return (localtime_s(&_wincompat_tm_buf, &t) == 0) ? &_wincompat_tm_buf : NULL;
}
#define gmtime(timep)    _wincompat_gmtime((time_t)(*(timep)))
#define localtime(timep) _wincompat_localtime((time_t)(*(timep)))

/* stpcpy(3) — GNU extension (strcpy that returns a pointer to the new NUL).
 * Not declared by mingw <string.h>; map to the GCC builtin. */
#ifndef stpcpy
#define stpcpy __builtin_stpcpy
#endif

/* Minimal POSIX signal shim. Windows lacks sigaction()/sigemptyset()/SIGQUIT.
 * acarsdec only uses these to install a clean-shutdown handler; INTERCEPT
 * terminates the child process directly, so mapping to the C-standard
 * signal() (and ignoring SIGQUIT, which Windows never raises) is sufficient. */
#ifndef SIGQUIT
#define SIGQUIT 3
#endif
/* Other POSIX signals Windows doesn't define. The values match POSIX; the
 * sigaction shim maps handlers to signal(), and Windows never raises these,
 * so registering for them is a harmless no-op. */
#ifndef SIGHUP
#define SIGHUP 1
#endif
#ifndef SIGPIPE
#define SIGPIPE 13
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
