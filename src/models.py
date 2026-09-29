from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class Gesture(Enum):
    NONE = auto()
    PLAY_PAUSE = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME_MODE = auto()
    VOLUME = auto()
    VOLUME_SAVE = auto()


@dataclass(frozen=True, slots=True)
class GestureEvent:
    gesture: Gesture
    confidence: float = 0.0
    volume: float | None = None
    handedness: str = "Unknown"
    label: str = "Waiting..."
    progress: float | None = None


@dataclass(frozen=True, slots=True)
class Track:
    path: Path
    title: str
    artist: str = "Unknown Artist"
    album: str = "Unknown Album"
    duration: float = 0.0
    artwork: bytes | None = None

    @property
    def display_title(self) -> str:
        return self.title or self.path.stem
