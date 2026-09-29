from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AppSettings:
    hand_tracking: bool = True
    camera_index: int = 0
    gesture_sensitivity: str = "Medium"
    gesture_cooldown: float = 1.0
    visualizer_mode: str = "Spectrum"
    visualizer_sensitivity: float = 1.0
    show_landmarks: bool = True
    control_hand: str = "Auto"
    volume: float = 0.72
    muted: bool = False
    shuffle: bool = False
    repeat_mode: str = "playlist"

    def normalize(self) -> None:
        self.camera_index = max(0, min(int(self.camera_index), 9))
        self.gesture_sensitivity = (
            self.gesture_sensitivity if self.gesture_sensitivity in {"Low", "Medium", "High"} else "Medium"
        )
        self.gesture_cooldown = max(0.4, min(float(self.gesture_cooldown), 2.5))
        self.visualizer_mode = (
            self.visualizer_mode if self.visualizer_mode in {"Spectrum", "Wave", "Circular"} else "Spectrum"
        )
        self.visualizer_sensitivity = max(0.5, min(float(self.visualizer_sensitivity), 2.0))
        self.control_hand = self.control_hand if self.control_hand in {"Auto", "Left", "Right"} else "Auto"
        self.volume = max(0.0, min(float(self.volume), 1.0))
        self.repeat_mode = (
            self.repeat_mode if self.repeat_mode in {"off", "playlist", "track"} else "playlist"
        )


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings root must be an object")
            allowed = {field.name for field in fields(AppSettings)}
            settings = AppSettings(**{key: value for key, value in raw.items() if key in allowed})
            settings.normalize()
            return settings
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            LOGGER.exception("Could not load settings; using safe defaults")
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        settings.normalize()
        try:
            self.path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        except OSError:
            LOGGER.exception("Could not save settings")
