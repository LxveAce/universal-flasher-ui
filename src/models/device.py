from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConnectedDevice:
    port: str
    connection: object
    protocol: str = "raw"
    baud: int = 115200
    label: str = ""
    firmware: str = ""
    connected_at: datetime = field(default_factory=datetime.now)

    @property
    def display_name(self) -> str:
        if self.label:
            return f"{self.label} ({self.port})"
        if self.firmware:
            return f"{self.firmware} ({self.port})"
        return self.port
