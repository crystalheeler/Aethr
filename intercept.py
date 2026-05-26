#!/usr/bin/env python3
"""
INTERCEPT - Signal Intelligence Platform

A comprehensive signal intelligence tool featuring:
- Pager decoding (POCSAG/FLEX)
- 433MHz sensor monitoring
- ADS-B aircraft tracking with WarGames-style display
- Satellite pass prediction
- WiFi reconnaissance and drone detection
- Bluetooth scanning

Requires RTL-SDR hardware for RF modes.
"""

import sys

# Force UTF-8 on stdout/stderr on Windows so emoji/box-drawing in startup
# banners don't crash with UnicodeEncodeError on cp1252 consoles.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# When this exe is built with PyInstaller --windowed (no console attached to
# the parent), every child console-mode process (rtl_sdr.exe, rtl_test.exe,
# multimon-ng, dump1090, etc.) gets a fresh OS-allocated console window —
# the black box that flashes briefly each time we probe the SDR. Fix it
# globally by monkey-patching subprocess.Popen to set CREATE_NO_WINDOW.
#
# Only applied when frozen on Windows. Dev runs from a terminal already have
# a console, and developers may want to see subprocess output there.
if sys.platform == "win32" and getattr(sys, "frozen", False):
    import subprocess as _subprocess
    if not getattr(_subprocess.Popen, "_intercept_no_window_patched", False):
        _CREATE_NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW since 3.7
        _orig_popen_init = _subprocess.Popen.__init__

        def _patched_popen_init(self, *args, **kwargs):
            kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | _CREATE_NO_WINDOW
            _orig_popen_init(self, *args, **kwargs)

        _subprocess.Popen.__init__ = _patched_popen_init  # type: ignore[method-assign]
        _subprocess.Popen._intercept_no_window_patched = True  # type: ignore[attr-defined]

# Check Python version early, before imports that use 3.9+ syntax

# Handle --version early before other imports
if '--version' in sys.argv or '-V' in sys.argv:
    from config import VERSION
    print(f"INTERCEPT v{VERSION}")
    sys.exit(0)

import os
import site

# Ensure user site-packages is available (may be disabled when running as root/sudo)
if not site.ENABLE_USER_SITE:
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.insert(0, user_site)


def _use_windows_tray_runtime() -> bool:
    """Use the tray-icon runtime when launched as a frozen Windows exe.

    Bypass conditions (keep the dev-server path):
      --no-tray flag passed explicitly (debugging from a terminal)
      --check-deps / --help / dev-server-only flags
      INTERCEPT_NO_TRAY=1 env var
    """
    if sys.platform != "win32":
        return False
    if not getattr(sys, "frozen", False):
        return False
    if os.environ.get("INTERCEPT_NO_TRAY", "").lower() in ("1", "true", "yes"):
        return False
    if "--no-tray" in sys.argv or "--check-deps" in sys.argv:
        return False
    return True


if __name__ == '__main__':
    if _use_windows_tray_runtime():
        from windows_runtime import run as _win_run
        sys.exit(_win_run())

    from app import main
    main()
