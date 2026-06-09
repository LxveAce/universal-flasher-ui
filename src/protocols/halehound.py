from src.protocols.base import DeviceProtocol


class HaleHoundProtocol(DeviceProtocol):

    name = "halehound"
    commands = {
        "wifi_scan": "Scan WiFi access points",
        "wifi_deauth": "WiFi deauth attack",
        "iot_recon": "IoT Recon — automated LAN scan + credential brute force",
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
        "guardian": "WiFi Guardian — rogue AP detection",
        "stalkerware": "Stalkerware Detect",
    }

    def get_scan_command(self) -> str:
        return "wifi_scan"

    def get_stop_command(self) -> str:
        return "stop"
