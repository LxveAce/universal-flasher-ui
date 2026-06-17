from dataclasses import dataclass
from datetime import datetime

from src.models.target import Target


@dataclass
class CrossCommMessage:
    target: Target
    dest_port: str
    action: str
    timestamp: datetime
    executed: bool = False
    result: str = ""
