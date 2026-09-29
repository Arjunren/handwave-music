from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable

from src.models import Track

LOGGER = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self, tracks: list[Track]) -> None:
        self.tracks = tracks
        self.index = -1
        self.volume = 0.72
        self.muted = False
        self.shuffle = False
        self.repeat_mode = "playlist"
        self.playing = False
        self.paused = False
        self._offset = 0.0
        self._started_at = 0.0
        self._lock = threading.RLock()
        self.on_track_changed: Callable[[Track], None] | None = None
        self.on_state_changed: Callable[[bool], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.available = False
        self.initialization_error = ""
        try:
            import pygame

            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.set_endevent()
            self.available = True
        except Exception as exc:
            LOGGER.exception("Audio initialization failed")
            self.initialization_error = f"Audio device unavailable: {exc}"
            self._error(self.initialization_error)

    @property
    def current(self) -> Track | None:
        return self.tracks[self.index] if 0 <= self.index < len(self.tracks) else None

    def _error(self, message: str) -> None:
        if self.on_error:
            self.on_error(message)

    def play_index(self, index: int, start: float = 0.0) -> bool:
        if not self.tracks or not self.available:
            return False
        index %= len(self.tracks)
        try:
            import pygame

            with self._lock:
                track = self.tracks[index]
                pygame.mixer.music.load(str(track.path))
                pygame.mixer.music.set_volume(0.0 if self.muted else self.volume)
                pygame.mixer.music.play(start=max(0.0, start))
                self.index = index
                self._offset = max(0.0, start)
                self._started_at = time.monotonic()
                self.playing = True
                self.paused = False
            if self.on_track_changed:
                self.on_track_changed(track)
            if self.on_state_changed:
                self.on_state_changed(True)
            return True
        except Exception as exc:
            LOGGER.exception("Could not play track")
            self._error(f"Could not play {self.tracks[index].path.name}: {exc}")
            return False

    def toggle(self) -> bool:
        if not self.current:
            return self.play_index(0)
        try:
            import pygame

            if self.paused:
                pygame.mixer.music.unpause()
                self._started_at = time.monotonic()
                self.paused = False
                self.playing = True
            elif self.playing:
                self._offset = self.position
                pygame.mixer.music.pause()
                self.paused = True
                self.playing = False
            else:
                return self.play_index(self.index)
            if self.on_state_changed:
                self.on_state_changed(self.playing)
            return True
        except Exception as exc:
            self._error(f"Playback control failed: {exc}")
            return False

    def next(self, automatic: bool = False) -> bool:
        if not self.tracks:
            return False
        if automatic and self.repeat_mode == "track":
            target = self.index
        elif self.shuffle and len(self.tracks) > 1:
            choices = [value for value in range(len(self.tracks)) if value != self.index]
            target = random.choice(choices)
        else:
            target = self.index + 1
            if target >= len(self.tracks) and self.repeat_mode == "off":
                self.stop()
                return False
        return self.play_index(target)

    def previous(self) -> bool:
        if self.position > 4.0:
            return self.seek(0.0)
        return self.play_index(self.index - 1)

    def seek(self, seconds: float) -> bool:
        if not self.current:
            return False
        seconds = max(0.0, min(seconds, self.current.duration or seconds))
        was_paused = self.paused
        success = self.play_index(self.index, seconds)
        if success and was_paused:
            self.toggle()
        return success

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(float(volume), 1.0))
        try:
            import pygame

            pygame.mixer.music.set_volume(0.0 if self.muted else self.volume)
        except Exception:
            LOGGER.debug("Volume backend unavailable", exc_info=True)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        self.set_volume(self.volume)
        return self.muted

    @property
    def position(self) -> float:
        if not self.current:
            return 0.0
        if self.paused:
            return min(self._offset, self.current.duration or self._offset)
        if self.playing:
            value = self._offset + (time.monotonic() - self._started_at)
            return min(value, self.current.duration or value)
        return 0.0

    def poll_finished(self) -> bool:
        if not self.playing or not self.current or self.position + 0.25 < self.current.duration:
            return False
        return self.next(automatic=True)

    def stop(self) -> None:
        try:
            import pygame

            pygame.mixer.music.stop()
        except Exception:
            pass
        self.playing = self.paused = False
        self._offset = 0.0
        if self.on_state_changed:
            self.on_state_changed(False)

    def close(self) -> None:
        try:
            import pygame

            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass
