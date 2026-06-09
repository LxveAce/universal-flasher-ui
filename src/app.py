from PyQt5.QtWidgets import QMainWindow, QTabWidget, QStatusBar
from PyQt5.QtCore import Qt

from src.ui.flash_tab import FlashTab
from src.ui.device_tab import DeviceTab
from src.ui.cross_comm_tab import CrossCommTab
from src.ui.settings_tab import SettingsTab
from src.core.device_manager import DeviceManager
from src.core.cross_comm import CrossCommBroker


class UniversalFlasherUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Flasher & UI")
        self.setMinimumSize(1200, 800)

        self.device_manager = DeviceManager()
        self.cross_comm = CrossCommBroker()

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        self.flash_tab = FlashTab(self.device_manager)
        self.device_tab = DeviceTab(self.device_manager, self.cross_comm)
        self.cross_comm_tab = CrossCommTab(self.cross_comm, self.device_manager)
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.flash_tab, "Flash")
        self.tabs.addTab(self.device_tab, "Devices")
        self.tabs.addTab(self.cross_comm_tab, "Cross-Comm")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("No devices connected")

    def _connect_signals(self):
        self.device_manager.device_connected.connect(self._on_device_connected)
        self.device_manager.device_disconnected.connect(self._on_device_disconnected)

    def _on_device_connected(self, device):
        count = len(self.device_manager.connected_devices)
        self.status_bar.showMessage(f"{count} device(s) connected")

    def _on_device_disconnected(self, port):
        count = len(self.device_manager.connected_devices)
        msg = f"{count} device(s) connected" if count else "No devices connected"
        self.status_bar.showMessage(msg)

    def closeEvent(self, event):
        self.device_manager.disconnect_all()
        super().closeEvent(event)
