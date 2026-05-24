"""Cross-platform helpers for OS detection and process management.

INTERCEPT historically targeted Linux. This module centralizes the
Windows/macOS abstractions so the rest of the codebase doesn't have to
sprinkle ``hasattr(os, "geteuid")`` checks everywhere.
"""

from __future__ import annotations

import contextlib
import logging
import platform as _platform
import subprocess
import sys
from typing import Iterable

logger = logging.getLogger("intercept.platform")

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"


def is_admin() -> bool:
    """Return True if the current process has elevated privileges.

    Unix: euid == 0. Windows: shell32.IsUserAnAdmin().
    """
    import os

    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def terminate_process_tree(pid: int, timeout: float = 2.0) -> None:
    """Cross-platform: terminate a process and all its children.

    On Linux this used to be ``os.killpg(os.getpgid(pid), SIGTERM)``.
    psutil's process-tree walk gives us the same semantics on Windows.
    """
    try:
        import psutil
    except ImportError:
        logger.debug("psutil unavailable; cannot perform tree termination for pid=%s", pid)
        return

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    try:
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []

    for proc in (*children, parent):
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            proc.terminate()

    _, alive = psutil.wait_procs([parent, *children], timeout=timeout)
    for proc in alive:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            proc.kill()


def kill_processes_by_name(names: Iterable[str]) -> list[str]:
    """Cross-platform replacement for ``pkill -f <name>``.

    Matches the substring against both the process name and the full
    command line, so it catches ``rtl_fm`` invoked as
    ``/usr/local/bin/rtl_fm`` as well as a Windows ``rtl_fm.exe``.

    Returns the list of process names that matched and were killed.
    """
    try:
        import psutil
    except ImportError:
        return _pkill_fallback(names)

    name_list = list(names)
    killed: list[str] = []

    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            info = proc.info
            proc_name = info.get("name") or ""
            cmdline = " ".join(info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        for target in name_list:
            if target in proc_name or target in cmdline:
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    proc.kill()
                    killed.append(target)
                break

    return killed


def _pkill_fallback(names: Iterable[str]) -> list[str]:
    """Fall back to ``pkill -f`` when psutil isn't available.

    Should never run in practice — psutil is a hard requirement of the
    app — but kept as a safety net.
    """
    if IS_WINDOWS:
        # No pkill on Windows; we have no fallback path here.
        return []

    killed: list[str] = []
    for name in names:
        with contextlib.suppress(subprocess.SubprocessError, OSError):
            result = subprocess.run(["pkill", "-f", name], capture_output=True)
            if result.returncode == 0:
                killed.append(name)
    return killed


def system_summary() -> str:
    """Short human-readable platform string for diagnostics/logs."""
    return f"{_platform.system()} {_platform.release()} ({sys.platform})"


def windows_not_supported_response(mode: str, reason: str) -> tuple:
    """Standard 503 JSON for endpoints that can't function on Windows.

    Args:
        mode: User-facing mode name (e.g., ``"WiFi monitor mode"``).
        reason: Short technical reason shown in the message.

    Returns:
        ``(json_dict, status_code)`` tuple ready to hand to Flask. Callers
        wrap it with ``jsonify(...)`` themselves to avoid pulling Flask into
        this leaf module.
    """
    return (
        {
            "status": "error",
            "error_type": "PLATFORM_UNSUPPORTED",
            "platform": "windows",
            "mode": mode,
            "message": (
                f"{mode} is not available on Windows. {reason} "
                "Run INTERCEPT on Linux (or via Docker) for this feature."
            ),
        },
        503,
    )
