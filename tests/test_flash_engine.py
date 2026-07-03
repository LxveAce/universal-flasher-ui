"""FlashEngine.start_operation dispatch + OperationWorker behaviour.

OperationWorker.run() is called directly (synchronous, no event loop), and the
custom finished/log/progress signals fire on direct connections, so these run
headlessly under the offscreen platform.
"""

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
