"""Settings that were saved but never consumed are now wired (UFUI-GC part b, flash/serial half).

- flash.baud  -> injected into the esptool flash options (and NOT into non-esptool backends, whose
  flash(**options) would raise on an unexpected `baud` kwarg).
- serial.timeout -> forwarded to serial.Serial(timeout=...) instead of the old hard-coded 1s.
- serial.default_baud -> read by device_tab.connect (thin pass-through to the manager tested here).
"""

from types import SimpleNamespace

import pytest
from PyQt5.QtCore import QThread, pyqtSignal


class _StubWorker(QThread):
    """A worker with the signals _do_flash wires to, but start() never runs a real flash."""
    progress = pyqtSignal(int)
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def start(self):  # override QThread.start so no thread actually launches
        pass


@pytest.fixture
def flash(qapp):
    from src.core.device_manager import DeviceManager
    from src.ui.flash_tab import FlashTab

    dm = DeviceManager()
    dm._poll_timer.stop()
    tab = FlashTab(dm)
    yield tab
    tab.deleteLater()


def test_flash_baud_setting_overrides_profile_for_esptool(flash, monkeypatch):
    import src.ui.flash_tab as ft
    monkeypatch.setattr(ft, "load_settings", lambda: {"flash": {"baud": 460800}})

    captured = {}
    monkeypatch.setattr(
        flash.flash_engine, "start_flash",
        lambda backend_name, port, firmware_path, options=None: captured.setdefault("o", options) or _StubWorker(),
    )
    prof = SimpleNamespace(name="Marauder", backend="esptool",
                           flash_args={"baud": 921600, "flash_mode": "dio"})
    flash._firmware_path = "f.bin"
    flash._do_flash("COM1", prof)

    assert captured["o"]["baud"] == 460800        # user setting won over the profile's 921600
    assert captured["o"]["flash_mode"] == "dio"   # other profile args untouched


def test_flash_baud_not_injected_for_non_esptool(flash, monkeypatch):
    import src.ui.flash_tab as ft
    monkeypatch.setattr(ft, "load_settings", lambda: {"flash": {"baud": 460800}})

    captured = {}
    monkeypatch.setattr(
        flash.flash_engine, "start_flash",
        lambda backend_name, port, firmware_path, options=None: captured.setdefault("o", options) or _StubWorker(),
    )
    prof = SimpleNamespace(name="Flipper", backend="qflipper", flash_args={"variant": "x"})
    flash._firmware_path = "f.bin"
    flash._do_flash("COM1", prof)

    assert "baud" not in captured["o"]            # would have raised in backend.flash(**options)
    assert captured["o"]["variant"] == "x"


def test_connect_forwards_timeout_and_baud(qapp, monkeypatch):
    from src.core import device_manager as dmmod

    captured = {}

    class _FakeSerial:
        def __init__(self, port, baud, timeout=1):
            captured.update(port=port, baud=baud, timeout=timeout)

    monkeypatch.setattr(dmmod.serial, "Serial", _FakeSerial)
    dm = dmmod.DeviceManager()
    dm._poll_timer.stop()
    dm.connect("COM9", baud=921600, timeout=5)

    assert captured["baud"] == 921600
    assert captured["timeout"] == 5               # was hard-coded 1 before the fix
