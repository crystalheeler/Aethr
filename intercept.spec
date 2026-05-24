# PyInstaller spec for INTERCEPT — Windows single-file build.
#
# Build:   venv\Scripts\pyinstaller.exe intercept.spec
# Output:  dist\intercept.exe
#
# This spec is Windows-targeted. The Linux/Docker path remains the
# canonical deployment for non-Windows users.

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Routes use a mix of static (`from .pager import pager_bp`) and dynamic
# (`importlib.import_module("utils.meshtastic")`) imports. The static ones
# PyInstaller picks up via Analysis; the dynamic ones we declare here.
hidden_imports = [
    *collect_submodules("routes"),
    *collect_submodules("utils"),
    *collect_submodules("data"),
    # Singletons reached via importlib in app._get_singleton_running:
    "utils.meshtastic",
    "utils.sstv",
    "utils.weather_sat",
    "utils.wefax",
    "utils.gps",
    "utils.bt_locate",
    # Optional Flask extensions checked at runtime:
    "flask_limiter",
    "flask_compress",
    "flask_wtf",
    "flask_sock",
    # Windows-native BLE backend pulled by bleak at runtime:
    "winrt.windows.devices.bluetooth",
    "winrt.windows.devices.bluetooth.advertisement",
]

datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("data", "data"),  # oui_database.json, satellites.py data tables, etc.
]

# Bundle Windows SDR tool binaries if present. The directory may be empty in
# a fresh checkout — that's fine; gated modes surface a useful "tool missing"
# error at runtime.
import os as _os
if _os.path.isdir("tools/windows"):
    datas.append(("tools/windows", "tools/windows"))

# Skyfield ships its data tables outside the package; pull them in.
datas += collect_data_files("skyfield")
# Meshtastic includes protobuf descriptors as package data.
datas += collect_data_files("meshtastic")

a = Analysis(
    ["intercept.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Linux-only modules that fail to install on Windows anyway,
        # but excluding them prevents PyInstaller from warning:
        "gunicorn",
        # Test infra never ships in a release build:
        "pytest",
        "_pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="intercept",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX often triggers antivirus false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep a console so server logs are visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: add static/favicon.ico once we have a Windows .ico
)
