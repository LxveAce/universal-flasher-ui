from PyQt5.QtCore import QObject, pyqtSignal
from datetime import datetime

from src.models.target import Target
from src.models.message import CrossCommMessage


class CrossCommBroker(QObject):
    """
    Event bus for cross-device communication.

    When any connected device discovers a target (AP, MAC, BLE device,
    SubGHz signal), it publishes to the broker. Other devices can
    subscribe and act on shared targets.

    Flow:
        Device A (Marauder scanap) -> discovers AP "MyNetwork"
        -> broker.publish(target) -> shared pool
        -> Device B subscribes -> auto-sends "sniffpmkid MyNetwork"
    """

    target_discovered = pyqtSignal(object)   # Target
    target_routed = pyqtSignal(object)       # CrossCommMessage
    event_logged = pyqtSignal(str)           # log line

    def __init__(self):
        super().__init__()
        self.target_pool: list[Target] = []
        self.event_log: list[str] = []
        self._subscriptions: list[dict] = []

    def publish(self, target: Target):
        """Add a discovered target to the shared pool."""
        if not self._is_duplicate(target):
            self.target_pool.append(target)
            self.target_discovered.emit(target)
            self._log(f"[DISCOVER] {target.type}: {target.identifier} from {target.source_device} (ch:{target.channel}, rssi:{target.rssi})")
            self._check_auto_routes(target)

    def route_to_device(self, target: Target, dest_port: str, action: str):
        """Send a target to a specific device with an action command."""
        msg = CrossCommMessage(
            target=target,
            dest_port=dest_port,
            action=action,
            timestamp=datetime.now(),
        )
        self.target_routed.emit(msg)
        self._log(f"[ROUTE] {target.identifier} -> {dest_port} ({action})")

    def subscribe(self, rule: dict):
        """
        Add an auto-routing rule.
        rule = {
            "match_type": "AP" | "BLE" | "SubGHz" | "*",
            "match_source": "COM3" | "*",
            "dest_port": "COM5",
            "action": "sniffpmkid {identifier}",
        }
        """
        self._subscriptions.append(rule)
        self._log(f"[RULE] Added: {rule.get('match_type', '*')} -> {rule['dest_port']} ({rule['action']})")

    def clear_pool(self):
        self.target_pool.clear()
        self._log("[POOL] Cleared")

    def _is_duplicate(self, target: Target) -> bool:
        return any(
            t.identifier == target.identifier and t.type == target.type
            for t in self.target_pool
        )

    def _check_auto_routes(self, target: Target):
        for rule in self._subscriptions:
            type_match = rule.get("match_type", "*") in ("*", target.type)
            source_match = rule.get("match_source", "*") in ("*", target.source_device)
            if type_match and source_match:
                action = rule["action"].format(
                    identifier=target.identifier,
                    mac=target.mac or "",
                    channel=target.channel or "",
                )
                self.route_to_device(target, rule["dest_port"], action)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.event_log.append(line)
        self.event_logged.emit(line)
