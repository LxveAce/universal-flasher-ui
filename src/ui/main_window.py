"""Main window shell -- menu bar and toolbar setup."""

from PyQt5.QtWidgets import QAction, QMessageBox


class MainWindowMixin:
    """Mixin for menu bar and toolbar setup. Applied to UniversalFlasherUI."""

    def build_menu_bar(self):
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("&File")

        scan_action = QAction("&Scan for Devices", self)
        scan_action.setShortcut("Ctrl+Shift+S")
        scan_action.triggered.connect(self._menu_scan)
        file_menu.addAction(scan_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menu.addMenu("&View")

        flash_action = QAction("&Flash", self)
        flash_action.setShortcut("Ctrl+1")
        flash_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction(flash_action)

        device_action = QAction("&Devices", self)
        device_action.setShortcut("Ctrl+2")
        device_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction(device_action)

        cross_action = QAction("&Cross-Comm", self)
        cross_action.setShortcut("Ctrl+3")
        cross_action.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        view_menu.addAction(cross_action)

        settings_action = QAction("&Settings", self)
        settings_action.setShortcut("Ctrl+4")
        settings_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        view_menu.addAction(settings_action)

        # Help menu
        help_menu = menu.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _menu_scan(self):
        """Trigger a device scan from the menu."""
        self.device_tab._scan_ports()
        self.tabs.setCurrentIndex(1)

    def _show_about(self):
        QMessageBox.about(
            self,
            "Universal Flasher & UI",
            "Universal Flasher & UI v0.1.0\n\n"
            "Unified firmware flashing, device serial control,\n"
            "and cross-device coordination.\n\n"
            "Supports ESP32, Flipper Zero, and Raspberry Pi.\n\n"
            "github.com/LxveAce/universal-flasher-ui",
        )
