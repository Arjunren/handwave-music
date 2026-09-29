from __future__ import annotations

import math
import time
from dataclasses import dataclass

from src.models import Gesture, GestureEvent


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
    z: float = 0.0


class GestureDetector:
    """Stateful landmark interpreter independent from MediaPipe and playback."""

    VOLUME_ACTIVATION_DELAY = 0.45
    DOUBLE_PINCH_WINDOW = 0.58
    OPEN_PALM_HOLD = 0.85

    def __init__(self, sensitivity: str = "Medium") -> None:
        self.sensitivity = sensitivity
        self._index_down = False
        self._middle_down = False
        self._volume_mode = False
        self._volume_activation_at: float | None = None
        self._save_first_at: float | None = None
        self._open_palm_at: float | None = None
        self._open_palm_sent = False

    @property
    def volume_mode(self) -> bool:
        return self._volume_mode

    def reset(self, clear_mode: bool = False) -> None:
        self._index_down = False
        self._middle_down = False
        self._volume_activation_at = None
        self._save_first_at = None
        self._open_palm_at = None
        self._open_palm_sent = False
        if clear_mode:
            self._volume_mode = False

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _extended(points: list[Point], tip: int, pip: int, mcp: int) -> bool:
        return points[tip].y < points[pip].y - 0.012 and points[pip].y < points[mcp].y + 0.04

    def update(
        self, landmarks: list[Point], handedness: str = "Unknown", now: float | None = None
    ) -> GestureEvent:
        now = time.monotonic() if now is None else now
        if len(landmarks) != 21:
            self.reset()
            return GestureEvent(Gesture.NONE)
        palm_width = max(self._distance(landmarks[5], landmarks[17]), 0.04)
        fingers = [
            self._extended(landmarks, 8, 6, 5),
            self._extended(landmarks, 12, 10, 9),
            self._extended(landmarks, 16, 14, 13),
            self._extended(landmarks, 20, 18, 17),
        ]
        thumb_index = self._distance(landmarks[4], landmarks[8]) / palm_width
        thumb_middle = self._distance(landmarks[4], landmarks[12]) / palm_width
        pinch_on = {"Low": 0.24, "Medium": 0.30, "High": 0.36}.get(self.sensitivity, 0.30)
        pinch_off = pinch_on + 0.17
        index_now = thumb_index <= (pinch_off if self._index_down else pinch_on)
        middle_now = thumb_middle <= (pinch_off if self._middle_down else pinch_on)
        index_pressed = index_now and not self._index_down
        middle_pressed = middle_now and not self._middle_down
        self._index_down = index_now
        self._middle_down = middle_now
        handedness = handedness.title()

        if self._volume_mode:
            self._open_palm_at = None
            self._open_palm_sent = False
            if self._save_first_at is not None and now - self._save_first_at > self.DOUBLE_PINCH_WINDOW:
                self._save_first_at = None
            if middle_pressed:
                if self._save_first_at is not None:
                    self._save_first_at = None
                    self._volume_mode = False
                    return GestureEvent(
                        Gesture.VOLUME_SAVE,
                        1.0,
                        handedness=handedness,
                        label="Volume Saved",
                    )
                self._save_first_at = now
            if middle_now:
                return GestureEvent(
                    Gesture.NONE,
                    handedness=handedness,
                    label="Pinch middle + thumb again to save",
                )
            normalized = max(0.0, min((thumb_index - 0.22) / 1.65, 1.0))
            smooth = normalized * normalized * (3.0 - 2.0 * normalized)
            return GestureEvent(
                Gesture.VOLUME,
                0.85,
                volume=smooth,
                handedness=handedness,
                label=f"Volume Mode · {round(smooth * 100)}%",
            )

        if middle_pressed and self._volume_activation_at is None:
            self._volume_activation_at = now
        if self._volume_activation_at is not None:
            self._open_palm_at = None
            if now - self._volume_activation_at >= self.VOLUME_ACTIVATION_DELAY:
                self._volume_activation_at = None
                self._volume_mode = True
                self._save_first_at = None
                return GestureEvent(
                    Gesture.VOLUME_MODE,
                    1.0,
                    handedness=handedness,
                    label="Volume Mode On",
                )
            return GestureEvent(
                Gesture.NONE,
                handedness=handedness,
                label="Entering Volume Mode…",
            )

        if index_pressed:
            self._open_palm_at = None
            self._open_palm_sent = False
            if handedness == "Right":
                return GestureEvent(
                    Gesture.NEXT,
                    1.0,
                    handedness=handedness,
                    label="Right Index Pinch · Next",
                )
            if handedness == "Left":
                return GestureEvent(
                    Gesture.PREVIOUS,
                    1.0,
                    handedness=handedness,
                    label="Left Index Pinch · Previous",
                )

        open_palm = all(fingers) and thumb_index > 0.62 and thumb_middle > 0.62
        if open_palm:
            if self._open_palm_at is None:
                self._open_palm_at = now
            if not self._open_palm_sent and now - self._open_palm_at >= self.OPEN_PALM_HOLD:
                self._open_palm_sent = True
                confidence = min(1.0, 0.68 + thumb_index * 0.12)
                return GestureEvent(
                    Gesture.PLAY_PAUSE,
                    confidence,
                    handedness=handedness,
                    label="Open Palm Hold · Play / Pause",
                )
            return GestureEvent(
                Gesture.NONE,
                handedness=handedness,
                label="Hold palm for Play / Pause",
            )
        self._open_palm_at = None
        self._open_palm_sent = False
        return GestureEvent(Gesture.NONE, handedness=handedness)
