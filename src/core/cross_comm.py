from collections import deque
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

    # A busy scan streams thousands of targets; device_tab publishes every one here. Bound the shared
    # pool (and, because the cross_comm_tab table mirrors it 1:1 by index for routing, the UI table too)
    # and the retained event log so neither grows without limit.
    _MAX_POOL = 5000
    _MAX_EVENT_LOG = 5000

    def __init__(self):
        super().__init__()
        self.target_pool: list[Target] = []
        self.event_log: deque = deque(maxlen=self._MAX_EVENT_LOG)
        self._subscriptions: list[dict] = []
        # O(1) dedup index mirroring target_pool, keyed exactly like _is_duplicate ((type, identifier)).
        # device_tab publishes EVERY discovered target here (even past its own local cap), so a busy scan
        # streams thousands — a linear per-publish scan would make discovery O(n^2) and stall the GUI thread.
        self._seen_keys: set[tuple] = set()

    def publish(self, target: Target):
        """Add a discovered target to the shared pool."""
        # Drop past the cap (not a dup, pool full) rather than grow the pool + the 1:1 UI table forever.
        if not self._is_duplicate(target) and len(self.target_pool) < self._MAX_POOL:
            self._seen_keys.add((target.type, target.identifier))
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
        self._seen_keys.clear()   # keep the dedup index in sync so cleared targets can be re-published
        self._log("[POOL] Cleared")

    def _is_duplicate(self, target: Target) -> bool:
        # O(1) membership check against the seen-key index (was an O(n) scan of target_pool).
        return (target.type, target.identifier) in self._seen_keys

    def _check_auto_routes(self, target: Target):
        for rule in self._subscriptions:
            type_match = rule.get("match_type", "*") in ("*", target.type)
            source_match = rule.get("match_source", "*") in ("*", target.source_device)
            if type_match and source_match:
                try:
                    action = rule["action"].format(
                        identifier=target.identifier,
                        mac=target.mac or "",
                        channel=target.channel or "",
                    )
                except (KeyError, IndexError, ValueError) as e:
                    # A user rule may contain an unsupported placeholder (e.g.
                    # "{name}") or an unbalanced brace. Skip that rule instead of
                    # letting the exception break the whole discovery pipeline.
                    self._log(
                        f"[RULE] Skipped route: bad action template "
                        f"{rule.get('action')!r} ({e})"
                    )
                    continue
                self.route_to_device(target, rule["dest_port"], action)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.event_log.append(line)
        self.event_logged.emit(line)
