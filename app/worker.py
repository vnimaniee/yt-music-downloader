import os
import sys
import shutil
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QObject, Signal

import yt_dlp
from .tagging import tag_audio

class DownloadWorker(QObject):
    finished = Signal(str)
    error = Signal(str, str) # Changed: summary, details

    def run(self, playlist_id, track_indices, save_path, audio_format):
        with TemporaryDirectory() as temp_save_path:
            try: # download
                playlist_url = f"https://youtube.com/playlist?list={playlist_id}"
                output_template = {
                    'default': os.path.join(temp_save_path, "%(artist)s - %(track)s.%(ext)s"),
                    'pl_thumbnail': os.path.join(temp_save_path, 'cover'),
                    'thumbnail': ''
                }
                items_to_download = ",".join(map(str, track_indices))

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [
                        {
                            'key': 'FFmpegExtractAudio',
                            'nopostoverwrites': False,
                            'preferredcodec': audio_format,
                            'preferredquality': '0'
                        },
                        {
                            'add_chapters': True,
                            'add_infojson': 'if_exists',
                            'add_metadata': True,
                            'key': 'FFmpegMetadata'
                        },
                        {
                            'key': 'FFmpegConcat',
                            'only_multi_video': True,
                            'when': 'playlist'
                        }
                    ],
                    'outtmpl': output_template,
                    'playlist_items': items_to_download,
                    'writethumbnail': True,
                }

                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    ydl_opts['ffmpeg_location'] = os.path.join(sys._MEIPASS, 'ffmpeg.exe')

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([playlist_url])

            except Exception:
                tb = traceback.format_exc()
                print(tb, file=sys.stderr)
                self.error.emit("Download failed.", tb)
                return # Stop execution if download fails

            try: # tagging
                files = [
                    p
                    for p in Path(temp_save_path).iterdir()
                    if p.suffix.lower() in {'.mp3', '.flac', '.m4a', '.opus', '.wav'}
                ]
                img_path = os.path.join(temp_save_path, "cover.jpg")
                for file in files:
                    try:
                        tag_audio(file, img_path)
                    except NotImplementedError:
                        # unsupported MIME: skip tagging
                        pass
                    shutil.copy(file, save_path)

            except Exception:
                tb = traceback.format_exc()
                print(tb, file=sys.stderr)
                self.error.emit("Tagging failed.", tb)
            else:
                self.finished.emit(f"Successfully downloaded {len(track_indices)} track(s)!")