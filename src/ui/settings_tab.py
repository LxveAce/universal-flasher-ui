from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QLineEdit, QPushButton, QLabel,
    QMessageBox, QHBoxLayout,
)
from PyQt5.QtCore import pyqtSignal

from src.config.settings import load_settings, save_settings
from src.core.profile_loader import ProfileLoader


class SettingsTab(QWidget):

    # Emitted when the user clicks "Reload Profiles"; the main window routes
    # this to the Flash tab so it re-reads the profiles directory from disk.
    profiles_reload_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._settings = load_settings()
        self._build_ui()
        self._connect_signals()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Serial settings
        serial_group = QGroupBox("Serial Defaults")
        serial_form = QFormLayout(serial_group)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "921600", "9600", "57600"])
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 30)
        self.timeout_spin.setValue(5)
        serial_form.addRow("Default Baud Rate:", self.baud_combo)
        serial_form.addRow("Connection Timeout (s):", self.timeout_spin)
        layout.addWidget(serial_group)

        # Flash settings
        flash_group = QGroupBox("Flash Defaults")
        flash_form = QFormLayout(flash_group)
        self.verify_check = QCheckBox("Verify after flash")
        self.verify_check.setChecked(True)
        self.backup_check = QCheckBox("Auto-backup before flash")
        self.backup_check.setChecked(True)
        self.flash_baud = QComboBox()
        self.flash_baud.addItems(["921600", "460800", "230400", "115200"])
        flash_form.addRow(self.verify_check)
        flash_form.addRow(self.backup_check)
        flash_form.addRow("Flash Baud Rate:", self.flash_baud)
        layout.addWidget(flash_group)

        # Cross-comm settings
        comm_group = QGroupBox("Cross-Communication")
        comm_form = QFormLayout(comm_group)
        self.auto_discover = QCheckBox("Auto-share discoveries to pool")
        self.auto_discover.setChecked(True)
        self.dedup_check = QCheckBox("De-duplicate targets by MAC")
        self.dedup_check.setChecked(True)
        comm_form.addRow(self.auto_discover)
        comm_form.addRow(self.dedup_check)
        layout.addWidget(comm_group)

        # Profile directory
        profile_group = QGroupBox("Firmware Profiles")
        profile_form = QFormLayout(profile_group)
        self.profile_dir = QLineEdit()
        self.profile_dir.setPlaceholderText("./src/config/profiles/")
        self.profile_dir.setReadOnly(True)
        self.profile_dir.setText(ProfileLoader().profile_dir)
        self.reload_btn = QPushButton("Reload Profiles")
        profile_form.addRow("Profile Directory:", self.profile_dir)
        profile_form.addRow(self.reload_btn)
        layout.addWidget(profile_group)

        # Save / Reset buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.reset_btn = QPushButton("Reset to Defaults")
        btn_row.addStretch()
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _connect_signals(self):
        self.save_btn.clicked.connect(self._save)
        self.reset_btn.clicked.connect(self._reset)
        self.reload_btn.clicked.connect(lambda: self.profiles_reload_requested.emit())

    def _load_current(self):
        """Load current settings into the UI widgets."""
        s = self._settings

        # Serial
        baud = str(s.get("serial", {}).get("default_baud", 115200))
        idx = self.baud_combo.findText(baud)
        if idx >= 0:
            self.baud_combo.setCurrentIndex(idx)
        self.timeout_spin.setValue(s.get("serial", {}).get("timeout", 5))

        # Flash
        self.verify_check.setChecked(s.get("flash", {}).get("verify", True))
        self.backup_check.setChecked(s.get("flash", {}).get("auto_backup", True))
        flash_baud = str(s.get("flash", {}).get("baud", 921600))
        idx = self.flash_baud.findText(flash_baud)
        if idx >= 0:
            self.flash_baud.setCurrentIndex(idx)

        # Cross-comm
        self.auto_discover.setChecked(s.get("cross_comm", {}).get("auto_share", True))
        self.dedup_check.setChecked(s.get("cross_comm", {}).get("dedup_by_mac", True))

    def _gather(self) -> dict:
        """Gather current UI state into a settings dict."""
        return {
            "serial": {
                "default_baud": int(self.baud_combo.currentText()),
                "timeout": self.timeout_spin.value(),
            },
            "flash": {
                "baud": int(self.flash_baud.currentText()),
                "verify": self.verify_check.isChecked(),
                "auto_backup": self.backup_check.isChecked(),
            },
            "cross_comm": {
                "auto_share": self.auto_discover.isChecked(),
                "dedup_by_mac": self.dedup_check.isChecked(),
            },
        }

    def _save(self):
        """Save settings to disk."""
        self._settings = self._gather()
        try:
            save_settings(self._settings)
            QMessageBox.information(self, "Settings", "Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def _reset(self):
        """Reset all settings to defaults."""
        from src.config.settings import DEFAULTS
        self._settings = dict(DEFAULTS)
        self._load_current()

    def showEvent(self, event):
        """Reload settings from disk when tab is shown."""
        super().showEvent(event)
        self._settings = load_settings()
        self._load_current()

    def get_settings(self) -> dict:
        """Get current settings (for use by other components)."""
        return self._settings
