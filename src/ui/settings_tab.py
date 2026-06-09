from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QComboBox,
    QSpinBox, QCheckBox, QLineEdit, QPushButton, QLabel,
)


class SettingsTab(QWidget):

    def __init__(self):
        super().__init__()
        self._build_ui()

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
        self.reload_btn = QPushButton("Reload Profiles")
        profile_form.addRow("Profile Directory:", self.profile_dir)
        profile_form.addRow(self.reload_btn)
        layout.addWidget(profile_group)

        layout.addStretch()
