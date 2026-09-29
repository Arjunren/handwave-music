from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.audio.importer import MusicImporter, is_youtube_url, safe_mp3_name


def test_youtube_url_validation_is_host_exact() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert is_youtube_url("https://music.youtube.com/watch?v=abc")
    assert not is_youtube_url("https://youtube.com.evil.example/watch?v=abc")
    assert not is_youtube_url("file:///youtube.com/video")


def test_optional_filename_is_sanitized() -> None:
    assert safe_mp3_name('  My <Song>: "Live".mp3  ') == "My _Song__ _Live.mp3"
    assert safe_mp3_name("CON") == "_CON.mp3"
    assert safe_mp3_name("...") == "track.mp3"


def test_local_import_copies_and_never_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "source.mp3"
    source.write_bytes(b"ID3-test")
    music = tmp_path / "music"
    importer = MusicImporter(music)
    importer._copy_local([str(source)])
    importer._copy_local([str(source)])
    assert (music / "source.mp3").read_bytes() == b"ID3-test"
    assert (music / "source (2).mp3").read_bytes() == b"ID3-test"


def test_local_import_rejects_non_mp3(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not audio")
    with pytest.raises(ValueError, match="not an MP3"):
        MusicImporter(tmp_path / "music")._copy_local([str(source)])


def test_youtube_download_uses_safe_optional_name(tmp_path: Path, monkeypatch) -> None:
    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def download(self, urls: list[str]) -> None:
            destination = Path(self.options["outtmpl"].replace("%(ext)s", "mp3"))
            destination.write_bytes(b"ID3-downloaded")

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    monkeypatch.setitem(
        sys.modules,
        "imageio_ffmpeg",
        SimpleNamespace(get_ffmpeg_exe=lambda: str(tmp_path / "ffmpeg")),
    )
    monkeypatch.setattr(
        "src.audio.importer.shutil.which",
        lambda name: str(tmp_path / "node") if name == "node" else None,
    )
    importer = MusicImporter(tmp_path / "music")
    message = importer._download_youtube("https://youtu.be/example", "My / Song.mp3")
    assert (tmp_path / "music" / "Song.mp3").exists()
    assert "Song.mp3" in message
