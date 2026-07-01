"""SerialHandler.start_reading: don't get stuck on a dead reader thread.

A reader whose run() exited on disconnect used to stay registered and block a
fresh reader on reconnect. Fakes stand in for the running/dead reader so we
never depend on real serial hardware or thread timing.
"""


class _FakeReader:
    def __init__(self, running):
        self._running = running
        self.stopped = False

    def isRunning(self):
        return self._running

    def stop(self):
        self.stopped = True


class _FakeConn:
    """Minimal serial-like object; is_open=False makes the real reader
    thread's run() loop exit immediately."""

    def __init__(self, is_open=False):
        self.is_open = is_open
        self.in_waiting = 0

    def read(self, n):  # pragma: no cover - not reached with is_open False
        return b""


def test_skips_when_existing_reader_is_running(qapp):
    from src.core.serial_handler import SerialHandler

    h = SerialHandler()
    live = _FakeReader(running=True)
    h._readers["COM9"] = live

    h.start_reading("COM9", _FakeConn())

    # Not replaced: the live reader keeps ownership of the port.
    assert h._readers["COM9"] is live


def test_replaces_dead_reader_on_reconnect(qapp):
    from src.core.serial_handler import SerialHandler, SerialReaderThread

    h = SerialHandler()
    dead = _FakeReader(running=False)
    h._readers["COM9"] = dead

    h.start_reading("COM9", _FakeConn(is_open=False))

    new = h._readers["COM9"]
    assert new is not dead
    assert isinstance(new, SerialReaderThread)

    h.stop_reading("COM9")
    assert "COM9" not in h._readers


def test_start_then_stop_registers_and_cleans(qapp):
    from src.core.serial_handler import SerialHandler, SerialReaderThread

    h = SerialHandler()
    h.start_reading("COM9", _FakeConn(is_open=False))
    assert isinstance(h._readers["COM9"], SerialReaderThread)
    assert h._buffers["COM9"] == ""

    h.stop_reading("COM9")
    assert "COM9" not in h._readers
    assert "COM9" not in h._buffers
