import re

from src.protocols.base import DeviceProtocol
from src.models.target import Target


class GhostESPProtocol(DeviceProtocol):
    """
    GhostESP firmware protocol parser.

    GhostESP outputs WiFi scan results in a format similar to Marauder but
    with its own variations. It also supports BLE scanning and wardriving.

    Typical AP scan output:
        [WiFi] SSID: HomeNetwork | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -42 | ENC: WPA2
        [WiFi] SSID: CoffeeShop | BSSID: 11:22:33:44:55:66 | CH: 11 | RSSI: -65 | ENC: OPEN

    Station output:
        [STA] MAC: AA:BB:CC:DD:EE:FF | RSSI: -55 | AP: HomeNetwork

    BLE scan output:
        [BLE] Name: MI Band 5 | MAC: AA:BB:CC:DD:EE:FF | RSSI: -70
    """

    name = "ghost_esp"
    commands = {
        "scanap": "Scan for access points",
        "scansta": "Scan for stations",
        "beacon": "Start beacon spam",
        "deauth": "Deauth attack",
        "probe": "Probe request flood",
        "stop": "Stop current operation",
        "wardrive": "Start wardriving mode",
        "bleSpam": "BLE advertisement spam",
        "bleScan": "Scan BLE devices",
        "status": "Show device status",
        "reboot": "Reboot device",
    }

    # [WiFi] SSID: ... | BSSID: ... | CH: ... | RSSI: ...
    AP_PATTERN = re.compile(
        r"\[WiFi\]\s*SSID:\s*(.+?)\s*\|\s*BSSID:\s*([0-9A-Fa-f:]{17})"
        r"\s*\|\s*CH:\s*(\d+)\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # Also match simpler format: SSID: ... BSSID: ... Ch: ... RSSI: ...
    AP_SIMPLE = re.compile(
        r"SSID:\s*(.+?)\s+BSSID:\s*([0-9A-Fa-f:]{17})\s+Ch:\s*(\d+)\s+RSSI:\s*(-?\d+)"
    )

    # [STA] MAC: ... | RSSI: ...
    STA_PATTERN = re.compile(
        r"\[STA\]\s*MAC:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # [BLE] Name: ... | MAC: ... | RSSI: ...
    BLE_PATTERN = re.compile(
        r"\[BLE\]\s*Name:\s*(.+?)\s*\|\s*MAC:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    def parse_line(self, line: str, source_port: str) -> Target | None:
        # WiFi AP (bracketed format)
        m = self.AP_PATTERN.search(line)
        if m:
            return Target(
                type="AP",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                channel=int(m.group(3)),
                rssi=int(m.group(4)),
                source_device=source_port,
            )

        # WiFi AP (simple format)
        m = self.AP_SIMPLE.search(line)
        if m:
            return Target(
                type="AP",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                channel=int(m.group(3)),
                rssi=int(m.group(4)),
                source_device=source_port,
            )

        # Station
        m = self.STA_PATTERN.search(line)
        if m:
            return Target(
                type="STA",
                identifier=m.group(1),
                mac=m.group(1),
                rssi=int(m.group(2)),
                source_device=source_port,
            )

        # BLE device
        m = self.BLE_PATTERN.search(line)
        if m:
            return Target(
                type="BLE",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                rssi=int(m.group(3)),
                source_device=source_port,
            )

        return None

    def build_command(self, action: str, target: Target = None) -> str:
        if target and action == "deauth" and target.mac:
            return f"deauth {target.mac}"
        return action

    def get_scan_command(self) -> str:
        return "scanap"

    def get_stop_command(self) -> str:
        return "stop"
