from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class Visualizer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.mode = "Spectrum"
        self.sensitivity = 1.0
        self.target = np.zeros(48, dtype=np.float32)
        self.levels = np.zeros(48, dtype=np.float32)

    def set_data(self, levels: np.ndarray) -> None:
        if len(levels):
            self.target = np.resize(levels.astype(np.float32), 48)
        rising = self.target > self.levels
        self.levels[rising] += (self.target[rising] - self.levels[rising]) * 0.48
        self.levels[~rising] += (self.target[~rising] - self.levels[~rising]) * 0.13
        self.levels = np.clip(self.levels * self.sensitivity, 0.015, 1.0)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#121621"))
        if self.mode == "Wave":
            self._paint_wave(painter)
        elif self.mode == "Circular":
            self._paint_circular(painter)
        else:
            self._paint_spectrum(painter)

    def _paint_spectrum(self, painter: QPainter) -> None:
        margin, gap = 18.0, 3.0
        width = max(2.0, (self.width() - margin * 2 - gap * 47) / 48)
        usable = self.height() - 34
        gradient = QLinearGradient(0, self.height(), 0, 10)
        gradient.setColorAt(0, QColor("#5b4dff"))
        gradient.setColorAt(0.55, QColor("#aa5cff"))
        gradient.setColorAt(1, QColor("#68edff"))
        for index, level in enumerate(self.levels):
            height = max(4.0, float(level) * usable)
            x = margin + index * (width + gap)
            rect = QRectF(x, self.height() - 18 - height, width, height)
            glow = QColor(166, 92, 255, 35)
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 3), width / 2 + 2, width / 2 + 2)
            painter.setBrush(gradient)
            painter.drawRoundedRect(rect, width / 2, width / 2)

    def _paint_wave(self, painter: QPainter) -> None:
        center = self.height() / 2
        amplitude = self.height() * 0.40
        path = QPainterPath(QPointF(0, center))
        for x in range(self.width()):
            position = x / max(1, self.width() - 1) * (len(self.levels) - 1)
            index = int(position)
            level = float(self.levels[index])
            y = center + math.sin(position * 1.9) * amplitude * level
            path.lineTo(x, y)
        glow_pen = QPen(QColor(166, 92, 255, 50), 11)
        painter.setPen(glow_pen)
        painter.drawPath(path)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor("#6956ff"))
        gradient.setColorAt(0.5, QColor("#c167ff"))
        gradient.setColorAt(1, QColor("#68edff"))
        painter.setPen(QPen(gradient, 3))
        painter.drawPath(path)

    def _paint_circular(self, painter: QPainter) -> None:
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.22
        glow = QRadialGradient(center, radius * 1.5)
        glow.setColorAt(0, QColor(166, 92, 255, 55))
        glow.setColorAt(1, QColor(166, 92, 255, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius * 1.5, radius * 1.5)
        for index, level in enumerate(self.levels):
            angle = index / len(self.levels) * math.tau - math.pi / 2
            length = 5 + float(level) * radius * 0.72
            start = QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius)
            end = QPointF(
                center.x() + math.cos(angle) * (radius + length),
                center.y() + math.sin(angle) * (radius + length),
            )
            color = QColor.fromHsvF(0.70 + 0.14 * index / len(self.levels), 0.58, 1.0)
            painter.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(start, end)
