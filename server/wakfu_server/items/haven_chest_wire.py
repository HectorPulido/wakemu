"""Account chest codecs verified against current cqe/cqi/cxt and lY/lj/lm.

No official account identity or inventory contents are reused.
"""
import struct

# Original ciB..ciI/ciK mutate account compartment/PvP inventory state.
# Capture templates must never publish another account's compartments or resets.
CAPTURE_STATE_OPCODES = frozenset(
    {318, 12224, 13223, 13301, 13364, 13430, 13716, 13929, 23627}
)


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
    if not 1 <= count <= 32767:
        raise ValueError("Invalid deposit group count")
    result, used = [], set()
    for _ in range(count):
        compartment = reader.string()
        (rows,) = reader.number("h")
        if not 1 <= rows <= 32767 or len(result) + rows > 32767:
            raise ValueError("Invalid deposit item count")
        for _ in range(rows):
            uid, slot, quantity = reader.number("qhh")
            # Native bmH quick transfer can split one source across slots and
            # merge distinct source UIDs into the same compatible target.
            target = (compartment, slot, uid)
            if uid <= 0 or target in used or slot < -1 or quantity <= 0:
                raise ValueError("Invalid or duplicate chest deposit")
            used.add(target)
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


def decode_relocate(body):
    """13050/cqh with foT rows; FF destination identity means source tab."""
    reader = _Reader(body)
    compartment = reader.string()
    (count,) = reader.number("h")
    if not 1 <= count <= 32767:
        raise ValueError("Invalid chest relocation count")
    result, used = [], set()
    for _ in range(count):
        slot, quantity = reader.number("hh")
        (length,) = reader.number("b")
        if length == -1:
            destination_compartment = compartment
        elif 1 <= length <= 64:
            try:
                destination_compartment = reader.take(length).decode("ascii")
            except UnicodeDecodeError as error:
                raise ValueError("Invalid chest relocation identity") from error
        else:
            raise ValueError("Invalid chest relocation identity")
        (destination,) = reader.number("i")
        key = (slot, destination_compartment, destination)
        if slot < 0 or quantity <= 0 or destination < 0 or key in used:
            raise ValueError("Invalid or duplicate chest relocation")
        used.add(key)
        result.append(
            dict(
                compartment=compartment,
                slot=slot,
                quantity=quantity,
                destination_compartment=destination_compartment,
                destination=destination,
            )
        )
    reader.finish()
    return result


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
    if any(
        type(entry["slot"]) is not int or not 0 <= entry["slot"] < capacity
        for entry in chest["items"]
    ):
        raise ValueError("Chest item exceeds capacity")
    from .haven_chest_layout import compartments

    encoded = []
    for tab in compartments(chest):
        offset = tab["offset"]
        entries = [
            dict(entry, slot=entry["slot"] - offset)
            for entry in chest["items"]
            if offset <= entry["slot"] < offset + tab["capacity"]
        ]
        name = "Haven chest" if tab["index"] == 0 else f"Haven chest {tab['index'] + 1}"
        compartment = (
            _blob(1, tab["id"].encode("ascii"))
            + _scalar(2, chest["account_id"])
            + _blob(3, name.encode("ascii"))
            + _scalar(5, tab["index"])
            + _scalar(7, tab["capacity"])
            + _scalar(8, 0)
            + _blob(9, item_list(entries))
        )
        encoded.append(struct.pack(">I", len(compartment)) + compartment)
    return 318, struct.pack(">h", len(encoded)) + b"".join(encoded) + b"\x01"


def contents(chest):
    """13929/cxn adds item quantities; never send this after a full318 snapshot.

    This is a delta codec. Use action_result() to acknowledge snapshot responses.
    """
    from .haven_chest_layout import compartments

    if any(
        type(entry["slot"]) is not int or not 0 <= entry["slot"] < chest["capacity"]
        for entry in chest["items"]
    ):
        raise ValueError("Chest item exceeds capacity")
    encoded = []
    for tab in compartments(chest):
        identity = tab["id"].encode("ascii")
        offset = tab["offset"]
        entries = [
            dict(entry, slot=entry["slot"] - offset)
            for entry in chest["items"]
            if offset <= entry["slot"] < offset + tab["capacity"]
        ]
        blob = item_list(entries)
        encoded.append(
            struct.pack(">B", len(identity))
            + identity
            + struct.pack(">I", len(blob))
            + blob
        )
    return 13929, struct.pack(">h", len(encoded)) + b"".join(encoded)


def action_result(*, rejected=False):
    """13301/cxu: acknowledge pending action, optionally show GENERIC_ERROR."""
    if type(rejected) is not bool:
        raise ValueError("Invalid chest action result")
    return 13301, bytes([2 if rejected else 0])


def open_packet(character_id):
    """12088/cyN: captured chest occupation type31, empty extension data."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid chest actor")
    return 12088, struct.pack(">BhqI", 1, 31, character_id, 0)


def close_packet(character_id):
    """End the old actor's chest occupation without clearing account custody."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid chest actor")
    return 12088, struct.pack(">BhqI", 2, 31, character_id, 0)


def scene_packet(identity):
    """13984 reconstructs and hydrates the installed AccountChest object.

    The available state is recorded before the official action12 open. Object
    identity comes from the installed map catalog, never captured ownership.
    """
    if type(identity) is not int or identity <= 0:
        raise ValueError("Invalid native chest object identity")
    state = bytes.fromhex("01020000000602000101010001010000000000")
    return 13984, struct.pack(">hqh", 1, identity, len(state)) + state
