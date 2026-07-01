"""ProfileLoader tests against the shipped profile JSONs."""

import json

from src.core.profile_loader import ProfileLoader, FirmwareProfile

# The six profiles that ship in src/config/profiles/.
SHIPPED_PROFILES = {
    "bruce",
    "flipper_momentum",
    "flipper_unleashed",
    "ghost_esp",
    "halehound",
    "marauder",
}


def test_loads_all_shipped_profiles():
    loader = ProfileLoader()
    loader.load_all()
    # Every shipped JSON parsed into a FirmwareProfile.
    assert len(loader.profiles) == 6
    for profile in loader.profiles.values():
        assert isinstance(profile, FirmwareProfile)
        assert profile.name
        assert profile.backend


def test_default_profile_dir_matches_disk():
    loader = ProfileLoader()
    import os

    on_disk = {
        f[:-5] for f in os.listdir(loader.profile_dir) if f.endswith(".json")
    }
    assert on_disk == SHIPPED_PROFILES


def test_get_and_list_names():
    loader = ProfileLoader()
    loader.load_all()
    names = loader.list_names()
    assert names == sorted(names)  # list_names returns sorted
    first = names[0]
    assert loader.get(first).name == first
    assert loader.get("no-such-profile") is None


def test_load_from_custom_dir(tmp_path):
    (tmp_path / "good.json").write_text(
        json.dumps({"name": "good", "backend": "esptool"})
    )
    # Missing required key ("backend") -> skipped, not fatal.
    (tmp_path / "bad.json").write_text(json.dumps({"name": "bad"}))
    # Invalid JSON -> skipped.
    (tmp_path / "broken.json").write_text("{not json")

    loader = ProfileLoader(profile_dir=str(tmp_path))
    loader.load_all()
    assert set(loader.profiles) == {"good"}


def test_missing_dir_is_noop():
    loader = ProfileLoader(profile_dir="/does/not/exist/xyz")
    loader.load_all()
    assert loader.profiles == {}
