from PyQt5.QtCore import QObject, QThread, pyqtSignal


class FlashWorker(QThread):
    """Background thread for firmware flashing."""

    progress = pyqtSignal(int)       # 0-100
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # (success, message)

    def __init__(self, backend, port, firmware_path, options=None):
        super().__init__()
        self.backend = backend
        self.port = port
        self.firmware_path = firmware_path
        self.options = options or {}

    def run(self):
        try:
            self.backend.flash(
                port=self.port,
                firmware=self.firmware_path,
                progress_cb=self.progress.emit,
                log_cb=self.log_line.emit,
                **self.options,
            )
            self.finished.emit(True, "Flash complete")
        except Exception as e:
            self.finished.emit(False, str(e))


class FlashBackend:
    """Abstract flash backend."""

    name = "base"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        raise NotImplementedError

    def backup(self, port, output_path, progress_cb=None, log_cb=None):
        raise NotImplementedError

    def verify(self, port, firmware, log_cb=None):
        raise NotImplementedError


class EsptoolBackend(FlashBackend):
    """ESP32 flashing via esptool."""

    name = "esptool"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, baud=921600, **kwargs):
        if log_cb:
            log_cb(f"[esptool] Flashing {firmware} to {port} at {baud} baud...")
        # TODO: implement esptool.main() call with progress parsing
        if progress_cb:
            progress_cb(100)

    def backup(self, port, output_path, progress_cb=None, log_cb=None):
        if log_cb:
            log_cb(f"[esptool] Backing up firmware from {port}...")
        # TODO: esptool read_flash

    def verify(self, port, firmware, log_cb=None):
        if log_cb:
            log_cb(f"[esptool] Verifying {firmware} on {port}...")
        # TODO: esptool verify_flash


class SDImageBackend(FlashBackend):
    """Raspberry Pi SD card image writer."""
    name = "sd-image"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        if log_cb:
            log_cb(f"[sd-image] Writing {firmware} to {port}...")
        # TODO: implement dd-style image write


class ADBBackend(FlashBackend):
    """Android Debug Bridge for ADB-based devices (Orbic RC400L, etc.)."""
    name = "adb"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        if log_cb:
            log_cb(f"[adb] Pushing {firmware} via ADB...")
        # TODO: adb push + install


class QFlipperBackend(FlashBackend):
    """Flipper Zero via qFlipper CLI."""
    name = "qflipper"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        if log_cb:
            log_cb(f"[qflipper] Flashing {firmware} to Flipper Zero...")
        # TODO: qflipper CLI integration


BACKENDS = {
    "esptool": EsptoolBackend(),
    "sd-image": SDImageBackend(),
    "adb": ADBBackend(),
    "qflipper": QFlipperBackend(),
}


class FlashEngine(QObject):
    """Orchestrates flash operations with backend selection."""

    def __init__(self):
        super().__init__()
        self.backends = BACKENDS
        self._active_worker = None

    def get_backend(self, name):
        return self.backends.get(name)

    def start_flash(self, backend_name, port, firmware_path, options=None):
        backend = self.get_backend(backend_name)
        if not backend:
            raise ValueError(f"Unknown backend: {backend_name}")
        self._active_worker = FlashWorker(backend, port, firmware_path, options)
        return self._active_worker

    def cancel(self):
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()
