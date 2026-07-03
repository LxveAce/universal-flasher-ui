import re
from src.protocols.base import DeviceProtocol
from src.models.target import Target


class MarauderProtocol(DeviceProtocol):

    name = "marauder"
    commands = {
        "scanap": "Scan for access points",
        "scansta": "Scan for stations",
        "stopscan": "Stop current scan",
        "sniffpmkid": "Sniff PMKID on target AP",
        "sniffbeacon": "Sniff beacon frames",
        "sniffdeauth": "Sniff deauth frames",
        "sniffraw": "Sniff raw packets",
        "attack -t deauth": "Deauth selected targets",
        "attack -t beacon -l": "Beacon spam (AP list)",
        "attack -t rickroll": "Rickroll beacon spam",
        "list -a": "List scanned access points",
        "list -s": "List scanned stations",
        "select -a": "Select AP by index",
        "select -s": "Select station by index",
        "clearlist": "Clear AP/station lists",
        "channel": "Set/get WiFi channel",
        "update": "Check for firmware updates",
        "reboot": "Reboot the device",
    }

    # Marauder AP scan output: "SSID: MyNetwork BSSID: AA:BB:CC:DD:EE:FF Ch: 6 RSSI: -45"
    AP_PATTERN = re.compile(
        r"SSID:\s*(.+?)\s+BSSID:\s*([0-9A-Fa-f:]{17})\s+Ch:\s*(\d+)\s+RSSI:\s*(-?\d+)"
    )

    # Station: "MAC: AA:BB:CC:DD:EE:FF RSSI: -60"
    STA_PATTERN = re.compile(
        r"MAC:\s*([0-9A-Fa-f:]{17})\s+RSSI:\s*(-?\d+)"
    )

    def parse_line(self, line: str, source_port: str) -> Target | None:
        ap_match = self.AP_PATTERN.search(line)
        if ap_match:
            return Target(
                type="AP",
                identifier=ap_match.group(1),
                mac=ap_match.group(2),
                channel=self._to_int(ap_match.group(3)),
                rssi=self._to_int(ap_match.group(4)),
                source_device=source_port,
            )

        sta_match = self.STA_PATTERN.search(line)
        if sta_match:
            return Target(
                type="STA",
                identifier=sta_match.group(1),
                mac=sta_match.group(1),
                rssi=self._to_int(sta_match.group(2)),
                source_device=source_port,
            )

        return None

    def build_command(self, action: str, target: Target = None) -> str:
        if target and action == "sniffpmkid" and target.channel:
            return f"channel {target.channel}\nsniffpmkid"
        if target and action == "deauth" and target.mac:
            return f"select -a {target.mac}\nattack -t deauth"
        return action

    def get_scan_command(self) -> str:
        return "scanap"

    def get_stop_command(self) -> str:
        return "stopscan"
