from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QTextEdit, QLineEdit, QPushButton, QGroupBox,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt

from src.core.serial_handler import SerialHandler
from src.protocols import PROTOCOL_DISPLAY_NAMES, get_protocol_by_display


class DeviceTab(QWidget):
    """Per-device serial terminal, command palette, and live data tables."""

    # A scanning device (marauder/bruce/etc.) can stream thousands of APs/stations rapidly. Cap the
    # per-device target store so neither the list nor the QTableWidget grows without bound and freezes
    # the UI, and cap the terminal so it can't accumulate unbounded text. Mirrors the headless-marauder-gui
    # table-row cap (HMG-Q1).
    _MAX_TARGETS = 2000
    _MAX_TERMINAL_BLOCKS = 5000

    def __init__(self, device_manager, cross_comm):
        super().__init__()
        self.device_manager = device_manager
        self.cross_comm = cross_comm
        self.serial_handler = SerialHandler()
        self._current_port = None
        self._protocols = {}  # port -> protocol instance
        self._targets = {}    # port -> list of Target

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # Left: device list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.device_list = QListWidget()
        self.device_list.setMaximumWidth(250)
        self.scan_btn = QPushButton("Scan Ports")
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)

        left_layout.addWidget(QLabel("Available Devices"))
        left_layout.addWidget(self.device_list)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.disconnect_btn)
        left_layout.addLayout(btn_row)
        left_layout.addWidget(self.scan_btn)

        splitter.addWidget(left)

        # Right: terminal + data
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Command bar
        cmd_row = QHBoxLayout()
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(list(PROTOCOL_DISPLAY_NAMES.keys()))
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command...")
        self.send_btn = QPushButton("Send")
        self.scan_device_btn = QPushButton("Start Scan")
        self.stop_scan_btn = QPushButton("Stop")
        cmd_row.addWidget(QLabel("Protocol:"))
        cmd_row.addWidget(self.protocol_combo)
        cmd_row.addWidget(self.cmd_input, 1)
        cmd_row.addWidget(self.send_btn)
        cmd_row.addWidget(self.scan_device_btn)
        cmd_row.addWidget(self.stop_scan_btn)
        right_layout.addLayout(cmd_row)

        # Serial output
        self.serial_output = QTextEdit()
        self.serial_output.setReadOnly(True)
        self.serial_output.setStyleSheet(
            "font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 11px;"
        )
        self.serial_output.setPlaceholderText("Connect to a device to see serial output...")
        # Bound the live terminal — a long scan streams endlessly; drop the oldest blocks past the cap.
        self.serial_output.document().setMaximumBlockCount(self._MAX_TERMINAL_BLOCKS)
        right_layout.addWidget(self.serial_output, 2)

        # Command palette
        cmd_group = QGroupBox("Available Commands")
        cmd_layout = QVBoxLayout(cmd_group)
        self.cmd_list = QListWidget()
        self.cmd_list.setMaximumHeight(100)
        cmd_layout.addWidget(self.cmd_list)
        right_layout.addWidget(cmd_group)

        # Live data table (APs, stations, BLE, targets)
        data_group = QGroupBox("Discovered Targets")
        data_layout = QVBoxLayout(data_group)
        self.target_table = QTableWidget(0, 6)
        self.target_table.setHorizontalHeaderLabels([
            "Type", "Identifier", "MAC", "RSSI", "Channel", "Source Device",
        ])
        self.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        share_row = QHBoxLayout()
        self.share_btn = QPushButton("Share Selected to Cross-Comm")
        self.share_btn.setEnabled(False)
        self.clear_targets_btn = QPushButton("Clear Targets")
        share_row.addStretch()
        share_row.addWidget(self.clear_targets_btn)
        share_row.addWidget(self.share_btn)

        data_layout.addWidget(self.target_table)
        data_layout.addLayout(share_row)
        right_layout.addWidget(data_group, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def _connect_signals(self):
        # Buttons
        self.scan_btn.clicked.connect(self._scan_ports)
        self.connect_btn.clicked.connect(self._connect_device)
        self.disconnect_btn.clicked.connect(self._disconnect_device)
        self.send_btn.clicked.connect(self._send_command)
        self.scan_device_btn.clicked.connect(self._start_device_scan)
        self.stop_scan_btn.clicked.connect(self._stop_device_scan)
        self.share_btn.clicked.connect(self._share_target)
        self.clear_targets_btn.clicked.connect(self._clear_targets)

        # Enter key in command input
        self.cmd_input.returnPressed.connect(self._send_command)

        # Device list selection changes
        self.device_list.currentRowChanged.connect(self._on_device_selected)

        # Protocol combo changes
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)

        # Command list double-click sends the command
        self.cmd_list.itemDoubleClicked.connect(self._on_cmd_double_click)

        # Target table selection enables share button
        self.target_table.itemSelectionChanged.connect(self._on_target_selection)

        # Serial handler data
        self.serial_handler.line_received.connect(self._on_serial_line)

        # Device manager signals
        self.device_manager.device_connected.connect(lambda _: self._scan_ports())
        self.device_manager.device_disconnected.connect(self._on_device_disconnected)

    def _scan_ports(self):
        """Scan for available serial ports and populate the device list."""
        self.device_list.clear()
        scanned = self.device_manager.scan()

        for info in scanned:
            port = info["port"]
            connected = port in self.device_manager.connected_devices
            status = " [CONNECTED]" if connected else ""
            label = f"{port} - {info['desc']}{status}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, port)
            if connected:
                item.setForeground(Qt.green)
            self.device_list.addItem(item)

        if not scanned:
            item = QListWidgetItem("No devices found")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.device_list.addItem(item)

    def _get_selected_port(self):
        """Get port from currently selected device list item."""
        item = self.device_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _connect_device(self):
        """Connect to the selected serial device."""
        port = self._get_selected_port()
        if not port:
            return

        if port in self.device_manager.connected_devices:
            self.serial_output.append(f"[INFO] Already connected to {port}")
            return

        # Get protocol key for the selected protocol
        proto_display = self.protocol_combo.currentText()
        proto_key = PROTOCOL_DISPLAY_NAMES.get(proto_display, "raw")

        try:
            baud = 115200
            device = self.device_manager.connect(port, baud, proto_key)
            self._current_port = port
            self._protocols[port] = get_protocol_by_display(proto_display)
            self._targets[port] = []

            # Start reading serial data
            self.serial_handler.start_reading(port, device.connection)

            self.serial_output.append(f"[INFO] Connected to {port} at {baud} baud ({proto_display})")
            self.disconnect_btn.setEnabled(True)
            self._scan_ports()  # refresh list to show connected status
            self._update_command_list()
        except Exception as e:
            self.serial_output.append(f"[ERROR] Failed to connect to {port}: {e}")

    def _disconnect_device(self):
        """Disconnect from the current device."""
        port = self._current_port
        if not port:
            return

        self.serial_handler.stop_reading(port)
        self.device_manager.disconnect(port)
        self._protocols.pop(port, None)
        self._targets.pop(port, None)

        self.serial_output.append(f"[INFO] Disconnected from {port}")
        self._current_port = None
        self.disconnect_btn.setEnabled(False)
        self._scan_ports()

    def _on_device_disconnected(self, port):
        """Handle device being disconnected (USB unplug, etc.)."""
        if port == self._current_port:
            self.serial_handler.stop_reading(port)
            self._protocols.pop(port, None)
            self._targets.pop(port, None)
            self.serial_output.append(f"[WARN] Device {port} disconnected unexpectedly")
            self._current_port = None
            self.disconnect_btn.setEnabled(False)
        self._scan_ports()

    def _on_device_selected(self, row):
        """When a device is selected in the list, switch context to it."""
        port = self._get_selected_port()
        if port and port in self.device_manager.connected_devices:
            self._current_port = port
            self.disconnect_btn.setEnabled(True)
            self._update_command_list()
            self._refresh_target_table()
        else:
            self.connect_btn.setEnabled(port is not None)

    def _send_command(self):
        """Send the command input text to the current device."""
        if not self._current_port:
            self.serial_output.append("[WARN] No device connected")
            return

        text = self.cmd_input.text().strip()
        if not text:
            return

        # Check if protocol has a build_command that transforms the input
        proto = self._protocols.get(self._current_port)
        if proto:
            text = proto.build_command(text)

        # If the command contains newlines (multi-step), send each line
        for line in text.split("\n"):
            line = line.strip()
            if line:
                self.device_manager.send(self._current_port, line)
                self.serial_output.append(f"> {line}")

        self.cmd_input.clear()

    def _start_device_scan(self):
        """Send the protocol's scan command to the current device."""
        if not self._current_port:
            return
        proto = self._protocols.get(self._current_port)
        if proto:
            cmd = proto.get_scan_command()
            if cmd:
                self.device_manager.send(self._current_port, cmd)
                self.serial_output.append(f"> {cmd}")

    def _stop_device_scan(self):
        """Send the protocol's stop command to the current device."""
        if not self._current_port:
            return
        proto = self._protocols.get(self._current_port)
        if proto:
            cmd = proto.get_stop_command()
            if cmd:
                self.device_manager.send(self._current_port, cmd)
                self.serial_output.append(f"> {cmd}")

    def _on_serial_line(self, port, line):
        """Handle a line of serial data from a device."""
        # Only show output for the currently viewed device
        if port == self._current_port:
            self.serial_output.append(line)
            # Auto-scroll
            scrollbar = self.serial_output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        # Parse through protocol regardless of which device is displayed
        proto = self._protocols.get(port)
        if proto:
            target = proto.parse_line(line, port)
            if target:
                # Add to local target list
                if port not in self._targets:
                    self._targets[port] = []
                # Cap the local store so a device streaming thousands of targets can't grow the list +
                # QTableWidget without bound (UI freeze / memory). Cross-comm still gets every target.
                if len(self._targets[port]) < self._MAX_TARGETS:
                    self._targets[port].append(target)

                    # Update table if this is the current device
                    if port == self._current_port:
                        self._add_target_to_table(target)

                # Auto-share to cross-comm if enabled
                # (The CrossCommTab's auto_share checkbox controls this,
                #  but we always publish here -- the broker deduplicates)
                self.cross_comm.publish(target)

    def _on_protocol_changed(self, display_name):
        """Switch the active protocol for the current device."""
        if self._current_port and self._current_port in self._protocols:
            self._protocols[self._current_port] = get_protocol_by_display(display_name)
            self._update_command_list()

    def _update_command_list(self):
        """Populate the command palette based on current protocol."""
        self.cmd_list.clear()
        proto = self._protocols.get(self._current_port)
        if not proto:
            return
        for cmd, desc in proto.list_commands().items():
            self.cmd_list.addItem(f"{cmd}  --  {desc}")

    def _on_cmd_double_click(self, item):
        """Insert a command from the palette into the input field."""
        text = item.text()
        cmd = text.split("  --  ")[0].strip()
        self.cmd_input.setText(cmd)

    def _add_target_to_table(self, target):
        """Add a discovered target to the table widget."""
        row = self.target_table.rowCount()
        self.target_table.insertRow(row)
        self.target_table.setItem(row, 0, QTableWidgetItem(target.type))
        self.target_table.setItem(row, 1, QTableWidgetItem(target.identifier))
        self.target_table.setItem(row, 2, QTableWidgetItem(target.mac or ""))
        self.target_table.setItem(row, 3, QTableWidgetItem(str(target.rssi) if target.rssi else ""))
        self.target_table.setItem(row, 4, QTableWidgetItem(str(target.channel) if target.channel else ""))
        self.target_table.setItem(row, 5, QTableWidgetItem(target.source_device))

    def _refresh_target_table(self):
        """Rebuild the target table from stored targets for current device."""
        self.target_table.setRowCount(0)
        targets = self._targets.get(self._current_port, [])
        for target in targets:
            self._add_target_to_table(target)

    def _clear_targets(self):
        """Clear the target table and stored targets for current device."""
        if self._current_port:
            self._targets[self._current_port] = []
        self.target_table.setRowCount(0)

    def _on_target_selection(self):
        """Enable share button when a target is selected."""
        self.share_btn.setEnabled(len(self.target_table.selectedItems()) > 0)

    def _share_target(self):
        """Share the selected target to the cross-comm pool."""
        row = self.target_table.currentRow()
        if row < 0:
            return

        targets = self._targets.get(self._current_port, [])
        if row < len(targets):
            target = targets[row]
            if not target.shared:
                target.shared = True
                self.cross_comm.publish(target)
                self.serial_output.append(f"[CROSS-COMM] Shared: {target.type} {target.identifier}")

    def showEvent(self, event):
        """Refresh port list when tab becomes visible."""
        super().showEvent(event)
        self._scan_ports()

    def cleanup(self):
        """Stop all serial readers on shutdown."""
        self.serial_handler.stop_all()
