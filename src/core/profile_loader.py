import json
import os


class FirmwareProfile:
    """Represents a firmware's flash configuration."""

    def __init__(self, data: dict):
        self.name = data["name"]
        self.version = data.get("version", "latest")
        self.backend = data["backend"]
        self.board_variants = data.get("board_variants", [])
        self.download_url = data.get("download_url", "")
        self.flash_args = data.get("flash_args", {})
        self.description = data.get("description", "")
        self.protocol = data.get("protocol", "raw")

    def __repr__(self):
        return f"<FirmwareProfile {self.name} v{self.version} [{self.backend}]>"


class ProfileLoader:
    """Loads firmware profiles from JSON files in a directory."""

    def __init__(self, profile_dir="src/config/profiles"):
        self.profile_dir = profile_dir
        self.profiles: dict[str, FirmwareProfile] = {}

    def load_all(self):
        self.profiles.clear()
        if not os.path.isdir(self.profile_dir):
            return

        for fname in os.listdir(self.profile_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.profile_dir, fname)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                profile = FirmwareProfile(data)
                self.profiles[profile.name] = profile
            except (json.JSONDecodeError, KeyError):
                continue

    def get(self, name):
        return self.profiles.get(name)

    def list_names(self):
        return sorted(self.profiles.keys())
