"""Cross-comm honesty (UFUI-GC part b, cross-comm half): the auto_share + dedup_by_mac controls now do
something instead of being decorative.

- auto_share off  -> broker.publish() is a no-op (discoveries do not flood the shared pool).
- dedup_by_mac on -> two APs sharing an SSID but with different BSSIDs stay distinct (were collapsed).
- dedup_by_mac off -> same-SSID targets collapse (the old behavior, now explicit and opt-in).
- the Cross-Comm tab checkbox live-drives broker.auto_share.
"""

import pytest

from src.core.cross_comm import CrossCommBroker
from src.models.target import Target


def _ap(ssid, mac, src="COM1"):
    return Target(type="AP", identifier=ssid, source_device=src, mac=mac)


@pytest.fixture
def broker(qapp):
    b = CrossCommBroker()
    b.auto_share = True          # normalize regardless of the machine's saved settings
    b.dedup_by_mac = True
    return b


def test_dedup_by_mac_keeps_same_ssid_distinct_bssids(broker):
    broker.publish(_ap("xfinitywifi", "AA:AA:AA:AA:AA:01"))
    broker.publish(_ap("xfinitywifi", "AA:AA:AA:AA:AA:02"))
    assert len(broker.target_pool) == 2          # two physical radios, both kept


def test_dedup_by_mac_still_collapses_the_same_radio(broker):
    broker.publish(_ap("net", "AA:AA:AA:AA:AA:01"))
    broker.publish(_ap("net", "AA:AA:AA:AA:AA:01"))
    assert len(broker.target_pool) == 1          # exact same BSSID is a real duplicate


def test_dedup_by_ssid_collapses_when_mac_off(broker):
    broker.dedup_by_mac = False
    broker.publish(_ap("xfinitywifi", "AA:AA:AA:AA:AA:01"))
    broker.publish(_ap("xfinitywifi", "AA:AA:AA:AA:AA:02"))
    assert len(broker.target_pool) == 1          # SSID-keyed: distinct radios collapse (opt-in legacy)


def test_dedup_falls_back_to_identifier_without_mac(broker):
    broker.publish(Target(type="BLE", identifier="dev-1", source_device="COM1"))
    broker.publish(Target(type="BLE", identifier="dev-1", source_device="COM1"))
    assert len(broker.target_pool) == 1          # no MAC -> identifier keyed, still dedups


def test_auto_share_off_suppresses_publish(broker):
    broker.auto_share = False
    broker.publish(_ap("net", "AA:AA:AA:AA:AA:01"))
    assert broker.target_pool == []              # discoveries are not auto-added
    broker.auto_share = True
    broker.publish(_ap("net", "AA:AA:AA:AA:AA:01"))
    assert len(broker.target_pool) == 1          # re-enabling resumes sharing


def test_broker_reads_cross_comm_settings(qapp, monkeypatch):
    monkeypatch.setattr("src.config.settings.load_settings",
                        lambda: {"cross_comm": {"auto_share": False, "dedup_by_mac": False}})
    b = CrossCommBroker()
    assert b.auto_share is False and b.dedup_by_mac is False


def test_checkbox_live_toggles_broker_auto_share(qapp):
    from src.core.device_manager import DeviceManager
    from src.ui.cross_comm_tab import CrossCommTab

    b = CrossCommBroker()
    b.auto_share = True
    dm = DeviceManager()
    dm._poll_timer.stop()
    tab = CrossCommTab(b, dm)
    assert tab.auto_share.isChecked() is True    # checkbox initialized from the broker
    tab.auto_share.setChecked(False)
    assert b.auto_share is False                  # unticking stops auto-sharing live
    tab.auto_share.setChecked(True)
    assert b.auto_share is True
    tab.deleteLater()
