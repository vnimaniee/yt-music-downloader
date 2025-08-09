# -*- mode: python ; coding: utf-8 -*-

import shutil
import sys
from pathlib import Path

# --- Find required data files ---

# 1. Find ffmpeg.exe in system PATH
ffmpeg_path = shutil.which('ffmpeg.exe')
if not ffmpeg_path:
    raise FileNotFoundError(
        "ffmpeg.exe not found in your system PATH. "
        "Please install ffmpeg and ensure its location is in the PATH environment variable."
    )

# 2. Find the `locales` directory from the installed `ytmusicapi` package
try:
    import ytmusicapi
    ytmusicapi_locales_path = str(Path(ytmusicapi.__file__).parent / 'locales')
except ImportError:
    raise ImportError("ytmusicapi is not installed. Please run 'pip install -r requirements.txt'")


# --- PyInstaller Analysis ---

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(ffmpeg_path, '.')],  # Add ffmpeg.exe to the root of the bundle
    datas=[(ytmusicapi_locales_path, 'ytmusicapi/locales'), ('translations', 'translations')],
    hiddenimports=[],
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


# --- EXE Bundle --- 

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='yt-music-downloader',  # Name of the final executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Use False for a windowed (GUI) application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None, # You can add an icon here, e.g., icon='app.ico'
    version='version_info.txt'
)