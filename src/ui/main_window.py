from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.audio.analyzer import AudioAnalyzer
from src.audio.audio_player import AudioPlayer
from src.config.settings import AppSettings, SettingsStore
from src.models import Gesture, GestureEvent, Track
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
        self._seeking = False
        self._available_cameras = [settings.camera_index]
        self.setWindowTitle("HandWave Music")
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
        brand = QLabel("HANDWAVE  MUSIC")
        brand.setObjectName("Brand")
        subtitle = QLabel("Gesture-powered listening")
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

        playlist_card, playlist_layout = self._card()
        playlist_card.setFixedWidth(270)
        playlist_header = QLabel("YOUR MUSIC")
        playlist_header.setObjectName("Eyebrow")
        playlist_layout.addWidget(playlist_header)
        self.playlist_count = QLabel("0 tracks")
        self.playlist_count.setObjectName("Muted")
        playlist_layout.addWidget(self.playlist_count)
        self.playlist = QListWidget()
        self.playlist.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        playlist_layout.addWidget(self.playlist, 1)
        self.empty_message = QLabel("No music found.\n\nAdd MP3 files inside\nthe /music folder.")
        self.empty_message.setObjectName("Empty")
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message.setWordWrap(True)
        playlist_layout.addWidget(self.empty_message)
        content.addWidget(playlist_card)

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
        self.playlist.itemClicked.connect(lambda item: self.player.play_index(self.playlist.row(item)))
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
        self.player.on_track_changed = self._track_changed
        self.player.on_state_changed = self._play_state_changed
        self.player.on_error = self._show_error
        self.camera.frame_ready.connect(self.camera_view.set_frame)
        self.camera.gesture_ready.connect(self._gesture_received)
        self.camera.status_changed.connect(self._camera_status_changed)
        self.camera.cameras_found.connect(self._cameras_discovered)
        self.controller.on_action = self._gesture_action
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
        self.playlist.clear()
        for number, track in enumerate(self.tracks, 1):
            item = QListWidgetItem(f"{number:02d}   {track.display_title}\n       {track.artist}")
            item.setToolTip(track.path.name)
            self.playlist.addItem(item)
        self.playlist_count.setText(f"{len(self.tracks)} track{'s' if len(self.tracks) != 1 else ''}")
        self.empty_message.setVisible(not self.tracks)
        self.playlist.setVisible(bool(self.tracks))

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
        self.gesture_text.setText(event.label if event.gesture is not Gesture.NONE else "Waiting…")
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
        elif event.gesture is Gesture.VOLUME and event.volume is not None:
            value = round(event.volume * 100)
            self.volume.blockSignals(True)
            self.volume.setValue(value)
            self.volume.blockSignals(False)
            self._set_volume(event.volume)
            self._feedback(f"🔊  VOLUME {value}%", 520)

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
        self.playlist.setCurrentRow(self.player.index)
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

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "HandWave Music", message)

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
        self.camera.stop()
        self.player.close()
        self.settings_store.save(self.settings)
        event.accept()
