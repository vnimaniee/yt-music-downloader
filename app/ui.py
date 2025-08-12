import requests
import re
import yt_dlp

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QFileDialog, QStatusBar, QCheckBox, QDialog, QTextEdit, QSlider
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QThread, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from .worker import DownloadWorker
from .youtube_api import YouTubeMusicClient, get_ytmusicapi_lang, supported_lang
from .utils import get_system_locale

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Downloading..."))
        self.setModal(True)
        self.setFixedSize(400, 100)
        layout = QVBoxLayout(self)
        self.status_label = QLabel(self.tr("Download in progress, please wait..."))
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

class ErrorDialog(QDialog):
    def __init__(self, summary, details, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Error"))
        self.setModal(True)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        
        summary_label = QLabel(summary)
        layout.addWidget(summary_label)

        details_box = QTextEdit()
        details_box.setText(details)
        details_box.setReadOnly(True)
        layout.addWidget(details_box)

        close_button = QPushButton(self.tr("Close"))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignRight)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"YT Music Downloader")
        self.resize(1200, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)

        main_content_widget = QWidget()
        main_layout = QHBoxLayout(main_content_widget)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Enter album name to search..."))
        self.search_button = QPushButton(self.tr("Search"))
        self.search_language = QComboBox()
        self.search_language.addItems(supported_lang)
        try:
            self.search_language.setCurrentText(get_ytmusicapi_lang(get_system_locale()))
        except:
            self.search_language.setCurrentText('en')
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_language)
        search_layout.addWidget(self.search_button)
        left_layout.addLayout(search_layout)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([self.tr("Title"), self.tr("Artist"), self.tr("Year"), self.tr("Type")])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        left_layout.addWidget(self.results_table)

        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.album_details_widget = QWidget()
        album_details_layout = QVBoxLayout(self.album_details_widget)
        self.album_art_label = QLabel(self.tr("Select an album to see details"))
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setMinimumSize(300, 300)
        self.album_title_label = QLabel()
        self.album_title_label.setAlignment(Qt.AlignCenter)
        self.album_artist_label = QLabel()
        self.album_artist_label.setAlignment(Qt.AlignCenter)
        self.album_year_label = QLabel()
        self.album_year_label.setAlignment(Qt.AlignCenter)
        album_details_layout.addWidget(self.album_art_label)
        album_details_layout.addWidget(self.album_title_label)
        album_details_layout.addWidget(self.album_artist_label)
        album_details_layout.addWidget(self.album_year_label)
        right_layout.addWidget(self.album_details_widget)

        self.tracklist_table = QTableWidget()
        self.tracklist_table.setColumnCount(4)
        self.tracklist_table.setHorizontalHeaderLabels((["", "#", self.tr("Title"), self.tr("Duration")]))
        track_header = self.tracklist_table.horizontalHeader()
        track_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        track_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        track_header.setSectionResizeMode(2, QHeaderView.Stretch)
        track_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tracklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tracklist_table.verticalHeader().setVisible(False)

        self.select_all_checkbox = QCheckBox(parent=track_header)
        self.select_all_checkbox.setTristate(True)
        self.select_all_checkbox.show()
        track_header.geometriesChanged.connect(self._reposition_select_all_checkbox)
        track_header.sectionResized.connect(lambda index, old, new: self._reposition_select_all_checkbox() if index == 0 else None)

        right_layout.addWidget(self.tracklist_table)

        # --- Download Controls ---
        download_controls_layout = QHBoxLayout()
        self.format_selector = QComboBox()
        self.format_selector.addItems(['mp3', 'flac', 'wav', 'm4a', 'opus'])
        self.download_button = QPushButton(self.tr("Download"))
        download_controls_layout.addWidget(QLabel(self.tr("Format:")))
        download_controls_layout.addWidget(self.format_selector)
        download_controls_layout.addWidget(self.download_button)
        right_layout.addLayout(download_controls_layout)

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 1)
        
        root_layout.addWidget(main_content_widget)

        # --- Music Player UI ---
        emoji_font = QFont()
        emoji_font.setPointSize(14)

        player_widget = QWidget()
        player_layout = QHBoxLayout(player_widget)
        player_layout.setContentsMargins(5, 2, 5, 2) # Reduce margins

        self.current_track_label = QLabel(self.tr("No music selected"))
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
            btn.setFixedSize(32, 32) # Reduce button size

        self.current_time_label = QLabel("00:00")
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.total_time_label = QLabel("00:00")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(150)
        self.volume_icon_label = QLabel("🔊")
        self.volume_icon_label.setFont(emoji_font)

        player_layout.addWidget(self.current_track_label, 2)
        player_layout.addWidget(self.prev_button)
        player_layout.addWidget(self.play_pause_button)
        player_layout.addWidget(self.stop_button)
        player_layout.addWidget(self.next_button)
        player_layout.addWidget(self.current_time_label)
        player_layout.addWidget(self.timeline_slider, 5)
        player_layout.addWidget(self.total_time_label)
        player_layout.addWidget(self.volume_icon_label)
        player_layout.addWidget(self.volume_slider)
        
        root_layout.addWidget(player_widget)
        root_layout.setStretchFactor(main_content_widget, 1)
        
        self.setStatusBar(QStatusBar(self))

        # --- Player ---
        self.player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self.player.setAudioOutput(self._audio_output)
        self.volume_slider.valueChanged.connect(self.set_player_volume)
        self.set_player_volume(self.volume_slider.value())

        # --- Connections & State ---
        self.search_button.clicked.connect(lambda: self.search_albums())
        self.search_input.returnPressed.connect(lambda: self.search_albums())
        self.search_language.currentTextChanged.connect(self.on_search_language_changed)
        self.results_table.itemSelectionChanged.connect(self.display_album_details)
        self.tracklist_table.itemChanged.connect(self.on_track_check_changed)
        self.tracklist_table.itemDoubleClicked.connect(self.play_track_from_table)
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_tracks)
        self.download_button.clicked.connect(self.initiate_download)
        self.play_pause_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.stop_playback)
        self.prev_button.clicked.connect(self.play_previous_track)
        self.next_button.clicked.connect(self.play_next_track)
        
        self.player.playingChanged.connect(self.update_play_pause_button)
        self.player.errorOccurred.connect(self.handle_player_error)
        self.player.durationChanged.connect(self.update_slider_range)
        self.player.positionChanged.connect(self.update_slider_position)
        self.player.mediaStatusChanged.connect(self.handle_media_status_changed)
        self.timeline_slider.sliderMoved.connect(self.set_player_position)
        
        self.ytmusic_client = YouTubeMusicClient()
        self.download_thread = None
        self.current_album_playlist_id = None
        self.current_album_details = None
        self.currently_playing_track = None
        self.current_track_row = -1
        self.current_track_retries = 0
        self.yt_dlp = yt_dlp.YoutubeDL({
            'quiet': True,
            'format': 'bestaudio/best',
        })
        self.clear_details() # Set initial state

    def format_time(self, ms):
        seconds = int((ms/1000)%60)
        minutes = int((ms/(1000*60))%60)
        return f"{minutes:02d}:{seconds:02d}"

    def set_player_volume(self, value):
        volume_float = value / 100.0
        self._audio_output.setVolume(volume_float)

    def search_albums(self, query=None, preserve_details=False):
        if query is None:
            query = self.search_input.text()
        if not query: return
        self.results_table.setRowCount(0)
        if not preserve_details:
            self.clear_details()
        try:
            search_results = self.ytmusic_client.search_albums(query)
        except Exception as e:
            self.statusBar().showMessage(f"Search failed: {e}", 5000)
            return
        for album in search_results:
            row = self.results_table.rowCount()

            artists_list = album.get('artists', [])
            year = album.get('year')
            album_type = album.get('type')

            if not year and artists_list:
                last_artist_name = artists_list[-1]['name']
                if re.match(r'^\d{4}[년年]?$', last_artist_name):
                    year = last_artist_name.replace('년', '').replace('年', '')
                    artists_list = artists_list[:-1]
            
            if artists_list and artists_list[0]['name'] == album_type:
                artists_list = artists_list[1:]

            artists = ', '.join([a['name'] for a in artists_list]) or 'N/A'
            year = str(year) if year else 'N/A'

            self.results_table.insertRow(row)
            title_item = QTableWidgetItem(album.get('title', 'N/A'))
            title_item.setToolTip(album.get('title', 'N/A'))
            title_item.setData(Qt.UserRole, album.get('browseId'))
            self.results_table.setItem(row, 0, title_item)
            self.results_table.setItem(row, 1, QTableWidgetItem(artists))
            self.results_table.setItem(row, 2, QTableWidgetItem(year))
            self.results_table.setItem(row, 3, QTableWidgetItem(album_type))

    def display_album_details(self):
        selected = self.results_table.selectedItems()
        if not selected: return
        browse_id = selected[0].data(Qt.UserRole)
        if not browse_id: self.clear_details(); return
        try:
            album_details = self.ytmusic_client.get_album_details(browse_id)
            self._update_album_details_ui(album_details)
        except Exception as e:
            self.statusBar().showMessage(f"Error fetching album details: {e}", 5000)
            self.clear_details()

    def _update_album_details_ui(self, album_details):
        self.current_album_details = album_details
        self.current_album_playlist_id = album_details.get('audioPlaylistId')

        self.album_title_label.setText(f"<b>{album_details['title']}</b>")
        self.album_artist_label.setText(', '.join([a['name'] for a in album_details.get('artists', [])]))
        self.album_year_label.setText(str(album_details.get('year', '')))

        if album_details.get('thumbnails'):
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(requests.get(album_details['thumbnails'][-1]['url']).content)
                self.album_art_label.setPixmap(pixmap.scaled(self.album_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except requests.exceptions.RequestException:
                self.album_art_label.setText(self.tr("Image not available"))
        
        self.tracklist_table.blockSignals(True)
        self.tracklist_table.setRowCount(0)
        if album_details.get('tracks'):
            for i, track in enumerate(album_details['tracks']):
                row = self.tracklist_table.rowCount()
                self.tracklist_table.insertRow(row)
                check_item, num_item = QTableWidgetItem(), QTableWidgetItem(str(i + 1))
                title_item, duration_item = QTableWidgetItem(track.get('title', 'N/A')), QTableWidgetItem(track.get('duration', 'N/A'))
                title_item.setToolTip(track.get('title', 'N/A'))
                
                if self.current_album_playlist_id:
                    check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    check_item.setData(Qt.UserRole, i + 1) # Store track index (1-based)
                else:
                    check_item.setFlags(Qt.ItemIsEnabled)
                    check_item.setToolTip(self.tr("This album is not available for download."))
                
                check_item.setCheckState(Qt.Unchecked)
                num_item.setTextAlignment(Qt.AlignCenter)
                for item in [num_item, title_item, duration_item]: item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.tracklist_table.setItem(row, 0, check_item)
                self.tracklist_table.setItem(row, 1, num_item)
                self.tracklist_table.setItem(row, 2, title_item)
                self.tracklist_table.setItem(row, 3, duration_item)
        self.tracklist_table.blockSignals(False)
        self._update_download_controls_state()

    def on_search_language_changed(self):
        self.ytmusic_client.set_language(self.search_language.currentText())
        
        current_browse_id = self.current_album_details.get('browseId') if self.current_album_details else None

        self.search_albums(preserve_details=bool(current_browse_id))

        if current_browse_id:
            try:
                new_details = self.ytmusic_client.get_album_details(current_browse_id)
                self._update_album_details_ui(new_details)
            except Exception as e:
                self.statusBar().showMessage(f"Error refreshing album details: {e}", 5000)

    def _get_checkable_rows(self):
        return [r for r in range(self.tracklist_table.rowCount()) if self.tracklist_table.item(r, 0).flags() & Qt.ItemIsUserCheckable]

    def _update_download_controls_state(self):
        checkable_rows = self._get_checkable_rows()
        checked_rows = [r for r in checkable_rows if self.tracklist_table.item(r, 0).checkState() == Qt.Checked]
        
        self.download_button.setEnabled(len(checked_rows) > 0)
        self.select_all_checkbox.setEnabled(len(checkable_rows) > 0)

        self.select_all_checkbox.blockSignals(True)
        if not checked_rows:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif len(checked_rows) == len(checkable_rows):
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)
        self.select_all_checkbox.blockSignals(False)

    def _reposition_select_all_checkbox(self):
        header = self.tracklist_table.horizontalHeader()
        checkbox_size = self.select_all_checkbox.sizeHint()
        y = int((header.height() - checkbox_size.height()) / 2)
        x = int((header.sectionSize(0) - checkbox_size.width()) / 2)
        self.select_all_checkbox.move(x, y)

    def on_track_check_changed(self, item):
        if item.column() == 0:
            self._update_download_controls_state()

    def toggle_all_tracks(self, state):
        state = Qt.CheckState(state)
        if state == Qt.Checked or state == Qt.PartiallyChecked:
            new_check_state = Qt.Checked
        else:  # state == Qt.Unchecked
            new_check_state = Qt.Unchecked

        self.tracklist_table.blockSignals(True)
        for row in self._get_checkable_rows():
            self.tracklist_table.item(row, 0).setCheckState(new_check_state)
        self.tracklist_table.blockSignals(False)
        self._update_download_controls_state()

    def initiate_download(self):
        if not self.current_album_playlist_id:
            self.statusBar().showMessage(self.tr("This album is not available for download."), 3000); return

        track_indices = []
        for row in range(self.tracklist_table.rowCount()):
            if self.tracklist_table.item(row, 0).checkState() == Qt.Checked:
                track_indices.append(self.tracklist_table.item(row, 0).data(Qt.UserRole))
        
        if not track_indices: self.statusBar().showMessage(self.tr("No tracks checked for download."), 3000); return
        
        save_path = QFileDialog.getExistingDirectory(self, self.tr("Select Download Folder"))
        if not save_path: return
        
        audio_format = self.format_selector.currentText()
        language = self.search_language.currentText()
        self.download_button.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.statusBar().showMessage(self.tr(f"Preparing download for {len(track_indices)} track(s)..."))

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.show()

        self.download_thread = QThread()
        worker = DownloadWorker()
        worker.moveToThread(self.download_thread)
        
        worker.finished.connect(self.progress_dialog.accept)
        worker.error.connect(self.progress_dialog.reject)

        worker.finished.connect(self.on_download_finished)
        worker.error.connect(self.on_download_error)
        
        self.download_thread.started.connect(lambda: worker.run(self.current_album_playlist_id, track_indices, save_path, audio_format, self.current_album_details))
        worker.finished.connect(self.download_thread.quit)
        worker.error.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.start()

    def on_download_finished(self, message):
        self.statusBar().showMessage(message, 5000)
        self._update_download_controls_state()

    def on_download_error(self, summary, details):
        self.statusBar().showMessage(summary, 10000)
        self._update_download_controls_state()
        error_dialog = ErrorDialog(summary, details, self)
        error_dialog.exec()

    def clear_details(self):
        self.album_art_label.clear()
        self.album_art_label.setText(self.tr("Select an album to see details"))
        self.album_title_label.clear()
        self.album_artist_label.clear()
        self.album_year_label.clear()
        self.tracklist_table.setRowCount(0)
        self.download_button.setEnabled(False)
        self.select_all_checkbox.setCheckState(Qt.Unchecked)
        self.select_all_checkbox.setEnabled(False)
        self.current_album_playlist_id = None
        self.current_album_details = None
        self.stop_playback()

    def get_track_info(self, row):
        if not (0 <= row < self.tracklist_table.rowCount()):
            return None
        
        title_item = self.tracklist_table.item(row, 2)
        track_details = self.current_album_details['tracks'][row]
        
        artists = 'N/A'
        if 'artists' in track_details and track_details['artists']:
            artists = ', '.join([a['name'] for a in track_details['artists']])

        return {
            'title': title_item.text(),
            'artists': artists
        }

    def play_track_from_table(self, item):
        self.statusBar().showMessage(self.tr("Preparing to play track..."), 2000)
        self.play_track(item.row())

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.player.playbackState() == QMediaPlayer.PausedState:
            self.player.play()
        else: # Stopped or no media
            selected_items = self.tracklist_table.selectedItems()
            if selected_items:
                self.play_track(selected_items[0].row())

    def stop_playback(self):
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

        if not self.current_album_playlist_id:
            self.statusBar().showMessage(self.tr("Cannot play track - no album playlist ID found."), 3000)
            return

        track_info = self.get_track_info(row)
        if not track_info:
            self.statusBar().showMessage(self.tr("Could not find track info."), 3000)
            return

        playlist_id = self.current_album_playlist_id
        track_index = str(row + 1) # yt-dlp needs a string for playlist_items

        self.statusBar().showMessage(self.tr("Fetching stream URL..."))
        
        try:
            ydl_opts = {
                'quiet': True,
                'format': 'bestaudio/best',
                'playlist_items': track_index,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)

            if 'entries' in info and info['entries']:
                video_info = info['entries'][0]
                stream_url = video_info['url']
                track_info['title'] = track_info['title']
                track_info['artists'] = track_info['artists'] # yt-dlp may use 'artist'
            else:
                raise yt_dlp.utils.DownloadError("Track not found in playlist.")

        except Exception as e:
            self.statusBar().showMessage(f"{self.tr('Error getting stream URL')}: {e}", 5000)
            self.handle_player_error()
            return

        self.currently_playing_track = track_info
        self.current_track_row = row
        self.current_track_label.setText(f"<b>{track_info['title']}</b><br>{track_info['artists']}")
        self.player.setSource(QUrl(stream_url))
        self.player.play()
        self.statusBar().showMessage(self.tr("Playing..."), 3000)

    def handle_player_error(self):
        if self.current_track_row != -1 and self.current_track_retries < 3:
            self.current_track_retries += 1
            self.statusBar().showMessage(self.tr(f"Playback failed. Retrying... ({self.current_track_retries}/3)"), 3000)
            QTimer.singleShot(1000, lambda: self.play_track(self.current_track_row, is_retry=True))
        else:
            self.statusBar().showMessage(self.tr("Playback failed. Please try another track."), 5000)
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
        self.player.setPosition(position)

    def handle_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.current_track_row != -1:
            self.play_next_track()

    def play_next_track(self):
        next_row = self.current_track_row + 1
        if 0 <= next_row < self.tracklist_table.rowCount():
            self.play_track(next_row)
        else:
            self.stop_playback()

    def play_previous_track(self):
        prev_row = self.current_track_row - 1
        if 0 <= prev_row < self.tracklist_table.rowCount():
            self.play_track(prev_row)
