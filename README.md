# yt-music-downloader-gui

This script is currently tested and built only on Windows.

## Requirements

### For running script directly

- [`ffmpeg`](https://ffmpeg.org/download.html) must be installed on your system PATH.

### For building

- Same as 'running script directly'.

### For running the built executable

- No additional requirements needed.

## Usage

### Run script directly

> [!NOTE]
> `ffmpeg` must be installed on your system, either when runnig the script directly or
> building it with `pyinstaller`.

#### 1. Create virtual environment (Recommended)

```powershell
# create venv
python -m venv .venv

# activate venv
.venv\Scripts\Activate.ps1
```

#### 2. Install required packages

```powershell
python -m pip install -U -r requirements.txt
```

#### 3. run

```powershell
python .\main.py
```

### Build with pyinstaller

> [!NOTE]
> As mentioned above, `ffmpeg` is required when building.

Follow steps 1-2 of 'Run script directly', and run below:

```powershell
pyinstaller .\app.spec
```

Output executable file will be generated in `dist` folder. The build output executable does not require `ffmpeg` to be installed on the system.
