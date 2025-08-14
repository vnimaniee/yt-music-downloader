import os
import sys
import shutil
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QObject, Signal

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor

from .tagging import tag_audio

class TagAudioPP(PostProcessor):
    def __init__(self, ydl, album_details=None):
        super().__init__(ydl)
        self.album_details = album_details

    def run(self, info):
        filepath = Path(info['filepath'])
        self.to_screen(f'Checking for tags for {filepath.name}')
        temp_save_path = filepath.parent
        
        cover_path = None
        for ext in ('.jpg', '.jpeg', '.png', '.webp'):
            p = temp_save_path / ('cover' + ext)
            if p.exists():
                cover_path = p
                break
        
        tags = {}
        if self.album_details:
            playlist_index = info.get('playlist_index')
            
            track_info = None
            if playlist_index and self.album_details.get('tracks'):
                if 0 < playlist_index <= len(self.album_details['tracks']):
                    track_info = self.album_details['tracks'][playlist_index - 1]

            if track_info:
                self.to_screen(f"Found metadata for track #{playlist_index}: {track_info.get('title')}")
                tags['title'] = track_info.get('title')
                if track_info.get('artists'):
                    tags['artist'] = ', '.join([a['name'] for a in track_info['artists']])
                tags['album'] = self.album_details.get('title')
                if self.album_details.get('artists'):
                    tags['album_artist'] = ', '.join([a['name'] for a in self.album_details['artists']])
                
                tags['track_number'] = playlist_index
                if self.album_details.get('trackCount'):
                    tags['total_tracks'] = self.album_details.get('trackCount')
                if self.album_details.get('year'):
                    tags['year'] = self.album_details.get('year')
            else:
                self.to_screen(f"Could not find metadata for {filepath.name} in album details.")

        if cover_path or tags:
            try:
                self.to_screen(f'Applying metadata for {filepath.name}')
                tag_audio(filepath, tags, cover_path)
            except NotImplementedError:
                self.to_screen(f'Skipping tagging for {filepath.name}: unsupported file type')
            except Exception as e:
                self.report_warning(f'Could not tag {filepath.name}: {e}')
        else:
            self.to_screen('No cover art or metadata found.')

        return [], info

class DownloadWorker(QObject):
    finished = Signal(str)
    error = Signal(str, str)

    def run(self, playlist_id, track_indices, save_path, audio_format, album_details=None):
        with TemporaryDirectory() as temp_save_path:
            try:
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
                    ydl.add_post_processor(TagAudioPP(ydl, album_details), when='post_process')
                    ydl.download([playlist_url])

                for p in Path(temp_save_path).iterdir():
                    if p.is_file() and p.suffix.lower() in {'.mp3', '.flac', '.m4a', '.opus', '.wav'}:
                        shutil.copy(p, save_path)

            except Exception:
                tb = traceback.format_exc()
                print(tb, file=sys.stderr)
                self.error.emit("An error occurred during processing.", tb)
            else:
                self.finished.emit(self.tr("Successfully downloaded {0} track(s)!").format(len(track_indices)))