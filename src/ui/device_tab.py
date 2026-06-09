from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QTextEdit, QLineEdit, QPushButton, QGroupBox,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt


class DeviceTab(QWidget):
    """Per-device serial terminal, command palette, and live data tables."""

    def __init__(self, device_manager, cross_comm):
        super().__init__()
        self.device_manager = device_manager
        self.cross_comm = cross_comm
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # Left: device list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.device_list = QListWidget()
        self.device_list.setMaximumWidth(220)
        self.scan_btn = QPushButton("Scan Ports")
        left_layout.addWidget(QLabel("Connected Devices"))
        left_layout.addWidget(self.device_list)
        left_layout.addWidget(self.scan_btn)

        splitter.addWidget(left)

        # Right: terminal + data
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Command bar
        cmd_row = QHBoxLayout()
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["Marauder", "GhostESP", "Bruce", "HaleHound", "Flipper", "Raw"])
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command...")
        self.send_btn = QPushButton("Send")
        cmd_row.addWidget(self.protocol_combo)
        cmd_row.addWidget(self.cmd_input, 1)
        cmd_row.addWidget(self.send_btn)
        right_layout.addLayout(cmd_row)

        # Serial output
        self.serial_output = QTextEdit()
        self.serial_output.setReadOnly(True)
        self.serial_output.setStyleSheet("font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 11px;")
        right_layout.addWidget(self.serial_output, 2)

        # Live data table (APs, stations, BLE, targets)
        data_group = QGroupBox("Discovered Targets")
        data_layout = QVBoxLayout(data_group)
        self.target_table = QTableWidget(0, 5)
        self.target_table.setHorizontalHeaderLabels(["Type", "Identifier", "RSSI", "Channel", "Source Device"])
        self.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        share_row = QHBoxLayout()
        self.share_btn = QPushButton("Share Selected to Cross-Comm")
        self.share_btn.setEnabled(False)
        share_row.addStretch()
        share_row.addWidget(self.share_btn)

        data_layout.addWidget(self.target_table)
        data_layout.addLayout(share_row)
        right_layout.addWidget(data_group, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
