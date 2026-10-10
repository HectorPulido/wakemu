"""Account chest codecs verified against current cqe/cqi/cxt and lY/lj/lm.

No official account identity or inventory contents are reused.
"""
import struct


class _Reader:
    def __init__(self, body):
        if not isinstance(body, bytes):
            raise ValueError("Chest request must be bytes")
        self.body, self.offset = body, 0

    def take(self, size):
        result = self.body[self.offset : self.offset + size]
        if len(result) != size:
            raise ValueError("Truncated chest request")
        self.offset += size
        return result

    def number(self, fmt):
        return struct.unpack(">" + fmt, self.take(struct.calcsize(">" + fmt)))

    def string(self):
        (size,) = self.number("B")
        try:
            result = self.take(size).decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("Invalid chest compartment identity") from error
        if not result or len(result) > 64:
            raise ValueError("Invalid chest compartment identity")
        return result

    def finish(self):
        if self.offset != len(self.body):
            raise ValueError("Trailing chest request bytes")


def decode_deposit(body):
    reader = _Reader(body)
    (count,) = reader.number("h")
    if not 1 <= count <= 16:
        raise ValueError("Invalid deposit group count")
    result, used = [], set()
    for _ in range(count):
        compartment = reader.string()
        (rows,) = reader.number("h")
        if not 1 <= rows <= 32767 or len(result) + rows > 32767:
            raise ValueError("Invalid deposit item count")
        for _ in range(rows):
            uid, slot, quantity = reader.number("qhh")
            if uid <= 0 or uid in used or slot < -1 or quantity <= 0:
                raise ValueError("Invalid or duplicate chest deposit")
            used.add(uid)
            result.append(
                dict(compartment=compartment, uid=uid, slot=slot, quantity=quantity)
            )
    reader.finish()
    return result


def decode_withdraw(body):
    reader = _Reader(body)
    (actor,) = reader.number("q")
    compartment = reader.string()
    (count,) = reader.number("h")
    if actor <= 0 or not 1 <= count <= 32767:
        raise ValueError("Invalid chest withdrawal identity/count")
    result, used = [], set()
    for _ in range(count):
        reference, slot, quantity, container, destination = reader.number("ihhqh")
        if (
            reference <= 0
            or slot < 0
            or slot in used
            or quantity <= 0
            or container <= 0
            or destination < -1
        ):
            raise ValueError("Invalid or duplicate chest withdrawal")
        used.add(slot)
        result.append(
            dict(
                compartment=compartment,
                reference=reference,
                slot=slot,
                quantity=quantity,
                container=container,
                destination=destination,
            )
        )
    reader.finish()
    return actor, result


def _varint(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid chest protobuf integer")
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _scalar(number, value):
    return _varint(number << 3) + _varint(value)


def _blob(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def item_list(items):
    """lm: repeated lj {kX item, int32 position, bool locked}."""
    from .inventory_items import item_proto

    result, used = [], set()
    for entry in items:
        slot, item = entry["slot"], entry["item"]
        if type(slot) is not int or not 0 <= slot <= 32766 or slot in used:
            raise ValueError("Invalid chest item slot")
        used.add(slot)
        result.append(
            _blob(1, _blob(1, item_proto(item)) + _scalar(2, slot) + _scalar(3, 0))
        )
    return b"".join(result)


def bootstrap(chest):
    """318/cxt: signed-short list, int length + Compartment, bool finished."""
    capacity = chest["capacity"]
    if type(capacity) is not int or not 1 <= capacity <= 32767:
        raise ValueError("Invalid chest capacity")
    if any(entry["slot"] >= capacity for entry in chest["items"]):
        raise ValueError("Chest item exceeds capacity")
    compartment = (
        _blob(1, chest["id"].encode("ascii"))
        + _scalar(2, chest["account_id"])
        + _blob(3, b"Haven chest")
        + _scalar(5, 0)
        + _scalar(7, capacity)
        + _scalar(8, 0)
        + _blob(9, item_list(chest["items"]))
    )
    return 318, struct.pack(">hI", 1, len(compartment)) + compartment + b"\x01"


def contents(chest):
    """13929/cxn supplies the complete occupied positions in one compartment."""
    identity = chest["id"].encode("ascii")
    blob = item_list(chest["items"])
    return (
        13929,
        struct.pack(">hB", 1, len(identity))
        + identity
        + struct.pack(">I", len(blob))
        + blob,
    )


def open_packet(character_id):
    """12088/cyN: captured chest occupation type31, empty extension data."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid chest actor")
    return 12088, struct.pack(">BhqI", 1, 31, character_id, 0)


def scene_packet(identity):
    """13984 reconstructs and hydrates the installed AccountChest object.

    The available state is recorded before the official action12 open. Object
    identity comes from the installed map catalog, never captured ownership.
    """
    if type(identity) is not int or identity <= 0:
        raise ValueError("Invalid native chest object identity")
    state = bytes.fromhex("01020000000602000101010001010000000000")
    return 13984, struct.pack(">hqh", 1, identity, len(state)) + state
