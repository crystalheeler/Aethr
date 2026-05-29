/* wincompat: satisfy <netinet/in.h> on mingw by mapping to Winsock.
 *
 * struct sockaddr_in / in_addr / IPPROTO_* / htons live in <winsock2.h>.
 * mingw ships no <netinet/in.h>, so this is the only header by that name on
 * the include path. Inert off-Windows.
 */
#ifndef WINCOMPAT_NETINET_IN_H
#define WINCOMPAT_NETINET_IN_H

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

#endif /* WINCOMPAT_NETINET_IN_H */
