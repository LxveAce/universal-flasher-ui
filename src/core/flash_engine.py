import os
import sys
import io
import re
import subprocess

from PyQt5.QtCore import QObject, QThread, pyqtSignal


class FlashWorker(QThread):
    """Background thread for firmware flashing."""

    progress = pyqtSignal(int)       # 0-100
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # (success, message)

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


class OperationWorker(QThread):
    """Background thread for a one-shot device op (erase / backup / verify)."""

    progress = pyqtSignal(int)        # 0-100 (backup only)
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, fn, kwargs, ok_message, wants_progress=False):
        super().__init__()
        self._fn = fn
        self._kwargs = dict(kwargs)
        self._ok = ok_message
        self._wants_progress = wants_progress

    def run(self):
        try:
            self._kwargs["log_cb"] = self.log_line.emit
            if self._wants_progress:
                self._kwargs["progress_cb"] = self.progress.emit
            self._fn(**self._kwargs)
            self.finished.emit(True, self._ok)
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

    def erase_flash(self, port, log_cb=None, **kwargs):
        raise NotImplementedError(f"{self.name} backend does not support erase")


class EsptoolBackend(FlashBackend):
    """ESP32 flashing via esptool."""

    name = "esptool"

    # Regex to pull percentage out of esptool's progress output
    PROGRESS_RE = re.compile(r"(\d+)\s*%")

    def flash(self, port, firmware, progress_cb=None, log_cb=None,
              baud=921600, flash_mode="dio", flash_size="detect",
              flash_freq="40m", erase_before=True, chip="auto", **kwargs):
        """
        Flash firmware to an ESP32 device using esptool.

        Uses subprocess to run esptool so we can capture real-time output
        for progress reporting without esptool's internal state interfering
        with the Qt event loop.
        """
        if not os.path.isfile(firmware):
            raise FileNotFoundError(f"Firmware file not found: {firmware}")

        if log_cb:
            log_cb(f"[esptool] Starting flash: {os.path.basename(firmware)}")
            log_cb(f"[esptool] Port: {port} | Baud: {baud} | Mode: {flash_mode}")

        # Build esptool command line
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
        ]

        if erase_before:
            cmd.append("--before=default_reset")
            cmd.append("--after=hard_reset")

        cmd.extend([
            "write_flash",
            "--flash_mode", str(flash_mode),
            "--flash_size", str(flash_size),
            "--flash_freq", str(flash_freq),
        ])

        # Handle address+binary pairs from kwargs, or default to 0x0
        flash_files = kwargs.get("flash_files", {})
        if flash_files:
            for addr, path in flash_files.items():
                cmd.extend([str(addr), str(path)])
        else:
            cmd.extend(["0x0", str(firmware)])

        if log_cb:
            log_cb(f"[esptool] Command: {' '.join(cmd)}")

        if progress_cb:
            progress_cb(0)

        # Run esptool as a subprocess to capture real-time output
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            last_pct = 0
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if not line:
                    continue

                if log_cb:
                    log_cb(f"[esptool] {line}")

                # Parse progress percentage from esptool output
                pct_match = self.PROGRESS_RE.search(line)
                if pct_match and progress_cb:
                    pct = int(pct_match.group(1))
                    if pct > last_pct:
                        last_pct = pct
                        progress_cb(pct)

            process.wait()

            if process.returncode != 0:
                raise RuntimeError(f"esptool exited with code {process.returncode}")

            if progress_cb:
                progress_cb(100)
            if log_cb:
                log_cb("[esptool] Flash completed successfully")

        except FileNotFoundError:
            raise RuntimeError(
                "esptool not found. Install with: pip install esptool"
            )

    def erase_flash(self, port, log_cb=None, baud=921600, chip="auto"):
        """Erase entire flash on the device."""
        if log_cb:
            log_cb(f"[esptool] Erasing flash on {port}...")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
            "erase_flash",
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in iter(process.stdout.readline, ""):
            line = line.rstrip()
            if line and log_cb:
                log_cb(f"[esptool] {line}")

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"erase_flash failed (exit code {process.returncode})")
        if log_cb:
            log_cb("[esptool] Erase complete")

    def backup(self, port, output_path, progress_cb=None, log_cb=None,
               baud=921600, chip="auto", flash_size="0x400000"):
        """Read entire flash contents and save to file."""
        if log_cb:
            log_cb(f"[esptool] Backing up firmware from {port} to {output_path}...")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
            "read_flash",
            "0x0", str(flash_size),
            str(output_path),
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )

        last_pct = 0
        for line in iter(process.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            if log_cb:
                log_cb(f"[esptool] {line}")
            pct_match = self.PROGRESS_RE.search(line)
            if pct_match and progress_cb:
                pct = int(pct_match.group(1))
                if pct > last_pct:
                    last_pct = pct
                    progress_cb(pct)

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"read_flash failed (exit code {process.returncode})")
        if progress_cb:
            progress_cb(100)
        if log_cb:
            log_cb("[esptool] Backup complete")

    def verify(self, port, firmware, log_cb=None, baud=921600, chip="auto"):
        """Verify flash contents match a firmware file."""
        if log_cb:
            log_cb(f"[esptool] Verifying {firmware} on {port}...")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
            "verify_flash",
            "0x0", str(firmware),
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in iter(process.stdout.readline, ""):
            line = line.rstrip()
            if line and log_cb:
                log_cb(f"[esptool] {line}")

        process.wait()
        if process.returncode != 0:
            raise RuntimeError("Verification failed — flash contents do not match")
        if log_cb:
            log_cb("[esptool] Verification passed")


class SDImageBackend(FlashBackend):
    """Raspberry Pi SD card image writer."""
    name = "sd-image"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        """
        Write an image file to an SD card / USB drive.

        On Windows uses Win32 disk access, on Linux/macOS uses dd.
        'port' here is the drive path (e.g., /dev/sdb or \\\\.\\PhysicalDrive2).
        """
        if not os.path.isfile(firmware):
            raise FileNotFoundError(f"Image file not found: {firmware}")

        if log_cb:
            log_cb(f"[sd-image] Writing {os.path.basename(firmware)} to {port}...")

        if sys.platform == "win32":
            # On Windows, use PowerShell or direct block write
            # For safety, we require the user to confirm the drive
            raise NotImplementedError(
                "SD image writing on Windows requires administrator privileges. "
                "Use Raspberry Pi Imager or balenaEtcher for now."
            )
        else:
            # Linux/macOS: use dd with progress
            block_size = kwargs.get("bs", "4M")
            cmd = [
                "sudo", "dd",
                f"if={firmware}",
                f"of={port}",
                f"bs={block_size}",
                "status=progress",
                "conv=fsync",
            ]
            if log_cb:
                log_cb(f"[sd-image] Running: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if line and log_cb:
                    log_cb(f"[sd-image] {line}")

            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"dd failed with exit code {process.returncode}")

        if progress_cb:
            progress_cb(100)
        if log_cb:
            log_cb("[sd-image] Write complete")


class ADBBackend(FlashBackend):
    """Android Debug Bridge for ADB-based devices."""
    name = "adb"

    def _run_adb(self, args, log_cb=None):
        """Run an adb command and stream output."""
        cmd = ["adb"] + args
        if log_cb:
            log_cb(f"[adb] Running: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            output_lines = []
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    if log_cb:
                        log_cb(f"[adb] {line}")
                    output_lines.append(line)

            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"adb command failed (exit code {process.returncode})")
            return "\n".join(output_lines)

        except FileNotFoundError:
            raise RuntimeError("adb not found. Install Android SDK platform-tools.")

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        """Push and install firmware/APK via ADB."""
        if not os.path.isfile(firmware):
            raise FileNotFoundError(f"File not found: {firmware}")

        if log_cb:
            log_cb(f"[adb] Pushing {os.path.basename(firmware)} via ADB...")

        if progress_cb:
            progress_cb(10)

        if firmware.endswith(".apk"):
            self._run_adb(["install", "-r", firmware], log_cb)
        else:
            dest = kwargs.get("dest_path", f"/sdcard/{os.path.basename(firmware)}")
            self._run_adb(["push", firmware, dest], log_cb)

        if progress_cb:
            progress_cb(100)
        if log_cb:
            log_cb("[adb] Push complete")


class QFlipperBackend(FlashBackend):
    """Flipper Zero via qFlipper CLI."""
    name = "qflipper"

    def flash(self, port, firmware, progress_cb=None, log_cb=None, **kwargs):
        """Flash firmware to Flipper Zero using qFlipper CLI."""
        if not os.path.isfile(firmware):
            raise FileNotFoundError(f"Firmware file not found: {firmware}")

        if log_cb:
            log_cb(f"[qflipper] Flashing {os.path.basename(firmware)} to Flipper Zero...")

        qflipper_bin = kwargs.get("qflipper_path", "qFlipper")
        cmd = [qflipper_bin, "--firmware-update", firmware]

        if progress_cb:
            progress_cb(0)

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if line and log_cb:
                    log_cb(f"[qflipper] {line}")

            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"qFlipper exited with code {process.returncode}")

            if progress_cb:
                progress_cb(100)
            if log_cb:
                log_cb("[qflipper] Flash complete")

        except FileNotFoundError:
            raise RuntimeError(
                "qFlipper not found. Download from https://flipperzero.one/update"
            )


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

    def start_operation(self, backend_name, op_name, op_kwargs, ok_message,
                        wants_progress=False):
        """Return a worker that runs a one-shot backend op (erase / backup / verify)."""
        backend = self.get_backend(backend_name)
        if not backend:
            raise ValueError(f"Unknown backend: {backend_name}")
        fn = getattr(backend, op_name, None)
        if not callable(fn):
            raise ValueError(f"{backend_name} backend has no '{op_name}' operation")
        self._active_worker = OperationWorker(fn, op_kwargs, ok_message, wants_progress)
        return self._active_worker

    def cancel(self):
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()

    @property
    def is_flashing(self):
        return self._active_worker is not None and self._active_worker.isRunning()
