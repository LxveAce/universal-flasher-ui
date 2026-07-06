"""CrossCommTab render bounds: the shared-pool table and the event stream must stay bounded.

The table is index-mapped to broker.target_pool for routing, so the pool cap (in the broker) is what
keeps the table 1:1 and bounded; the event stream QTextEdit caps its own block count. Fakes/real broker
are used with direct (same-thread) signal connections, so no real serial hardware is touched.
"""

from src.models.target import Target

PORT_A = "COM3"


def _ap(identifier="MyNetwork"):
    return Target(type="AP", identifier=identifier, source_device=PORT_A,
                  mac="AA:BB:CC:DD:EE:FF", channel=6, rssi=-42)


def _make_tab(qapp):
    from src.core.cross_comm import CrossCommBroker
    from src.core.device_manager import DeviceManager
    from src.ui.cross_comm_tab import CrossCommTab

    dm = DeviceManager()
    dm._poll_timer.stop()             # no background port polling during the test
    broker = CrossCommBroker()
    return CrossCommTab(broker, dm), broker


def test_event_stream_has_max_block_count(qapp):
    tab, _broker = _make_tab(qapp)
    try:
        assert tab.event_log.document().maximumBlockCount() == 5000
    finally:
        tab.deleteLater()


def test_pool_table_stays_bounded_via_broker_cap(qapp):
    """Publishing past the broker's pool cap must not keep inserting rows (which would also desync the
    row->target_pool index mapping used by _execute_action)."""
    tab, broker = _make_tab(qapp)
    try:
        broker.dedup_by_mac = False   # _ap() shares one dummy MAC; key on the unique identifiers instead
        broker._MAX_POOL = 5           # shrink the cap for a fast test
        for i in range(8):
            broker.publish(_ap(identifier=f"net{i}"))
        assert broker.target_pool and len(broker.target_pool) == 5   # pool bounded
        assert tab.target_pool_table.rowCount() == 5                 # table mirrors it 1:1, bounded
    finally:
        tab.deleteLater()
