from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QProgressBar, QLabel, QGroupBox, QListWidget, QTextEdit,
)
from PyQt5.QtCore import Qt


class FlashTab(QWidget):
    """Firmware flashing interface — profile selection, batch queue, progress."""

    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Device + firmware selection
        select_group = QGroupBox("Flash Configuration")
        select_layout = QHBoxLayout(select_group)

        self.device_combo = QComboBox()
        self.device_combo.setPlaceholderText("Select device...")
        self.firmware_combo = QComboBox()
        self.firmware_combo.setPlaceholderText("Select firmware...")
        self.flash_btn = QPushButton("Flash")
        self.flash_btn.setEnabled(False)

        select_layout.addWidget(QLabel("Device:"))
        select_layout.addWidget(self.device_combo, 1)
        select_layout.addWidget(QLabel("Firmware:"))
        select_layout.addWidget(self.firmware_combo, 1)
        select_layout.addWidget(self.flash_btn)

        layout.addWidget(select_group)

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
        add_row.addWidget(self.add_to_queue_btn)
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
