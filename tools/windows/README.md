# Windows SDR tool bundle

This directory holds Windows builds of the external SDR command-line tools that
INTERCEPT shells out to. They're bundled into the release `intercept.exe` by
PyInstaller (see `intercept.spec`) and resolved by `utils.dependencies.get_tool_path`,
which checks this directory before falling back to system PATH.

## What goes here

| Binary | Source | Used by |
|---|---|---|
| `rtl_fm.exe` | [RTL-SDR Blog releases](https://github.com/rtlsdrblog/rtl-sdr-blog/releases) | pager, sensor, ACARS, APRS, listening post, TSCM, weather sat, SSTV |
| `rtl_test.exe` | same | SDR detection |
| `rtl_power.exe` | same | listening post scanner, TSCM |
| `rtl_tcp.exe` | same | remote SDR |
| `rtl_eeprom.exe` | same | device admin |
| `rtl_sdr.exe` | same | low-level IQ capture |
| `multimon-ng.exe` | [multimon-ng releases](https://github.com/EliasOenal/multimon-ng/releases) | pager, APRS |
| `rtl_433.exe` | [rtl_433 releases](https://github.com/merbanan/rtl_433/releases) | sensor, sub-GHz |
| `AIS-catcher.exe` | [AIS-catcher releases](https://github.com/jvde-github/AIS-catcher/releases) | AIS |
| `dump1090.exe` | [dump1090 win port](https://github.com/MalcolmRobb/dump1090) | ADS-B |
| `hackrf_transfer.exe`, `hackrf_sweep.exe`, `hackrf_info.exe` | [HackRF releases](https://github.com/greatscottgadgets/hackrf/releases) | sub-GHz, listening post |
| `direwolf.exe` | [direwolf releases](https://github.com/wb2osz/direwolf/releases) | APRS |
| `satdump.exe` + `satdump-cli.exe` | [SatDump releases](https://github.com/SatDump/SatDump/releases) | weather satellite, wefax |

## Tools without a working Windows build

These modes are gated on Windows in `routes/*.py` because the tools they need
don't (yet) have a usable Windows binary:

| Tool | Mode |
|---|---|
| `airmon-ng` / `airodump-ng` | WiFi monitor mode (Windows drivers don't support it) |
| `hcitool` / `bluetoothctl` | Legacy Bluetooth (the v2 `/bt/v2/*` API uses bleak/WinRT and works) |
| `bin/dsc-decoder` | DSC (vendored Linux ELF, no Windows build) |
| `acarsdec` | ACARS (no Windows build; gated at runtime) |
| `dumpvdl2` | VDL2 (no Windows build; gated at runtime) |

## How discovery works

`utils.dependencies.get_tool_path(name)` checks, in order:

1. `INTERCEPT_<NAME>_PATH` environment variable
2. Bundled `tools/windows/<name>[.exe]` (Windows only)
3. System `PATH` via `shutil.which`
4. Extra Unix paths (`/usr/local/bin`, `/usr/sbin`, `/sbin`)
5. Known absolute paths (`KNOWN_TOOL_PATHS`)

On Linux the bundled-tools check is a no-op — system PATH still wins.

## Adding a tool

1. Drop `<name>.exe` (and any DLLs it needs) into this directory.
2. Confirm it runs standalone: `tools/windows/rtl_test.exe -t`.
3. Rebuild the exe: `venv/Scripts/pyinstaller.exe --noconfirm intercept.spec`.
4. The new tool is automatically bundled and discovered.

## License notes

Each bundled tool ships under its own license. Keep upstream LICENSE files
next to the binary (e.g. `LICENSE-rtl-sdr.txt`) so redistribution complies
with the original terms.
