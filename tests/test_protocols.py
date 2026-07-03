"""Parser + command-builder tests for all five firmware protocols.

Each sample line is taken verbatim from the protocol's own docstring/comment,
so these lock the documented behaviour against regex regressions.
"""

from src.models.target import Target
from src.protocols import (
    PROTOCOLS,
    PROTOCOL_DISPLAY_NAMES,
    get_protocol,
    get_protocol_by_display,
)
from src.protocols.base import DeviceProtocol
from src.protocols.marauder import MarauderProtocol
from src.protocols.ghost_esp import GhostESPProtocol
from src.protocols.bruce import BruceProtocol
from src.protocols.halehound import HaleHoundProtocol
from src.protocols.flipper import FlipperProtocol

PORT = "COM3"


# -- Marauder --------------------------------------------------------------

def test_marauder_ap():
    t = MarauderProtocol().parse_line(
        "SSID: MyNetwork BSSID: AA:BB:CC:DD:EE:FF Ch: 6 RSSI: -45", PORT
    )
    assert t is not None
    assert t.type == "AP"
    assert t.identifier == "MyNetwork"
    assert t.mac == "AA:BB:CC:DD:EE:FF"
    assert t.channel == 6
    assert t.rssi == -45
    assert t.source_device == PORT


def test_marauder_station():
    t = MarauderProtocol().parse_line("MAC: AA:BB:CC:DD:EE:FF RSSI: -60", PORT)
    assert t is not None
    assert t.type == "STA"
    assert t.mac == "AA:BB:CC:DD:EE:FF"
    assert t.identifier == "AA:BB:CC:DD:EE:FF"
    assert t.rssi == -60


def test_marauder_build_command():
    p = MarauderProtocol()
    ap = Target(type="AP", identifier="X", source_device=PORT, mac="AA:BB:CC:DD:EE:FF")
    assert p.build_command("deauth", ap) == "select -a AA:BB:CC:DD:EE:FF\nattack -t deauth"
    ch = Target(type="AP", identifier="X", source_device=PORT, channel=11)
    assert p.build_command("sniffpmkid", ch) == "channel 11\nsniffpmkid"
    assert p.build_command("scanap") == "scanap"
    assert p.get_scan_command() == "scanap"
    assert p.get_stop_command() == "stopscan"


# -- GhostESP ---------------------------------------------------------------

def test_ghost_esp_ap():
    t = GhostESPProtocol().parse_line(
        "[WiFi] SSID: HomeNetwork | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -42 | ENC: WPA2",
        PORT,
    )
    assert t.type == "AP"
    assert t.identifier == "HomeNetwork"
    assert t.mac == "AA:BB:CC:DD:EE:FF"
    assert t.channel == 6
    assert t.rssi == -42


def test_ghost_esp_station_and_ble():
    p = GhostESPProtocol()
    sta = p.parse_line("[STA] MAC: AA:BB:CC:DD:EE:FF | RSSI: -55 | AP: HomeNetwork", PORT)
    assert sta.type == "STA"
    assert sta.rssi == -55
    ble = p.parse_line("[BLE] Name: MI Band 5 | MAC: AA:BB:CC:DD:EE:FF | RSSI: -70", PORT)
    assert ble.type == "BLE"
    assert ble.identifier == "MI Band 5"
    assert ble.rssi == -70


def test_ghost_esp_build_command():
    p = GhostESPProtocol()
    t = Target(type="STA", identifier="x", source_device=PORT, mac="AA:BB:CC:DD:EE:FF")
    assert p.build_command("deauth", t) == "deauth AA:BB:CC:DD:EE:FF"


# -- Bruce ------------------------------------------------------------------

def test_bruce_wifi_ap():
    t = BruceProtocol().parse_line(
        "[WIFI] AP: CoffeeShop | BSSID: AA:BB:CC:DD:EE:FF | CH: 1 | RSSI: -50 | AUTH: WPA2",
        PORT,
    )
    assert t.type == "AP"
    assert t.identifier == "CoffeeShop"
    assert t.channel == 1
    assert t.rssi == -50


def test_bruce_ble_subghz_nfc_ir():
    p = BruceProtocol()
    ble = p.parse_line("[BLE] Device: FitBand | ADDR: AA:BB:CC:DD:EE:FF | RSSI: -60", PORT)
    assert ble.type == "BLE" and ble.identifier == "FitBand" and ble.rssi == -60

    sg = p.parse_line("[SUBGHZ] Freq: 433.92MHz | Protocol: Princeton | Data: 0x1234ABCD", PORT)
    assert sg.type == "SubGHz"
    assert sg.frequency == "433.92MHz"
    assert sg.extra["protocol"] == "Princeton"
    assert sg.extra["data"] == "0x1234ABCD"

    nfc = p.parse_line("[NFC] Type: NTAG215 | UID: 04:AB:CD:EF:12:34:56", PORT)
    assert nfc.type == "NFC"
    assert nfc.identifier == "04:AB:CD:EF:12:34:56"
    assert nfc.extra["nfc_type"] == "NTAG215"

    ir = p.parse_line("[IR] Protocol: NEC | Address: 0x04 | Command: 0x08", PORT)
    assert ir.type == "IR"
    assert ir.identifier == "NEC Addr:0x04 Cmd:0x08"


def test_bruce_build_command():
    p = BruceProtocol()
    t = Target(type="AP", identifier="x", source_device=PORT, mac="AA:BB:CC:DD:EE:FF")
    assert p.build_command("wifi deauth", t) == "wifi deauth AA:BB:CC:DD:EE:FF"


# -- Flipper Zero -----------------------------------------------------------

def test_flipper_subghz():
    t = FlipperProtocol().parse_line(
        "SubGhz: Protocol: Princeton | Bit: 24 | Key: 0x001234 | Freq: 433.92MHz | RSSI: -40.5",
        PORT,
    )
    assert t.type == "SubGHz"
    assert t.frequency == "433.92MHz"
    assert t.extra["key"] == "0x001234"
    assert t.rssi == -40  # int(float(-40.5))


def test_flipper_nfc_rfid_bt():
    p = FlipperProtocol()
    nfc = p.parse_line(
        "NFC: Type: Mifare Classic 1K | UID: 04:AB:CD:EF | ATQA: 0004 | SAK: 08", PORT
    )
    assert nfc.type == "NFC"
    assert nfc.identifier == "04:AB:CD:EF"
    assert nfc.extra["nfc_type"] == "Mifare Classic 1K"
    assert nfc.extra["atqa"] == "0004"

    rfid = p.parse_line("RFID: Type: EM4100 | Data: 01 02 03 04 05", PORT)
    assert rfid.type == "RFID"
    assert rfid.identifier == "01 02 03 04 05"

    bt = p.parse_line("BT: Name: MyDevice | MAC: AA:BB:CC:DD:EE:FF | RSSI: -55", PORT)
    assert bt.type == "BLE"
    assert bt.identifier == "MyDevice"
    assert bt.rssi == -55


def test_flipper_build_command():
    p = FlipperProtocol()
    t = Target(type="NFC", identifier="04:AB:CD:EF", source_device=PORT)
    assert p.build_command("nfc emulate", t) == "nfc emulate --uid 04:AB:CD:EF"


# -- HaleHound --------------------------------------------------------------

def test_halehound_wifi_and_station():
    p = HaleHoundProtocol()
    ap = p.parse_line(
        "[WIFI] SSID: NetworkName | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -42 | ENC: WPA2",
        PORT,
    )
    assert ap.type == "AP"
    assert ap.identifier == "NetworkName"
    assert ap.channel == 6

    sta = p.parse_line(
        "[WIFI_STA] MAC: AA:BB:CC:DD:EE:FF | RSSI: -55 | AP_BSSID: 11:22:33:44:55:66", PORT
    )
    assert sta.type == "STA"
    assert sta.rssi == -55


def test_halehound_subghz_nfc_nrf_extras():
    p = HaleHoundProtocol()
    sg = p.parse_line(
        "[SUBGHZ] Freq: 315.00MHz | Mod: ASK | Data: AA BB CC DD | RSSI: -30", PORT
    )
    assert sg.type == "SubGHz"
    assert sg.frequency == "315.00MHz"
    assert sg.extra["data"] == "AA BB CC DD"
    assert sg.rssi == -30

    nfc = p.parse_line("[NFC] UID: 04:AB:CD:EF:12:34:56 | ATQA: 0044 | SAK: 00", PORT)
    assert nfc.type == "NFC"
    assert nfc.identifier == "04:AB:CD:EF:12:34:56"

    nrf = p.parse_line("[NRF24] Channel: 76 | Addr: AA:BB:CC:DD:EE | Payload: 48656C6C6F", PORT)
    assert nrf.type == "NRF24"
    assert nrf.channel == 76

    guardian = p.parse_line(
        "[GUARDIAN] ROGUE AP: EvilTwin | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -30", PORT
    )
    assert guardian.type == "RogueAP"
    assert guardian.identifier == "EvilTwin"


def test_halehound_build_command():
    p = HaleHoundProtocol()
    t = Target(type="AP", identifier="x", source_device=PORT, mac="AA:BB:CC:DD:EE:FF")
    assert p.build_command("wifi_deauth", t) == "wifi_deauth AA:BB:CC:DD:EE:FF"


def test_halehound_oversized_numeric_field_does_not_crash():
    """Untrusted device output with a pathologically long digit run must NOT raise out of parse_line
    (device_tab calls it with no try/except — an unguarded int() would crash the GUI on CPython's
    4300-digit int<-str limit). The oversized field degrades to None; the rest still parses."""
    p = HaleHoundProtocol()
    line = "[WIFI] SSID: Net | BSSID: AA:BB:CC:DD:EE:FF | CH: " + "9" * 5000 + " | RSSI: -42"
    t = p.parse_line(line, PORT)              # must not raise
    assert t is not None and t.type == "AP"
    assert t.identifier == "Net"
    assert t.mac == "AA:BB:CC:DD:EE:FF"
    assert t.channel is None                  # oversized channel rejected safely...
    assert t.rssi == -42                      # ...while the valid RSSI still parses

    # A normal channel is unaffected.
    ok = p.parse_line("[WIFI] SSID: N | BSSID: AA:BB:CC:DD:EE:FF | CH: 6 | RSSI: -42", PORT)
    assert ok.channel == 6


# -- Registry + non-matching lines -----------------------------------------

def test_registry_lookup():
    assert isinstance(get_protocol("marauder"), MarauderProtocol)
    assert isinstance(get_protocol("does-not-exist"), DeviceProtocol)  # raw fallback
    assert isinstance(get_protocol_by_display("Flipper"), FlipperProtocol)
    assert isinstance(get_protocol_by_display("Nonsense"), DeviceProtocol)
    # Every display name resolves to a registered protocol.
    for display, key in PROTOCOL_DISPLAY_NAMES.items():
        assert key in PROTOCOLS


def test_non_matching_lines_return_none():
    for proto in (
        MarauderProtocol(),
        GhostESPProtocol(),
        BruceProtocol(),
        HaleHoundProtocol(),
        FlipperProtocol(),
    ):
        assert proto.parse_line("", PORT) is None
        assert proto.parse_line("random boot log line", PORT) is None
    # Raw passthrough never parses.
    assert DeviceProtocol().parse_line("SSID: X BSSID: AA:BB:CC:DD:EE:FF Ch: 1 RSSI: -1", PORT) is None
