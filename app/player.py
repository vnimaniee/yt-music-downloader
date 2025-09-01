import yt_dlp
import logging
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSlider
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class MusicPlayer(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        logging.info("Initializing music player")
        self.main_window = main_window

        self._create_ui()

        self.player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self.player.setAudioOutput(self._audio_output)

        self.currently_playing_track = None
        self.current_track_row = -1
        self.current_track_retries = 0
        self.yt_dlp = yt_dlp.YoutubeDL({
            'quiet': True,
            'format': 'bestaudio/best',
        })

        self.volume_before_mute = 100

        self._connect_signals()
        self.set_player_volume(self.volume_slider.value())
        self.stop_playback() # Set initial state

    def _create_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        emoji_font = QFont()
        emoji_font.setPointSize(14)

        self.current_track_label = QLabel()
        self.current_track_label.setMaximumWidth(400)
        self.prev_button = QPushButton("⏮︎")
        self.play_pause_button = QPushButton("⏵︎")
        self.stop_button = QPushButton("⏹︎")
        self.next_button = QPushButton("⏭︎")
        self.prev_button.setFont(emoji_font)
        self.play_pause_button.setFont(emoji_font)
        self.stop_button.setFont(emoji_font)
        self.next_button.setFont(emoji_font)

        for btn in [self.prev_button, self.play_pause_button, self.stop_button, self.next_button]:
            btn.setFixedSize(32, 32)

        self.current_time_label = QLabel()
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.total_time_label = QLabel()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(150)
        self.volume_icon_label = QPushButton("🔊")
        self.volume_icon_label.setFont(emoji_font)
        self.volume_icon_label.setFixedSize(32, 32)
        self.volume_icon_label.setStyleSheet("border: none;")

        layout.addWidget(self.current_track_label, 2)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.play_pause_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.current_time_label)
        layout.addWidget(self.timeline_slider, 5)
        layout.addWidget(self.total_time_label)
        layout.addWidget(self.volume_icon_label)
        layout.addWidget(self.volume_slider)

    def _connect_signals(self):
        self.play_pause_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.stop_playback)
        self.prev_button.clicked.connect(self.play_previous_track)
        self.next_button.clicked.connect(self.play_next_track)
        self.volume_slider.valueChanged.connect(self.set_player_volume)
        self.timeline_slider.sliderMoved.connect(self.set_player_position)
        self.volume_icon_label.clicked.connect(self.toggle_mute)

        self.player.playingChanged.connect(self.update_play_pause_button)
        self.player.errorOccurred.connect(self.handle_player_error)
        self.player.durationChanged.connect(self.update_slider_range)
        self.player.positionChanged.connect(self.update_slider_position)
        self.player.mediaStatusChanged.connect(self.handle_media_status_changed)

    def format_time(self, ms):
        seconds = int((ms/1000)%60)
        minutes = int((ms/(1000*60))%60)
        return f"{minutes:02d}:{seconds:02d}"

    def set_player_volume(self, value):
        logging.debug(f"Setting player volume to {value}")
        volume_float = value / 100.0
        self._audio_output.setVolume(volume_float)
        if value == 0:
            self.volume_icon_label.setText("🔇")
        else:
            self.volume_icon_label.setText("🔊")
            self.volume_before_mute = value

    def toggle_mute(self):
        logging.debug("Toggling mute")
        if self.volume_slider.value() > 0:
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(self.volume_before_mute)

    def get_track_info(self, row):
        tracklist_table = self.main_window.tracklist_table
        album_details = self.main_window.current_album_details
        if not (0 <= row < tracklist_table.rowCount()) or not album_details:
            return None
        
        title_item = tracklist_table.item(row, 2)
        track_details = album_details['tracks'][row]
        
        artists = 'N/A'
        if 'artists' in track_details and track_details['artists']:
            artists = ', '.join([a['name'] for a in track_details['artists']])

        return {
            'title': title_item.text(),
            'artists': artists
        }

    def play_track_from_table(self, item):
        logging.info(f"User requested to play track from table, row: {item.row()}")
        self.main_window.statusBar().showMessage(self.tr("Preparing to play track..."), 2000)
        self.play_track(item.row())

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            logging.info("Pausing playback")
            self.player.pause()
        elif self.player.playbackState() == QMediaPlayer.PausedState:
            logging.info("Resuming playback")
            self.player.play()
        else: # Stopped or no media
            logging.info("No media, attempting to play from selection")
            selected_items = self.main_window.tracklist_table.selectedItems()
            if selected_items:
                self.play_track(selected_items[0].row())

    def stop_playback(self):
        logging.info("Stopping playback")
        self.player.stop()
        self.current_track_label.setText(self.tr("No music selected"))
        self.timeline_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        self.currently_playing_track = None
        self.current_track_row = -1
        self.current_track_retries = 0

    def play_track(self, row, is_retry=False):
        if not is_retry and self.current_track_row == row and self.player.playbackState() != QMediaPlayer.StoppedState:
            self.toggle_playback()
            return

        if self.current_track_row != row:
            self.current_track_retries = 0

        playlist_id = self.main_window.current_album_playlist_id
        if not playlist_id:
            logging.warning("Cannot play track - no album playlist ID found.")
            self.main_window.statusBar().showMessage(self.tr("Cannot play track - no album playlist ID found."), 3000)
            return

        track_info = self.get_track_info(row)
        if not track_info:
            logging.warning(f"Could not find track info for row: {row}")
            self.main_window.statusBar().showMessage(self.tr("Could not find track info."), 3000)
            return

        track_index = str(row + 1)
        logging.info(f"Fetching stream URL for track: {track_info['title']} (index: {track_index})")
        self.main_window.statusBar().showMessage(self.tr("Fetching stream URL..."))
        
        try:
            ydl_opts = {
                'quiet': True,
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'playlist_items': track_index,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)

            if 'entries' in info and info['entries']:
                video_info = info['entries'][0]
                stream_url = video_info['url']
                logging.debug(f"Found stream URL: {stream_url}")
            else:
                raise yt_dlp.utils.DownloadError("Track not found in playlist.")

        except Exception as e:
            logging.error(f"Error getting stream URL: {e}")
            self.main_window.statusBar().showMessage(f"{self.tr('Error getting stream URL')}: {e}", 5000)
            self.handle_player_error()
            return

        self.currently_playing_track = track_info
        self.current_track_row = row
        self.current_track_label.setText(f"<b>{track_info['title']}</b><br>{track_info['artists']}")
        self.player.setSource(QUrl(stream_url))
        self.player.play()
        logging.info(f"Playing track: {track_info['title']}")
        self.main_window.statusBar().showMessage(self.tr("Playing..."), 3000)

    def handle_player_error(self):
        logging.error(f"Player error occurred. State: {self.player.error()}, String: {self.player.errorString()}")
        if self.current_track_row != -1 and self.current_track_retries < 3:
            self.current_track_retries += 1
            logging.info(f"Retrying playback... ({self.current_track_retries}/3)")
            self.main_window.statusBar().showMessage(self.tr("Playback failed. Retrying... ({0}/3)").format(self.current_track_retries), 3000)
            QTimer.singleShot(1000, lambda: self.play_track(self.current_track_row, is_retry=True))
        else:
            logging.error("Playback failed after multiple retries.")
            self.main_window.statusBar().showMessage(self.tr("Playback failed. Please try another track."), 5000)
            self.stop_playback()

    def update_play_pause_button(self, playing):
        if playing:
            self.play_pause_button.setText("⏸︎")
        else:
            self.play_pause_button.setText("⏵︎")

    def update_slider_range(self, duration):
        self.timeline_slider.setRange(0, duration)
        self.total_time_label.setText(self.format_time(duration))

    def update_slider_position(self, position):
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(position)
        self.timeline_slider.blockSignals(False)
        self.current_time_label.setText(self.format_time(position))

    def set_player_position(self, position):
        logging.debug(f"Setting player position to {position}")
        self.player.setPosition(position)

    def handle_media_status_changed(self, status):
        logging.debug(f"Media status changed: {status}")
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.current_track_row != -1:
            logging.info("Track finished, playing next")
            self.play_next_track()

    def play_next_track(self):
        next_row = self.current_track_row + 1
        logging.info(f"Attempting to play next track, row: {next_row}")
        if 0 <= next_row < self.main_window.tracklist_table.rowCount():
            self.play_track(next_row)
        else:
            logging.info("End of playlist reached")
            self.stop_playback()

    def play_previous_track(self):
        prev_row = self.current_track_row - 1
        logging.info(f"Attempting to play previous track, row: {prev_row}")
        if 0 <= prev_row < self.main_window.tracklist_table.rowCount():
            self.play_track(prev_row)
