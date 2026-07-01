"""settings.load_settings deep-merge behaviour against DEFAULTS."""

import json

from src.config import settings as settings_mod
from src.config.settings import DEFAULTS


def test_missing_file_returns_defaults_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(tmp_path / "none.json"))
    loaded = settings_mod.load_settings()
    assert loaded == DEFAULTS
    # A copy, not the module-level dict.
    assert loaded is not DEFAULTS


def test_partial_saved_deep_merges(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "serial": {"default_baud": 9600},
        "flash": {"baud": 230400},
    }))
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(path))

    loaded = settings_mod.load_settings()
    # Overridden key wins.
    assert loaded["serial"]["default_baud"] == 9600
    # Sibling key inside the same section is preserved from DEFAULTS.
    assert loaded["serial"]["timeout"] == DEFAULTS["serial"]["timeout"]
    assert loaded["flash"]["baud"] == 230400
    assert loaded["flash"]["verify"] == DEFAULTS["flash"]["verify"]
    # Untouched sections fall through unchanged.
    assert loaded["cross_comm"] == DEFAULTS["cross_comm"]
    assert loaded["ui"] == DEFAULTS["ui"]


def test_unknown_top_level_key_passes_through(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"custom_scalar": 42}))
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(path))
    loaded = settings_mod.load_settings()
    assert loaded["custom_scalar"] == 42
    assert loaded["ui"] == DEFAULTS["ui"]


def test_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    # A truncated/hand-edited settings.json must not crash the app on startup.
    path = tmp_path / "settings.json"
    path.write_text("{ this is not valid json ")
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(path))
    loaded = settings_mod.load_settings()
    assert loaded == DEFAULTS
    assert loaded is not DEFAULTS


def test_non_dict_json_returns_defaults(tmp_path, monkeypatch):
    # Valid JSON that is not an object (a list/scalar) is ignored, not crashed on.
    path = tmp_path / "settings.json"
    path.write_text(json.dumps([1, 2, 3]))
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(path))
    loaded = settings_mod.load_settings()
    assert loaded == DEFAULTS


def test_loaded_sections_are_independent_copies(tmp_path, monkeypatch):
    # Mutating the returned dict must never leak back into the module DEFAULTS.
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(tmp_path / "none.json"))
    loaded = settings_mod.load_settings()
    loaded["ui"]["theme"] = "light"
    loaded["cross_comm"]["dedup_by_mac"] = False
    assert DEFAULTS["ui"]["theme"] == "dark"
    assert DEFAULTS["cross_comm"]["dedup_by_mac"] is True


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "sub" / "settings.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_PATH", str(path))
    payload = {"serial": {"default_baud": 57600, "timeout": 9}}
    settings_mod.save_settings(payload)
    assert path.exists()
    loaded = settings_mod.load_settings()
    assert loaded["serial"]["default_baud"] == 57600
    assert loaded["serial"]["timeout"] == 9
