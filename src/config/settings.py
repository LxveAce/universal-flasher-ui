import json
import os

DEFAULTS = {
    "serial": {
        "default_baud": 115200,
        "timeout": 5,
    },
    "flash": {
        "baud": 921600,
        "verify": True,
        "auto_backup": True,
    },
    "cross_comm": {
        "auto_share": True,
        "dedup_by_mac": True,
    },
    "ui": {
        "theme": "dark",
        "font_size": 11,
    },
}

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".universal-flasher-ui", "settings.json")


def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as f:
            saved = json.load(f)
        merged = {**DEFAULTS}
        for k, v in saved.items():
            if isinstance(v, dict) and k in merged:
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        return merged
    return dict(DEFAULTS)


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
