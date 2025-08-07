import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QFileDialog, QStatusBar, QCheckBox, QDialog, QTextEdit
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread

from .worker import DownloadWorker
from .youtube_api import YouTubeMusicClient

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloading...")
        self.setModal(True)
        self.setFixedSize(400, 100)
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Download in progress, please wait...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

class ErrorDialog(QDialog):
    def __init__(self, summary, details, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error")
        self.setModal(True)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        
        summary_label = QLabel(summary)
        layout.addWidget(summary_label)

        details_box = QTextEdit()
        details_box.setText(details)
        details_box.setReadOnly(True)
        layout.addWidget(details_box)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignRight)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"YT Music Downloader")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter album name to search...")
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        left_layout.addLayout(search_layout)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Title", "Artist", "Year", "Type"])
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

        self.album_art_label = QLabel("Select an album to see details")
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setMinimumSize(300, 300)
        right_layout.addWidget(self.album_art_label)

        self.tracklist_table = QTableWidget()
        self.tracklist_table.setColumnCount(4)
        self.tracklist_table.setHorizontalHeaderLabels(["", "#", "Title", "Duration"])
        track_header = self.tracklist_table.horizontalHeader()
        track_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        track_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        track_header.setSectionResizeMode(2, QHeaderView.Stretch)
        track_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tracklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tracklist_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.tracklist_table)

        # --- Download Controls ---
        download_controls_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.setTristate(True)
        self.format_selector = QComboBox()
        self.format_selector.addItems(['mp3', 'flac', 'wav', 'm4a', 'opus'])
        self.download_button = QPushButton("Download Checked")
        download_controls_layout.addWidget(self.select_all_checkbox)
        download_controls_layout.addWidget(QLabel("Format:"))
        download_controls_layout.addWidget(self.format_selector)
        download_controls_layout.addWidget(self.download_button)
        right_layout.addLayout(download_controls_layout)

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 1)
        self.setStatusBar(QStatusBar(self))

        # --- Connections & State ---
        self.search_button.clicked.connect(self.search_albums)
        self.search_input.returnPressed.connect(self.search_albums)
        self.results_table.itemSelectionChanged.connect(self.display_album_details)
        self.tracklist_table.itemChanged.connect(self.on_track_check_changed)
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_tracks)
        self.download_button.clicked.connect(self.initiate_download)
        
        self.ytmusic_client = YouTubeMusicClient()
        self.download_thread = None
        self.current_album_playlist_id = None
        self.clear_details() # Set initial state

    def search_albums(self):
        query = self.search_input.text()
        if not query: return
        self.results_table.setRowCount(0)
        self.clear_details()
        try:
            search_results = self.ytmusic_client.search_albums(query)
        except Exception as e:
            self.statusBar().showMessage(f"Search failed: {e}", 5000)
            return
        for album in search_results:
            row, artists = self.results_table.rowCount(), ', '.join([a['name'] for a in album.get('artists', [])]) or 'N/A'
            self.results_table.insertRow(row)
            title_item = QTableWidgetItem(album.get('title', 'N/A'))
            title_item.setData(Qt.UserRole, album.get('browseId'))
            self.results_table.setItem(row, 0, title_item)
            self.results_table.setItem(row, 1, QTableWidgetItem(artists))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(album.get('year', 'N/A'))))
            self.results_table.setItem(row, 3, QTableWidgetItem(album.get('type', 'N/A')))

    def display_album_details(self):
        selected = self.results_table.selectedItems()
        if not selected: return
        browse_id = selected[0].data(Qt.UserRole)
        if not browse_id: self.clear_details(); return
        try:
            album_details = self.ytmusic_client.get_album_details(browse_id)
            self.current_album_playlist_id = album_details.get('audioPlaylistId')
        except Exception as e:
            self.statusBar().showMessage(f"Error fetching album details: {e}", 5000); self.clear_details(); return
        
        if album_details.get('thumbnails'):
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(requests.get(album_details['thumbnails'][-1]['url']).content)
                self.album_art_label.setPixmap(pixmap.scaled(self.album_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except requests.exceptions.RequestException:
                self.album_art_label.setText("Image not available")
        
        self.tracklist_table.blockSignals(True)
        self.tracklist_table.setRowCount(0)
        if album_details.get('tracks'):
            for i, track in enumerate(album_details['tracks']):
                row = self.tracklist_table.rowCount()
                self.tracklist_table.insertRow(row)
                check_item, num_item = QTableWidgetItem(), QTableWidgetItem(str(i + 1))
                title_item, duration_item = QTableWidgetItem(track.get('title', 'N/A')), QTableWidgetItem(track.get('duration', 'N/A'))
                
                if self.current_album_playlist_id:
                    check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    check_item.setData(Qt.UserRole, i + 1) # Store track index (1-based)
                else:
                    check_item.setFlags(Qt.ItemIsEnabled)
                    check_item.setToolTip("This album is not available for download.")
                
                check_item.setCheckState(Qt.Unchecked)
                num_item.setTextAlignment(Qt.AlignCenter)
                for item in [num_item, title_item, duration_item]: item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.tracklist_table.setItem(row, 0, check_item)
                self.tracklist_table.setItem(row, 1, num_item)
                self.tracklist_table.setItem(row, 2, title_item)
                self.tracklist_table.setItem(row, 3, duration_item)
        self.tracklist_table.blockSignals(False)
        self._update_download_controls_state()

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
            self.statusBar().showMessage("This album is not available for download.", 3000); return

        track_indices = []
        for row in range(self.tracklist_table.rowCount()):
            if self.tracklist_table.item(row, 0).checkState() == Qt.Checked:
                track_indices.append(self.tracklist_table.item(row, 0).data(Qt.UserRole))
        
        if not track_indices: self.statusBar().showMessage("No tracks checked for download.", 3000); return
        
        save_path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if not save_path: return
        
        audio_format = self.format_selector.currentText()
        self.download_button.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.statusBar().showMessage(f"Preparing download for {len(track_indices)} track(s)...")

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.show()

        self.download_thread = QThread()
        worker = DownloadWorker()
        worker.moveToThread(self.download_thread)
        
        worker.finished.connect(self.progress_dialog.accept)
        worker.error.connect(self.progress_dialog.reject)

        worker.finished.connect(self.on_download_finished)
        worker.error.connect(self.on_download_error)
        
        self.download_thread.started.connect(lambda: worker.run(self.current_album_playlist_id, track_indices, save_path, audio_format))
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
        self.album_art_label.setText("Select an album to see details")
        self.tracklist_table.setRowCount(0)
        self.download_button.setEnabled(False)
        self.select_all_checkbox.setCheckState(Qt.Unchecked)
        self.select_all_checkbox.setEnabled(False)
        self.current_album_playlist_id = None