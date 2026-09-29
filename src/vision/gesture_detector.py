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

    TRACK_HOLD = 2.0
    OPEN_PALM_HOLD = 0.85

    def __init__(self, sensitivity: str = "Medium") -> None:
        self.sensitivity = sensitivity
        self._pinch_hand: str | None = None
        self._pinch_started_at: float | None = None
        self._pinch_fired = False
        self._volume_mode = False
        self._open_palm_at: float | None = None
        self._open_palm_sent = False

    @property
    def volume_mode(self) -> bool:
        return self._volume_mode

    def reset(self, clear_mode: bool = False) -> None:
        self._reset_pinch()
        self._open_palm_at = None
        self._open_palm_sent = False
        if clear_mode:
            self._volume_mode = False

    def _reset_pinch(self) -> None:
        self._pinch_hand = None
        self._pinch_started_at = None
        self._pinch_fired = False

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _extended(points: list[Point], tip: int, pip: int, mcp: int) -> bool:
        return points[tip].y < points[pip].y - 0.012 and points[pip].y < points[mcp].y + 0.04

    @classmethod
    def _hand_state(cls, points: list[Point]) -> tuple[list[bool], float, float]:
        palm_width = max(cls._distance(points[5], points[17]), 0.04)
        fingers = [
            cls._extended(points, 8, 6, 5),
            cls._extended(points, 12, 10, 9),
            cls._extended(points, 16, 14, 13),
            cls._extended(points, 20, 18, 17),
        ]
        thumb_index = cls._distance(points[4], points[8]) / palm_width
        return fingers, thumb_index, palm_width

    def update(
        self, landmarks: list[Point], handedness: str = "Unknown", now: float | None = None
    ) -> GestureEvent:
        confidence = 1.0 if handedness != "Unknown" else 0.0
        return self.update_hands([(landmarks, handedness, confidence)], now=now)

    def update_hands(
        self,
        hands: list[tuple[list[Point], str, float]],
        control_hand: str = "Auto",
        now: float | None = None,
    ) -> GestureEvent:
        now = time.monotonic() if now is None else now
        valid_hands = [
            (points, handedness.title(), confidence)
            for points, handedness, confidence in hands
            if len(points) == 21
        ]
        pinch_on = {"Low": 0.24, "Medium": 0.30, "High": 0.36}.get(self.sensitivity, 0.30)
        pinch_off = pinch_on + 0.17

        states = [
            (points, handedness, confidence, *self._hand_state(points))
            for points, handedness, confidence in valid_hands
        ]
        peace_hands = [
            state
            for state in states
            if state[3][0] and state[3][1] and not state[3][2] and not state[3][3] and state[4] > pinch_off
        ]
        volume_pair = None
        for anchor in sorted(peace_hands, key=lambda state: state[2], reverse=True):
            other_hands = [state for state in states if state is not anchor]
            if other_hands:
                volume_pair = (anchor, max(other_hands, key=lambda state: state[2]))
                break

        if volume_pair is not None:
            _, controller = volume_pair
            self._reset_pinch()
            self._open_palm_at = None
            self._open_palm_sent = False
            if not self._volume_mode:
                self._volume_mode = True
                return GestureEvent(
                    Gesture.VOLUME_MODE,
                    1.0,
                    handedness=controller[1],
                    label="Two-Hand Volume On",
                )
            normalized = max(0.0, min((controller[4] - 0.20) / 1.55, 1.0))
            smooth = normalized * normalized * (3.0 - 2.0 * normalized)
            return GestureEvent(
                Gesture.VOLUME,
                0.85,
                volume=smooth,
                handedness=controller[1],
                label=f"Pinch Distance · Volume {round(smooth * 100)}%",
            )

        if self._volume_mode:
            self._volume_mode = False
            self._reset_pinch()
            self._open_palm_at = None
            self._open_palm_sent = False
            return GestureEvent(
                Gesture.VOLUME_SAVE,
                1.0,
                label="Volume Set · Peace Sign Released",
            )

        candidates = [state for state in states if control_hand == "Auto" or state[1] == control_hand]
        if not candidates:
            self.reset()
            return GestureEvent(Gesture.NONE)
        _points, handedness, _confidence, fingers, thumb_index, _palm_width = max(
            candidates, key=lambda state: (state[2], state[5])
        )

        active_threshold = pinch_off if self._pinch_hand == handedness else pinch_on
        index_pinched = thumb_index <= active_threshold
        if index_pinched and handedness in {"Left", "Right"}:
            self._open_palm_at = None
            self._open_palm_sent = False
            if self._pinch_hand != handedness or self._pinch_started_at is None:
                self._pinch_hand = handedness
                self._pinch_started_at = now
                self._pinch_fired = False
            progress = min(1.0, max(0.0, (now - self._pinch_started_at) / self.TRACK_HOLD))
            action = Gesture.NEXT if handedness == "Right" else Gesture.PREVIOUS
            action_name = "Next" if action is Gesture.NEXT else "Previous"
            if self._pinch_fired:
                return GestureEvent(
                    Gesture.NONE,
                    handedness=handedness,
                    label=f"{action_name} complete · Release pinch",
                    progress=1.0,
                )
            if progress >= 1.0:
                self._pinch_fired = True
                return GestureEvent(
                    action,
                    1.0,
                    handedness=handedness,
                    label=f"{action_name} Track",
                    progress=1.0,
                )
            return GestureEvent(
                Gesture.NONE,
                handedness=handedness,
                label=f"Hold for {action_name} · {round(progress * 100)}%",
                progress=progress,
            )
        self._reset_pinch()

        open_palm = all(fingers) and thumb_index > 0.62
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
