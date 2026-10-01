from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.audio.analyzer import AudioAnalyzer
from src.audio.audio_player import AudioPlayer
from src.audio.importer import MusicImporter
from src.audio.metadata import scan_music
from src.config.settings import AppSettings, SettingsStore
from src.library.groups import LocalGroupStore
from src.models import Gesture, GestureEvent, Track
from src.online.spotify_service import SpotifyResult, SpotifyService
from src.ui.add_music_dialog import AddMusicDialog
from src.ui.artwork import ArtworkWidget
from src.ui.camera_widget import CameraView
from src.ui.settings_dialog import SettingsDialog
from src.ui.visualizer import Visualizer
from src.vision.gesture_controller import GestureController
from src.vision.hand_tracker import CameraWorker

LOGGER = logging.getLogger(__name__)


def format_time(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_root: Path,
        tracks: list[Track],
        settings: AppSettings,
        settings_store: SettingsStore,
    ) -> None:
        super().__init__()
        self.project_root = project_root
        self.settings = settings
        self.settings_store = settings_store
        self.tracks = tracks
        self.player = AudioPlayer(tracks)
        self.analyzer = AudioAnalyzer()
        self.camera = CameraWorker(project_root)
        self.controller = GestureController(settings.gesture_cooldown)
        self.importer = MusicImporter(project_root / "music")
        self.group_store = LocalGroupStore(project_root / "local_groups.json")
        self.spotify = SpotifyService()
        self._spotify_search_request = 0
        self._spotify_search_timer = QTimer(self)
        self._spotify_search_timer.setSingleShot(True)
        self._seeking = False
        self._available_cameras = [settings.camera_index]
        self.setWindowTitle("Music HandControl")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 720)
        self._build_ui()
        self._connect()
        self._populate_playlist()
        self._apply_settings(restart_camera=False)
        self._timers()
        QTimer.singleShot(200, self._discover_and_start_camera)

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        return frame, layout

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 22)
        root.setSpacing(15)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(2, 0, 2, 0)
        brand = QLabel("MUSIC  HANDCONTROL")
        brand.setObjectName("Brand")
        subtitle = QLabel("Gesture-powered listening · Arjunrenvon")
        subtitle.setObjectName("Muted")
        brand_column = QVBoxLayout()
        brand_column.setSpacing(0)
        brand_column.addWidget(brand)
        brand_column.addWidget(subtitle)
        top_layout.addLayout(brand_column)
        top_layout.addStretch()
        self.camera_toggle = QPushButton("●  Hand Control")
        self.camera_toggle.setObjectName("Toggle")
        self.camera_toggle.setCheckable(True)
        self.camera_toggle.setChecked(self.settings.hand_tracking)
        self.settings_button = QPushButton("⚙  Settings")
        top_layout.addWidget(self.camera_toggle)
        top_layout.addWidget(self.settings_button)
        root.addWidget(top)

        content = QHBoxLayout()
        content.setSpacing(15)
        root.addLayout(content, 1)

        library_card, library_layout = self._card()
        library_card.setFixedWidth(300)
        playlist_header_row = QHBoxLayout()
        playlist_header = QLabel("YOUR MUSIC")
        playlist_header.setObjectName("Eyebrow")
        self.add_music_button = QPushButton("＋ Add")
        playlist_header_row.addWidget(playlist_header)
        playlist_header_row.addStretch()
        playlist_header_row.addWidget(self.add_music_button)
        library_layout.addLayout(playlist_header_row)

        self.library_tabs = QTabWidget()
        library_layout.addWidget(self.library_tabs, 1)

        local_tab = QWidget()
        local_layout = QVBoxLayout(local_tab)
        local_layout.setContentsMargins(8, 12, 8, 8)
        local_layout.setSpacing(8)
        group_row = QHBoxLayout()
        self.group_filter = QComboBox()
        self.group_filter.setToolTip("Show all local tracks or one local group")
        self.new_group_button = QPushButton("＋")
        self.new_group_button.setToolTip("Create a local music group")
        self.delete_group_button = QPushButton("×")
        self.delete_group_button.setToolTip("Delete the selected local group")
        group_row.addWidget(self.group_filter, 1)
        group_row.addWidget(self.new_group_button)
        group_row.addWidget(self.delete_group_button)
        local_layout.addLayout(group_row)
        self.playlist_count = QLabel("0 tracks")
        self.playlist_count.setObjectName("Muted")
        local_layout.addWidget(self.playlist_count)
        self.playlist = QListWidget()
        self.playlist.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        local_layout.addWidget(self.playlist, 1)
        self.empty_message = QLabel("No music found.\n\nAdd MP3 files inside\nthe /music folder.")
        self.empty_message.setObjectName("Empty")
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message.setWordWrap(True)
        local_layout.addWidget(self.empty_message)
        self.add_to_group_button = QPushButton("Add selected to group")
        local_layout.addWidget(self.add_to_group_button)
        self.import_status = QLabel("")
        self.import_status.setObjectName("Muted")
        self.import_status.setWordWrap(True)
        self.import_status.hide()
        self.import_progress = QProgressBar()
        self.import_progress.setRange(0, 100)
        self.import_progress.hide()
        local_layout.addWidget(self.import_status)
        local_layout.addWidget(self.import_progress)
        self.library_tabs.addTab(local_tab, "Local")

        online_tab = QWidget()
        online_layout = QVBoxLayout(online_tab)
        online_layout.setContentsMargins(8, 12, 8, 8)
        online_layout.setSpacing(8)
        self.spotify_connect_button = QPushButton("Connect Spotify")
        self.spotify_status = QLabel("Connect your Spotify app to search the catalog.")
        self.spotify_status.setObjectName("Muted")
        self.spotify_status.setWordWrap(True)
        self.spotify_search = QLineEdit()
        self.spotify_search.setPlaceholderText("Search Spotify…")
        self.spotify_search.setEnabled(False)
        self.spotify_filter = QComboBox()
        self.spotify_filter.addItem("Tracks", "track")
        self.spotify_filter.addItem("Artists", "artist")
        self.spotify_filter.addItem("Albums", "album")
        self.spotify_filter.addItem("Playlists", "playlist")
        self.spotify_filter.setEnabled(False)
        self.spotify_results = QListWidget()
        self.spotify_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.spotify_results.setEnabled(False)
        self.spotify_open_button = QPushButton("Open selected in Spotify ↗")
        self.spotify_open_button.setEnabled(False)
        spotify_attribution = QLabel("Spotify catalog search · Opens results in Spotify")
        spotify_attribution.setObjectName("Muted")
        spotify_attribution.setWordWrap(True)
        online_layout.addWidget(self.spotify_connect_button)
        online_layout.addWidget(self.spotify_status)
        online_layout.addWidget(self.spotify_search)
        online_layout.addWidget(self.spotify_filter)
        online_layout.addWidget(self.spotify_results, 1)
        online_layout.addWidget(self.spotify_open_button)
        online_layout.addWidget(spotify_attribution)
        self.library_tabs.addTab(online_tab, "Online · Spotify")
        content.addWidget(library_card)

        middle = QVBoxLayout()
        middle.setSpacing(15)
        content.addLayout(middle, 3)
        camera_card, camera_layout = self._card()
        camera_row = QHBoxLayout()
        camera_title = QLabel("LIVE HAND TRACKING")
        camera_title.setObjectName("Eyebrow")
        self.camera_status = QLabel("Starting…")
        self.camera_status.setObjectName("Muted")
        camera_row.addWidget(camera_title)
        camera_row.addStretch()
        camera_row.addWidget(self.camera_status)
        camera_layout.addLayout(camera_row)
        self.camera_view = CameraView()
        camera_layout.addWidget(self.camera_view, 1)
        gesture_row = QHBoxLayout()
        gesture_label = QLabel("GESTURE")
        gesture_label.setObjectName("Eyebrow")
        self.gesture_text = QLabel("Waiting…")
        self.gesture_text.setObjectName("Gesture")
        gesture_row.addWidget(gesture_label)
        gesture_row.addStretch()
        gesture_row.addWidget(self.gesture_text)
        camera_layout.addLayout(gesture_row)
        self.gesture_progress = QProgressBar()
        self.gesture_progress.setRange(0, 100)
        self.gesture_progress.setTextVisible(False)
        self.gesture_progress.setFixedHeight(7)
        self.gesture_progress.hide()
        camera_layout.addWidget(self.gesture_progress)
        middle.addWidget(camera_card, 2)
        visual_card, visual_layout = self._card()
        visual_head = QHBoxLayout()
        vis_title = QLabel("AUDIO VISUALIZER")
        vis_title.setObjectName("Eyebrow")
        visual_head.addWidget(vis_title)
        visual_head.addStretch()
        self.mode_buttons: list[QPushButton] = []
        for mode in ("Spectrum", "Wave", "Circular"):
            button = QPushButton(mode)
            button.setCheckable(True)
            button.setChecked(mode == self.settings.visualizer_mode)
            button.clicked.connect(lambda checked=False, value=mode: self._set_visualizer_mode(value))
            self.mode_buttons.append(button)
            visual_head.addWidget(button)
        visual_layout.addLayout(visual_head)
        self.visualizer = Visualizer()
        visual_layout.addWidget(self.visualizer)
        middle.addWidget(visual_card, 1)

        now_card, now_layout = self._card()
        now_card.setFixedWidth(330)
        now_head = QLabel("NOW PLAYING")
        now_head.setObjectName("Eyebrow")
        now_layout.addWidget(now_head)
        now_layout.addStretch()
        artwork_row = QHBoxLayout()
        artwork_row.addStretch()
        self.artwork = ArtworkWidget()
        artwork_row.addWidget(self.artwork)
        artwork_row.addStretch()
        now_layout.addLayout(artwork_row)
        self.title = QLabel("Ready to play")
        self.title.setObjectName("Title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        self.artist = QLabel("Choose a track from your library")
        self.artist.setObjectName("Artist")
        self.artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album = QLabel("")
        self.album.setObjectName("Muted")
        self.album.setAlignment(Qt.AlignmentFlag.AlignCenter)
        now_layout.addWidget(self.title)
        now_layout.addWidget(self.artist)
        now_layout.addWidget(self.album)
        now_layout.addStretch()
        time_row = QHBoxLayout()
        self.elapsed = QLabel("00:00")
        self.elapsed.setObjectName("Muted")
        self.total = QLabel("00:00")
        self.total.setObjectName("Muted")
        time_row.addWidget(self.elapsed)
        time_row.addStretch()
        time_row.addWidget(self.total)
        now_layout.addLayout(time_row)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        now_layout.addWidget(self.progress)
        control_row = QHBoxLayout()
        control_row.addStretch()
        self.shuffle_button = QPushButton("↝")
        self.shuffle_button.setObjectName("Round")
        self.shuffle_button.setToolTip("Shuffle")
        self.previous_button = QPushButton("⏮")
        self.previous_button.setObjectName("Round")
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("Primary")
        self.next_button = QPushButton("⏭")
        self.next_button.setObjectName("Round")
        self.repeat_button = QPushButton("↻")
        self.repeat_button.setObjectName("Round")
        self.repeat_button.setToolTip("Repeat playlist")
        for button in (
            self.shuffle_button,
            self.previous_button,
            self.play_button,
            self.next_button,
            self.repeat_button,
        ):
            control_row.addWidget(button)
        control_row.addStretch()
        now_layout.addLayout(control_row)
        volume_row = QHBoxLayout()
        self.mute_button = QPushButton("🔊")
        self.mute_button.setObjectName("Round")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(self.settings.volume * 100))
        self.volume_text = QLabel(f"{self.volume.value()}%")
        self.volume_text.setObjectName("Muted")
        volume_row.addWidget(self.mute_button)
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_text)
        now_layout.addLayout(volume_row)
        content.addWidget(now_card)

        self.overlay = QLabel("", central)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setStyleSheet(
            "background: rgba(18,22,33,225); border: 1px solid #864fc2; border-radius: 16px; "
            "padding: 18px 28px; font-size: 21px; font-weight: 700; color: white;"
        )
        self.overlay.hide()

    def _connect(self) -> None:
        self.playlist.itemClicked.connect(self._play_local_item)
        self.play_button.clicked.connect(self.player.toggle)
        self.previous_button.clicked.connect(self.player.previous)
        self.next_button.clicked.connect(self.player.next)
        self.volume.valueChanged.connect(lambda value: self._set_volume(value / 100))
        self.mute_button.clicked.connect(self._toggle_mute)
        self.shuffle_button.clicked.connect(self._toggle_shuffle)
        self.repeat_button.clicked.connect(self._cycle_repeat)
        self.progress.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.progress.sliderReleased.connect(self._seek_released)
        self.camera_toggle.toggled.connect(self._toggle_camera)
        self.settings_button.clicked.connect(self._show_settings)
        self.add_music_button.clicked.connect(self._show_add_music)
        self.group_filter.currentTextChanged.connect(lambda _value: self._populate_playlist())
        self.new_group_button.clicked.connect(self._create_group)
        self.delete_group_button.clicked.connect(self._delete_selected_group)
        self.add_to_group_button.clicked.connect(self._add_selected_track_to_group)
        self.spotify_connect_button.clicked.connect(self._connect_spotify)
        self.spotify_search.textChanged.connect(self._schedule_spotify_search)
        self.spotify_filter.currentIndexChanged.connect(self._schedule_spotify_search)
        self.spotify_results.itemSelectionChanged.connect(self._spotify_selection_changed)
        self.spotify_results.itemDoubleClicked.connect(lambda _item: self._open_selected_spotify())
        self.spotify_open_button.clicked.connect(self._open_selected_spotify)
        self._spotify_search_timer.timeout.connect(self._run_spotify_search)
        self.player.on_track_changed = self._track_changed
        self.player.on_state_changed = self._play_state_changed
        self.player.on_error = self._show_error
        self.camera.frame_ready.connect(self.camera_view.set_frame)
        self.camera.gesture_ready.connect(self._gesture_received)
        self.camera.status_changed.connect(self._camera_status_changed)
        self.camera.cameras_found.connect(self._cameras_discovered)
        self.controller.on_action = self._gesture_action
        self.importer.progress.connect(self._import_progress_changed)
        self.importer.completed.connect(self._import_completed)
        self.importer.failed.connect(self._import_failed)
        self.spotify.authorization_requested.connect(self._open_spotify_authorization)
        self.spotify.connected.connect(self._spotify_connected)
        self.spotify.connection_failed.connect(self._spotify_connection_failed)
        self.spotify.results_ready.connect(self._spotify_results_ready)
        self.spotify.search_failed.connect(self._spotify_search_failed)
        if not self.player.available:
            QTimer.singleShot(
                0, lambda: self._show_error(self.player.initialization_error or "Audio is unavailable")
            )

    def _timers(self) -> None:
        self.visual_timer = QTimer(self)
        self.visual_timer.timeout.connect(self._animate)
        self.visual_timer.start(33)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(200)
        self.overlay_timer = QTimer(self)
        self.overlay_timer.setSingleShot(True)
        self.overlay_timer.timeout.connect(self.overlay.hide)

    def _populate_playlist(self) -> None:
        self.group_store.prune({track.path.name for track in self.tracks})
        selected_group = str(self.group_filter.currentData() or "")
        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem("All local music", "")
        for name in self.group_store.names:
            self.group_filter.addItem(name, name)
        selected_index = self.group_filter.findData(selected_group)
        self.group_filter.setCurrentIndex(max(0, selected_index))
        self.group_filter.blockSignals(False)
        selected_group = str(self.group_filter.currentData() or "")
        grouped_tracks = self.group_store.tracks_for(selected_group)
        visible_tracks = [
            (index, track)
            for index, track in enumerate(self.tracks)
            if not selected_group or track.path.name in grouped_tracks
        ]
        self.playlist.clear()
        for number, (track_index, track) in enumerate(visible_tracks, 1):
            item = QListWidgetItem(f"{number:02d}   {track.display_title}\n       {track.artist}")
            item.setToolTip(track.path.name)
            item.setData(Qt.ItemDataRole.UserRole, track_index)
            self.playlist.addItem(item)
        count = len(visible_tracks)
        if selected_group:
            self.playlist_count.setText(f"{count} track{'s' if count != 1 else ''} in {selected_group}")
        else:
            self.playlist_count.setText(f"{count} local track{'s' if count != 1 else ''}")
        self.empty_message.setText(
            "No tracks in this group."
            if selected_group
            else "No music found.\n\nAdd MP3 files inside\nthe /music folder."
        )
        self.empty_message.setVisible(not visible_tracks)
        self.playlist.setVisible(bool(visible_tracks))
        self.delete_group_button.setEnabled(bool(selected_group))
        self.add_to_group_button.setEnabled(bool(self.tracks))

    def _play_local_item(self, item: QListWidgetItem) -> None:
        track_index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(track_index, int):
            self.player.play_index(track_index)

    def _create_group(self) -> None:
        name, accepted = QInputDialog.getText(self, "Create Local Group", "Group name:")
        if not accepted:
            return
        try:
            created = self.group_store.create(name)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self.group_filter.blockSignals(True)
        self.group_filter.addItem(created, created)
        self.group_filter.setCurrentIndex(self.group_filter.findData(created))
        self.group_filter.blockSignals(False)
        self._populate_playlist()

    def _delete_selected_group(self) -> None:
        name = str(self.group_filter.currentData() or "")
        if not name:
            return
        response = QMessageBox.question(
            self,
            "Delete Local Group",
            f"Delete the group '{name}'? Your MP3 files will not be removed.",
        )
        if response is QMessageBox.StandardButton.Yes:
            self.group_store.delete(name)
            self._populate_playlist()

    def _add_selected_track_to_group(self) -> None:
        item = self.playlist.currentItem()
        if item is None:
            self._feedback("SELECT A LOCAL TRACK FIRST", 1200)
            return
        track_index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(track_index, int) or not (0 <= track_index < len(self.tracks)):
            return
        if not self.group_store.names:
            self._feedback("CREATE A LOCAL GROUP FIRST", 1200)
            return
        name, accepted = QInputDialog.getItem(
            self, "Add to Local Group", "Add selected track to:", self.group_store.names, 0, False
        )
        if not accepted:
            return
        try:
            self.group_store.add_track(name, self.tracks[track_index].path.name)
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._feedback(f"✓  ADDED TO {name.upper()}", 1100)
        self._populate_playlist()

    def _connect_spotify(self) -> None:
        client_id, accepted = QInputDialog.getText(
            self,
            "Connect Spotify",
            "Spotify Client ID:\n\n"
            "Create a Web API app in Spotify for Developers and register http://127.0.0.1 as its redirect URI. "
            "The Client ID is safe to save; Spotify tokens stay only in this app session.",
            text=self.settings.spotify_client_id,
        )
        if not accepted:
            return
        self.settings.spotify_client_id = client_id.strip()
        self.spotify_connect_button.setEnabled(False)
        self.spotify_status.setText("Preparing secure Spotify sign-in…")
        self.spotify.connect(self.settings.spotify_client_id)

    def _open_spotify_authorization(self, url: str) -> None:
        self.spotify_status.setText("Finish Spotify sign-in in your browser…")
        if not QDesktopServices.openUrl(QUrl(url)):
            self._spotify_connection_failed("Could not open your browser for Spotify sign-in.")

    def _spotify_connected(self) -> None:
        self.spotify_connect_button.setText("Spotify Connected")
        self.spotify_connect_button.setEnabled(False)
        self.spotify_search.setEnabled(True)
        self.spotify_filter.setEnabled(True)
        self.spotify_results.setEnabled(True)
        self.spotify_status.setText("Connected. Search Spotify tracks, artists, albums, or playlists.")
        self.spotify_search.setFocus()

    def _spotify_connection_failed(self, message: str) -> None:
        self.spotify_connect_button.setEnabled(True)
        self.spotify_status.setText(f"Spotify connection unavailable: {message}")

    def _schedule_spotify_search(self) -> None:
        if not self.spotify.connected_to_spotify:
            return
        self._spotify_search_timer.start(350)

    def _run_spotify_search(self) -> None:
        query = self.spotify_search.text().strip()
        if len(query) < 2:
            self.spotify_results.clear()
            self.spotify_open_button.setEnabled(False)
            self.spotify_status.setText("Type at least two characters to search Spotify.")
            return
        self._spotify_search_request += 1
        self.spotify_results.clear()
        self.spotify_open_button.setEnabled(False)
        self.spotify_status.setText("Searching Spotify…")
        kind = str(self.spotify_filter.currentData() or "track")
        self.spotify.search(query, kind, self._spotify_search_request)

    def _spotify_results_ready(self, request_id: int, results: object) -> None:
        if request_id != self._spotify_search_request:
            return
        self.spotify_results.clear()
        for result in results if isinstance(results, list) else []:
            if not isinstance(result, SpotifyResult):
                continue
            item = QListWidgetItem(f"{result.name}\n       {result.subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.spotify_results.addItem(item)
        total = self.spotify_results.count()
        self.spotify_status.setText(
            f"{total} Spotify result{'s' if total != 1 else ''}. Double-click to open in Spotify."
        )

    def _spotify_search_failed(self, request_id: int, message: str) -> None:
        if request_id == self._spotify_search_request:
            self.spotify_status.setText(f"Spotify search unavailable: {message}")

    def _spotify_selection_changed(self) -> None:
        item = self.spotify_results.currentItem()
        result = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.spotify_open_button.setEnabled(isinstance(result, SpotifyResult) and bool(result.url))

    def _open_selected_spotify(self) -> None:
        item = self.spotify_results.currentItem()
        result = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(result, SpotifyResult) and result.url:
            QDesktopServices.openUrl(QUrl(result.url))

    def _show_add_music(self) -> None:
        if self.importer.busy:
            self._feedback("MUSIC IMPORT IN PROGRESS", 800)
            return
        dialog = AddMusicDialog(self)
        if not dialog.exec():
            return
        self.add_music_button.setEnabled(False)
        self.import_status.setText("Preparing…")
        self.import_status.show()
        self.import_progress.setValue(0)
        self.import_progress.show()
        if dialog.mode == "files":
            started = self.importer.import_local(dialog.files)
        else:
            started = self.importer.download_youtube(dialog.youtube_url, dialog.optional_name)
        if not started:
            self.add_music_button.setEnabled(True)

    def _import_progress_changed(self, percent: int, message: str) -> None:
        self.import_progress.setValue(percent)
        self.import_status.setText(message)

    def _reload_library(self) -> None:
        current_path = self.player.current.path if self.player.current else None
        self.tracks = scan_music(self.project_root / "music")
        self.player.tracks = self.tracks
        if current_path:
            matching = [index for index, track in enumerate(self.tracks) if track.path == current_path]
            if matching:
                self.player.index = matching[0]
            else:
                self.player.stop()
                self.player.index = -1
        self._populate_playlist()

    def _import_completed(self, message: str) -> None:
        self._reload_library()
        self.import_progress.setValue(100)
        self.import_status.setText(message)
        self.add_music_button.setEnabled(True)
        self._feedback("✓  MUSIC ADDED", 1200)
        QTimer.singleShot(4500, self._hide_import_status)

    def _import_failed(self, message: str) -> None:
        self.import_status.setText("Import failed")
        self.import_progress.hide()
        self.add_music_button.setEnabled(True)
        QMessageBox.warning(self, "Could Not Add Music", message)

    def _hide_import_status(self) -> None:
        if not self.importer.busy:
            self.import_status.hide()
            self.import_progress.hide()

    def _discover_and_start_camera(self) -> None:
        if not self.settings.hand_tracking:
            self.camera_view.set_message("Hand control is off")
            return
        self.camera_status.setText("Finding cameras…")
        # Device probing can be slow on Windows and therefore never blocks Qt.
        self.camera.discover_async()

    def _cameras_discovered(self, cameras: list[int]) -> None:
        if not self.settings.hand_tracking:
            return
        self._available_cameras = cameras or [self.settings.camera_index]
        if self.settings.camera_index not in self._available_cameras:
            self.settings.camera_index = self._available_cameras[0]
        self._start_camera()

    def _start_camera(self) -> None:
        self.camera.start(
            self.settings.camera_index,
            self.settings.gesture_sensitivity,
            self.settings.show_landmarks,
            self.settings.control_hand,
        )

    def _toggle_camera(self, enabled: bool) -> None:
        self.settings.hand_tracking = enabled
        if enabled:
            self.camera_view.set_message("Starting camera…")
            self._start_camera()
        else:
            self.camera.stop()
            self.camera_status.setText("Off")
            self.camera_view.set_message("Hand control is off\nMusic and mouse controls remain available")
            self.gesture_text.setText("Waiting…")

    def _camera_status_changed(self, message: str) -> None:
        self.camera_status.setText(message)
        if message != "Camera live":
            self.camera_view.set_message(f"Camera unavailable\n{message}")

    def _gesture_received(self, event: GestureEvent) -> None:
        self.gesture_text.setText(event.label if event.label != "Waiting..." else "Waiting…")
        if event.progress is None:
            self.gesture_progress.hide()
        else:
            self.gesture_progress.setValue(round(event.progress * 100))
            self.gesture_progress.show()
        self.controller.process(event)

    def _gesture_action(self, event: GestureEvent) -> None:
        if event.gesture is Gesture.PLAY_PAUSE:
            self.player.toggle()
            self._feedback("⏯  PLAY / PAUSE")
        elif event.gesture is Gesture.NEXT:
            self.player.next()
            self._feedback("⏭  NEXT TRACK")
        elif event.gesture is Gesture.PREVIOUS:
            self.player.previous()
            self._feedback("⏮  PREVIOUS TRACK")
        elif event.gesture is Gesture.VOLUME_MODE:
            self._feedback("✌  TWO-HAND VOLUME ON", 950)
        elif event.gesture is Gesture.VOLUME and event.volume is not None:
            value = round(event.volume * 100)
            self.volume.blockSignals(True)
            self.volume.setValue(value)
            self.volume.blockSignals(False)
            self._set_volume(event.volume)
            self._feedback(f"🔊  VOLUME {value}%", 520)
        elif event.gesture is Gesture.VOLUME_SAVE:
            self._feedback(f"✓  VOLUME SET · {self.volume.value()}%", 1100)

    def _feedback(self, text: str, duration: int = 950) -> None:
        self.overlay.setText(text)
        self.overlay.adjustSize()
        point = self.centralWidget().rect().center() - self.overlay.rect().center()
        self.overlay.move(point)
        self.overlay.show()
        self.overlay.raise_()
        self.overlay_timer.start(duration)

    def _track_changed(self, track: Track) -> None:
        self.title.setText(track.display_title)
        self.artist.setText(track.artist)
        self.album.setText(track.album)
        self.artwork.set_artwork(track.artwork)
        self.total.setText(format_time(track.duration))
        for row in range(self.playlist.count()):
            if self.playlist.item(row).data(Qt.ItemDataRole.UserRole) == self.player.index:
                self.playlist.setCurrentRow(row)
                break
        self.analyzer.analyze_async(track.path, track.duration)

    def _play_state_changed(self, playing: bool) -> None:
        self.play_button.setText("⏸" if playing else "▶")

    def _set_volume(self, value: float) -> None:
        self.player.set_volume(value)
        self.settings.volume = value
        self.volume_text.setText(f"{round(value * 100)}%")
        if self.player.muted and value > 0:
            self.player.muted = False
            self.mute_button.setText("🔊")

    def _toggle_mute(self) -> None:
        muted = self.player.toggle_mute()
        self.settings.muted = muted
        self.mute_button.setText("🔇" if muted else "🔊")
        self._feedback("🔇  MUTED" if muted else f"🔊  VOLUME {round(self.player.volume * 100)}%", 600)

    def _toggle_shuffle(self) -> None:
        self.player.shuffle = not self.player.shuffle
        self.settings.shuffle = self.player.shuffle
        self.shuffle_button.setStyleSheet("color: #c993ff;" if self.player.shuffle else "")
        self._feedback("SHUFFLE ON" if self.player.shuffle else "SHUFFLE OFF", 600)

    def _cycle_repeat(self) -> None:
        modes = ["off", "playlist", "track"]
        self.player.repeat_mode = modes[(modes.index(self.player.repeat_mode) + 1) % len(modes)]
        self.settings.repeat_mode = self.player.repeat_mode
        self.repeat_button.setText("↻¹" if self.player.repeat_mode == "track" else "↻")
        self.repeat_button.setStyleSheet("color: #c993ff;" if self.player.repeat_mode != "off" else "")
        self._feedback(f"REPEAT {self.player.repeat_mode.upper()}", 600)

    def _seek_released(self) -> None:
        self._seeking = False
        if self.player.current:
            self.player.seek(self.progress.value() / 1000 * self.player.current.duration)

    def _animate(self) -> None:
        self.visualizer.set_data(self.analyzer.levels_at(self.player.position))

    def _update_status(self) -> None:
        if self.player.current:
            position = self.player.position
            self.elapsed.setText(format_time(position))
            if not self._seeking and self.player.current.duration:
                self.progress.setValue(round(position / self.player.current.duration * 1000))
            self.player.poll_finished()

    def _set_visualizer_mode(self, mode: str) -> None:
        self.settings.visualizer_mode = mode
        self.visualizer.mode = mode
        for button in self.mode_buttons:
            button.setChecked(button.text() == mode)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self._available_cameras, self)
        if dialog.exec():
            old_camera = self.settings.camera_index
            self.settings = dialog.result_settings
            self._apply_settings(restart_camera=self.settings.hand_tracking)
            if old_camera != self.settings.camera_index:
                self.camera_status.setText(f"Camera {self.settings.camera_index}")

    def _apply_settings(self, restart_camera: bool) -> None:
        self.controller.cooldown = self.settings.gesture_cooldown
        self.visualizer.mode = self.settings.visualizer_mode
        self.visualizer.sensitivity = self.settings.visualizer_sensitivity
        self.player.volume = self.settings.volume
        self.player.muted = self.settings.muted
        self.player.shuffle = self.settings.shuffle
        self.player.repeat_mode = self.settings.repeat_mode
        self.player.set_volume(self.settings.volume)
        self.camera_toggle.blockSignals(True)
        self.camera_toggle.setChecked(self.settings.hand_tracking)
        self.camera_toggle.blockSignals(False)
        self._set_visualizer_mode(self.settings.visualizer_mode)
        if restart_camera:
            self._start_camera()
        elif not self.settings.hand_tracking:
            self.camera.stop()
            self.camera_status.setText("Off")
            self.camera_view.set_message("Hand control is off\nMusic and mouse controls remain available")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Music HandControl", message)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.player.toggle()
        elif key == Qt.Key.Key_Right:
            self.player.next()
        elif key == Qt.Key.Key_Left:
            self.player.previous()
        elif key == Qt.Key.Key_Up:
            self.volume.setValue(min(100, self.volume.value() + 5))
        elif key == Qt.Key.Key_Down:
            self.volume.setValue(max(0, self.volume.value() - 5))
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.importer.busy:
            QMessageBox.information(
                self,
                "Music Import in Progress",
                "Please wait for the current music import to finish before closing Music HandControl.",
            )
            event.ignore()
            return
        self.camera.stop()
        self.player.close()
        self.settings_store.save(self.settings)
        event.accept()
