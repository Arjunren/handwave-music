from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class ArtworkWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(184, 184)
        self._image: QImage | None = None

    def set_artwork(self, data: bytes | None) -> None:
        image = QImage()
        self._image = image if data and image.loadFromData(data) else None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 20, 20)
        painter.setClipPath(path)
        if self._image and not self._image.isNull():
            pixmap = QPixmap.fromImage(self._image).scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(self.rect(), pixmap)
        else:
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, QColor("#4e2b7e"))
            gradient.setColorAt(0.55, QColor("#161d3e"))
            gradient.setColorAt(1, QColor("#0e5660"))
            painter.fillRect(self.rect(), gradient)
            painter.setPen(QColor(255, 255, 255, 215))
            painter.setFont(QFont("Segoe UI Symbol", 58, QFont.Weight.DemiBold))
            painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, "♫")
