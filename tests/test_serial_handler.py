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


def test_on_data_splits_lines_and_holds_partial(qapp):
    """Regression guard: normal newline splitting + partial-line carry-over is unchanged."""
    from src.core.serial_handler import SerialHandler

    h = SerialHandler()
    seen = []
    h.line_received.connect(lambda p, ln: seen.append((p, ln)))
    h._buffers["COM9"] = ""

    h._on_data("COM9", "hello\nwor")
    assert seen == [("COM9", "hello")]        # complete line emitted
    assert h._buffers["COM9"] == "wor"        # partial held for the next chunk

    h._on_data("COM9", "ld\n")
    assert seen[-1] == ("COM9", "world")      # partial completed
    assert h._buffers["COM9"] == ""


def test_on_data_flushes_overlong_newlineless_buffer(qapp):
    """A stream with no newline must not grow the per-port buffer without bound."""
    from src.core.serial_handler import SerialHandler

    h = SerialHandler()
    seen = []
    h.line_received.connect(lambda p, ln: seen.append((p, ln)))
    h._buffers["COM9"] = ""

    blob = "A" * (h._MAX_LINE_BUFFER + 100)    # no newline anywhere
    h._on_data("COM9", blob)

    assert len(seen) == 1                       # flushed as one line instead of buffered forever
    assert h._buffers["COM9"] == ""             # buffer reset — memory stays bounded
    assert len(h._buffers["COM9"]) <= h._MAX_LINE_BUFFER
