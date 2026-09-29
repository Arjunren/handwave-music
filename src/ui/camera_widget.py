from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel


class CameraView(QLabel):
    def __init__(self) -> None:
        super().__init__("Hand control is off")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(440, 270)
        self.setStyleSheet("background: #080a10; border-radius: 14px; color: #6f778a;")
        self._image: QImage | None = None

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self._refresh()

    def set_message(self, message: str) -> None:
        self._image = None
        self.setText(message)
        self.setPixmap(QPixmap())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._image:
            pixmap = QPixmap.fromImage(self._image).scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(pixmap)
