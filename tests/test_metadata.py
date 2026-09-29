from src.audio.metadata import scan_music


def test_empty_music_folder_is_safe(tmp_path) -> None:
    music = tmp_path / "music"
    assert scan_music(music) == []
    assert music.is_dir()


def test_non_mp3_files_are_ignored(tmp_path) -> None:
    music = tmp_path / "music"
    music.mkdir()
    (music / "notes.txt").write_text("not music")
    (music / "fake.MP3").write_text("not an mp3")
    assert scan_music(music) == []
