from src.protocols.base import DeviceProtocol


class BruceProtocol(DeviceProtocol):

    name = "bruce"
    commands = {
        "wifi scan": "Scan WiFi networks",
        "wifi deauth": "Deauth attack",
        "ble scan": "Scan BLE devices",
        "ble spam": "BLE advertisement spam",
        "ir send": "Send IR signal",
        "ir receive": "Receive IR signal",
        "subghz scan": "Scan SubGHz frequencies",
        "subghz send": "Send SubGHz signal",
        "nfc read": "Read NFC tag",
    }

    def get_scan_command(self) -> str:
        return "wifi scan"

    def get_stop_command(self) -> str:
        return "stop"
