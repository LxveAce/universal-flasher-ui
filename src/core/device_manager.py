import serial.tools.list_ports
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from src.models.device import ConnectedDevice


class DeviceManager(QObject):
    """Detects, connects, and manages serial devices."""

    device_connected = pyqtSignal(object)
    device_disconnected = pyqtSignal(str)

    KNOWN_VIDS = {
        0x1A86: "CH340 (ESP32 clone)",
        0x10C4: "CP2102 (ESP32/Heltec)",
        0x303A: "ESP32-S2/S3 native USB",
        0x0403: "FTDI (generic)",
    }

    def __init__(self):
        super().__init__()
        self.connected_devices: dict[str, ConnectedDevice] = {}

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_ports)
        self._poll_timer.start(2000)

    def scan(self):
        """Manual scan for available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [
            {
                "port": p.device,
                "desc": p.description,
                "vid": p.vid,
                "pid": p.pid,
                "serial": p.serial_number,
                "chip": self.KNOWN_VIDS.get(p.vid, "Unknown"),
            }
            for p in ports
        ]

    def connect(self, port, baud=115200, protocol="raw"):
        """Open a serial connection and register the device."""
        if port in self.connected_devices:
            return self.connected_devices[port]

        conn = serial.Serial(port, baud, timeout=1)
        device = ConnectedDevice(
            port=port,
            connection=conn,
            protocol=protocol,
            baud=baud,
        )
        self.connected_devices[port] = device
        self.device_connected.emit(device)
        return device

    def disconnect(self, port):
        """Close connection and unregister."""
        device = self.connected_devices.pop(port, None)
        if device and device.connection.is_open:
            device.connection.close()
        self.device_disconnected.emit(port)

    def disconnect_all(self):
        for port in list(self.connected_devices.keys()):
            self.disconnect(port)

    def send(self, port, command):
        """Send a command string to a connected device."""
        device = self.connected_devices.get(port)
        if not device or not device.connection.is_open:
            return
        device.connection.write(f"{command}\n".encode())

    def read(self, port):
        """Read available data from a connected device."""
        device = self.connected_devices.get(port)
        if not device or not device.connection.is_open:
            return ""
        if device.connection.in_waiting:
            return device.connection.read(device.connection.in_waiting).decode(errors="replace")
        return ""

    def _poll_ports(self):
        """Auto-detect disconnected devices."""
        current = {p.device for p in serial.tools.list_ports.comports()}
        for port in list(self.connected_devices.keys()):
            if port not in current:
                self.disconnect(port)
