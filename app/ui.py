import requests
import re
import logging

from PySide6.QtWidgets import (
    QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QFileDialog, QStatusBar, QCheckBox, QDialog, QTextEdit, QProgressDialog
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread

from .worker import DownloadWorker
from .youtube_api import YouTubeMusicClient, get_ytmusicapi_lang, supported_lang
from .utils import get_system_locale
from .player import MusicPlayer

class ProgressDialog(QProgressDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Downloading..."))
        self.setLabelText(self.tr("Download in progress, please wait..."))
        self.setMinimumSize(400, 100)
        self.setModal(True)
        self.setMinimumDuration(0)
        self.setValue(0)

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
        logging.info("Initializing main window")
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

        # --- Music Player ---
        self.player_widget = MusicPlayer(self)
        root_layout.addWidget(self.player_widget)
        
        root_layout.setStretchFactor(main_content_widget, 1)
        
        self.setStatusBar(QStatusBar(self))

        # --- Connections & State ---
        self.search_button.clicked.connect(lambda: self.search_albums())
        self.search_input.returnPressed.connect(lambda: self.search_albums())
        self.search_language.currentTextChanged.connect(self.on_search_language_changed)
        self.results_table.itemSelectionChanged.connect(self.display_album_details)
        self.tracklist_table.itemChanged.connect(self.on_track_check_changed)
        self.tracklist_table.itemDoubleClicked.connect(self.player_widget.play_track_from_table)
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_tracks)
        self.download_button.clicked.connect(self.initiate_download)
        
        self.ytmusic_client = YouTubeMusicClient()
        self.download_thread = None
        self.download_worker = None
        self.current_album_playlist_id = None
        self.current_album_details = None
        
        self.clear_details() # Set initial state

    def search_albums(self, query=None, preserve_details=False):
        if query is None:
            query = self.search_input.text()
        if not query: return
        logging.info(f"Searching for albums with query: '{query}'")
        self.results_table.setRowCount(0)
        if not preserve_details:
            self.clear_details()
        try:
            search_results = self.ytmusic_client.search_albums(query)
            logging.info(f"Found {len(search_results)} results")
        except Exception as e:
            logging.error(f"Search failed: {e}")
            self.statusBar().showMessage(f"Search failed: {e}", 5000)
            return
        for album in search_results:
            row = self.results_table.rowCount()

            artists_list = album.get('artists', [])
            year = album.get('year')
            album_type = album.get('type')

            if not year and artists_list:
                last_artist_name = artists_list[-1]['name']
                if re.match(r'^\d{4}[년年]?', last_artist_name):
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
        logging.info(f"Displaying album details for browse_id: {browse_id}")
        if not browse_id: self.clear_details(); return
        try:
            album_details = self.ytmusic_client.get_album_details(browse_id)
            self._update_album_details_ui(album_details)
        except Exception as e:
            logging.error(f"Error fetching album details: {e}")
            self.statusBar().showMessage(f"Error fetching album details: {e}", 5000)
            self.clear_details()

    def _update_album_details_ui(self, album_details):
        logging.info(f"Updating album details UI for album: {album_details.get('title')}")
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
            except requests.exceptions.RequestException as e:
                logging.warning(f"Failed to load album art: {e}")
                self.album_art_label.setText(self.tr("Image not available"))
        
        self.tracklist_table.blockSignals(True)
        self.tracklist_table.setRowCount(0)
        if album_details.get('tracks'):
            logging.info(f"Populating tracklist with {len(album_details['tracks'])} tracks")
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
        new_lang = self.search_language.currentText()
        logging.info(f"Search language changed to: {new_lang}")
        self.ytmusic_client.set_language(new_lang)
        
        current_browse_id = self.current_album_details.get('browseId') if self.current_album_details else None

        self.search_albums(preserve_details=bool(current_browse_id))

        if current_browse_id:
            try:
                logging.info(f"Refreshing album details for browse_id: {current_browse_id}")
                new_details = self.ytmusic_client.get_album_details(current_browse_id)
                self._update_album_details_ui(new_details)
            except Exception as e:
                logging.error(f"Error refreshing album details: {e}")
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
        logging.debug(f"Toggling all tracks to state: {state}")
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
        logging.info(f"Initiating download of {len(track_indices)} tracks to '{save_path}' in format '{audio_format}'")
        self.download_button.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.statusBar().showMessage(self.tr("Preparing download for {0} track(s)...").format(len(track_indices)))

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()

        self.download_thread = QThread()
        self.download_worker = DownloadWorker()
        self.download_worker.moveToThread(self.download_thread)
        
        self.download_worker.progress.connect(self.progress_dialog.setValue)
        self.download_worker.progress_label.connect(self.progress_dialog.setLabelText)
        
        self.download_worker.finished.connect(self.progress_dialog.accept)
        self.download_worker.error.connect(self.progress_dialog.reject)

        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(self.on_download_error)
        
        self.download_thread.started.connect(lambda: self.download_worker.start_download.emit(self.current_album_playlist_id, track_indices, save_path, audio_format, self.current_album_details))
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.error.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.finished.connect(self._clear_download_worker)
        self.download_thread.start()

    def on_download_finished(self, message):
        logging.info(f"Download finished: {message}")
        self.statusBar().showMessage(message, 5000)
        self._update_download_controls_state()

    def on_download_error(self, summary, details):
        logging.error(f"Download error: {summary} - {details}")
        self.statusBar().showMessage(summary, 10000)
        self._update_download_controls_state()
        error_dialog = ErrorDialog(summary, details, self)
        error_dialog.exec()

    def cancel_download(self):
        logging.info("Download cancellation requested by user.")
        if self.download_worker:
            self.download_worker.cancel()

    def _clear_download_worker(self):
        logging.debug("Clearing download worker and thread references.")
        self.download_worker = None
        self.download_thread = None

    def clear_details(self):
        logging.info("Clearing album details")
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
        self.player_widget.stop_playback()

