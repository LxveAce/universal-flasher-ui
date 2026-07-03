"""DeviceTab: the discovered-targets store/table must stay bounded.

A scanning device (marauder/bruce/etc.) streams targets endlessly; without a cap the per-device list
and the QTableWidget grow without bound and freeze the UI (same class as headless-marauder-gui HMG-Q1).
Fakes stand in for the protocol + cross-comm broker so no real serial hardware is touched.
"""


class _FakeTarget:
    def __init__(self, i):
        self.type = "AP"
        self.identifier = f"net{i}"
        self.mac = None
        self.rssi = None
        self.channel = None
        self.source_device = "COM9"
        self.shared = False


class _FakeProto:
    def parse_line(self, line, port):
        return _FakeTarget(line)

    def list_commands(self):
        return {}


class _FakeCrossComm:
    def __init__(self):
        self.published = []

    def publish(self, target):
        self.published.append(target)


def _make_tab(qapp, cross_comm):
    from src.core.device_manager import DeviceManager
    from src.ui.device_tab import DeviceTab

    dm = DeviceManager()
    dm._poll_timer.stop()  # no background port polling during the test
    return DeviceTab(dm, cross_comm)


def test_target_store_and_table_are_capped(qapp):
    cc = _FakeCrossComm()
    tab = _make_tab(qapp, cc)
    try:
        tab._MAX_TARGETS = 5           # shrink the cap for a fast, precise test
        tab._current_port = "COM9"
        tab._protocols["COM9"] = _FakeProto()
        tab._targets["COM9"] = []

        for i in range(8):
            tab._on_serial_line("COM9", str(i))

        assert len(tab._targets["COM9"]) == 5      # local store bounded — was unbounded before
        assert tab.target_table.rowCount() == 5    # QTableWidget bounded — no UI-freeze growth
        assert len(cc.published) == 8              # cross-comm still gets EVERY target (behavior kept)
    finally:
        tab.deleteLater()


def test_terminal_has_a_max_block_count(qapp):
    """The live serial terminal is bounded so a long scan can't accumulate unbounded text."""
    cc = _FakeCrossComm()
    tab = _make_tab(qapp, cc)
    try:
        assert tab.serial_output.document().maximumBlockCount() == tab._MAX_TERMINAL_BLOCKS
    finally:
        tab.deleteLater()
