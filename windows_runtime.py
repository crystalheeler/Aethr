"""Windows runtime launcher for INTERCEPT.

When intercept.exe is launched on Windows (PyInstaller, --windowed), it
runs this module instead of going through ``app.main()``. The runtime:

1. Initializes the Flask app via importing ``app``.
2. Spawns a Werkzeug ``make_server`` in a daemon thread. We use Werkzeug
   (not waitress) because waitress doesn't expose the raw socket that
   ``flask_sock`` / ``simple_websocket`` need to perform the WebSocket
   upgrade. WebSocket-heavy modes (Waterfall, audio, KiwiSDR, ground
   station) all break under waitress.
3. Opens a system-tray icon via ``pystray`` on the main thread. The menu:
     - "Open Dashboard" → launches the user's default browser
     - "Quit"           → shuts down the server + cleans up subprocesses

This is what fixes the three Windows-specific complaints:
- No console window (PyInstaller --windowed + this is the entry point)
- Ctrl+C never worked → you Quit from the tray menu instead
- Choppy audio under load is addressed separately by the audio-queue
  backpressure fix in routes/waterfall_websocket.py (skips Python numpy
  demod work when the audio sink can't keep up)

Linux/macOS users never hit this path — start.sh keeps using gunicorn
+ gevent and intercept.py runs app.main() directly.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

LOG_DIR_NAME = "INTERCEPT"


def _setup_logging() -> Path:
    """Send logs to %LOCALAPPDATA%\\INTERCEPT\\logs\\intercept.log.

    No console means stdout/stderr are unwritable (PyInstaller --windowed
    binds them to NUL). Route Python logging to a file so the user can
    actually debug crashes.
    """
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    log_dir = Path(base) / LOG_DIR_NAME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "intercept.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    # If another handler exists (e.g. werkzeug default), keep it — file handler
    # is additional. Set level conservatively so logs don't fill the disk.
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    return log_path


def _make_tray_icon(open_url: str, on_quit) -> "pystray.Icon":  # noqa: F821
    """Build the system-tray icon + menu. Returns an unstarted pystray.Icon."""
    import pystray
    from PIL import Image, ImageDraw

    # No bundled .ico yet — draw a tiny cyan-on-black "I" so the user has
    # something visible in the tray. Easy to replace later with a real icon.
    image = Image.new("RGB", (64, 64), color=(10, 10, 14))
    draw = ImageDraw.Draw(image)
    draw.rectangle((26, 12, 38, 52), fill=(0, 200, 220))
    draw.rectangle((18, 8, 46, 16), fill=(0, 200, 220))
    draw.rectangle((18, 48, 46, 56), fill=(0, 200, 220))

    def _open(_icon, _item):
        webbrowser.open(open_url)

    def _quit(icon, _item):
        try:
            on_quit()
        finally:
            icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", _open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit),
    )
    return pystray.Icon("INTERCEPT", image, "INTERCEPT — Signal Intelligence", menu)


def run() -> int:
    """Entry point — returns a process exit code."""
    log_path = _setup_logging()
    logger = logging.getLogger("intercept.windows_runtime")
    logger.info("Windows runtime starting. Logs: %s", log_path)

    # Importing app initializes Flask, registers blueprints, etc.
    import app as _app
    import config

    host = "127.0.0.1"  # tray icon implies single-user local — bind tight
    port = int(config.PORT)
    open_url = f"http://{host}:{port}/"

    # Werkzeug make_server gives us a server object with a clean .shutdown()
    # method — Flask's app.run() doesn't expose that. Use threaded mode for
    # concurrent SSE / WebSocket / regular request handling.
    from werkzeug.serving import make_server

    server = make_server(host, port, _app.app, threaded=True)

    def _serve():
        try:
            server.serve_forever()
        except Exception:
            logger.exception("Werkzeug server crashed")

    server_thread = threading.Thread(target=_serve, name="werkzeug-serve", daemon=True)
    server_thread.start()
    logger.info("Werkzeug serving on %s (threaded)", open_url)

    # Auto-open the dashboard on first launch — most users expect this.
    try:
        webbrowser.open(open_url)
    except Exception:
        logger.warning("Could not auto-open browser", exc_info=True)

    def _on_quit():
        logger.info("Quit requested via tray menu — stopping HTTP server")
        try:
            server.shutdown()
        except Exception:
            logger.exception("Error shutting down HTTP server")
        # Kill any leftover subprocess children (rtl_fm, dump1090, etc.)
        try:
            from utils.process import cleanup_all_processes

            cleanup_all_processes()
        except Exception:
            logger.exception("Error cleaning up child processes")

    icon = _make_tray_icon(open_url, _on_quit)
    logger.info("Showing tray icon — close via right-click → Quit")
    icon.run()  # blocks until icon.stop() is called by _quit
    logger.info("Tray icon exited, runtime done")
    return 0


if __name__ == "__main__":
    sys.exit(run())
