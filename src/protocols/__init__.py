"""Protocol registry — maps protocol names to parser instances."""

from src.protocols.base import DeviceProtocol
from src.protocols.marauder import MarauderProtocol
from src.protocols.ghost_esp import GhostESPProtocol
from src.protocols.bruce import BruceProtocol
from src.protocols.halehound import HaleHoundProtocol
from src.protocols.flipper import FlipperProtocol


# Canonical protocol registry
PROTOCOLS: dict[str, DeviceProtocol] = {
    "marauder": MarauderProtocol(),
    "ghost_esp": GhostESPProtocol(),
    "bruce": BruceProtocol(),
    "halehound": HaleHoundProtocol(),
    "flipper": FlipperProtocol(),
    "raw": DeviceProtocol(),  # passthrough, no parsing
}

# Display name -> internal key mapping for the UI combo box
PROTOCOL_DISPLAY_NAMES = {
    "Marauder": "marauder",
    "GhostESP": "ghost_esp",
    "Bruce": "bruce",
    "HaleHound": "halehound",
    "Flipper": "flipper",
    "Raw": "raw",
}


def get_protocol(name: str) -> DeviceProtocol:
    """Get a protocol instance by internal name. Falls back to raw."""
    return PROTOCOLS.get(name, PROTOCOLS["raw"])


def get_protocol_by_display(display_name: str) -> DeviceProtocol:
    """Get a protocol instance by its display name."""
    key = PROTOCOL_DISPLAY_NAMES.get(display_name, "raw")
    return PROTOCOLS.get(key, PROTOCOLS["raw"])
