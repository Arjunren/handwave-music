import json

from src.config.settings import AppSettings, SettingsStore


def test_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    expected = AppSettings(volume=0.42, visualizer_mode="Wave", control_hand="Left")
    store.save(expected)
    actual = store.load()
    assert actual.volume == 0.42
    assert actual.visualizer_mode == "Wave"
    assert actual.control_hand == "Left"


def test_invalid_values_are_normalized(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"volume": 99, "visualizer_mode": "Bad", "unknown": True}))
    settings = SettingsStore(path).load()
    assert settings.volume == 1.0
    assert settings.visualizer_mode == "Spectrum"


def test_corrupt_settings_use_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not-json")
    assert SettingsStore(path).load() == AppSettings()
