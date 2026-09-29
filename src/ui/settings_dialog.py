from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from src.config.settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, cameras: list[int], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HandWave Settings")
        self.setMinimumWidth(430)
        self.result_settings = replace(settings)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        title = QLabel("SETTINGS")
        title.setObjectName("Eyebrow")
        layout.addWidget(title)
        form = QFormLayout()
        form.setVerticalSpacing(17)
        form.setHorizontalSpacing(20)
        self.camera = QComboBox()
        camera_values = cameras or [settings.camera_index]
        self.camera.addItems([f"Camera {value}" for value in camera_values])
        self.camera.setCurrentText(f"Camera {settings.camera_index}")
        form.addRow("Camera", self.camera)
        self.sensitivity = QComboBox()
        self.sensitivity.addItems(["Low", "Medium", "High"])
        self.sensitivity.setCurrentText(settings.gesture_sensitivity)
        form.addRow("Gesture sensitivity", self.sensitivity)
        self.cooldown = QDoubleSpinBox()
        self.cooldown.setRange(0.4, 2.5)
        self.cooldown.setSingleStep(0.1)
        self.cooldown.setSuffix(" s")
        self.cooldown.setValue(settings.gesture_cooldown)
        form.addRow("Gesture cooldown", self.cooldown)
        self.control_hand = QComboBox()
        self.control_hand.addItems(["Auto", "Left", "Right"])
        self.control_hand.setCurrentText(settings.control_hand)
        form.addRow("Control hand", self.control_hand)
        self.visualizer = QComboBox()
        self.visualizer.addItems(["Spectrum", "Wave", "Circular"])
        self.visualizer.setCurrentText(settings.visualizer_mode)
        form.addRow("Visualizer", self.visualizer)
        self.visualizer_sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.visualizer_sensitivity.setRange(50, 200)
        self.visualizer_sensitivity.setValue(round(settings.visualizer_sensitivity * 100))
        form.addRow("Visualizer sensitivity", self.visualizer_sensitivity)
        self.landmarks = QComboBox()
        self.landmarks.addItems(["On", "Off"])
        self.landmarks.setCurrentText("On" if settings.show_landmarks else "Off")
        form.addRow("Hand landmarks", self.landmarks)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self.result_settings.camera_index = int(self.camera.currentText().split()[-1])
        self.result_settings.gesture_sensitivity = self.sensitivity.currentText()
        self.result_settings.gesture_cooldown = self.cooldown.value()
        self.result_settings.control_hand = self.control_hand.currentText()
        self.result_settings.visualizer_mode = self.visualizer.currentText()
        self.result_settings.visualizer_sensitivity = self.visualizer_sensitivity.value() / 100
        self.result_settings.show_landmarks = self.landmarks.currentText() == "On"
        self.accept()
