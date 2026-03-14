# -*- mode: python ; coding: utf-8 -*-
#
# KWPBridge PyInstaller spec
#
# Bundles:
#   - kwpbridge package (protocol, server, client, GUI, lbl_parser)
#   - labels/  (engine/ and modules/ subdirectories — all .lbl files)
#   - scaling/ (.a01, .a03, .SCL presets)
#   - PyQt5 (GUI framework)
#   - pyserial (K-line communication)
#
# Build:  pyinstaller kwpbridge.spec
# Output: dist/KWPBridge.exe

import os
from pathlib import Path

ROOT = Path('.').resolve()


# ── Collect all label files (subdirectories included) ────────────────────────
label_datas = []
for subdir in ['', 'engine', 'modules']:
    label_path = ROOT / 'labels' / subdir if subdir else ROOT / 'labels'
    if label_path.exists():
        for f in label_path.iterdir():
            if f.suffix.lower() in ('.lbl',) and f.is_file():
                dest = f'labels/{subdir}' if subdir else 'labels'
                label_datas.append((str(f), dest))

# Scaling files
scaling_datas = []
scaling_path = ROOT / 'scaling'
if scaling_path.exists():
    for f in scaling_path.iterdir():
        if f.is_file() and f.suffix.lower() in ('.a01', '.a03', '.scl', '.SCL'):
            scaling_datas.append((str(f), 'scaling'))

print(f"Bundling {len(label_datas)} label files")
print(f"Bundling {len(scaling_datas)} scaling files")

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['kwpbridge/__main__.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=label_datas + scaling_datas,
    hiddenimports=[
        'kwpbridge',
        'kwpbridge.protocol',
        'kwpbridge.server',
        'kwpbridge.client',
        'kwpbridge.lbl_parser',
        'kwpbridge.formula',
        'kwpbridge.models',
        'kwpbridge.ecu_defs',
        'kwpbridge.constants',
        'kwpbridge.gui',
        'kwpbridge.gui.main',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    noarchive=False,
)

# ── PYZ ───────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure)

# ── EXE ───────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KWPBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='kwpbridge/gui/icon.ico',   # uncomment when icon is added
    version_file=None,
)
