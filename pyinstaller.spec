# -*- mode: python ; coding: utf-8 -*-

import shutil
import sys
from pathlib import Path
import re

# --- Find required data files ---

# 1. Find ffmpeg binary based on the operating system
if sys.platform.startswith('win'):
    ffmpeg_name = 'ffmpeg.exe'
else:  # for linux, darwin (macOS), etc.
    ffmpeg_name = 'ffmpeg'

ffmpeg_path = shutil.which(ffmpeg_name)
print(f"Found ffmpeg at: {ffmpeg_path}")
if not ffmpeg_path:
    raise FileNotFoundError(
        f"'{ffmpeg_name}' not found in your system PATH. "
        "Please install ffmpeg and ensure its location is in the PATH environment variable."
    )

# 2. Find the `locales` directory from the installed `ytmusicapi` package
try:
    import ytmusicapi
    ytmusicapi_locales_path = str(Path(ytmusicapi.__file__).parent / 'locales')
except ImportError:
    raise ImportError("ytmusicapi is not installed. Please run 'pip install -r requirements.txt'")


# --- Read version and create app name ---
version_info_path = Path('version_info.txt')
version_info_content = version_info_path.read_text(encoding='utf-8')
version_match = re.search(r"StringStruct\(u'FileVersion', u'([^']*)'\)", version_info_content)
if not version_match:
    raise RuntimeError("Could not find FileVersion in version_info.txt")
file_version = version_match.group(1)
app_version = '.'.join(file_version.split('.')[:3])
app_name = f'yt-music-downloader-v{app_version}'


# --- PyInstaller Analysis ---

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(ffmpeg_path, '.')],  # Add ffmpeg to the root of the bundle
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
    name=app_name,  # Name of the final executable
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