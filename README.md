# yt-music-downloader-gui

This script is currently tested and built only on Windows.

## Run script directly

> [!NOTE]
> `ffmpeg` must be installed on your system, either when runnig the script directly or
> building it with `pyinstaller`.

### 1. Create virtual environment (Recommended)

```powershell
# create venv
python -m venv .venv

# activate venv
.venv\Scripts\Activate.ps1
```

### 2. Install required packages

```powershell
python -m pip install -U -r requirements.txt
```

### 3. run

```powershell
python .\main.py
```

## Build with pyinstaller

> [!NOTE]
> As mentioned above, `ffmpeg` is required when building.
> The build output executable does not require `ffmpeg` to be installed on the system.

Follow steps 1-2 of 'Run script directly', and run below:

```powershell
pyinstaller .\pyinstaller.spec
```
