import re

from src.protocols.base import DeviceProtocol
from src.models.target import Target


class HaleHoundProtocol(DeviceProtocol):
    """
    HaleHound firmware protocol parser.

    HaleHound is a multi-protocol offensive security firmware supporting
    WiFi, BLE, SubGHz (CC1101), NFC (PN532), and NRF24 modules.

    Output formats:
        [WIFI] SSID: NetworkName | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -42 | ENC: WPA2
        [WIFI_STA] MAC: AA:BB:CC:DD:EE:FF | RSSI: -55 | AP_BSSID: 11:22:33:44:55:66
        [BLE] Name: Device | ADDR: AA:BB:CC:DD:EE:FF | RSSI: -60 | Type: Random
        [SUBGHZ] Freq: 315.00MHz | Mod: ASK | Data: AA BB CC DD | RSSI: -30
        [NFC] UID: 04:AB:CD:EF:12:34:56 | ATQA: 0044 | SAK: 00 | Type: NTAG215
        [NRF24] Channel: 76 | Addr: AA:BB:CC:DD:EE | Payload: 48656C6C6F
        [MOUSEJACK] Device: Logitech | Addr: AA:BB:CC:DD:EE | Type: Mouse
        [IOT] IP: 192.168.1.50 | MAC: AA:BB:CC:DD:EE:FF | Service: HTTP | Port: 80
        [GUARDIAN] ROGUE AP: EvilTwin | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -30
        [TESLA] Signal: 315MHz | Status: Sent
    """

    name = "halehound"
    commands = {
        "wifi_scan": "Scan WiFi access points",
        "wifi_deauth": "WiFi deauth attack",
        "iot_recon": "IoT Recon -- automated LAN scan + credential brute force",
        "ble_scan": "BLE device scan",
        "ble_cinder": "BLE Cinder attack",
        "subghz_scan": "SubGHz spectrum scan (CC1101)",
        "subghz_replay": "SubGHz replay attack",
        "subghz_brute": "SubGHz brute force",
        "tesla_charge": "Tesla charge port opener (315/433MHz)",
        "nfc_scan": "NFC card scan (PN532)",
        "nfc_read": "NFC card read",
        "nfc_clone": "NFC card clone",
        "nrf_scan": "NRF24 2.4GHz scan",
        "mousejack": "MouseJack keystroke injection",
        "guardian": "WiFi Guardian -- rogue AP detection",
        "stalkerware": "Stalkerware Detect",
        "stop": "Stop current operation",
        "status": "Device status",
        "reboot": "Reboot device",
    }

    # WiFi AP
    WIFI_AP = re.compile(
        r"\[WIFI\]\s*SSID:\s*(.+?)\s*\|\s*BSSID:\s*([0-9A-Fa-f:]{17})"
        r"\s*\|\s*CH:\s*(\d+)\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # WiFi Station
    WIFI_STA = re.compile(
        r"\[WIFI_STA\]\s*MAC:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # BLE device
    BLE_DEV = re.compile(
        r"\[BLE\]\s*Name:\s*(.+?)\s*\|\s*ADDR:\s*([0-9A-Fa-f:]{17})\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # SubGHz signal
    SUBGHZ = re.compile(
        r"\[SUBGHZ\]\s*Freq:\s*([\d.]+\s*MHz)\s*\|\s*Mod:\s*(\w+)\s*\|\s*Data:\s*(.+?)\s*\|\s*RSSI:\s*(-?\d+)"
    )

    # SubGHz without RSSI
    SUBGHZ_NORSSI = re.compile(
        r"\[SUBGHZ\]\s*Freq:\s*([\d.]+\s*MHz)\s*\|\s*Mod:\s*(\w+)\s*\|\s*Data:\s*(.+)"
    )

    # NFC tag
    NFC_TAG = re.compile(
        r"\[NFC\]\s*UID:\s*([0-9A-Fa-f:]+)\s*\|\s*ATQA:\s*(\w+)\s*\|\s*SAK:\s*(\w+)"
    )

    # NRF24 packet
    NRF24 = re.compile(
        r"\[NRF24\]\s*Channel:\s*(\d+)\s*\|\s*Addr:\s*([0-9A-Fa-f:]+)\s*\|\s*Payload:\s*(\S+)"
    )

    # MouseJack device
    MOUSEJACK = re.compile(
        r"\[MOUSEJACK\]\s*Device:\s*(.+?)\s*\|\s*Addr:\s*([0-9A-Fa-f:]+)\s*\|\s*Type:\s*(\w+)"
    )

    # IoT Recon result
    IOT = re.compile(
        r"\[IOT\]\s*IP:\s*([\d.]+)\s*\|\s*MAC:\s*([0-9A-Fa-f:]{17})\s*\|\s*Service:\s*(\w+)"
    )

    # Guardian rogue AP
    GUARDIAN = re.compile(
        r"\[GUARDIAN\]\s*ROGUE\s*AP:\s*(.+?)\s*\|\s*BSSID:\s*([0-9A-Fa-f:]{17})"
        r"\s*\|\s*CH:\s*(\d+)\s*\|\s*RSSI:\s*(-?\d+)"
    )

    def parse_line(self, line: str, source_port: str) -> Target | None:
        # WiFi AP
        m = self.WIFI_AP.search(line)
        if m:
            return Target(
                type="AP",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                channel=int(m.group(3)),
                rssi=int(m.group(4)),
                source_device=source_port,
            )

        # WiFi Station
        m = self.WIFI_STA.search(line)
        if m:
            return Target(
                type="STA",
                identifier=m.group(1),
                mac=m.group(1),
                rssi=int(m.group(2)),
                source_device=source_port,
            )

        # BLE device
        m = self.BLE_DEV.search(line)
        if m:
            return Target(
                type="BLE",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                rssi=int(m.group(3)),
                source_device=source_port,
            )

        # SubGHz with RSSI
        m = self.SUBGHZ.search(line)
        if m:
            return Target(
                type="SubGHz",
                identifier=f"{m.group(2)}: {m.group(3).strip()}",
                frequency=m.group(1),
                rssi=int(m.group(4)),
                source_device=source_port,
                extra={"modulation": m.group(2), "data": m.group(3).strip()},
            )

        # SubGHz without RSSI
        m = self.SUBGHZ_NORSSI.search(line)
        if m:
            return Target(
                type="SubGHz",
                identifier=f"{m.group(2)}: {m.group(3).strip()}",
                frequency=m.group(1),
                source_device=source_port,
                extra={"modulation": m.group(2), "data": m.group(3).strip()},
            )

        # NFC tag
        m = self.NFC_TAG.search(line)
        if m:
            return Target(
                type="NFC",
                identifier=m.group(1),
                source_device=source_port,
                extra={"atqa": m.group(2), "sak": m.group(3)},
            )

        # NRF24 packet
        m = self.NRF24.search(line)
        if m:
            return Target(
                type="NRF24",
                identifier=m.group(2),
                channel=int(m.group(1)),
                source_device=source_port,
                extra={"payload": m.group(3)},
            )

        # MouseJack
        m = self.MOUSEJACK.search(line)
        if m:
            return Target(
                type="MouseJack",
                identifier=f"{m.group(1)} ({m.group(3)})",
                mac=m.group(2),
                source_device=source_port,
                extra={"device_type": m.group(3)},
            )

        # IoT device
        m = self.IOT.search(line)
        if m:
            return Target(
                type="IoT",
                identifier=f"{m.group(3)}@{m.group(1)}",
                mac=m.group(2),
                source_device=source_port,
                extra={"ip": m.group(1), "service": m.group(3)},
            )

        # Guardian rogue AP
        m = self.GUARDIAN.search(line)
        if m:
            return Target(
                type="RogueAP",
                identifier=m.group(1).strip(),
                mac=m.group(2),
                channel=int(m.group(3)),
                rssi=int(m.group(4)),
                source_device=source_port,
            )

        return None

    def build_command(self, action: str, target: Target = None) -> str:
        if target:
            if action == "wifi_deauth" and target.mac:
                return f"wifi_deauth {target.mac}"
            if action == "subghz_replay" and target.extra.get("data"):
                freq = target.frequency or "433.92MHz"
                return f"subghz_replay {freq} {target.extra['data']}"
            if action == "nfc_clone" and target.identifier:
                return f"nfc_clone {target.identifier}"
            if action == "mousejack" and target.mac:
                return f"mousejack {target.mac}"
        return action

    def get_scan_command(self) -> str:
        return "wifi_scan"

    def get_stop_command(self) -> str:
        return "stop"
