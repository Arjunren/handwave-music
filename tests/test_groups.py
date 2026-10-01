import json

import pytest

from src.library.groups import LocalGroupStore


def test_local_groups_persist_and_only_store_mp3_filenames(tmp_path) -> None:
    path = tmp_path / "local_groups.json"
    groups = LocalGroupStore(path)
    name = groups.create("Road Trips")
    groups.add_track(name, "C:/elsewhere/First Song.mp3")
    groups.add_track(name, "First Song.mp3")

    restored = LocalGroupStore(path)
    assert restored.names == ["Road Trips"]
    assert restored.tracks_for("Road Trips") == {"First Song.mp3"}
    assert json.loads(path.read_text(encoding="utf-8")) == {"Road Trips": ["First Song.mp3"]}


def test_local_groups_reject_duplicates_and_prune_missing_tracks(tmp_path) -> None:
    groups = LocalGroupStore(tmp_path / "local_groups.json")
    groups.create("Focus")
    with pytest.raises(ValueError):
        groups.create("focus")
    groups.add_track("Focus", "keep.mp3")
    groups.add_track("Focus", "gone.mp3")
    groups.prune({"keep.mp3"})
    assert groups.tracks_for("Focus") == {"keep.mp3"}
