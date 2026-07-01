"""CrossCommBroker tests: dedup, publish signalling, and auto-routing.

The broker is a QObject but uses direct (same-thread) signal connections,
so emissions run synchronously without a Qt event loop.
"""

from src.core.cross_comm import CrossCommBroker
from src.models.message import CrossCommMessage
from src.models.target import Target

PORT_A = "COM3"
PORT_B = "COM5"


def _ap(identifier="MyNetwork", mac="AA:BB:CC:DD:EE:FF", channel=6, source=PORT_A):
    return Target(
        type="AP",
        identifier=identifier,
        source_device=source,
        mac=mac,
        channel=channel,
        rssi=-42,
    )


def test_publish_adds_and_emits():
    broker = CrossCommBroker()
    seen = []
    broker.target_discovered.connect(seen.append)

    broker.publish(_ap())
    assert len(broker.target_pool) == 1
    assert len(seen) == 1
    assert seen[0].identifier == "MyNetwork"


def test_publish_dedupes_by_identifier_and_type():
    broker = CrossCommBroker()
    broker.publish(_ap())
    broker.publish(_ap())  # same identifier + type -> dropped
    assert len(broker.target_pool) == 1

    # Same identifier, different type is NOT a duplicate.
    broker.publish(Target(type="STA", identifier="MyNetwork", source_device=PORT_A))
    assert len(broker.target_pool) == 2


def test_clear_pool():
    broker = CrossCommBroker()
    broker.publish(_ap())
    broker.clear_pool()
    assert broker.target_pool == []


def test_auto_route_matches_and_formats():
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)

    broker.subscribe({
        "match_type": "AP",
        "match_source": "*",
        "dest_port": PORT_B,
        "action": "sniffpmkid {identifier}",
    })
    broker.publish(_ap(identifier="CoffeeShop"))

    assert len(routed) == 1
    msg = routed[0]
    assert isinstance(msg, CrossCommMessage)
    assert msg.dest_port == PORT_B
    assert msg.action == "sniffpmkid CoffeeShop"


def test_auto_route_type_mismatch_does_not_route():
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)
    broker.subscribe({"match_type": "BLE", "dest_port": PORT_B, "action": "x"})
    broker.publish(_ap())  # AP, rule wants BLE
    assert routed == []


def test_auto_route_source_filter():
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)
    broker.subscribe({
        "match_type": "*",
        "match_source": PORT_A,
        "dest_port": PORT_B,
        "action": "go {mac}",
    })
    broker.publish(_ap(source=PORT_B))  # wrong source -> no route
    assert routed == []
    broker.publish(_ap(source=PORT_A, identifier="Other"))
    assert len(routed) == 1
    assert routed[0].action == "go AA:BB:CC:DD:EE:FF"


def test_auto_route_bad_template_does_not_crash():
    # The Add-Rule dialog's action field is free text, so a user can enter an
    # unsupported placeholder. A bad template must be skipped, not crash publish.
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)

    broker.subscribe({
        "match_type": "AP",
        "match_source": "*",
        "dest_port": PORT_B,
        "action": "clone {name}",  # {name} is not a provided placeholder
    })
    broker.publish(_ap(identifier="CoffeeShop"))  # must not raise

    assert routed == []                      # the bad rule produced no route
    assert len(broker.target_pool) == 1      # discovery still processed normally


def test_auto_route_unbalanced_brace_does_not_crash():
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)
    broker.subscribe({"match_type": "*", "dest_port": PORT_B, "action": "attack {"})
    broker.publish(_ap())  # unbalanced brace -> ValueError inside format(); must be caught
    assert routed == []
    assert len(broker.target_pool) == 1


def test_route_to_device_emits():
    broker = CrossCommBroker()
    routed = []
    broker.target_routed.connect(routed.append)
    broker.route_to_device(_ap(), PORT_B, "deauth")
    assert len(routed) == 1
    assert routed[0].action == "deauth"
    assert routed[0].dest_port == PORT_B
