from __future__ import annotations

import time
from collections.abc import Callable

from src.models import Gesture, GestureEvent


class GestureController:
    """Debounces discrete gestures and smooths continuous volume events."""

    def __init__(self, cooldown: float = 1.0) -> None:
        self.cooldown = cooldown
        self._last_action: dict[Gesture, float] = {}
        self._locked: Gesture | None = None
        self._volume = 0.72
        self._last_volume_emit = 0.0
        self.on_action: Callable[[GestureEvent], None] | None = None

    def process(self, event: GestureEvent, now: float | None = None) -> GestureEvent | None:
        now = time.monotonic() if now is None else now
        if event.gesture is Gesture.NONE:
            self._locked = None
            return None
        if event.gesture is Gesture.VOLUME and event.volume is not None:
            self._locked = None
            self._volume = self._volume * 0.78 + event.volume * 0.22
            if now - self._last_volume_emit < 1 / 15:
                return None
            self._last_volume_emit = now
            emitted = GestureEvent(
                Gesture.VOLUME,
                event.confidence,
                self._volume,
                event.handedness,
                f"Volume Mode · {round(self._volume * 100)}%",
            )
            if self.on_action:
                self.on_action(emitted)
            return emitted
        if self._locked is event.gesture:
            return None
        if now - self._last_action.get(event.gesture, -10.0) < self.cooldown:
            return None
        self._locked = event.gesture
        self._last_action[event.gesture] = now
        if self.on_action:
            self.on_action(event)
        return event
