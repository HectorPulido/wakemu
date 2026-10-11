"""Guild storage carriers verified against cDo/cDn/cDp and kd/kK/kt.

Guild compartments are fil.GUILD_1..4 (IDs 0..3), each with 40 slots.
These codecs carry snapshots; they never grant storage access or item ownership.
"""
import struct

from wakfu_server.haven_chest_wire import _blob, _scalar
from wakfu_server.inventory_items import item_proto


GUILD_COMPARTMENT_IDS = (0, 1, 2, 3)
GUILD_COMPARTMENT_CAPACITY = 40
MAX_SNAPSHOT_BYTES = 327664


def _money(value):
    if type(value) is not int or not 0 <= value < (1 << 63):
        raise ValueError("Invalid guild storage money")
    return value


def _compartments(chests):
    result, used = [], set()
    for chest in chests:
        identity = chest["id"]
        if (
            type(identity) is not int
            or identity not in GUILD_COMPARTMENT_IDS
            or identity in used
        ):
            raise ValueError("Invalid or duplicate guild compartment")
        if (
            chest.get("capacity", GUILD_COMPARTMENT_CAPACITY)
            != GUILD_COMPARTMENT_CAPACITY
        ):
            raise ValueError(
                "Guild compartment capacity differs from native definition"
            )
        enabled = chest.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("Invalid guild compartment enabled flag")
        used.add(identity)
        result.append((chest, identity, enabled))
    if not result:
        raise ValueError("Missing guild storage compartments")
    return result


def compartment_proto(chest):
    """kd: required ID/enabled, repeated kK {kX item, int32 position}."""
    [(chest, identity, enabled)] = _compartments([chest])
    result = _scalar(1, identity) + _scalar(2, int(enabled))
    slots, uids = set(), set()
    for entry in chest.get("items", []):
        slot, item = entry["slot"], entry["item"]
        if (
            type(slot) is not int
            or not 0 <= slot < GUILD_COMPARTMENT_CAPACITY
            or slot in slots
        ):
            raise ValueError("Invalid or duplicate guild storage slot")
        if item["uid"] in uids or not enabled:
            raise ValueError("Duplicate guild item or items in disabled compartment")
        slots.add(slot)
        uids.add(item["uid"])
        result += _blob(3, _blob(1, item_proto(item)) + _scalar(2, slot))
    # Optional kd.field4 is omitted: the native loader defaults it to -1.
    return result


def bootstrap(chests, money=0):
    """14424/cDo: enabled map, treasury, raw kh history protobuf (empty)."""
    entries = _compartments(chests)
    return 14424, (
        struct.pack(">i", len(entries))
        + b"".join(
            struct.pack(">iB", identity, int(enabled))
            for _, identity, enabled in entries
        )
        + struct.pack(">q", _money(money))
    )


def contents(chests):
    """14787/cDn: kt repeated compartment field1 + required history field2.

    Send the complete authoritative contents of affected compartments. Native
    fij.g(kd) clears that compartment before inserting this snapshot's items.
    """
    entries = _compartments(chests)
    uids = [
        entry["item"]["uid"]
        for chest, _, _ in entries
        for entry in chest.get("items", [])
    ]
    if len(set(uids)) != len(uids):
        raise ValueError("Duplicate item across guild compartments")
    body = b"".join(
        _blob(1, compartment_proto(chest)) for chest, _, _ in entries
    ) + _blob(2, b"")
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Guild compartment snapshot exceeds the frame budget")
    return 14787, body


def money_packet(money):
    """15817/cDp: treasury plus int32-length kh history protobuf (empty)."""
    return 15817, struct.pack(">qi", _money(money), 0)


def open_packet(character_id):
    """12088/cyN occupation carrier with native guild type23.

    The guild object bBX starts occupation blL locally on its browse action.
    This codec alone does not establish or identify an authorized world object.
    """
    if type(character_id) is not int or not 0 < character_id < (1 << 63):
        raise ValueError("Invalid guild chest actor")
    return 12088, struct.pack(">BhqI", 1, 23, character_id, 0)
