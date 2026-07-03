"""FlashEngine.start_operation dispatch + OperationWorker behaviour.

OperationWorker.run() is called directly (synchronous, no event loop), and the
custom finished/log/progress signals fire on direct connections, so these run
headlessly under the offscreen platform.
"""

import json

import pytest

from src.core.flash_engine import FlashEngine, OperationWorker, QFlipperBackend


def test_start_operation_returns_worker(qapp):
    w = FlashEngine().start_operation("esptool", "erase_flash", {"port": "COM_X"}, "Erase complete")
    assert isinstance(w, OperationWorker)


def test_start_operation_unknown_backend_raises(qapp):
    with pytest.raises(ValueError):
        FlashEngine().start_operation("nope", "erase_flash", {"port": "COM_X"}, "ok")


def test_start_operation_unknown_op_raises(qapp):
    with pytest.raises(ValueError):
        FlashEngine().start_operation("esptool", "does_not_exist", {"port": "COM_X"}, "ok")


def test_worker_success_emits_finished_true(qapp):
    calls = {}

    def fake_op(port, log_cb=None, **kw):
        calls["port"] = port
        calls["log_cb"] = log_cb

    w = OperationWorker(fake_op, {"port": "COM7"}, "Done!")
    seen = []
    w.finished.connect(lambda ok, msg: seen.append((ok, msg)))
    w.run()
    assert seen == [(True, "Done!")]
    assert calls["port"] == "COM7"
    assert callable(calls["log_cb"])  # worker injects log_cb


def test_worker_failure_emits_finished_false(qapp):
    def boom(port, log_cb=None, **kw):
        raise RuntimeError("nope")

    w = OperationWorker(boom, {"port": "COM7"}, "Done!")
    seen = []
    w.finished.connect(lambda ok, msg: seen.append((ok, msg)))
    w.run()
    assert len(seen) == 1
    assert seen[0][0] is False
    assert "nope" in seen[0][1]


def test_worker_injects_progress_cb_only_when_wanted(qapp):
    got = {}

    def op(port, log_cb=None, progress_cb=None, **kw):
        got["has_progress"] = progress_cb is not None

    OperationWorker(op, {"port": "X"}, "ok", wants_progress=False).run()
    assert got["has_progress"] is False
    OperationWorker(op, {"port": "X"}, "ok", wants_progress=True).run()
    assert got["has_progress"] is True


def test_base_backend_erase_raises_not_implemented(qapp):
    # non-esptool backends inherit a base erase_flash that fails clearly at run time
    with pytest.raises(NotImplementedError):
        QFlipperBackend().erase_flash("COM_X")


# --- EsptoolBackend._stream always reaps the child + closes the pipe --------- #
class _FakeProc:
    def __init__(self, lines, rc=0, readline_raises=None):
        self._lines = iter(list(lines) + [""])
        self.returncode = rc
        self._alive = True
        self.killed = False
        self.closed = False
        self._readline_raises = readline_raises
        self.stdout = self          # act as our own stdout stream

    def readline(self):
        if self._readline_raises:
            raise self._readline_raises
        return next(self._lines)

    def wait(self, timeout=None):
        self._alive = False
        return self.returncode

    def poll(self):
        return None if self._alive else self.returncode

    def kill(self):
        self.killed = True
        self._alive = False

    def close(self):
        self.closed = True


def test_stream_returns_rc_streams_and_closes_pipe(qapp, monkeypatch):
    from src.core import flash_engine
    fake = _FakeProc(["Writing at 0x0... 50 %", "Hash of data verified."], rc=0)
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    logs, pcts = [], []
    rc = flash_engine.EsptoolBackend()._stream(["x"], logs.append, "esptool", pcts.append)
    assert rc == 0
    assert fake.closed is True                    # pipe closed on the normal path
    assert any("50" in ln for ln in logs)         # output streamed
    assert 50 in pcts                             # progress parsed


def test_stream_reaps_child_and_closes_pipe_on_error(qapp, monkeypatch):
    """A broken pipe / callback error mid-stream must not orphan esptool holding the serial port."""
    from src.core import flash_engine
    fake = _FakeProc([], readline_raises=OSError("pipe broke"))
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    with pytest.raises(OSError):
        flash_engine.EsptoolBackend()._stream(["x"], None, "esptool")
    assert fake.killed is True                    # still-alive child was killed, not orphaned
    assert fake.closed is True                    # pipe closed even on the exception path


# --- the shared _stream_process powers dd / adb / qFlipper too (UFUI-2) ------ #
def test_stream_process_collects_lines_and_reaps(qapp, monkeypatch):
    from src.core import flash_engine
    fake = _FakeProc(["line one", "line two"], rc=0)
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    collected = []
    rc = flash_engine._stream_process(["x"], None, "adb", out_lines=collected)
    assert rc == 0
    assert collected == ["line one", "line two"]  # out_lines captured for callers that need output
    assert fake.closed is True


def test_stream_process_reaps_child_on_error(qapp, monkeypatch):
    from src.core import flash_engine
    fake = _FakeProc([], readline_raises=OSError("pipe broke"))
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    with pytest.raises(OSError):
        flash_engine._stream_process(["dd"], None, "sd-image")
    assert fake.killed is True                    # dd/adb/qFlipper child not orphaned on error either
    assert fake.closed is True


def test_run_adb_returns_collected_output(qapp, monkeypatch):
    from src.core import flash_engine
    fake = _FakeProc(["List of devices", "abc123\tdevice"], rc=0)
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    out = flash_engine.ADBBackend()._run_adb(["devices"])
    assert out == "List of devices\nabc123\tdevice"   # adb still returns its joined output
    assert fake.closed is True


def test_run_adb_raises_on_nonzero_rc(qapp, monkeypatch):
    from src.core import flash_engine
    fake = _FakeProc(["error: no devices"], rc=1)
    monkeypatch.setattr(flash_engine.subprocess, "Popen", lambda *a, **k: fake)
    with pytest.raises(RuntimeError, match="adb command failed"):
        flash_engine.ADBBackend()._run_adb(["push", "a", "b"])


# --- SDImageBackend refuses the OS/system disk before dd (UFUI-3) ------------ #
# ALL mocked: lsblk/diskutil output is faked and dd is never invoked — no real disk is ever touched.
class _FakeRun:
    def __init__(self, stdout, rc=0, stderr=""):
        self.stdout = stdout
        self.returncode = rc
        self.stderr = stderr


def test_sd_guard_refuses_system_disk_linux(qapp, monkeypatch):
    from src.core import flash_engine
    lsblk = {"blockdevices": [{"name": "sda", "type": "disk", "rm": False, "tran": "sata",
             "mountpoint": None, "children": [{"name": "sda2", "mountpoint": "/"}]}]}
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(flash_engine.subprocess, "run", lambda *a, **k: _FakeRun(json.dumps(lsblk)))
    with pytest.raises(ValueError, match="system mount|OS/boot"):
        flash_engine._assert_sd_target_safe("/dev/sda")


def test_sd_guard_allows_removable_card_linux(qapp, monkeypatch):
    from src.core import flash_engine
    lsblk = {"blockdevices": [{"name": "sdb", "type": "disk", "rm": True, "tran": "usb",
             "mountpoint": None, "children": [{"name": "sdb1", "mountpoint": "/media/pi/BOOT"}]}]}
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(flash_engine.subprocess, "run", lambda *a, **k: _FakeRun(json.dumps(lsblk)))
    flash_engine._assert_sd_target_safe("/dev/sdb")     # a real removable SD reader — must NOT raise


def test_sd_guard_refuses_internal_disk_macos(qapp, monkeypatch):
    from src.core import flash_engine
    import plistlib
    info = {"Internal": True, "Removable": False, "RemovableMedia": False}
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(flash_engine.subprocess, "run",
                        lambda *a, **k: _FakeRun(plistlib.dumps(info).decode()))
    with pytest.raises(ValueError, match="internal"):
        flash_engine._assert_sd_target_safe("/dev/disk0")


def test_sd_guard_allows_external_removable_macos(qapp, monkeypatch):
    from src.core import flash_engine
    import plistlib
    info = {"Internal": False, "Removable": True}
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(flash_engine.subprocess, "run",
                        lambda *a, **k: _FakeRun(plistlib.dumps(info).decode()))
    flash_engine._assert_sd_target_safe("/dev/disk4")   # a real external SD card — must NOT raise


def _macos_run_dispatch(port_info, boot_info):
    """Fake subprocess.run for the macOS guard: `diskutil info -plist /` returns the boot-disk plist,
    any other target returns the port's plist. All mocked — no diskutil/dd ever runs."""
    import plistlib

    def _run(cmd, *a, **k):
        info = boot_info if cmd[-1] == "/" else port_info
        return _FakeRun(plistlib.dumps(info).decode())
    return _run


def test_sd_guard_refuses_external_boot_disk_macos(qapp, monkeypatch):
    """An EXTERNAL, removable disk that backs '/' (external-boot macOS) must be refused (UFUI-3b) — it
    would pass the internal/removable check but a dd there destroys the running OS."""
    from src.core import flash_engine
    port_info = {"Internal": False, "Removable": True}   # external + removable -> passes the earlier check
    boot_info = {"ParentWholeDisk": "disk4"}             # '/' is backed by disk4
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(flash_engine.subprocess, "run", _macos_run_dispatch(port_info, boot_info))
    with pytest.raises(ValueError, match="backs the running system"):
        flash_engine._assert_sd_target_safe("/dev/disk4")


def test_sd_guard_resolves_apfs_external_boot_macos(qapp, monkeypatch):
    """APFS: '/' lives on a synthesized container, so the boot disk must be resolved via
    APFSPhysicalStores -> whole disk. An external APFS boot SSD (rdisk4) must be refused."""
    from src.core import flash_engine
    port_info = {"Internal": False, "Removable": True}
    boot_info = {"APFSPhysicalStores": [{"DeviceIdentifier": "disk4s2"}]}
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(flash_engine.subprocess, "run", _macos_run_dispatch(port_info, boot_info))
    with pytest.raises(ValueError, match="backs the running system"):
        flash_engine._assert_sd_target_safe("/dev/rdisk4")   # rdisk4 -> disk4 == APFS store's whole disk


def test_sd_guard_allows_external_non_boot_disk_macos(qapp, monkeypatch):
    """A genuine external SD that does NOT back '/' still writes."""
    from src.core import flash_engine
    port_info = {"Internal": False, "Removable": True}
    boot_info = {"ParentWholeDisk": "disk0"}             # boot is disk0, target is disk5
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(flash_engine.subprocess, "run", _macos_run_dispatch(port_info, boot_info))
    flash_engine._assert_sd_target_safe("/dev/disk5")    # must NOT raise


def test_sd_flash_refuses_system_disk_before_dd(qapp, tmp_path, monkeypatch):
    """SDImageBackend.flash must abort on a system-disk target BEFORE any dd runs."""
    from src.core import flash_engine
    img = tmp_path / "os.img"
    img.write_bytes(b"\x00" * 16)
    lsblk = {"blockdevices": [{"name": "sda", "type": "disk", "rm": False, "tran": "sata",
             "children": [{"name": "sda1", "mountpoint": "/boot"}]}]}
    monkeypatch.setattr(flash_engine.sys, "platform", "linux")     # take the dd branch, not win32
    monkeypatch.setattr(flash_engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(flash_engine.subprocess, "run", lambda *a, **k: _FakeRun(json.dumps(lsblk)))
    dd = {"ran": False}
    monkeypatch.setattr(flash_engine, "_stream_process",
                        lambda *a, **k: dd.__setitem__("ran", True) or 0)
    with pytest.raises(ValueError):
        flash_engine.SDImageBackend().flash("/dev/sda", str(img))
    assert dd["ran"] is False        # never reached dd
