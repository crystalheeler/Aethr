"""RTLAMR utility meter monitoring routes."""

from __future__ import annotations

import contextlib
import json
import queue
import re
import socket
import subprocess
import threading
import time
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

import app as app_module
from utils.dependencies import get_tool_path
from utils.event_pipeline import process_event
from utils.logging import sensor_logger as logger
from utils.process import register_process, unregister_process
from utils.responses import api_error
from utils.sse import sse_stream_fanout
from utils.validation import validate_device_index, validate_frequency, validate_gain, validate_ppm

rtlamr_bp = Blueprint('rtlamr', __name__)

# Store rtl_tcp process separately
rtl_tcp_process = None
rtl_tcp_lock = threading.Lock()

# Track which device is being used
rtlamr_active_device: int | None = None
rtlamr_active_sdr_type: str = 'rtlsdr'


def _wait_for_rtl_tcp(host: str = '127.0.0.1', port: int = 1234,
                      timeout: float = 30.0, interval: float = 0.25) -> bool:
    """Poll a TCP port until rtl_tcp is accepting connections.

    Replaces an unreliable ``time.sleep(3)`` warm-up. On a cold first launch
    the Windows Firewall prompt for rtl_tcp can hold the bind back for more
    than 3s, and rtlamr then fails its single connect attempt with
    "connectex: No connection could be made because the target machine
    actively refused it" and exits immediately.

    Returns True when the port accepts a TCP connection, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(interval)
    return False


# rtlamr's stderr is structured Go slog text:
#   time=... level=ERROR source=rtlamr\main.go:92 msg="..." error="..."
_RTLAMR_LEVEL_RE = re.compile(r'\blevel=(\w+)')
_RTLAMR_MSG_RE = re.compile(r'\bmsg="([^"]*)"')
_RTLAMR_ERROR_FIELD_RE = re.compile(r'\berror="((?:[^"\\]|\\.)*)"')

# rtlamr labels some chatter as level=ERROR even when it isn't an actionable
# problem. "not keeping up with rtl_tcp" is a known-noisy warning on slower
# CPUs that fires repeatedly without anything the user can act on.
_RTLAMR_NOISE_MSGS = (
    'not keeping up',
)


def _classify_rtlamr_stderr(line: str) -> tuple[str | None, str | None]:
    """Decide whether an rtlamr stderr line should reach the UI.

    Returns ``(event_type, text)`` to push as an SSE message, or
    ``(None, None)`` to suppress (the line is still logged to debug).
    Surfaces real errors as ``type: 'error'`` instead of the misleading
    ``type: 'info'`` (blue toast) that the original code used for every
    line — actual errors deserve red, and most rtlamr stderr lines are
    not user-facing in the first place.
    """
    msg_m = _RTLAMR_MSG_RE.search(line)
    msg = msg_m.group(1) if msg_m else line

    # Noise — known-harmless chatter, debug-log only.
    for needle in _RTLAMR_NOISE_MSGS:
        if needle in msg:
            return None, None

    level_m = _RTLAMR_LEVEL_RE.search(line)
    level = (level_m.group(1) if level_m else 'INFO').upper()

    if level in ('ERROR', 'WARN', 'FATAL'):
        err_m = _RTLAMR_ERROR_FIELD_RE.search(line)
        if err_m:
            # Show just the first line of multiline error= (rtlamr embeds
            # a full Go stack trace via escaped \n; truncating keeps the
            # toast readable).
            err_text = err_m.group(1).split('\\n')[0]
            return 'error', f'{msg}: {err_text}'
        return 'error', msg

    # INFO / DEBUG — log only, don't surface to UI.
    return None, None


def stream_rtlamr_output(process: subprocess.Popen[bytes]) -> None:
    """Stream rtlamr JSON output to queue."""
    try:
        app_module.rtlamr_queue.put({'type': 'status', 'text': 'started'})

        for line in iter(process.stdout.readline, b''):
            line = line.decode('utf-8', errors='replace').strip()
            if not line:
                continue

            try:
                # rtlamr outputs JSON objects, one per line
                data = json.loads(line)
                data['type'] = 'rtlamr'
                app_module.rtlamr_queue.put(data)

                # Log if enabled
                if app_module.logging_enabled:
                    try:
                        with open(app_module.log_file_path, 'a') as f:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"{timestamp} | RTLAMR | {json.dumps(data)}\n")
                    except Exception:
                        pass
            except json.JSONDecodeError:
                # Not JSON, send as raw
                app_module.rtlamr_queue.put({'type': 'raw', 'text': line})

    except Exception as e:
        app_module.rtlamr_queue.put({'type': 'error', 'text': str(e)})
    finally:
        global rtl_tcp_process, rtlamr_active_device, rtlamr_active_sdr_type
        # Ensure rtlamr process is terminated
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            with contextlib.suppress(Exception):
                process.kill()
        unregister_process(process)
        # Kill companion rtl_tcp process
        with rtl_tcp_lock:
            if rtl_tcp_process:
                try:
                    rtl_tcp_process.terminate()
                    rtl_tcp_process.wait(timeout=2)
                except Exception:
                    with contextlib.suppress(Exception):
                        rtl_tcp_process.kill()
                unregister_process(rtl_tcp_process)
                rtl_tcp_process = None
        app_module.rtlamr_queue.put({'type': 'status', 'text': 'stopped'})
        with app_module.rtlamr_lock:
            app_module.rtlamr_process = None
        # Release SDR device
        if rtlamr_active_device is not None:
            app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
            rtlamr_active_device = None


@rtlamr_bp.route('/start_rtlamr', methods=['POST'])
def start_rtlamr() -> Response:
    global rtl_tcp_process, rtlamr_active_device, rtlamr_active_sdr_type

    with app_module.rtlamr_lock:
        if app_module.rtlamr_process:
            return api_error('RTLAMR already running', 409)

        data = request.json or {}
        sdr_type_str = data.get('sdr_type', 'rtlsdr')

        if sdr_type_str != 'rtlsdr':
            return api_error(f'{sdr_type_str.replace("_", " ").title()} is not yet supported for this mode. Please use an RTL-SDR device.', 400)

        # Validate inputs
        try:
            freq = validate_frequency(data.get('frequency', '912.0'))
            gain = validate_gain(data.get('gain', '0'))
            ppm = validate_ppm(data.get('ppm', '0'))
            device = validate_device_index(data.get('device', '0'))
        except ValueError as e:
            return api_error(str(e), 400)

        # Check if device is available
        device_int = int(device)
        error = app_module.claim_sdr_device(device_int, 'rtlamr', sdr_type_str)
        if error:
            return api_error(error, 409, error_type='DEVICE_BUSY')

        rtlamr_active_device = device_int
        rtlamr_active_sdr_type = sdr_type_str

        # Clear queue
        while not app_module.rtlamr_queue.empty():
            try:
                app_module.rtlamr_queue.get_nowait()
            except queue.Empty:
                break

        # Get message type (default to scm)
        msgtype = data.get('msgtype', 'scm')
        output_format = data.get('format', 'json')

        # Resolve binary paths up front so we can surface a clean error
        # (instead of a bare FileNotFoundError) when a tool is missing on
        # this platform. On Windows the bundled tools/windows/ binaries
        # are preferred over PATH; on Linux/macOS PATH lookup wins.
        rtl_tcp_path = get_tool_path('rtl_tcp')
        if rtl_tcp_path is None:
            if rtlamr_active_device is not None:
                app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
                rtlamr_active_device = None
            return api_error(
                'rtl_tcp not found. On Windows it should ship with intercept.exe; '
                'on Linux install librtlsdr-dev / rtl-sdr.'
            )

        rtlamr_path = get_tool_path('rtlamr')
        if rtlamr_path is None:
            if rtlamr_active_device is not None:
                app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
                rtlamr_active_device = None
            return api_error(
                'rtlamr not found. On Windows it should ship with intercept.exe; '
                'on Linux install from https://github.com/bemasher/rtlamr'
            )

        # Start rtl_tcp first
        rtl_tcp_just_started = False
        rtl_tcp_cmd_str = ''
        with rtl_tcp_lock:
            if not rtl_tcp_process:
                logger.info("Starting rtl_tcp server...")
                try:
                    rtl_tcp_cmd = [rtl_tcp_path, '-a', '0.0.0.0']

                    # Add device index if not 0
                    if device and device != '0':
                        rtl_tcp_cmd.extend(['-d', str(device)])

                    # Add gain if not auto
                    if gain and gain != '0':
                        rtl_tcp_cmd.extend(['-g', str(gain)])

                    # Add PPM correction if not 0
                    if ppm and ppm != '0':
                        rtl_tcp_cmd.extend(['-p', str(ppm)])

                    rtl_tcp_process = subprocess.Popen(
                        rtl_tcp_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    register_process(rtl_tcp_process)
                    rtl_tcp_just_started = True
                    rtl_tcp_cmd_str = ' '.join(rtl_tcp_cmd)
                except Exception as e:
                    logger.error(f"Failed to start rtl_tcp: {e}")
                    # Release SDR device on rtl_tcp failure
                    if rtlamr_active_device is not None:
                        app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
                        rtlamr_active_device = None
                    return api_error(f'Failed to start rtl_tcp: {e}', 500)

        # Wait for rtl_tcp to actually be listening on 127.0.0.1:1234.
        # On a cold first launch the Windows Firewall prompt can hold the
        # bind back for more than the old fixed sleep(3); rtlamr makes a
        # single connect attempt at startup and dies on refusal, so we
        # have to KNOW the port is up before spawning it.
        if rtl_tcp_just_started:
            if not _wait_for_rtl_tcp():
                with rtl_tcp_lock:
                    if rtl_tcp_process:
                        with contextlib.suppress(Exception):
                            rtl_tcp_process.terminate()
                            rtl_tcp_process.wait(timeout=2)
                        unregister_process(rtl_tcp_process)
                        rtl_tcp_process = None
                if rtlamr_active_device is not None:
                    app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
                    rtlamr_active_device = None
                return api_error(
                    'rtl_tcp did not start listening on 127.0.0.1:1234 within 30s. '
                    'If Windows Firewall just prompted you, allow access and try '
                    'Start again. Otherwise check that an RTL-SDR dongle is connected '
                    'and not in use by another mode.',
                    500,
                )
            logger.info(f"rtl_tcp listening on 127.0.0.1:1234 ({rtl_tcp_cmd_str})")
            # NB: not pushing "rtl_tcp: ..." to UI — same rationale as the
            # "Command: ..." cleanup in -d. Developer context, surfaces as a
            # persistent info-style toast that reads like a notification.

        # Build rtlamr command (path resolved up front via get_tool_path)
        cmd = [
            rtlamr_path,
            '-server=127.0.0.1:1234',
            f'-msgtype={msgtype}',
            f'-format={output_format}',
            f'-centerfreq={int(float(freq) * 1e6)}'
        ]

        # Add filter options if provided
        filterid = data.get('filterid')
        if filterid:
            cmd.append(f'-filterid={filterid}')

        filtertype = data.get('filtertype')
        if filtertype:
            cmd.append(f'-filtertype={filtertype}')

        # Unique messages only
        if data.get('unique', True):
            cmd.append('-unique=true')

        full_cmd = ' '.join(cmd)
        logger.info(f"Running: {full_cmd}")

        try:
            app_module.rtlamr_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            register_process(app_module.rtlamr_process)

            # Start output thread
            thread = threading.Thread(target=stream_rtlamr_output, args=(app_module.rtlamr_process,))
            thread.daemon = True
            thread.start()

            # Monitor stderr — rtlamr is chatty on stderr (status, debug, all
            # mixed in). The previous "every line as info toast" approach
            # buried real errors in noise; classify each line and surface
            # only actionable problems, with the correct severity.
            def monitor_stderr():
                for line in app_module.rtlamr_process.stderr:
                    err = line.decode('utf-8', errors='replace').strip()
                    if not err:
                        continue
                    logger.debug(f"[rtlamr] {err}")
                    event_type, text = _classify_rtlamr_stderr(err)
                    if event_type:
                        app_module.rtlamr_queue.put({'type': event_type, 'text': text})

            stderr_thread = threading.Thread(target=monitor_stderr)
            stderr_thread.daemon = True
            stderr_thread.start()

            # NB: not pushing "Command: ..." to the UI here — same rationale
            # as routes/sensor.py (developer context, reads like a notification
            # but conveys nothing actionable to an end user). It's already
            # logged above and returned in the JSON response for debugging.
            logger.debug(f"Started rtlamr: {full_cmd}")

            return jsonify({'status': 'started', 'command': full_cmd})

        # FileNotFoundError can no longer happen here — rtlamr_path is
        # validated via get_tool_path() above before we get this far.
        except Exception as e:
            # If rtlamr fails, clean up rtl_tcp and release device
            with rtl_tcp_lock:
                if rtl_tcp_process:
                    rtl_tcp_process.terminate()
                    rtl_tcp_process.wait(timeout=2)
                    rtl_tcp_process = None
            if rtlamr_active_device is not None:
                app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
                rtlamr_active_device = None
            return api_error(str(e))


@rtlamr_bp.route('/stop_rtlamr', methods=['POST'])
def stop_rtlamr() -> Response:
    global rtl_tcp_process, rtlamr_active_device, rtlamr_active_sdr_type

    # Grab process refs inside locks, clear state, then terminate outside
    rtlamr_proc = None
    with app_module.rtlamr_lock:
        if app_module.rtlamr_process:
            rtlamr_proc = app_module.rtlamr_process
            app_module.rtlamr_process = None

    if rtlamr_proc:
        rtlamr_proc.terminate()
        try:
            rtlamr_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            rtlamr_proc.kill()

    # Also stop rtl_tcp
    tcp_proc = None
    with rtl_tcp_lock:
        if rtl_tcp_process:
            tcp_proc = rtl_tcp_process
            rtl_tcp_process = None

    if tcp_proc:
        tcp_proc.terminate()
        try:
            tcp_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            tcp_proc.kill()
        logger.info("rtl_tcp stopped")

    # Release device from registry
    if rtlamr_active_device is not None:
        app_module.release_sdr_device(rtlamr_active_device, rtlamr_active_sdr_type)
        rtlamr_active_device = None

    return jsonify({'status': 'stopped'})


@rtlamr_bp.route('/stream_rtlamr')
def stream_rtlamr() -> Response:
    def _on_msg(msg: dict[str, Any]) -> None:
        process_event('rtlamr', msg, msg.get('type'))

    response = Response(
        sse_stream_fanout(
            source_queue=app_module.rtlamr_queue,
            channel_key='rtlamr',
            timeout=1.0,
            keepalive_interval=30.0,
            on_message=_on_msg,
        ),
        mimetype='text/event-stream',
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response
