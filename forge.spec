# Forge.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all submodules from the 'forge' package
forge_hiddenimports = collect_submodules('forge')

# Also collect data files if any (icons, etc.)
datas = [('app_icon.ico', '.')]

a = Analysis(
    ['run.py'],
    pathex=[os.path.dirname(os.path.abspath(__file__))],  # IMPORTANT: add current dir to path
    binaries=[],
    datas=datas,
    hiddenimports=forge_hiddenimports + ['sv_ttk', 'zstandard', 'tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Forge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,              # KEEP THIS – shows error messages
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico' if os.path.exists('app_icon.ico') else None,
)
