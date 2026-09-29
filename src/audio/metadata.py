from __future__ import annotations

import logging
import re
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import APIC

from src.models import Track

LOGGER = logging.getLogger(__name__)
MAX_MP3_BYTES = 512 * 1024 * 1024
MAX_ARTWORK_BYTES = 8 * 1024 * 1024
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _safe_text(value: object, fallback: str, limit: int = 180) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    cleaned = CONTROL_CHARS.sub(" ", str(value or "")).strip()
    return cleaned[:limit] or fallback


def read_track(path: Path, music_dir: Path) -> Track | None:
    """Read MP3 metadata without trusting metadata as code or a filesystem path."""
    try:
        resolved = path.resolve(strict=True)
        root = music_dir.resolve(strict=True)
        if resolved.parent != root or resolved.suffix.lower() != ".mp3":
            return None
        if not resolved.is_file() or resolved.stat().st_size > MAX_MP3_BYTES:
            return None
        audio = MutagenFile(resolved)
        duration = float(getattr(getattr(audio, "info", None), "length", 0.0) or 0.0)
        tags = getattr(audio, "tags", None)
        title = _safe_text(tags.get("TIT2") if tags else None, resolved.stem)
        artist = _safe_text(tags.get("TPE1") if tags else None, "Unknown Artist")
        album = _safe_text(tags.get("TALB") if tags else None, "Unknown Album")
        artwork = None
        if tags:
            pictures = [value for value in tags.values() if isinstance(value, APIC)]
            if pictures and len(pictures[0].data) <= MAX_ARTWORK_BYTES:
                artwork = bytes(pictures[0].data)
        return Track(resolved, title, artist, album, max(0.0, duration), artwork)
    except Exception as exc:  # corrupt media can raise several backend-specific errors
        LOGGER.warning("Skipped unreadable MP3 %s: %s", path.name, exc)
        return None


def scan_music(music_dir: Path) -> list[Track]:
    music_dir.mkdir(parents=True, exist_ok=True)
    tracks: list[Track] = []
    for path in sorted(music_dir.iterdir(), key=lambda item: item.name.casefold()):
        if path.is_file() and path.suffix.lower() == ".mp3":
            track = read_track(path, music_dir)
            if track:
                tracks.append(track)
    return tracks
