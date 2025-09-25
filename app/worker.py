import os
import sys
import shutil
import traceback
import logging
import requests
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
        logging.info(f'Checking for tags for {filepath.name}')
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
                logging.info(f"Found metadata for track #{playlist_index}: {track_info.get('title')}")
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
                logging.warning(f"Could not find metadata for {filepath.name} in album details.")

        if cover_path or tags:
            try:
                logging.info(f'Applying metadata for {filepath.name}')
                tag_audio(filepath, tags, cover_path)
            except NotImplementedError:
                logging.warning(f'Skipping tagging for {filepath.name}: unsupported file type')
            except Exception as e:
                logging.error(f'Could not tag {filepath.name}: {e}')
        else:
            logging.info('No cover art or metadata found.')

        return [], info

class CancelledError(Exception):
    pass

class SearchWorker(QObject):
    finished = Signal(list)
    error = Signal(str, str)
    start_search = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_search.connect(self._do_search)

    def _do_search(self, ytmusic_client, query):
        try:
            logging.info(f"Worker searching for albums with query: '{query}'")
            search_results = ytmusic_client.search_albums(query)
            logging.info(f"Worker found {len(search_results)} results")
            self.finished.emit(search_results)
        except Exception:
            tb = traceback.format_exc()
            logging.error(f"An error occurred during search:\n{tb}")
            self.error.emit("An error occurred during search.", tb)

class AlbumDetailsWorker(QObject):
    finished = Signal(object, object)
    error = Signal(str, str)
    start_get_details = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_get_details.connect(self._do_get_details)

    def _do_get_details(self, ytmusic_client, browse_id):
        try:
            logging.info(f"Worker getting album details for browse_id: {browse_id}")
            album_details = ytmusic_client.get_album_details(browse_id)
            image_content = None
            if album_details and album_details.get('thumbnails'):
                try:
                    image_content = requests.get(album_details['thumbnails'][-1]['url']).content
                except requests.exceptions.RequestException as e:
                    logging.warning(f"Failed to load album art in worker: {e}")
            logging.info(f"Worker got album details for: {album_details.get('title')}")
            self.finished.emit(album_details, image_content)
        except Exception:
            tb = traceback.format_exc()
            logging.error(f"An error occurred during get_album_details:\n{tb}")
            self.error.emit("An error occurred while fetching album details.", tb)

class DownloadWorker(QObject):
    finished = Signal(str)
    error = Signal(str, str)
    progress = Signal(int)
    progress_label = Signal(str)
    start_download = Signal(str, list, str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_download.connect(self._do_download)
        self._is_cancelled = False

    def cancel(self):
        logging.info("Cancellation signal received in worker.")
        self._is_cancelled = True

    def _do_download(self, playlist_id, track_indices, save_path, audio_format, album_details):
        self._is_cancelled = False
        self.run(playlist_id, track_indices, save_path, audio_format, album_details)

    def run(self, playlist_id, track_indices, save_path, audio_format, album_details=None):
        logging.info(f"Starting download for playlist_id={playlist_id}, track_indices={track_indices}, save_path={save_path}, audio_format={audio_format}")
        
        total_tracks = len(track_indices)
        downloaded_count = 0

        def progress_hook(d):
            if self._is_cancelled:
                raise CancelledError("Download cancelled by user.")

            nonlocal downloaded_count
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes')

                if total and downloaded:
                    file_fraction = downloaded / total
                    file_contribution = (1 / total_tracks) * file_fraction
                    completed_fraction = downloaded_count / total_tracks
                    total_fraction = completed_fraction + file_contribution
                    progress_percent = int(total_fraction * 95)
                    self.progress.emit(progress_percent)
                    info = d.get('info_dict', {})
                    artist = info.get('artist')
                    track = info.get('track') or info.get('title')
                    if artist and track:
                        self.progress_label.emit(
                            self.tr("Downloading {0}/{1}: {2} - {3} ({4:.0%})").format(
                                downloaded_count + 1,
                                total_tracks,
                                artist,
                                track,
                                file_fraction
                            )
                        )
                    else:
                        self.progress_label.emit(
                            self.tr("Downloading track {0}/{1} ({2:.0%})").format(
                                downloaded_count + 1,
                                total_tracks,
                                file_fraction
                            )
                        )
            elif d['status'] == 'finished':
                downloaded_count += 1
                progress_percent = int((downloaded_count / total_tracks) * 95)
                self.progress.emit(progress_percent)
                info = d.get('info_dict', {})
                artist = info.get('artist')
                track = info.get('track') or info.get('title')
                
                self.progress_label.emit(
                    self.tr("Processing {0}/{1}: {2} - {3}").format(
                        downloaded_count,
                        total_tracks,
                        artist,
                        track
                    )
                )

        with TemporaryDirectory() as temp_save_path:
            try:
                playlist_url = f"https://youtube.com/playlist?list={playlist_id}"
                output_template = {
                    'default': os.path.join(temp_save_path, '%(artist)s - %(track)s.%(ext)s'),
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
                    'progress_hooks': [progress_hook],
                }
                logging.debug(f"yt-dlp options: {ydl_opts}")

                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    if sys.platform.startswith('win'):
                        ffmpeg_name = 'ffmpeg.exe'
                    else: # linux, darwin (macOS)
                        ffmpeg_name = 'ffmpeg'
                    
                    # set bundled ffmpeg location
                    ydl_opts['ffmpeg_location'] = os.path.join(sys._MEIPASS, ffmpeg_name)
                    logging.debug(f"Set ffmpeg location to: {ydl_opts['ffmpeg_location']}")

                self.progress_label.emit(self.tr("Preparing to download..."))
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.add_post_processor(TagAudioPP(ydl, album_details), when='post_process')
                    logging.info("Starting yt-dlp download")
                    ydl.download([playlist_url])
                    logging.info("Finished yt-dlp download")

                self.progress.emit(98)
                self.progress_label.emit(self.tr("Moving files..."))
                for i, p in enumerate(Path(temp_save_path).iterdir()):
                    if p.is_file() and p.suffix.lower() in {'.mp3', '.flac', '.m4a', '.opus', '.wav'}:
                        dest_dir = Path(save_path)
                        dest_path = dest_dir / p.name
                        
                        counter = 1
                        while dest_path.exists():
                            dest_path = dest_dir / f"{p.stem} ({counter}){p.suffix}"
                            counter += 1
                        
                        logging.info(f"Moving {p} to {dest_path}")
                        shutil.copy(p, dest_path)
                
                self.progress.emit(100)

            except CancelledError:
                logging.info("Download was cancelled by the user.")
                self.finished.emit(self.tr("Download cancelled."))
            except Exception:
                tb = traceback.format_exc()
                logging.error(f"An error occurred during processing:\n{tb}")
                self.error.emit("An error occurred during processing.", tb)
            else:
                if not self._is_cancelled:
                    logging.info(f"Successfully downloaded {len(track_indices)} track(s)!")
                    self.finished.emit(self.tr("Successfully downloaded {0} track(s)!").format(len(track_indices)))
