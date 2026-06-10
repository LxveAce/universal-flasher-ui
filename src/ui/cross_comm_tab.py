from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QTextEdit, QLabel, QComboBox, QCheckBox, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox, QListWidget,
    QListWidgetItem, QMessageBox,
)
from PyQt5.QtCore import Qt


class AddRuleDialog(QDialog):
    """Dialog for adding a new auto-routing rule."""

    def __init__(self, device_ports, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Auto-Routing Rule")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.match_type = QComboBox()
        self.match_type.addItems(["*", "AP", "STA", "BLE", "SubGHz", "NFC", "RFID", "IR", "IoT"])
        layout.addRow("Match target type:", self.match_type)

        self.match_source = QComboBox()
        self.match_source.addItem("* (any device)", "*")
        for port in device_ports:
            self.match_source.addItem(port, port)
        layout.addRow("Match source device:", self.match_source)

        self.dest_port = QComboBox()
        for port in device_ports:
            self.dest_port.addItem(port, port)
        layout.addRow("Send to device:", self.dest_port)

        self.action = QLineEdit()
        self.action.setPlaceholderText("e.g. sniffpmkid {identifier}")
        self.action.setToolTip(
            "Available placeholders: {identifier}, {mac}, {channel}"
        )
        layout.addRow("Action command:", self.action)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_rule(self):
        return {
            "match_type": self.match_type.currentText(),
            "match_source": self.match_source.currentData(),
            "dest_port": self.dest_port.currentData(),
            "action": self.action.text(),
        }


class CrossCommTab(QWidget):
    """Cross-device coordination -- shared target pool, event stream, auto-routing."""

    def __init__(self, cross_comm, device_manager):
        super().__init__()
        self.cross_comm = cross_comm
        self.device_manager = device_manager
        self._rules = []

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)

        # Top: shared target pool
        pool_group = QGroupBox("Shared Target Pool")
        pool_layout = QVBoxLayout(pool_group)

        self.target_pool_table = QTableWidget(0, 7)
        self.target_pool_table.setHorizontalHeaderLabels([
            "Type", "Identifier", "MAC", "RSSI", "Channel", "Source Device", "Timestamp",
        ])
        self.target_pool_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        action_row = QHBoxLayout()
        self.target_device_combo = QComboBox()
        self.target_device_combo.setPlaceholderText("Send to device...")
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            "Deauth", "Sniff PMKID", "Sniff Traffic",
            "Clone (BLE)", "Track", "Custom...",
        ])
        self.execute_btn = QPushButton("Execute on Target Device")
        self.execute_btn.setEnabled(False)
        self.clear_pool_btn = QPushButton("Clear Pool")

        action_row.addWidget(QLabel("Route to:"))
        action_row.addWidget(self.target_device_combo)
        action_row.addWidget(QLabel("Action:"))
        action_row.addWidget(self.action_combo)
        action_row.addWidget(self.execute_btn)
        action_row.addWidget(self.clear_pool_btn)

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
        self.event_log.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; font-size: 10px;"
        )
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

        self.rule_list = QListWidget()

        rule_btn_row = QHBoxLayout()
        self.add_rule_btn = QPushButton("Add Rule...")
        self.remove_rule_btn = QPushButton("Remove Rule")
        self.remove_rule_btn.setEnabled(False)
        rule_btn_row.addWidget(self.add_rule_btn)
        rule_btn_row.addWidget(self.remove_rule_btn)

        rules_layout.addWidget(self.rule_list)
        rules_layout.addLayout(rule_btn_row)
        bottom_layout.addWidget(rules_group, 1)

        splitter.addWidget(bottom)

        layout.addWidget(splitter)

    def _connect_signals(self):
        # Cross-comm broker signals
        self.cross_comm.target_discovered.connect(self._on_target_discovered)
        self.cross_comm.event_logged.connect(self._on_event_logged)
        self.cross_comm.target_routed.connect(self._on_target_routed)

        # Device manager signals (to update device combos)
        self.device_manager.device_connected.connect(self._refresh_device_combos)
        self.device_manager.device_disconnected.connect(self._refresh_device_combos)

        # Table selection
        self.target_pool_table.itemSelectionChanged.connect(self._on_pool_selection)

        # Buttons
        self.execute_btn.clicked.connect(self._execute_action)
        self.clear_pool_btn.clicked.connect(self._clear_pool)
        self.add_rule_btn.clicked.connect(self._add_rule)
        self.remove_rule_btn.clicked.connect(self._remove_rule)
        self.rule_list.currentRowChanged.connect(
            lambda row: self.remove_rule_btn.setEnabled(row >= 0)
        )

    def _on_target_discovered(self, target):
        """Add a newly discovered target to the pool table."""
        row = self.target_pool_table.rowCount()
        self.target_pool_table.insertRow(row)
        self.target_pool_table.setItem(row, 0, QTableWidgetItem(target.type))
        self.target_pool_table.setItem(row, 1, QTableWidgetItem(target.identifier))
        self.target_pool_table.setItem(row, 2, QTableWidgetItem(target.mac or ""))
        self.target_pool_table.setItem(row, 3, QTableWidgetItem(str(target.rssi) if target.rssi else ""))
        self.target_pool_table.setItem(row, 4, QTableWidgetItem(str(target.channel) if target.channel else ""))
        self.target_pool_table.setItem(row, 5, QTableWidgetItem(target.source_device))
        self.target_pool_table.setItem(row, 6, QTableWidgetItem(
            target.discovered_at.strftime("%H:%M:%S")
        ))

    def _on_event_logged(self, msg):
        """Append an event to the event stream."""
        self.event_log.append(msg)
        scrollbar = self.event_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_target_routed(self, message):
        """Handle a routed cross-comm message -- send the action to the target device."""
        port = message.dest_port
        action = message.action

        if port in self.device_manager.connected_devices:
            self.device_manager.send(port, action)
            message.executed = True
            message.result = "sent"
        else:
            message.result = f"device {port} not connected"

    def _on_pool_selection(self):
        """Enable execute button when a target and destination are selected."""
        has_selection = len(self.target_pool_table.selectedItems()) > 0
        has_dest = self.target_device_combo.currentIndex() >= 0
        self.execute_btn.setEnabled(has_selection and has_dest)

    def _refresh_device_combos(self, *_args):
        """Refresh device combo boxes with connected devices."""
        current = self.target_device_combo.currentText()
        self.target_device_combo.clear()

        for port, device in self.device_manager.connected_devices.items():
            self.target_device_combo.addItem(device.display_name, port)

        # Restore selection
        idx = self.target_device_combo.findText(current)
        if idx >= 0:
            self.target_device_combo.setCurrentIndex(idx)

    def _execute_action(self):
        """Execute the selected action on the selected target via the selected device."""
        row = self.target_pool_table.currentRow()
        if row < 0 or row >= len(self.cross_comm.target_pool):
            return

        dest_idx = self.target_device_combo.currentIndex()
        if dest_idx < 0:
            return

        target = self.cross_comm.target_pool[row]
        dest_port = self.target_device_combo.currentData()
        action_text = self.action_combo.currentText()

        # Map display action to protocol command
        action_map = {
            "Deauth": "deauth",
            "Sniff PMKID": "sniffpmkid",
            "Sniff Traffic": "sniffraw",
            "Clone (BLE)": "ble_clone",
            "Track": "track",
        }
        action_cmd = action_map.get(action_text, action_text)

        if action_text == "Custom...":
            from PyQt5.QtWidgets import QInputDialog
            cmd, ok = QInputDialog.getText(
                self, "Custom Command",
                f"Command to send to {dest_port} for target {target.identifier}:"
            )
            if ok and cmd:
                action_cmd = cmd
            else:
                return

        self.cross_comm.route_to_device(target, dest_port, action_cmd)

    def _clear_pool(self):
        """Clear the shared target pool."""
        self.cross_comm.clear_pool()
        self.target_pool_table.setRowCount(0)

    def _add_rule(self):
        """Open dialog to add a new auto-routing rule."""
        ports = list(self.device_manager.connected_devices.keys())
        if not ports:
            QMessageBox.information(
                self, "No Devices",
                "Connect at least one device before creating routing rules."
            )
            return

        dialog = AddRuleDialog(ports, self)
        if dialog.exec_() == QDialog.Accepted:
            rule = dialog.get_rule()
            if rule["action"]:
                self._rules.append(rule)
                self.cross_comm.subscribe(rule)
                display = (
                    f"IF type={rule['match_type']} AND source={rule['match_source']} "
                    f"THEN {rule['action']} -> {rule['dest_port']}"
                )
                self.rule_list.addItem(display)

    def _remove_rule(self):
        """Remove the selected auto-routing rule."""
        row = self.rule_list.currentRow()
        if row >= 0:
            self.rule_list.takeItem(row)
            if row < len(self._rules):
                self._rules.pop(row)

    def showEvent(self, event):
        """Refresh device combos when tab becomes visible."""
        super().showEvent(event)
        self._refresh_device_combos()
