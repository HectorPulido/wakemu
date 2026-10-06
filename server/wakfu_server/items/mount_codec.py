"""Native mount carriers; callers supply authoritative state, never defaults."""
import struct


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid native mount integer")
    return value


def _varint(value):
    # Protobuf int64 negatives occupy ten bytes, rather than zigzag encoding.
    value &= (1 << 64) - 1
    encoded = bytearray()
    while value > 127:
        encoded.append((value & 127) | 128)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _field(number, value):
    if isinstance(value, bytes):
        return _varint(number * 8 + 2) + _varint(len(value)) + value
    return _varint(number * 8) + _varint(value)


def pet_section(state):
    """rw: no companion pet, present mount rz (six big-endian int32)."""
    fields = (
        "definition_id",
        "color_item_ref",
        "equipped_item_ref",
        "sleep_item_ref",
        "health",
        "reskin_item_ref",
    )
    values = [_integer(state[key], 0, (1 << 31) - 1) for key in fields]
    if values[0] == 0:
        raise ValueError("Missing native mount definition")
    return b"\x00\x01" + struct.pack(">6i", *values)


def item_pet(state):
    """ProtoItem field50 containing ProtoPet; XP belongs here, not in rz."""
    if type(state["name"]) is not str:
        raise ValueError("Invalid mount name")
    name = state["name"].encode("utf-8")
    integers = (
        (1, "definition_id"),
        (3, "color_item_ref"),
        (4, "equipped_item_ref"),
        (5, "health"),
        (6, "xp"),
        (9, "sleep_item_ref"),
    )
    values = {
        number: _integer(state[key], 0, (1 << 31) - 1) for number, key in integers
    }
    if values[1] == 0:
        raise ValueError("Missing native mount definition")
    values[2] = name
    for number, key in (
        (7, "last_meal_date"),
        (8, "last_hungry_date"),
        (10, "sleep_date"),
    ):
        values[number] = _integer(state[key], -(1 << 63), (1 << 63) - 1)
    return _field(50, b"".join(_field(n, values[n]) for n in sorted(values)))


def entity_refresh(character_id, entity):
    """cyo15548 applies a complete entity to an existing actor."""
    _integer(character_id, 1, (1 << 63) - 1)
    if type(entity) is not bytes or not 1 <= len(entity) <= 32767:
        raise ValueError("Invalid mount entity refresh")
    return 15548, struct.pack(">qh", character_id, len(entity)) + entity


def ride_result(character_id, result):
    """cym12634: OK0 or the seven native mount rejection codes."""
    _integer(character_id, 1, (1 << 63) - 1)
    _integer(result, 0, 7)
    return 12634, struct.pack(">qi", character_id, result)


def dismounted(character_id):
    """cyn13928 confirms that the actor is no longer riding."""
    _integer(character_id, 1, (1 << 63) - 1)
    return 13928, struct.pack(">q", character_id)
