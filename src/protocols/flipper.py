import re

from src.protocols.base import DeviceProtocol
from src.models.target import Target


class FlipperProtocol(DeviceProtocol):
    """
    Flipper Zero CLI protocol parser.

    Flipper Zero communicates over serial CLI with structured output.
    The CLI uses a "module command" pattern and returns tagged results.

    SubGHz output:
        SubGhz: Protocol: Princeton | Bit: 24 | Key: 0x001234 | Freq: 433.92MHz | RSSI: -40.5
        SubGhz: Protocol: KeeLoq | Bit: 66 | Key: 0xABCDEF01 | Freq: 315.00MHz

    NFC output:
        NFC: Type: Mifare Classic 1K | UID: 04:AB:CD:EF | ATQA: 0004 | SAK: 08
        NFC: Type: NTAG215 | UID: 04:12:34:56:78:9A:BC | ATQA: 0044 | SAK: 00

    RFID output:
        RFID: Type: EM4100 | Data: 01 02 03 04 05

    IR output:
        IR: Protocol: NEC | Address: 0x04 | Command: 0x08

    BT output:
        BT: Name: MyDevice | MAC: AA:BB:CC:DD:EE:FF | RSSI: -55

    Power info:
        Power: Battery: 85% | Charging: No | Voltage: 4.1V
    """

    name = "flipper"
    commands = {
        "subghz rx": "Receive SubGHz signals",
        "subghz tx": "Transmit SubGHz signal",
        "subghz decode_raw": "Decode raw SubGHz recording",
        "nfc detect": "Detect NFC tags",
        "nfc read": "Read NFC tag data",
        "nfc emulate": "Emulate NFC tag",
        "rfid read": "Read 125kHz RFID",
        "rfid emulate": "Emulate RFID tag",
        "ir rx": "Receive IR signal",
        "ir tx": "Transmit IR signal",
        "bt info": "Bluetooth info",
        "gpio set": "Set GPIO pin state",
        "gpio read": "Read GPIO pin state",
        "storage list": "List storage contents",
        "storage read": "Read file from storage",
        "power info": "Battery and power info",
        "power reboot": "Reboot Flipper",
        "update": "Start firmware update",
    }

    # SubGHz: Protocol: ... | Key: ... | Freq: ...
    SUBGHZ_PATTERN = re.compile(
        r"SubGhz:\s*Protocol:\s*(\w+)\s*\|.*?Key:\s*(\S+)\s*\|\s*Freq:\s*([\d.]+\s*MHz)"
    )

    # SubGHz with RSSI
    SUBGHZ_RSSI = re.compile(
        r"SubGhz:.*Freq:\s*([\d.]+\s*MHz)\s*\|\s*RSSI:\s*(-?[\d.]+)"
    )

    # NFC: Type: ... | UID: ...
    NFC_PATTERN = re.compile(
        r"NFC:\s*Type:\s*(.+?)\s*\|\s*UID:\s*([0-9A-Fa-f:]+)"
    )

    # NFC with ATQA+SAK
    NFC_FULL = re.compile(
        r"NFC:\s*Type:\s*(.+?)\s*\|\s*UID:\s*([0-9A-Fa-f:]+)\s*\|\s*ATQA:\s*(\w+)\s*\|\s*SAK:\s*(\w+)"
    )

    # RFID: Type: ... | Data: ...
    RFID_PATTERN = re.compile(
        r"RFID:\s*Type:\s*(\w+)\s*\|\s*Data:\s*(.+)"
    )

    # IR: Protocol: ... | Address: ... | Command: ...
    IR_PATTERN = re.compile(
        r"IR:\s*Protocol:\s*(\w+)\s*\|\s*Address:\s*(\S+)\s*\|\s*Command:\s*(\S+)"
    )

    # BT: Name: ... | MAC: ... | RSSI: ...
    BT_PATTERN = re.compile(
        r"BT:\s*Name:\s*(.+?)\s*\|\s*MAC:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    def parse_line(self, line: str, source_port: str) -> Target | None:
        # SubGHz signal
        m = self.SUBGHZ_PATTERN.search(line)
        if m:
            rssi = 0
            rssi_m = self.SUBGHZ_RSSI.search(line)
            if rssi_m:
                rssi = int(float(rssi_m.group(2)))
            return Target(
                type="SubGHz",
                identifier=f"{m.group(1)}: {m.group(2)}",
                frequency=m.group(3),
                rssi=rssi,
                source_device=source_port,
                extra={"protocol": m.group(1), "key": m.group(2)},
            )

        # NFC tag (full with ATQA/SAK)
        m = self.NFC_FULL.search(line)
        if m:
            return Target(
                type="NFC",
                identifier=m.group(2),
                source_device=source_port,
                extra={
                    "nfc_type": m.group(1),
                    "atqa": m.group(3),
                    "sak": m.group(4),
                },
            )

        # NFC tag (basic)
        m = self.NFC_PATTERN.search(line)
        if m:
            return Target(
                type="NFC",
                identifier=m.group(2),
                source_device=source_port,
                extra={"nfc_type": m.group(1)},
            )

        # RFID tag
        m = self.RFID_PATTERN.search(line)
        if m:
            return Target(
                type="RFID",
                identifier=m.group(2).strip(),
                source_device=source_port,
                extra={"rfid_type": m.group(1)},
            )

        # IR signal
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

        # Bluetooth device
        m = self.BT_PATTERN.search(line)
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
        if target:
            if action == "nfc emulate" and target.identifier:
                return f"nfc emulate --uid {target.identifier}"
            if action == "subghz tx" and target.extra.get("key"):
                freq = target.frequency or "433.92MHz"
                proto = target.extra.get("protocol", "Princeton")
                return f"subghz tx {target.extra['key']} {freq} {proto}"
        return action

    def get_scan_command(self) -> str:
        return "subghz rx"

    def get_stop_command(self) -> str:
        return "subghz rx stop"
