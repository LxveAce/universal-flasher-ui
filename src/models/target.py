from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Target:
    type: str               # "AP", "STA", "BLE", "SubGHz", "NFC"
    identifier: str         # SSID, device name, frequency, etc.
    source_device: str      # port of the device that found it
    mac: str = ""
    rssi: int = 0
    channel: int = 0
    frequency: str = ""
    extra: dict = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.now)
    shared: bool = False    # True once published to cross-comm pool
