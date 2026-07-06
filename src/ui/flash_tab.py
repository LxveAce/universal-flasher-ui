import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QProgressBar, QLabel, QGroupBox, QListWidget, QTextEdit,
    QFileDialog, QMessageBox,
)

from src.core.flash_engine import FlashEngine
from src.core.profile_loader import ProfileLoader
from src.config.settings import load_settings


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
        self._pending_flash = None   # (port, profile) held while an auto-backup runs first
        self._verify_after_flash = False  # set per single-flash from settings

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

        # Device operations (on-demand: erase / read-flash backup / verify)
        ops_group = QGroupBox("Device Operations")
        ops_layout = QHBoxLayout(ops_group)
        self.erase_btn = QPushButton("Erase Flash")
        self.erase_btn.setToolTip("Erase all flash on the selected device (esptool)")
        self.backup_btn = QPushButton("Backup (read-flash)")
        self.backup_btn.setToolTip("Read the device's flash to a .bin file")
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setToolTip("Verify device flash against the selected firmware file")
        for b in (self.erase_btn, self.backup_btn, self.verify_btn):
            b.setEnabled(False)
            ops_layout.addWidget(b)
        ops_layout.addStretch()
        layout.addWidget(ops_group)

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
        self.erase_btn.clicked.connect(self._start_erase)
        self.backup_btn.clicked.connect(self._start_backup)
        self.verify_btn.clicked.connect(self._start_verify)

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
        """Enable buttons based on the current selection (and only when idle)."""
        has_device = self.device_combo.currentIndex() >= 0
        has_firmware = self.firmware_combo.currentIndex() >= 0
        has_file = bool(self._firmware_path) and os.path.isfile(self._firmware_path)
        not_flashing = not self.flash_engine.is_flashing
        self.flash_btn.setEnabled(has_device and has_firmware and has_file and not_flashing)
        # Erase/backup/verify are esptool-only ops — only offer them for an esptool profile.
        is_esptool = self._current_backend() == "esptool"
        self.erase_btn.setEnabled(has_device and is_esptool and not_flashing)
        self.backup_btn.setEnabled(has_device and is_esptool and not_flashing)
        self.verify_btn.setEnabled(has_device and is_esptool and has_file and not_flashing)
        # Queue controls: re-enable them when idle so _lock_ui() (which disables ALL buttons during an
        # operation) doesn't strand them — previously only flash/erase/backup/verify were re-enabled, so
        # Flash-All and Add-to-Queue stayed disabled after the first flash. Add-to-Queue needs a full
        # selection; Flash-All needs a non-empty queue.
        self.add_to_queue_btn.setEnabled(has_device and has_firmware and has_file and not_flashing)
        self.flash_all_btn.setEnabled(not_flashing and bool(self._batch_queue))

    def _lock_ui(self):
        """Disable every action button while an operation is running."""
        for b in (self.flash_btn, self.erase_btn, self.backup_btn, self.verify_btn,
                  self.flash_all_btn, self.add_to_queue_btn):
            b.setEnabled(False)

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
        """Validate the selection, optionally auto-backup first, then flash."""
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

        if self.flash_engine.is_flashing:
            return

        flash_cfg = load_settings().get("flash", {})
        # Remember whether to verify once the flash finishes (single-flash only).
        self._verify_after_flash = bool(flash_cfg.get("verify", False))

        # Disconnect serial reader if connected (flash needs exclusive port access)
        if port in self.device_manager.connected_devices:
            self._log(f"[INFO] Disconnecting {port} for flashing...")
            self.device_manager.disconnect(port)

        # Auto-backup before flash (opt-in). Only proceed to the actual flash once
        # the backup has really succeeded; if it fails we abort rather than flash.
        if flash_cfg.get("auto_backup", False) and profile.backend == "esptool":
            backup_path = self._default_backup_path(port)
            self._log(f"[INFO] Auto-backup before flash -> {backup_path}")
            self._pending_flash = (port, profile)
            self.progress.setValue(0)
            self._lock_ui()
            try:
                worker = self.flash_engine.start_operation(
                    profile.backend, "backup",
                    {"port": port, "output_path": backup_path},
                    "Backup complete", wants_progress=True,
                )
                self._active_worker = worker
                worker.progress.connect(self._on_progress)
                worker.log_line.connect(self._log)
                worker.finished.connect(self._on_prebackup_finished)
                worker.start()
            except Exception as e:
                self._log(f"[ERROR] {e}")
                self._pending_flash = None
                self._update_flash_btn()
            return

        self._do_flash(port, profile)

    def _on_prebackup_finished(self, success, message):
        """After an auto-backup: flash only if the backup actually succeeded."""
        worker = self._active_worker
        self._active_worker = None
        self._retire_worker(worker)
        pending = self._pending_flash
        self._pending_flash = None
        if not success:
            self._log(f"[FAILED] Auto-backup failed, flash aborted: {message}")
            self._update_flash_btn()
            self._refresh_devices()
            return
        self._log("[SUCCESS] Auto-backup complete")
        if pending:
            self._do_flash(*pending)

    def _do_flash(self, port, profile):
        """Kick off the real flash worker for an already-validated port + profile."""
        self._log(f"[INFO] Starting flash: {profile.name} -> {port}")
        self.progress.setValue(0)
        self._lock_ui()
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
            self._update_flash_btn()

    def _default_backup_path(self, port):
        safe = "".join(c if c.isalnum() else "-" for c in str(port))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        d = os.path.join(os.path.expanduser("~"), ".universal-flasher-ui", "backups")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"backup-{safe}-{stamp}.bin")

    def _on_progress(self, value):
        self.progress.setValue(value)

    def _retire_worker(self, worker):
        """Stop and release a worker whose `finished` signal just fired.

        FlashWorker/OperationWorker declare their own `finished` signal, so it is emitted from *inside*
        run() while the QThread is still executing. If the last reference is dropped (or the engine
        overwrites it with the next batch item) before run() returns, the QThread wrapper can be
        garbage-collected while the C++ thread is still alive, which aborts the whole process. Wait for
        run() to actually return, drop the engine's handle, then schedule safe deletion."""
        if worker is None:
            return
        try:
            if worker.isRunning():
                worker.wait(5000)
        except RuntimeError:
            return  # underlying C++ object already gone
        self.flash_engine.clear_worker(worker)
        worker.deleteLater()

    def _on_flash_finished(self, success, message):
        worker = self._active_worker
        self._active_worker = None
        self._retire_worker(worker)
        if success:
            self._log(f"[SUCCESS] {message}")
            self.progress.setValue(100)
            # Verify after a single flash if the setting asked for it (batch skips it).
            if self._verify_after_flash and not self._batch_active:
                self._verify_after_flash = False
                if self._start_verify_after_flash():
                    return  # verify worker running; its finish re-enables the UI
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

    def _start_verify_after_flash(self):
        """Auto-verify the firmware just written; returns True if a worker started."""
        port = self._get_selected_port()
        backend = self._current_backend()
        if not (port and backend == "esptool" and self._firmware_path):
            return False
        self._log("[INFO] Verifying flash (per settings)...")
        self._lock_ui()
        try:
            worker = self.flash_engine.start_operation(
                backend, "verify",
                {"port": port, "firmware": self._firmware_path},
                "Verification passed",
            )
            self._active_worker = worker
            worker.log_line.connect(self._log)
            worker.finished.connect(self._on_operation_finished)
            worker.start()
            return True
        except Exception as e:
            self._log(f"[ERROR] {e}")
            return False

    # -- On-demand device operations (erase / backup / verify) --

    def _current_backend(self):
        """Backend name from the selected firmware profile (needed for device ops)."""
        idx = self.firmware_combo.currentIndex()
        if idx < 0:
            return None
        profile = self.firmware_combo.itemData(idx)
        return getattr(profile, "backend", None) if profile else None

    def _run_operation(self, backend, op, kwargs, ok_msg, wants_progress=False):
        if self.flash_engine.is_flashing:
            return
        self.progress.setValue(0)
        self._lock_ui()
        try:
            worker = self.flash_engine.start_operation(backend, op, kwargs, ok_msg, wants_progress)
            self._active_worker = worker
            if wants_progress:
                worker.progress.connect(self._on_progress)
            worker.log_line.connect(self._log)
            worker.finished.connect(self._on_operation_finished)
            worker.start()
        except Exception as e:
            self._log(f"[ERROR] {e}")
            self._update_flash_btn()

    def _on_operation_finished(self, success, message):
        worker = self._active_worker
        self._active_worker = None
        self._retire_worker(worker)
        self._log(f"[{'SUCCESS' if success else 'FAILED'}] {message}")
        self._update_flash_btn()
        self._refresh_devices()

    def _start_erase(self):
        port = self._get_selected_port()
        backend = self._current_backend()
        if not port or not backend:
            self._log("[ERROR] Select a device and a firmware profile (for the device type) first")
            return
        reply = QMessageBox.warning(
            self, "Erase flash?",
            f"This ERASES ALL data on the device at {port} and cannot be undone.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if port in self.device_manager.connected_devices:
            self.device_manager.disconnect(port)
        self._log(f"[INFO] Erasing flash on {port}...")
        self._run_operation(backend, "erase_flash", {"port": port}, "Erase complete")

    def _start_backup(self):
        port = self._get_selected_port()
        backend = self._current_backend()
        if not port or not backend:
            self._log("[ERROR] Select a device and a firmware profile (for the device type) first")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save flash backup", "backup.bin", "Binary (*.bin);;All Files (*)")
        if not path:
            return
        if port in self.device_manager.connected_devices:
            self.device_manager.disconnect(port)
        self._log(f"[INFO] Backing up {port} -> {path}")
        self._run_operation(backend, "backup", {"port": port, "output_path": path},
                            "Backup complete", wants_progress=True)

    def _start_verify(self):
        port = self._get_selected_port()
        backend = self._current_backend()
        if not port or not backend:
            self._log("[ERROR] Select a device and a firmware profile first")
            return
        if not self._firmware_path or not os.path.isfile(self._firmware_path):
            self._log("[ERROR] Select a firmware file to verify against")
            return
        if port in self.device_manager.connected_devices:
            self.device_manager.disconnect(port)
        self._log(f"[INFO] Verifying {port} against {os.path.basename(self._firmware_path)}...")
        self._run_operation(backend, "verify",
                            {"port": port, "firmware": self._firmware_path},
                            "Verification passed")

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
        self._update_flash_btn()        # a non-empty queue enables Flash-All

    def _remove_from_queue(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            self.queue_list.takeItem(row)
            self._batch_queue.pop(row)
            self._update_flash_btn()

    def _clear_queue(self):
        self.queue_list.clear()
        self._batch_queue.clear()
        self._update_flash_btn()

    def _flash_all(self):
        """Flash all items in the batch queue sequentially."""
        # Re-entry guard (parity with _start_flash / _run_operation): the batch flow does not lock the
        # UI on every hop, so without this a second "Flash All" while a flash is already running would
        # overwrite the live worker reference — orphaning a still-running QThread (crash) and driving two
        # esptools onto the same port.
        if self.flash_engine.is_flashing:
            return
        if not self._batch_queue:
            self._log("[INFO] Batch queue is empty")
            return
        self._batch_active = True
        self._log(f"[INFO] Starting batch flash: {len(self._batch_queue)} items")
        self._lock_ui()                 # reflect the running state, like a single flash does
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
