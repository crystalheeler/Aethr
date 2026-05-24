# INTERCEPT on Windows

The Windows build is a single-file `intercept.exe` (~140 MB) with the Python
runtime, Flask app, and a curated set of SDR tools bundled inside. No Python
install required.

> **Linux/macOS is still the primary target.** A few modes can't work on
> Windows at all — see [What works on Windows](#what-works-on-windows) below.

## Install

1. Download `intercept.exe` from the latest [Releases page](https://github.com/themuseum1960/intercept-test/releases).
2. Put it anywhere — Desktop, Downloads, a dedicated folder. No installer.
3. Plug in your RTL-SDR dongle.
4. Install the WinUSB driver via **Zadig** (one-time, required — see below).
5. Double-click `intercept.exe`.

A console window opens, the Flask server starts, then point your browser at
<http://localhost:5050>. Default login is `admin` / `admin` (change it in
Settings).

## Zadig — install the WinUSB driver

Out of the box Windows binds your RTL-SDR dongle to the DVB-T TV driver, which
prevents `rtl_fm` / `dump1090` / SatDump from talking to it. You swap the driver
for WinUSB **once**, then every SDR app works.

1. Download Zadig from <https://zadig.akeo.ie/>.
2. Plug in the RTL-SDR. Run `zadig.exe` (as Administrator if prompted).
3. **Options → List All Devices** (this is the easy-to-miss step).
4. In the dropdown, select **"Bulk-In, Interface (Interface 0)"** — that's your dongle.
   Verify USB ID reads `0BDA 2838` (the RTL2832U vendor/product ID).
5. To the right of the green arrow, pick **WinUSB**.
6. Click **Replace Driver**. Wait ~30 seconds.
7. Unplug and replug the dongle.

Verify: open `intercept.exe`, go to Settings → Devices. You should see your
RTL-SDR listed. If not, see [Troubleshooting](#troubleshooting).

## First launch

The first launch may take longer than later ones — Windows scans the ~140 MB
exe with Defender, and PyInstaller unpacks the bundled runtime to a temp
directory each launch.

Windows Firewall will prompt for network access on first launch. INTERCEPT
serves locally on port 5050 — **Private networks** is enough. **Public
networks** is fine to leave unchecked.

## What works on Windows

| Mode | Status | Notes |
|---|---|---|
| **Pager (POCSAG/FLEX)** | ❌ Not available | multimon-ng has no Windows binary |
| **433 MHz sensors** | ✅ Works | bundled `rtl_433.exe` |
| **ADS-B aircraft** | ⚠️ Limited | `dump1090` not bundled; works if installed system-wide |
| **AIS vessels** | ✅ Works | bundled `AIS-catcher.exe` |
| **ACARS** | ❌ Not available | acarsdec has no Windows binary |
| **VDL2** | ❌ Not available | dumpvdl2 has no Windows binary |
| **APRS** | ❌ Not available | direwolf doesn't release Windows binaries |
| **DSC (maritime distress)** | ❌ Not available | vendored Linux-only decoder |
| **WiFi scanning** | ❌ Not available | Windows drivers don't support monitor mode |
| **Bluetooth scanning** | ✅ Works | uses bleak + WinRT (native Windows BLE stack) |
| **BT Locate** | ✅ Works | same WinRT backend |
| **Satellite tracking** | ✅ Works | pure Python (skyfield) — no SDR needed |
| **Weather satellites (NOAA APT / Meteor LRPT)** | ⚠️ Partial | bundled `satdump.exe` works; route uses POSIX pty pipes — needs refactor |
| **ISS SSTV** | ⚠️ Same as above | same blocker |
| **WeFax** | ⚠️ Same as above | same blocker |
| **Sub-GHz analyzer** | ⚠️ Limited | needs HackRF — official Windows builds source-only |
| **Meshtastic / MeshCore** | ✅ Works | serial + network, no SDR needed |
| **Listening Post** | ⚠️ Limited | rtl_fm bundled; ffmpeg needs to be on PATH |
| **TSCM counter-surveillance** | ⚠️ Partial | works with Bluetooth + RF scan; WiFi parts are gated |
| **Space Weather** | ✅ Works | pure REST APIs, no hardware |
| **WebSDR remote receiver** | ✅ Works | network-only |
| **GPS** | ✅ Works | pyserial / WinRT location |
| **System health** | ✅ Works | psutil cross-platform |

When you hit a mode that can't work on Windows, the dashboard surfaces a
clean 503 error explaining why instead of crashing.

## Troubleshooting

### "No SDR devices found" after Zadig

- Try **Options → List All Devices** again, make sure you selected
  *Bulk-In, Interface (Interface 0)* and not the DVB-T composite device.
- Unplug, wait 5 seconds, replug. Restart `intercept.exe`.
- Open Device Manager: under "Universal Serial Bus devices" you should see
  **Bulk-In, Interface (Interface 0)**. If you instead see *RTL2832U*
  under "DVB-T", Zadig didn't take — repeat with admin rights.

### Windows Defender quarantines `intercept.exe`

PyInstaller single-file exes have a long history of false-positive AV
flags. Click "More info → Run anyway" on the SmartScreen prompt, or
add an exclusion in Windows Security → Virus & threat protection →
Manage settings → Exclusions.

### Antivirus flagged after every release

If this becomes a recurring problem and you want to keep using the single-file
build, the alternatives are: extract-on-first-run installer (Inno Setup),
portable folder zip, or code-signing the exe. The first two are tracked but
not built yet.

### Port 5050 already in use

Pass `--port 5099` (or any free port) when launching from a terminal:

```
intercept.exe --port 5099
```

### Logs

The console window shows live logs. To capture to a file, run from a terminal
and redirect:

```
intercept.exe > intercept.log 2>&1
```

### Run as Administrator

Most Windows features don't need admin. The exe shows a warning on launch if
not elevated, but it's mostly cosmetic — the few features that genuinely
need elevation (TSCM RF scanning) will prompt with a clearer error.

## Building from source

If you'd rather build the exe yourself:

```powershell
git clone https://github.com/themuseum1960/intercept-test.git
cd intercept-test
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install pyinstaller
venv\Scripts\pyinstaller.exe --clean --noconfirm intercept.spec
# Output: dist\intercept.exe
```

See [tools/windows/README.md](../tools/windows/README.md) for how the bundled
SDR binaries are sourced and arranged.

## Known limitations / next build

Tracked for the next Windows-build pass:

1. **Weather satellite / ISS SSTV / WeFax routes still use POSIX `pty.openpty()`.**
   `satdump.exe` is bundled and works, but `utils/weather_sat.py` and the SSTV /
   WeFax singletons read its stdout through a pty pipe. Replace with a portable
   `subprocess.PIPE` + line-buffered reader (`bufsize=1`, `text=True`) so the
   bundled SatDump actually wires up to those routes on Windows. ~half a day.

2. **Antivirus false-positives on the single-file exe.** PyInstaller `--onefile`
   builds are routinely flagged by Defender / Chrome SmartScreen. If reports
   come in, switch to one of: an Inno Setup installer (extracts to Program
   Files, much friendlier to AV); a portable folder zip; or code-signing the
   exe with an EV cert.

## Reporting Windows-specific issues

File an issue with `[Windows]` in the title, include:

- Windows version (`winver`)
- The full console output from `intercept.exe`
- Output of `intercept.exe --check-deps`
- For driver issues: a screenshot of Device Manager → USB devices
