from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

from src.models import Gesture, GestureEvent


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
    z: float = 0.0


class GestureDetector:
    """Stateful landmark interpreter independent from MediaPipe and playback."""

    def __init__(self, sensitivity: str = "Medium") -> None:
        self.sensitivity = sensitivity
        self.motion: deque[tuple[float, float]] = deque(maxlen=18)
        self._last_seen = 0.0

    def reset(self) -> None:
        self.motion.clear()

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
        wrist = landmarks[0]
        palm_width = max(self._distance(landmarks[5], landmarks[17]), 0.04)
        fingers = [
            self._extended(landmarks, 8, 6, 5),
            self._extended(landmarks, 12, 10, 9),
            self._extended(landmarks, 16, 14, 13),
            self._extended(landmarks, 20, 18, 17),
        ]
        thumb_index = self._distance(landmarks[4], landmarks[8]) / palm_width

        self.motion.append((now, wrist.x))
        while self.motion and now - self.motion[0][0] > 0.55:
            self.motion.popleft()
        self._last_seen = now

        threshold = {"Low": 0.25, "Medium": 0.20, "High": 0.16}.get(self.sensitivity, 0.20)
        if len(self.motion) >= 5:
            elapsed = self.motion[-1][0] - self.motion[0][0]
            delta = self.motion[-1][1] - self.motion[0][1]
            velocity = abs(delta) / max(elapsed, 0.01)
            if abs(delta) >= threshold and velocity >= 0.38:
                self.motion.clear()
                if delta > 0:
                    return GestureEvent(
                        Gesture.NEXT, min(1.0, velocity), handedness=handedness, label="Swipe Right · Next"
                    )
                return GestureEvent(
                    Gesture.PREVIOUS, min(1.0, velocity), handedness=handedness, label="Swipe Left · Previous"
                )

        if all(fingers) and thumb_index > 0.62:
            confidence = min(1.0, 0.68 + thumb_index * 0.12)
            return GestureEvent(Gesture.PLAY_PAUSE, confidence, handedness=handedness, label="Open Palm")

        # Pinch volume is only active with the other fingers folded, preventing
        # an open palm from also controlling volume.
        if sum(fingers[1:]) <= 1:
            normalized = max(0.0, min((thumb_index - 0.22) / 1.65, 1.0))
            smooth = normalized * normalized * (3.0 - 2.0 * normalized)
            return GestureEvent(
                Gesture.VOLUME,
                0.85,
                volume=smooth,
                handedness=handedness,
                label=f"Pinch Volume · {round(smooth * 100)}%",
            )
        return GestureEvent(Gesture.NONE, handedness=handedness)
