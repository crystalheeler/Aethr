/* wincompat: satisfy <arpa/inet.h> on mingw by mapping to Winsock.
 *
 * inet_ntoa/inet_addr/htons/ntohs live in <winsock2.h>; inet_ntop/inet_pton
 * in <ws2tcpip.h>. mingw ships no <arpa/inet.h>, so this is the only header
 * by that name on the include path. Inert off-Windows.
 */
#ifndef WINCOMPAT_ARPA_INET_H
#define WINCOMPAT_ARPA_INET_H

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

#endif /* WINCOMPAT_ARPA_INET_H */
