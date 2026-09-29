from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

from src.models import Track


class FakeMusic:
    def __init__(self) -> None:
        self.loaded = ""
        self.volume = 0.0
        self.paused = False

    def set_endevent(self) -> None:
        pass

    def load(self, path: str) -> None:
        self.loaded = path

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self, start: float = 0.0) -> None:
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def unpause(self) -> None:
        self.paused = False

    def stop(self) -> None:
        pass


def fake_pygame(monkeypatch):
    music = FakeMusic()
    mixer = SimpleNamespace(init=lambda **kwargs: None, quit=lambda: None, music=music)
    monkeypatch.setitem(sys.modules, "pygame", SimpleNamespace(mixer=mixer))
    return music


def tracks() -> list[Track]:
    return [
        Track(Path("one.mp3"), "One", duration=10.0),
        Track(Path("two.mp3"), "Two", duration=12.0),
    ]


def test_play_pause_next_previous_and_volume(monkeypatch) -> None:
    music = fake_pygame(monkeypatch)
    from src.audio.audio_player import AudioPlayer

    player = AudioPlayer(tracks())
    assert player.play_index(0)
    assert player.current.title == "One"
    assert player.toggle() and player.paused and music.paused
    assert player.toggle() and player.playing and not music.paused
    assert player.next() and player.current.title == "Two"
    player._offset = 0.0
    player._started_at = time.monotonic()
    assert player.previous() and player.current.title == "One"
    player.set_volume(0.4)
    assert music.volume == 0.4


def test_completion_obeys_repeat_track(monkeypatch) -> None:
    fake_pygame(monkeypatch)
    from src.audio.audio_player import AudioPlayer

    player = AudioPlayer(tracks())
    player.play_index(0)
    player.repeat_mode = "track"
    player._offset = 10.0
    assert player.poll_finished()
    assert player.index == 0
