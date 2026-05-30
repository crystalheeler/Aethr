INTERCEPT bundles MalcolmRobb/dump1090's win32 binary release
(dump1090-win.1.10.3010.14.zip, October 2014) alongside its 4 required DLLs.

License: BSD 2-Clause (see LICENSE-dump1090.txt; original antirez copyright
preserved in source).

The binary is i386 (32-bit), so it lives in its own subdirectory with its
matching 32-bit DLLs (libusb-1.0.dll, rtlsdr.dll, pthreadVC2.dll, msvcr100.dll).
Windows loads DLLs from the spawned exe's own directory first, so this is
isolated from the 64-bit RTL-SDR Blog DLLs in the parent tools/windows/ dir.

Why not the gvanem fork? Tried it first — it required a config file, a
home-position setup wizard, and a 19 MB auto-downloaded aircraft database.
MalcolmRobb is the original Salvatore Sanfilippo lineage with the standard
CLI (--device-index, --quiet, --gain) and zero config baggage.
