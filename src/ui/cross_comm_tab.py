from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QTextEdit, QLabel, QComboBox, QCheckBox,
)
from PyQt5.QtCore import Qt


class CrossCommTab(QWidget):
    """Cross-device coordination — shared target pool, event stream, auto-routing."""

    def __init__(self, cross_comm, device_manager):
        super().__init__()
        self.cross_comm = cross_comm
        self.device_manager = device_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)

        # Top: shared target pool
        pool_group = QGroupBox("Shared Target Pool")
        pool_layout = QVBoxLayout(pool_group)

        self.target_pool_table = QTableWidget(0, 7)
        self.target_pool_table.setHorizontalHeaderLabels([
            "Type", "Identifier", "RSSI", "Channel", "Source Device", "Timestamp", "Status"
        ])
        self.target_pool_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        action_row = QHBoxLayout()
        self.target_device_combo = QComboBox()
        self.target_device_combo.setPlaceholderText("Send to device...")
        self.action_combo = QComboBox()
        self.action_combo.addItems(["Deauth", "Sniff PMKID", "Sniff Traffic", "Clone (BLE)", "Track", "Custom..."])
        self.execute_btn = QPushButton("Execute on Target Device")
        self.execute_btn.setEnabled(False)
        action_row.addWidget(QLabel("Route to:"))
        action_row.addWidget(self.target_device_combo)
        action_row.addWidget(QLabel("Action:"))
        action_row.addWidget(self.action_combo)
        action_row.addWidget(self.execute_btn)

        pool_layout.addWidget(self.target_pool_table)
        pool_layout.addLayout(action_row)
        splitter.addWidget(pool_group)

        # Bottom: event stream + auto-rules
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)

        # Event stream
        stream_group = QGroupBox("Event Stream")
        stream_layout = QVBoxLayout(stream_group)
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 10px;")
        self.event_log.setPlaceholderText("Device events will appear here in real-time...")
        self.auto_share = QCheckBox("Auto-share all discoveries to pool")
        self.auto_share.setChecked(True)
        stream_layout.addWidget(self.event_log)
        stream_layout.addWidget(self.auto_share)
        bottom_layout.addWidget(stream_group, 2)

        # Auto-routing rules
        rules_group = QGroupBox("Auto-Routing Rules")
        rules_layout = QVBoxLayout(rules_group)
        rules_layout.addWidget(QLabel("When a target is discovered:"))

        self.rule_list = QTextEdit()
        self.rule_list.setPlaceholderText(
            "Example rules (not yet implemented):\n\n"
            "IF source=Marauder AND type=AP\n"
            "  THEN send sniffpmkid to Sniffer\n\n"
            "IF source=BLE-Scanner AND type=BLE\n"
            "  THEN log + alert\n\n"
            "IF type=SubGHz AND freq=315MHz\n"
            "  THEN replay on HaleHound"
        )
        self.rule_list.setReadOnly(True)

        self.add_rule_btn = QPushButton("Add Rule...")
        self.add_rule_btn.setEnabled(False)

        rules_layout.addWidget(self.rule_list)
        rules_layout.addWidget(self.add_rule_btn)
        bottom_layout.addWidget(rules_group, 1)

        splitter.addWidget(bottom)

        layout.addWidget(splitter)
