from src.protocols.base import DeviceProtocol


class GhostESPProtocol(DeviceProtocol):

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
    }

    def get_scan_command(self) -> str:
        return "scanap"

    def get_stop_command(self) -> str:
        return "stop"
