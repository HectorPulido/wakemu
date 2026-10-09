"""Persist and serialize native lD/ProtoShard state without rerolling it.

The protobuf blob is the native 13766 socket carrier and ProtoItem field 52.
The inventory UI also uses the equivalent legacy ``yp`` binary option.  This
module converts the known lD fields into that option while preserving the
original protobuf bytes for reconnects and future fields.
"""
import struct

from wakfu_server.wire import proto_fields

MAX_BLOB = 65536
MAX_REPEATED = 32767


def _fields(blob):
    if not isinstance(blob, bytes) or not 1 <= len(blob) <= MAX_BLOB:
        raise ValueError("Invalid native shard state size")
    return list(proto_fields(blob))


def _validate_wire_types(blob, known_fields):
    for tag, _ in proto_fields(blob):
        field_number, wire_type = tag >> 3, tag & 7
        expected = known_fields.get(field_number)
        if expected is not None and wire_type != expected:
            raise ValueError("Invalid native shard field wire type")


def _varint_field(tag, value):
    if tag & 7 != 0 or type(value) is not int or value < 0:
        raise ValueError("Invalid native shard scalar")
    return value


def _bytes_field(tag, value):
    if tag & 7 != 2 or not isinstance(value, bytes):
        raise ValueError("Invalid native shard message")
    return value


def _int32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & (1 << 31) else value


def _scalar_map(blob, known):
    values = {}
    for tag, value in proto_fields(blob):
        if tag in known:
            values[tag] = _varint_field(tag, value)
    return values


def validate(blob):
    """Check protobuf framing and known native lD field wire types.

    Unknown fields remain in the stored bytes, so a newer client field is not
    discarded merely because this server does not interpret it yet.
    """
    fields = _fields(blob)
    # Protobuf normally treats a recognized field number with another wire
    # type as unknown. That is unsafe for our legacy yp conversion, so reject
    # it for every field the installed client defines. Truly unknown fields
    # remain byte-for-byte intact in storage and the ProtoItem carrier.
    _validate_wire_types(blob, {1: 2, 2: 2, 3: 0, 4: 0, 9: 0})
    for tag, value in fields:
        if tag == 10:
            nested = _bytes_field(tag, value)
            _validate_wire_types(nested, {10: 0, 11: 0, 12: 0, 14: 0})
            _scalar_map(nested, {80, 88, 96, 112})
        elif tag == 18:
            nested = _bytes_field(tag, value)
            _validate_wire_types(nested, {20: 0, 21: 0})
            _scalar_map(nested, {160, 168})
        elif tag in (24, 32, 72):
            _varint_field(tag, value)
    return blob


def initialized_wire_state(blob):
    """Complete legacy empty slots for native lK required field11.

    Missing item reference is the legacy empty-slot zero only when no shard
    quantity exists. Do not repair an occupied slot with an unknown reference.
    Persisted bytes remain unchanged; this is a protocol boundary adapter.
    """
    from wakfu_server.wire import proto_field

    validate(blob)
    fields = list(proto_fields(blob))
    changed = False
    result = []
    for tag, value in fields:
        if tag == 10:
            row = _scalar_map(value, {80, 88, 96, 112})
            if 80 not in row:
                raise ValueError("Native shard slot missing required position")
            if 88 not in row:
                if row.get(112, 0) != 0:
                    raise ValueError(
                        "Occupied native shard slot missing item reference"
                    )
                value += proto_field(88, 0)
                changed = True
        result.append(proto_field(tag, value))
    return b"".join(result) if changed else blob


def legacy_option(blob):
    """Encode native yp bytes from a ProtoShard/lD protobuf blob.

    yp.aF writes repeated yr slots, repeated yq additional gems, then the two
    sublimation IDs and signed charge byte. Native field order and primitive
    widths were read from the installed vj/yp/yr/yq classes.
    """
    fields = _fields(validate(blob))
    slots = []
    gems = []
    sublimation = 0
    special_sublimation = 0
    charges = 0
    for tag, value in fields:
        if tag == 10:
            row = _scalar_map(_bytes_field(tag, value), {80, 88, 96, 112})
            slots.append(
                (
                    _int32(row.get(80, 0)),
                    _int32(row.get(88, 0)),
                    _int32(row.get(96, 0)),
                    _int32(row.get(112, 0)),
                )
            )
        elif tag == 18:
            row = _scalar_map(_bytes_field(tag, value), {160, 168})
            gems.append((_int32(row.get(160, 0)), _int32(row.get(168, 0))))
        elif tag == 24:
            sublimation = _int32(_varint_field(tag, value))
        elif tag == 32:
            special_sublimation = _int32(_varint_field(tag, value))
        elif tag == 72:
            charges = _int32(_varint_field(tag, value))
    if len(slots) > MAX_REPEATED or len(gems) > MAX_REPEATED:
        raise ValueError("Native shard state has too many repeated values")
    if any(not -128 <= row[0] <= 255 or not -128 <= row[2] <= 255 for row in slots):
        raise ValueError("Native shard byte value is out of range")
    if any(not -128 <= row[0] <= 255 for row in gems):
        raise ValueError("Native gem property byte is out of range")
    if not -128 <= charges <= 255:
        raise ValueError("Native shard charge byte is out of range")

    result = bytearray(struct.pack(">H", len(slots)))
    for position, item_ref, color, amount in slots:
        result.extend(
            struct.pack(">BiBi", position & 0xFF, item_ref, color & 0xFF, amount)
        )
    result.extend(struct.pack(">H", len(gems)))
    for property_id, ref_id in gems:
        result.extend(struct.pack(">Bi", property_id & 0xFF, ref_id))
    result.extend(struct.pack(">iiB", sublimation, special_sublimation, charges & 0xFF))
    return bytes(result)


def save(db, uid, shard_state):
    """Store an already-authorized native result inside the caller's TX.

    This helper deliberately does not generate socket contents or decide costs.
    The caller must have validated its session/ownership and locked the item.
    """
    validate(shard_state)
    db.execute(
        "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s) "
        "ON CONFLICT(uid) DO UPDATE SET shard_state=EXCLUDED.shard_state",
        (uid, shard_state),
    )


def hydrate(db, items):
    if not items:
        return items
    by_uid = {item["uid"]: item for item in items}
    for row in db.execute(
        "SELECT uid,shard_state FROM inventory_item_shards WHERE uid=ANY(%s)",
        (list(by_uid),),
    ):
        state = validate(bytes(row["shard_state"]))
        by_uid[row["uid"]]["shard_state"] = state
    return items


def copy(db, source_uid, target_uid):
    row = db.execute(
        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s", (source_uid,)
    ).fetchone()
    if row is not None:
        save(db, target_uid, bytes(row["shard_state"]))


def proto(item):
    state = item.get("shard_state")
    if state is None:
        return b""
    from wakfu_server.wire import proto_field

    # ProtoItem.shard is protobuf field 52, length-delimited (wire tag 418).
    return proto_field(418, initialized_wire_state(state))


def option(item):
    state = item.get("shard_state")
    return None if state is None else legacy_option(state)
