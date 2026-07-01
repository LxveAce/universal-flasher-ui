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
