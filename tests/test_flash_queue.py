"""Batch-queue drain semantics for the Flash tab.

A single "Flash" must not auto-drain items only staged with "Add to Queue";
only a "Flash All" run should walk the queue. _flash_next_in_queue is
stubbed so no real flashing occurs.
"""

import pytest


@pytest.fixture
def flash(qapp):
    from src.core.device_manager import DeviceManager
    from src.ui.flash_tab import FlashTab

    dm = DeviceManager()
    dm._poll_timer.stop()
    tab = FlashTab(dm)
    yield tab
    tab.deleteLater()


def test_single_flash_does_not_drain_staged_queue(flash):
    calls = []
    flash._flash_next_in_queue = lambda: calls.append(1)

    # User staged one item but clicked "Flash" (single), not "Flash All".
    flash._batch_queue = [("COM1", "marauder", "f.bin")]
    flash._batch_active = False

    flash._on_flash_finished(True, "done")

    assert calls == []                       # queue not walked
    assert flash._batch_active is False
    assert len(flash._batch_queue) == 1      # still staged, untouched


def test_flash_all_activates_and_continues(flash):
    calls = []
    flash._flash_next_in_queue = lambda: calls.append(1)

    flash._batch_queue = [
        ("COM1", "marauder", "f.bin"),
        ("COM2", "bruce", "g.bin"),
    ]
    flash._flash_all()
    assert flash._batch_active is True
    assert calls == [1]                      # kicked off the first item

    # A mid-batch completion keeps draining while items remain.
    flash._on_flash_finished(True, "ok")
    assert calls == [1, 1]


def test_batch_completion_clears_active_flag(flash):
    calls = []
    flash._flash_next_in_queue = lambda: calls.append(1)

    flash._batch_active = True
    flash._batch_queue = []  # last item already popped/flashed

    flash._on_flash_finished(True, "ok")

    assert calls == []                       # nothing left to flash
    assert flash._batch_active is False


def test_flash_all_on_empty_queue_stays_inactive(flash):
    calls = []
    flash._flash_next_in_queue = lambda: calls.append(1)
    flash._batch_queue = []
    flash._flash_all()
    assert flash._batch_active is False
    assert calls == []
