"""Main window shell — tab management lives in app.py, this holds shared toolbar/menu logic."""

from PyQt5.QtWidgets import QMainWindow


class MainWindowMixin:
    """Mixin for menu bar and toolbar setup. Applied to UniversalFlasherUI."""

    def build_menu_bar(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        file_menu.addAction("&Scan for Devices", self.device_manager.scan)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        view_menu = menu.addMenu("&View")
        view_menu.addAction("&Flash", lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction("&Devices", lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction("&Cross-Comm", lambda: self.tabs.setCurrentIndex(2))
        view_menu.addAction("&Settings", lambda: self.tabs.setCurrentIndex(3))
