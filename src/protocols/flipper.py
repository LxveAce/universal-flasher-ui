from src.protocols.base import DeviceProtocol


class FlipperProtocol(DeviceProtocol):

    name = "flipper"
    commands = {
        "subghz rx": "Receive SubGHz signals",
        "subghz tx": "Transmit SubGHz signal",
        "nfc detect": "Detect NFC tags",
        "nfc read": "Read NFC tag data",
        "nfc emulate": "Emulate NFC tag",
        "rfid read": "Read 125kHz RFID",
        "ir rx": "Receive IR signal",
        "ir tx": "Transmit IR signal",
        "bt info": "Bluetooth info",
        "gpio": "GPIO control",
        "storage list": "List storage contents",
        "power info": "Battery and power info",
    }

    def get_scan_command(self) -> str:
        return "subghz rx"

    def get_stop_command(self) -> str:
        return "subghz rx stop"
