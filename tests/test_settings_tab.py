"""Settings tab: profile-directory display and the Reload Profiles wiring.

Runs headlessly via the offscreen Qt platform (see conftest.qapp).
"""

from src.core.profile_loader import ProfileLoader


def test_profile_dir_field_is_populated(qapp):
    from src.ui.settings_tab import SettingsTab

    tab = SettingsTab()
    assert tab.profile_dir.text() == ProfileLoader().profile_dir
    tab.deleteLater()


def test_reload_button_emits_signal(qapp):
    from src.ui.settings_tab import SettingsTab

    tab = SettingsTab()
    fired = []
    tab.profiles_reload_requested.connect(lambda: fired.append(True))
    tab.reload_btn.click()
    assert fired == [True]
    tab.deleteLater()


def test_reload_refreshes_flash_tab_profiles(qapp):
    """End-to-end: clicking Reload repopulates the Flash tab profile combo.

    Mirrors the connection made in app.UniversalFlasherUI._connect_signals.
    """
    from src.core.device_manager import DeviceManager
    from src.ui.flash_tab import FlashTab
    from src.ui.settings_tab import SettingsTab

    dm = DeviceManager()
    dm._poll_timer.stop()  # no background polling during the test
    flash = FlashTab(dm)
    settings = SettingsTab()
    settings.profiles_reload_requested.connect(flash._load_profiles)

    assert flash.firmware_combo.count() == 6  # populated on construction
    flash.firmware_combo.clear()
    assert flash.firmware_combo.count() == 0

    settings.reload_btn.click()
    assert flash.firmware_combo.count() == 6  # reloaded from disk

    flash.deleteLater()
    settings.deleteLater()


def test_app_window_wires_reload(qapp):
    """The assembled main window connects Reload -> Flash tab refresh."""
    from src.app import UniversalFlasherUI

    win = UniversalFlasherUI()
    win.device_manager._poll_timer.stop()
    try:
        win.flash_tab.firmware_combo.clear()
        assert win.flash_tab.firmware_combo.count() == 0
        win.settings_tab.reload_btn.click()
        assert win.flash_tab.firmware_combo.count() == 6
    finally:
        win.close()
        win.deleteLater()
