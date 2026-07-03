import re

from src.protocols.base import DeviceProtocol
from src.models.target import Target


class BruceProtocol(DeviceProtocol):
    """
    Bruce firmware protocol parser.

    Bruce is a multi-tool firmware for ESP32 (CYD and similar boards).
    Its serial output for scans uses a structured format:

    WiFi scan:
        [WIFI] AP: CoffeeShop | BSSID: AA:BB:CC:DD:EE:FF | CH: 1 | RSSI: -50 | AUTH: WPA2
        [WIFI] AP: OpenNet | BSSID: 11:22:33:44:55:66 | CH: 6 | RSSI: -72 | AUTH: OPEN

    BLE scan:
        [BLE] Device: FitBand | ADDR: AA:BB:CC:DD:EE:FF | RSSI: -60

    SubGHz scan:
        [SUBGHZ] Freq: 433.92MHz | Protocol: Princeton | Data: 0x1234ABCD

    IR received:
        [IR] Protocol: NEC | Address: 0x04 | Command: 0x08

    NFC read:
        [NFC] Type: NTAG215 | UID: 04:AB:CD:EF:12:34:56
    """

    name = "bruce"
    commands = {
        "wifi scan": "Scan WiFi networks",
        "wifi deauth": "Deauth attack",
        "wifi beacon": "Beacon spam",
        "ble scan": "Scan BLE devices",
        "ble spam": "BLE advertisement spam",
        "ir send": "Send IR signal",
        "ir receive": "Receive IR signal",
        "subghz scan": "Scan SubGHz frequencies",
        "subghz send": "Send SubGHz signal",
        "subghz replay": "Replay captured SubGHz signal",
        "nfc read": "Read NFC tag",
        "nfc emulate": "Emulate NFC tag",
        "stop": "Stop current operation",
        "reboot": "Reboot device",
        "status": "Device status",
    }

    # [WIFI] AP: ... | BSSID: ... | CH: ... | RSSI: ...
    WIFI_PATTERN = re.compile(
        r"\[WIFI\]\s*AP:\s*(.+?)\s*\|\s*BSSID:\s*([0-9A-Fa-f:]{17})"
        r"\s*\|\s*CH:\s*(\d+)\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # [BLE] Device: ... | ADDR: ... | RSSI: ...
    BLE_PATTERN = re.compile(
        r"\[BLE\]\s*Device:\s*(.+?)\s*\|\s*ADDR:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # [SUBGHZ] Freq: ... | Protocol: ... | Data: ...
    SUBGHZ_PATTERN = re.compile(
        r"\[SUBGHZ\]\s*Freq:\s*([\d.]+\s*MHz)\s*\|\s*Protocol:\s*(\w+)\s*\|\s*Data:\s*(\S+)"
    )

    # [NFC] Type: ... | UID: ...
    NFC_PATTERN = re.compile(
        r"\[NFC\]\s*Type:\s*(.+?)\s*\|\s*UID:\s*([0-9A-Fa-f:]+)"
    )

    # [IR] Protocol: ... | Address: ... | Command: ...
    IR_PATTERN = re.compile(
        r"\[IR\]\s*Protocol:\s*(\w+)\s*\|\s*Address:\s*(\S+)\s*\|\s*Command:\s*(\S+)"
    )

    def parse_line(self, line: str, source_port: str) -> Target | None:
        # WiFi AP
        m = self.WIFI_PATTERN.search(line)
        if m:
            return Target(
                type="AP",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                channel=self._to_int(m.group(3)),
                rssi=self._to_int(m.group(4)),
                source_device=source_port,
            )

        # BLE device
        m = self.BLE_PATTERN.search(line)
        if m:
            return Target(
                type="BLE",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                rssi=self._to_int(m.group(3)),
                source_device=source_port,
            )

        # SubGHz signal
        m = self.SUBGHZ_PATTERN.search(line)
        if m:
            return Target(
                type="SubGHz",
                identifier=f"{m.group(2)}: {m.group(3)}",
                frequency=m.group(1),
                source_device=source_port,
                extra={"protocol": m.group(2), "data": m.group(3)},
            )

        # NFC tag
        m = self.NFC_PATTERN.search(line)
        if m:
            return Target(
                type="NFC",
                identifier=m.group(2),  # UID as identifier
                source_device=source_port,
                extra={"nfc_type": m.group(1)},
            )

        # IR signal (logged but not a target for cross-comm)
        m = self.IR_PATTERN.search(line)
        if m:
            return Target(
                type="IR",
                identifier=f"{m.group(1)} Addr:{m.group(2)} Cmd:{m.group(3)}",
                source_device=source_port,
                extra={
                    "protocol": m.group(1),
                    "address": m.group(2),
                    "command": m.group(3),
                },
            )

        return None

    def build_command(self, action: str, target: Target = None) -> str:
        if target and action == "wifi deauth" and target.mac:
            return f"wifi deauth {target.mac}"
        if target and action == "subghz replay" and target.extra.get("data"):
            return f"subghz send {target.extra['data']}"
        return action

    def get_scan_command(self) -> str:
        return "wifi scan"

    def get_stop_command(self) -> str:
        return "stop"
