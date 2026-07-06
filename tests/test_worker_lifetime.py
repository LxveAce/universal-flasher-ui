"""QThread lifetime around flash/operation completion (UFUI-GC).

FlashWorker/OperationWorker declare their own ``finished`` signal, which shadows QThread's built-in one,
so it is emitted from *inside* run() while the thread is still alive. If the finished slot dropped the last
reference (or the engine overwrote it with the next batch item) before run() returned, the QThread wrapper
could be GC'd mid-run -> "QThread: Destroyed while thread is still running" -> process abort. These cover the
retirement path (wait-then-release) and the engine staying safe once a worker has been retired/deleted.
"""

import pytest
from PyQt5.QtCore import QThread, pyqtSignal


@pytest.fixture
def flash(qapp):
    from src.core.device_manager import DeviceManager
    from src.ui.flash_tab import FlashTab

    dm = DeviceManager()
    dm._poll_timer.stop()
    tab = FlashTab(dm)
    yield tab
    tab.deleteLater()


def test_retire_worker_blocks_until_thread_stops(flash):
    """_retire_worker must wait() a still-running thread out before releasing it."""
    class _SlowWorker(QThread):
        def run(self):
            self.msleep(150)

    w = _SlowWorker()
    flash.flash_engine._active_worker = w
    w.start()
    assert w.isRunning()                                # genuinely running when we retire it
    flash._retire_worker(w)                             # must block until run() returns
    assert not w.isRunning()                            # stopped cleanly, no destroy-while-running
    assert flash.flash_engine._active_worker is None    # engine handle dropped too


def test_worker_emitting_finished_from_run_is_retired(flash, qapp):
    """The real shape: a custom `finished` (shadowing QThread.finished) emitted from inside run()."""
    class _Worker(QThread):
        finished = pyqtSignal(bool, str)               # shadows QThread.finished, like FlashWorker

        def run(self):
            self.msleep(30)
            self.finished.emit(True, "ok")             # emitted while the thread is still alive

    w = _Worker()
    flash.flash_engine._active_worker = w
    got = []
    w.finished.connect(lambda ok, m: got.append((ok, m)))
    w.start()
    while not got:                                     # pump the loop until finished arrives (as the UI does)
        qapp.processEvents()
    flash._retire_worker(w)
    assert not w.isRunning()
    assert flash.flash_engine._active_worker is None


def test_retire_worker_none_is_noop(flash):
    """The finished slots call _retire_worker(self._active_worker); it must tolerate None."""
    flash._retire_worker(None)                          # must not raise


def test_is_flashing_survives_deleted_worker(flash):
    """A retired worker leaves a dangling wrapper; is_flashing must report idle, not crash."""
    class _Dead:
        def isRunning(self):
            raise RuntimeError("wrapped C/C++ object of type FlashWorker has been deleted")

    flash.flash_engine._active_worker = _Dead()
    assert flash.flash_engine.is_flashing is False
    assert flash.flash_engine._active_worker is None    # forgotten, so it won't be queried again


def test_cancel_survives_deleted_worker(flash):
    class _Dead:
        def isRunning(self):
            raise RuntimeError("deleted")

    flash.flash_engine._active_worker = _Dead()
    flash.flash_engine.cancel()                         # must not raise
    assert flash.flash_engine._active_worker is None


def test_clear_worker_only_clears_matching(flash):
    a, b = object(), object()
    eng = flash.flash_engine
    eng._active_worker = a
    eng.clear_worker(b)                                 # a newer/different worker must be left alone
    assert eng._active_worker is a
    eng.clear_worker(a)                                 # the matching one is cleared
    assert eng._active_worker is None
