from __future__ import annotations

import json
import re
from pathlib import Path


class LocalGroupStore:
    """Persist named groups of local MP3 filenames only."""

    _CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

    def __init__(self, path: Path) -> None:
        self.path = path
        self._groups: dict[str, list[str]] = {}
        self.load()

    @property
    def names(self) -> list[str]:
        return sorted(self._groups, key=str.casefold)

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            groups: dict[str, list[str]] = {}
            for raw_name, raw_tracks in raw.items():
                name = self._clean_name(raw_name)
                if not name or not isinstance(raw_tracks, list):
                    continue
                tracks = sorted(
                    {
                        Path(str(track)).name
                        for track in raw_tracks
                        if Path(str(track)).name.lower().endswith(".mp3")
                    },
                    key=str.casefold,
                )
                groups[name] = tracks
            self._groups = groups
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._groups = {}

    def create(self, value: str) -> str:
        name = self._clean_name(value)
        if not name:
            raise ValueError("Enter a group name.")
        if any(existing.casefold() == name.casefold() for existing in self._groups):
            raise ValueError("A group with that name already exists.")
        self._groups[name] = []
        self._save()
        return name

    def delete(self, name: str) -> None:
        if name in self._groups:
            del self._groups[name]
            self._save()

    def add_track(self, name: str, filename: str) -> None:
        if name not in self._groups:
            raise ValueError("Choose a valid local group.")
        safe_filename = Path(filename).name
        if not safe_filename.lower().endswith(".mp3"):
            raise ValueError("Only local MP3 files can be grouped.")
        if safe_filename not in self._groups[name]:
            self._groups[name].append(safe_filename)
            self._groups[name].sort(key=str.casefold)
            self._save()

    def tracks_for(self, name: str) -> set[str]:
        return set(self._groups.get(name, []))

    def prune(self, available_filenames: set[str]) -> None:
        changed = False
        for name, tracks in self._groups.items():
            remaining = [track for track in tracks if track in available_filenames]
            if remaining != tracks:
                self._groups[name] = remaining
                changed = True
        if changed:
            self._save()

    @classmethod
    def _clean_name(cls, value: object) -> str:
        return cls._CONTROL_CHARS.sub(" ", str(value or "")).strip()[:60]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._groups, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)
