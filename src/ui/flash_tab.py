import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QProgressBar, QLabel, QGroupBox, QListWidget, QTextEdit,
    QFileDialog, QMessageBox, QListWidgetItem,
)
from PyQt5.QtCore import Qt

from src.core.flash_engine import FlashEngine
from src.core.profile_loader import ProfileLoader


class FlashTab(QWidget):
    """Firmware flashing interface -- profile selection, batch queue, progress."""

    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self.flash_engine = FlashEngine()
        self.profile_loader = ProfileLoader()
        self._active_worker = None
        self._firmware_path = ""
        self._batch_queue = []  # list of (port, profile_name, firmware_path)
        self._batch_active = False  # True only while a "Flash All" run is draining

        self._build_ui()
        self._connect_signals()
        self._load_profiles()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Device + firmware selection
        select_group = QGroupBox("Flash Configuration")
        select_layout = QHBoxLayout(select_group)

        self.device_combo = QComboBox()
        self.device_combo.setPlaceholderText("Select device...")
        self.firmware_combo = QComboBox()
        self.firmware_combo.setPlaceholderText("Select firmware...")
        self.browse_btn = QPushButton("Browse...")
        self.flash_btn = QPushButton("Flash")
        self.flash_btn.setEnabled(False)

        select_layout.addWidget(QLabel("Device:"))
        select_layout.addWidget(self.device_combo, 1)
        select_layout.addWidget(QLabel("Firmware:"))
        select_layout.addWidget(self.firmware_combo, 1)
        select_layout.addWidget(self.browse_btn)
        select_layout.addWidget(self.flash_btn)

        layout.addWidget(select_group)

        # Firmware file path display
        file_row = QHBoxLayout()
        self.file_label = QLabel("No firmware file selected")
        self.file_label.setStyleSheet("color: #888; font-style: italic;")
        file_row.addWidget(QLabel("File:"))
        file_row.addWidget(self.file_label, 1)
        layout.addLayout(file_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Batch queue
        batch_group = QGroupBox("Batch Queue")
        batch_layout = QVBoxLayout(batch_group)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        add_row = QHBoxLayout()
        self.add_to_queue_btn = QPushButton("Add to Queue")
        self.flash_all_btn = QPushButton("Flash All")
        self.clear_queue_btn = QPushButton("Clear")
        self.remove_from_queue_btn = QPushButton("Remove Selected")
        add_row.addWidget(self.add_to_queue_btn)
        add_row.addWidget(self.remove_from_queue_btn)
        add_row.addWidget(self.flash_all_btn)
        add_row.addWidget(self.clear_queue_btn)
        add_row.addStretch()
        batch_layout.addWidget(self.queue_list)
        batch_layout.addLayout(add_row)
        layout.addWidget(batch_group)

        # Flash log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Flash output will appear here...")
        layout.addWidget(self.log_output, 1)

    def _connect_signals(self):
        # Device manager signals
        self.device_manager.device_connected.connect(self._refresh_devices)
        self.device_manager.device_disconnected.connect(self._refresh_devices)

        # Combo box changes
        self.device_combo.currentIndexChanged.connect(self._update_flash_btn)
        self.firmware_combo.currentIndexChanged.connect(self._update_flash_btn)

        # Buttons
        self.browse_btn.clicked.connect(self._browse_firmware)
        self.flash_btn.clicked.connect(self._start_flash)
        self.add_to_queue_btn.clicked.connect(self._add_to_queue)
        self.remove_from_queue_btn.clicked.connect(self._remove_from_queue)
        self.flash_all_btn.clicked.connect(self._flash_all)
        self.clear_queue_btn.clicked.connect(self._clear_queue)

    def _load_profiles(self):
        """Load firmware profiles and populate the combo box."""
        self.profile_loader.load_all()
        self.firmware_combo.clear()
        for name in self.profile_loader.list_names():
            profile = self.profile_loader.get(name)
            self.firmware_combo.addItem(name, profile)

    def _refresh_devices(self, *_args):
        """Refresh the device combo box from DeviceManager scan results."""
        current = self.device_combo.currentText()
        self.device_combo.clear()

        # Add currently connected devices
        for port, device in self.device_manager.connected_devices.items():
            self.device_combo.addItem(device.display_name, port)

        # Also add detected but unconnected ports
        scanned = self.device_manager.scan()
        for info in scanned:
            port = info["port"]
            if port not in self.device_manager.connected_devices:
                label = f"{port} - {info['desc']} [{info['chip']}]"
                self.device_combo.addItem(label, port)

        # Restore selection if possible
        idx = self.device_combo.findText(current)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)

        self._update_flash_btn()

    def _update_flash_btn(self, *_args):
        """Enable flash button only when device and firmware are selected."""
        has_device = self.device_combo.currentIndex() >= 0
        has_firmware = self.firmware_combo.currentIndex() >= 0
        has_file = bool(self._firmware_path) and os.path.isfile(self._firmware_path)
        not_flashing = not self.flash_engine.is_flashing
        self.flash_btn.setEnabled(has_device and has_firmware and has_file and not_flashing)

    def _browse_firmware(self):
        """Open file dialog to select a firmware binary."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Firmware File",
            "",
            "Firmware Files (*.bin *.hex *.uf2 *.tgz *.zip);;All Files (*)",
        )
        if path:
            self._firmware_path = path
            self.file_label.setText(os.path.basename(path))
            self.file_label.setToolTip(path)
            self.file_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self._update_flash_btn()

    def _get_selected_port(self):
        """Get the port string from current device combo selection."""
        idx = self.device_combo.currentIndex()
        if idx < 0:
            return None
        return self.device_combo.itemData(idx)

    def _start_flash(self):
        """Start flashing the selected firmware to the selected device."""
        port = self._get_selected_port()
        if not port:
            return

        profile_name = self.firmware_combo.currentText()
        profile = self.profile_loader.get(profile_name)
        if not profile:
            self._log("[ERROR] No firmware profile selected")
            return

        if not self._firmware_path or not os.path.isfile(self._firmware_path):
            self._log("[ERROR] No firmware file selected")
            return

        # Disconnect serial reader if connected (flash needs exclusive port access)
        if port in self.device_manager.connected_devices:
            self._log(f"[INFO] Disconnecting {port} for flashing...")
            self.device_manager.disconnect(port)

        self._log(f"[INFO] Starting flash: {profile.name} -> {port}")
        self.progress.setValue(0)
        self.flash_btn.setEnabled(False)

        # Build options from profile
        options = dict(profile.flash_args)

        try:
            worker = self.flash_engine.start_flash(
                backend_name=profile.backend,
                port=port,
                firmware_path=self._firmware_path,
                options=options,
            )
            self._active_worker = worker
            worker.progress.connect(self._on_progress)
            worker.log_line.connect(self._log)
            worker.finished.connect(self._on_flash_finished)
            worker.start()
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self.flash_btn.setEnabled(True)

    def _on_progress(self, value):
        self.progress.setValue(value)

    def _on_flash_finished(self, success, message):
        self._active_worker = None
        if success:
            self._log(f"[SUCCESS] {message}")
            self.progress.setValue(100)
        else:
            self._log(f"[FAILED] {message}")
        self._update_flash_btn()
        self._refresh_devices()

        # Only continue draining when a "Flash All" run is active. A single
        # "Flash" must not auto-flash items the user merely staged with
        # "Add to Queue".
        if self._batch_active and self._batch_queue:
            self._flash_next_in_queue()
        else:
            self._batch_active = False

    def _log(self, text):
        self.log_output.append(text)
        # Auto-scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # -- Batch queue --

    def _add_to_queue(self):
        port = self._get_selected_port()
        profile_name = self.firmware_combo.currentText()
        if not port or not profile_name or not self._firmware_path:
            return

        entry = (port, profile_name, self._firmware_path)
        self._batch_queue.append(entry)
        display = f"{port} <- {profile_name} ({os.path.basename(self._firmware_path)})"
        self.queue_list.addItem(display)

    def _remove_from_queue(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            self.queue_list.takeItem(row)
            self._batch_queue.pop(row)

    def _clear_queue(self):
        self.queue_list.clear()
        self._batch_queue.clear()

    def _flash_all(self):
        """Flash all items in the batch queue sequentially."""
        if not self._batch_queue:
            self._log("[INFO] Batch queue is empty")
            return
        self._batch_active = True
        self._log(f"[INFO] Starting batch flash: {len(self._batch_queue)} items")
        self._flash_next_in_queue()

    def _flash_next_in_queue(self):
        if not self._batch_queue:
            self._log("[INFO] Batch flash complete")
            return

        port, profile_name, firmware_path = self._batch_queue.pop(0)
        if self.queue_list.count() > 0:
            self.queue_list.takeItem(0)

        profile = self.profile_loader.get(profile_name)
        if not profile:
            self._log(f"[ERROR] Profile not found: {profile_name}")
            self._flash_next_in_queue()
            return

        self._log(f"[BATCH] Flashing {profile.name} -> {port}")
        self._firmware_path = firmware_path
        self.progress.setValue(0)

        if port in self.device_manager.connected_devices:
            self.device_manager.disconnect(port)

        options = dict(profile.flash_args)
        try:
            worker = self.flash_engine.start_flash(
                backend_name=profile.backend,
                port=port,
                firmware_path=firmware_path,
                options=options,
            )
            self._active_worker = worker
            worker.progress.connect(self._on_progress)
            worker.log_line.connect(self._log)
            worker.finished.connect(self._on_flash_finished)
            worker.start()
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self._flash_next_in_queue()

    def showEvent(self, event):
        """Refresh device list when tab becomes visible."""
        super().showEvent(event)
        self._refresh_devices()
