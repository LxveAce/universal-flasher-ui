import json
import os
import platform
import plistlib
import re
import subprocess
import sys

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


# Mount points that mark a disk as the OS/boot/system disk — never a raw-write target. A USB-attached
# root/boot disk (Pi USB-SSD boot, a live-USB install) is removable=False + tran=usb and would pass the
# bus/removable heuristic alone, so we key the refusal off a real system mount anywhere in the disk's
# partition subtree. (Mirrors the sibling uf_core/sd_backend guard.)
_SD_PROTECTED_MOUNTS = frozenset((
    "/", "/boot", "/boot/efi", "/boot/firmware", "/efi", "/usr", "/var", "/home",
))


def _sd_subtree_mountpoints(node):
    """Every mountpoint on an lsblk node and its partition descendants (handles the legacy string
    ``mountpoint`` and the newer ``mountpoints`` list)."""
    mps = []
    mp = node.get("mountpoint")
    if mp:
        mps.append(mp)
    for m in node.get("mountpoints") or []:
        if m:
            mps.append(m)
    for child in node.get("children") or []:
        mps.extend(_sd_subtree_mountpoints(child))
    return mps


def _assert_sd_target_safe(port, log_cb=None):
    """Refuse to raw-write ``port`` unless it is a removable, non-system disk — dd'ing the wrong drive
    (e.g. /dev/sda, the OS disk) silently destroys the running system, so this MUST run before dd.

    Linux uses lsblk (skip any disk hosting a protected system mount; require removable OR usb-attached);
    macOS uses diskutil (refuse an internal, non-removable disk). If detection itself fails we REFUSE
    rather than write blindly. Other platforms fall through unguarded — but the only caller is the SD dd
    path, which Windows already blocks with NotImplementedError before reaching here.
    """
    system = platform.system()
    if system == "Linux":
        try:
            r = subprocess.run(
                ["lsblk", "-J", "-b", "-o", "NAME,TYPE,RM,TRAN,MOUNTPOINT", port],
                capture_output=True, text=True, timeout=10,
            )
        except Exception as e:
            raise RuntimeError(f"refusing to write {port}: cannot verify it is an SD card (lsblk failed: {e})")
        if r.returncode != 0:
            raise ValueError(f"refusing to write {port}: lsblk could not describe it ({(r.stderr or '').strip()})")
        devs = json.loads(r.stdout or "{}").get("blockdevices", [])
        dev = devs[0] if devs else None
        if not dev:
            raise ValueError(f"refusing to write {port}: not a recognized block device")
        sys_mounts = [m for m in _sd_subtree_mountpoints(dev) if m in _SD_PROTECTED_MOUNTS]
        if sys_mounts:
            raise ValueError(
                f"refusing to write {port}: it hosts a system mount ({sys_mounts[0]}) — this looks like "
                f"your OS/boot disk, not an SD card")
        rm = dev.get("rm")
        removable = (rm.lower() in ("1", "true")) if isinstance(rm, str) else bool(rm)
        tran = (dev.get("tran") or "").lower()
        if not removable and tran != "usb":
            raise ValueError(
                f"refusing to write {port}: not a removable or USB-attached drive (looks fixed/internal)")
    elif system == "Darwin":
        try:
            r = subprocess.run(["diskutil", "info", "-plist", port],
                               capture_output=True, text=True, timeout=10)
            info = plistlib.loads((r.stdout or "").encode()) if r.returncode == 0 and r.stdout else {}
        except Exception as e:
            raise RuntimeError(f"refusing to write {port}: cannot verify it is an SD card (diskutil failed: {e})")
        if not info:
            raise ValueError(f"refusing to write {port}: diskutil could not describe it")
        removable = bool(info.get("Removable", info.get("RemovableMedia", False)))
        internal = bool(info.get("Internal", True))
        if internal and not removable:
            raise ValueError(
                f"refusing to write {port}: internal, non-removable disk — this looks like your system "
                f"disk, not an SD card")
        # macOS refinement TODO (parity with uf sd_backend beat-46): an EXTERNAL disk that backs '/'
        # (external boot) still passes here; catching it needs `diskutil info -plist /` ->
        # ParentWholeDisk + APFSPhysicalStores whole-disk resolution.


def _stream_process(cmd, log_cb, tag, progress_cb=None, progress_re=None, out_lines=None):
    """Run ``cmd``, stream combined stdout/stderr line-by-line via ``log_cb`` (prefixed ``[tag]``),
    optionally parse a percentage (``progress_re`` + ``progress_cb``) and/or collect the lines into
    ``out_lines``. Return the exit code.

    The child is ALWAYS reaped and the pipe ALWAYS closed on the way out — even if the read loop raises
    (a broken pipe, a callback error) or the caller aborts the worker thread. Without that finally a
    failed/cancelled op would orphan the subprocess still holding the serial port / SD device, so the
    next op fails 'busy'. Popen stays OUTSIDE the try so a missing executable raises FileNotFoundError to
    the caller (which maps it to a friendly install hint) rather than being masked here.
    """
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    last_pct = 0
    try:
        for line in iter(process.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            if log_cb:
                log_cb(f"[{tag}] {line}")
            if out_lines is not None:
                out_lines.append(line)
            if progress_cb and progress_re is not None:
                pct_match = progress_re.search(line)
                if pct_match:
                    pct = int(pct_match.group(1))
                    if pct > last_pct:
                        last_pct = pct
                        progress_cb(pct)
        process.wait()
        return process.returncode
    finally:
        if process.poll() is None:              # still alive after an exception/abort — don't orphan it
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        try:
            if process.stdout:
                process.stdout.close()
        except Exception:
            pass


class EsptoolBackend(FlashBackend):
    """ESP32 flashing via esptool."""

    name = "esptool"

    # Regex to pull percentage out of esptool's progress output
    PROGRESS_RE = re.compile(r"(\d+)\s*%")

    def _stream(self, cmd, log_cb, tag, progress_cb=None):
        """Stream an esptool subprocess with progress parsing (thin wrapper over the shared
        _stream_process, kept as a method so existing esptool callers/tests are unchanged)."""
        return _stream_process(cmd, log_cb, tag, progress_cb=progress_cb, progress_re=self.PROGRESS_RE)

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
            "write-flash",
            "--flash-mode", str(flash_mode),
            "--flash-size", str(flash_size),
            "--flash-freq", str(flash_freq),
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

        # Run esptool as a subprocess to capture real-time output (child always reaped — see _stream).
        try:
            rc = self._stream(cmd, log_cb, "esptool", progress_cb)
        except FileNotFoundError:
            raise RuntimeError(
                "esptool not found. Install with: pip install esptool"
            )

        if rc != 0:
            raise RuntimeError(f"esptool exited with code {rc}")

        if progress_cb:
            progress_cb(100)
        if log_cb:
            log_cb("[esptool] Flash completed successfully")

    def erase_flash(self, port, log_cb=None, baud=921600, chip="auto"):
        """Erase entire flash on the device."""
        if log_cb:
            log_cb(f"[esptool] Erasing flash on {port}...")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
            "erase-flash",
        ]

        rc = self._stream(cmd, log_cb, "esptool")
        if rc != 0:
            raise RuntimeError(f"erase_flash failed (exit code {rc})")
        if log_cb:
            log_cb("[esptool] Erase complete")

    def backup(self, port, output_path, progress_cb=None, log_cb=None,
               baud=921600, chip="auto", flash_size="0x400000"):
        """Read flash contents (``flash_size`` bytes from 0x0, default 4 MB) and save to file.

        Note: reads exactly ``flash_size`` — on boards larger than the default this backup is
        truncated. Pass the true size (or detect it via ``flash_id``) for a complete image.
        """
        if log_cb:
            log_cb(f"[esptool] Backing up firmware from {port} to {output_path}...")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", str(chip),
            "--port", str(port),
            "--baud", str(baud),
            "read-flash",
            "0x0", str(flash_size),
            str(output_path),
        ]

        rc = self._stream(cmd, log_cb, "esptool", progress_cb)
        if rc != 0:
            raise RuntimeError(f"read_flash failed (exit code {rc})")
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
            "verify-flash",
            "0x0", str(firmware),
        ]

        rc = self._stream(cmd, log_cb, "esptool")
        if rc != 0:
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
            # Data-loss guard: dd to the wrong drive destroys the running system. Refuse anything that
            # is not a removable, non-system disk BEFORE building/running the dd command.
            _assert_sd_target_safe(port, log_cb)

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

            rc = _stream_process(cmd, log_cb, "sd-image")     # child always reaped — see _stream_process
            if rc != 0:
                raise RuntimeError(f"dd failed with exit code {rc}")

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

        output_lines = []
        try:
            rc = _stream_process(cmd, log_cb, "adb", out_lines=output_lines)
        except FileNotFoundError:
            raise RuntimeError("adb not found. Install Android SDK platform-tools.")
        if rc != 0:
            raise RuntimeError(f"adb command failed (exit code {rc})")
        return "\n".join(output_lines)

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
            rc = _stream_process(cmd, log_cb, "qflipper")
        except FileNotFoundError:
            raise RuntimeError(
                "qFlipper not found. Download from https://flipperzero.one/update"
            )
        if rc != 0:
            raise RuntimeError(f"qFlipper exited with code {rc}")

        if progress_cb:
            progress_cb(100)
        if log_cb:
            log_cb("[qflipper] Flash complete")


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
