from __future__ import annotations

import atexit
import contextlib
import logging
import os
import platform
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .dependencies import check_tool
from .platform import IS_WINDOWS, kill_processes_by_name, terminate_process_tree

try:
    import pty as _pty
except ImportError:  # Windows: pty requires termios, which doesn't exist there
    _pty = None  # type: ignore[assignment]

logger = logging.getLogger('intercept.process')

# Track all spawned processes for cleanup
_spawned_processes: list[subprocess.Popen] = []
_process_lock = threading.Lock()


def spawn_line_buffered_decoder(
    cmd: list[str],
    *,
    stdin: Any,
    close_fds: bool = True,
    start_new_session: bool = False,
) -> tuple[subprocess.Popen, Any]:
    """Spawn a decoder whose combined stdout+stderr we read line by line.

    Sparse decoders (multimon-ng, direwolf) line-buffer their stdout only when
    it's a TTY; against a plain pipe their libc full-buffers (~4-8 KB), which
    delays low-rate output (a single APRS/pager line) for minutes.

    POSIX: route stdout+stderr through a pty so the child sees a TTY and
    line-buffers. Returns ``(process, master_fd)`` where master_fd is an int.

    Windows: pty doesn't exist; combine stdout+stderr into one pipe. Returns
    ``(process, process.stdout)``. (Buffering then depends on the decoder;
    direwolf flushes per frame, so APRS is fine.)

    Pair the returned source with :func:`read_decoder_lines`.
    """
    if _pty is not None:
        master_fd, slave_fd = _pty.openpty()
        popen_kwargs: dict[str, Any] = dict(
            stdin=stdin, stdout=slave_fd, stderr=slave_fd, close_fds=close_fds
        )
        if start_new_session:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(cmd, **popen_kwargs)
        os.close(slave_fd)  # child owns the slave end now
        return process, master_fd

    # Windows: no pty — combined stdout/stderr pipe, unbuffered on our side.
    process = subprocess.Popen(
        cmd,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        close_fds=close_fds,
    )
    return process, process.stdout


def read_decoder_lines(source: Any, process: subprocess.Popen | None = None, timeout: float = 1.0):
    """Yield decoded, stripped, non-empty text lines from a decoder's output.

    ``source`` is whatever :func:`spawn_line_buffered_decoder` returned:

      * an int — a POSIX pty master fd, polled with ``select()`` + ``os.read()``
        (matches the long-standing pager/APRS behavior); or
      * a binary file object — e.g. ``process.stdout`` on Windows, drained with
        blocking ``readline()`` (``select()`` doesn't work on Windows pipes).

    Stops at EOF, or — on POSIX — once ``process`` has exited.
    """
    if isinstance(source, int):
        import select

        buffer = ""
        while True:
            try:
                ready, _, _ = select.select([source], [], [], timeout)
            except Exception:
                break
            if ready:
                try:
                    data = os.read(source, 1024)
                except OSError:
                    break
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        yield line
            if process is not None and process.poll() is not None:
                break
        return

    # Windows pipe: blocking readline; returns b'' (EOF) when the child exits.
    while True:
        try:
            raw = source.readline()
        except (OSError, ValueError):
            break
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else raw
        line = line.strip()
        if line:
            yield line


def close_decoder_source(source: Any) -> None:
    """Close the source returned by :func:`spawn_line_buffered_decoder`."""
    with contextlib.suppress(Exception):
        if isinstance(source, int):
            os.close(source)
        elif source is not None:
            source.close()


def register_process(process: subprocess.Popen) -> None:
    """Register a spawned process for cleanup on exit."""
    with _process_lock:
        _spawned_processes.append(process)


def unregister_process(process: subprocess.Popen) -> None:
    """Unregister a process from cleanup list."""
    with _process_lock:
        if process in _spawned_processes:
            _spawned_processes.remove(process)


def close_process_pipes(process: subprocess.Popen) -> None:
    """Close stdin/stdout/stderr pipes on a subprocess to free file descriptors."""
    for pipe in (process.stdin, process.stdout, process.stderr):
        if pipe:
            with contextlib.suppress(OSError):
                pipe.close()


def cleanup_all_processes() -> None:
    """Clean up all registered processes and flush DataStores on exit."""
    logger.info("Cleaning up all spawned processes...")
    with _process_lock:
        for process in _spawned_processes:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    logger.warning(f"Error cleaning up process: {e}")
            close_process_pipes(process)
        _spawned_processes.clear()

    # Stop DataStore cleanup timers and run final cleanup
    try:
        from utils.cleanup import cleanup_manager
        cleanup_manager.cleanup_now()
        cleanup_manager.stop()
    except Exception as e:
        logger.warning(f"Error during DataStore cleanup: {e}")


def safe_terminate(process: subprocess.Popen | None, timeout: float = 2.0) -> bool:
    """
    Safely terminate a process.

    Args:
        process: Process to terminate
        timeout: Seconds to wait before killing

    Returns:
        True if process was terminated, False if already dead or None
    """
    if not process:
        return False

    if process.poll() is not None:
        # Already dead
        close_process_pipes(process)
        unregister_process(process)
        return False

    try:
        process.terminate()
        process.wait(timeout=timeout)
        close_process_pipes(process)
        unregister_process(process)
        return True
    except subprocess.TimeoutExpired:
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=3)
        close_process_pipes(process)
        unregister_process(process)
        return True
    except Exception as e:
        logger.warning(f"Error terminating process: {e}")
        close_process_pipes(process)
        return False


# Register cleanup handlers
atexit.register(cleanup_all_processes)

# Handle signals for graceful shutdown
def _signal_handler(signum, frame):
    """Handle termination signals.

    Keep this minimal — logging and lock acquisition in signal handlers
    can deadlock when another thread holds the logging or process lock.
    Process cleanup is handled by the atexit handler registered above.
    """
    import sys
    if signum == signal.SIGINT:
        raise KeyboardInterrupt()
    sys.exit(0)


# Only register signal handlers when running standalone (not under gunicorn).
# Gunicorn manages its own SIGINT/SIGTERM handling for graceful shutdown;
# overriding those signals causes KeyboardInterrupt in the wrong context.
def _is_under_gunicorn():
    """Check if we're running inside a gunicorn worker."""
    try:
        import gunicorn.arbiter  # noqa: F401
        # If gunicorn is importable AND we were invoked via gunicorn, the
        # arbiter will have installed its own signal handlers already.
        # Check the current SIGTERM handler — if it's not the default,
        # gunicorn (or another manager) owns signals.
        current = signal.getsignal(signal.SIGTERM)
        return current not in (signal.SIG_DFL, signal.SIG_IGN, None)
    except ImportError:
        return False

if not _is_under_gunicorn():
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
    except ValueError:
        # Can't set signal handlers from a thread
        pass


def cleanup_stale_processes() -> None:
    """Kill any stale processes from previous runs (but not system services)."""
    # Note: dump1090 is NOT included here as users may run it as a system service
    processes_to_kill = ['rtl_adsb', 'rtl_433', 'multimon-ng', 'rtl_fm']
    kill_processes_by_name(processes_to_kill)


_DUMP1090_PID_FILE = Path(__file__).resolve().parent.parent / 'instance' / 'dump1090.pid'


def write_dump1090_pid(pid: int) -> None:
    """Write the PID of an app-spawned dump1090 process to a PID file."""
    try:
        _DUMP1090_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DUMP1090_PID_FILE.write_text(str(pid))
        logger.debug(f"Wrote dump1090 PID file: {pid}")
    except OSError as e:
        logger.warning(f"Failed to write dump1090 PID file: {e}")


def clear_dump1090_pid() -> None:
    """Remove the dump1090 PID file."""
    try:
        _DUMP1090_PID_FILE.unlink(missing_ok=True)
        logger.debug("Cleared dump1090 PID file")
    except OSError as e:
        logger.warning(f"Failed to clear dump1090 PID file: {e}")


def _is_dump1090_process(pid: int) -> bool:
    """Check if the given PID is actually a dump1090/readsb process."""
    try:
        import psutil

        proc = psutil.Process(pid)
        name = proc.name() or ''
        cmdline = ' '.join(proc.cmdline() or [])
        haystack = (name + ' ' + cmdline).lower()
        return 'dump1090' in haystack or 'readsb' in haystack
    except Exception:
        return False


def cleanup_stale_dump1090() -> None:
    """Kill a stale app-spawned dump1090 using the PID file.

    Safe no-op if no PID file exists, process is dead, or PID was reused
    by another program.
    """
    if not _DUMP1090_PID_FILE.exists():
        return

    try:
        pid = int(_DUMP1090_PID_FILE.read_text().strip())
    except (ValueError, OSError) as e:
        logger.warning(f"Invalid dump1090 PID file: {e}")
        clear_dump1090_pid()
        return

    # Verify this PID is still a dump1090/readsb process
    if not _is_dump1090_process(pid):
        logger.debug(f"PID {pid} is not dump1090/readsb (dead or reused), removing stale PID file")
        clear_dump1090_pid()
        return

    # Terminate the process tree (children inclusive)
    logger.info(f"Killing stale app-spawned dump1090 (PID {pid})")
    terminate_process_tree(pid, timeout=2.0)

    clear_dump1090_pid()


def is_valid_mac(mac: str | None) -> bool:
    """Validate MAC address format."""
    if not mac:
        return False
    return bool(re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', mac))


def is_valid_channel(channel: str | int | None) -> bool:
    """Validate WiFi channel number."""
    try:
        ch = int(channel)  # type: ignore[arg-type]
        return 1 <= ch <= 200
    except (ValueError, TypeError):
        return False


def detect_devices() -> list[dict[str, Any]]:
    """Detect RTL-SDR devices."""
    devices: list[dict[str, Any]] = []

    if not check_tool('rtl_test'):
        return devices

    try:
        result = subprocess.run(
            ['rtl_test', '-t'],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stderr + result.stdout

        # Parse device info
        device_pattern = r'(\d+):\s+(.+?)(?:,\s*SN:\s*(\S+))?$'

        for line in output.split('\n'):
            line = line.strip()
            match = re.match(device_pattern, line)
            if match:
                devices.append({
                    'index': int(match.group(1)),
                    'name': match.group(2).strip().rstrip(','),
                    'serial': match.group(3) or 'N/A'
                })

        if not devices:
            found_match = re.search(r'Found (\d+) device', output)
            if found_match:
                count = int(found_match.group(1))
                for i in range(count):
                    devices.append({
                        'index': i,
                        'name': f'RTL-SDR Device {i}',
                        'serial': 'Unknown'
                    })

    except Exception:
        pass

    return devices
