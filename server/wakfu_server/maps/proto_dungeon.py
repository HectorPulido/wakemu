"""Strict codec for the native ProtoDungeon message (fields 1–8)."""


_SINGULAR_FIELDS = {
    1: "max_level",
    2: "difficulty_level",
    3: "is_difficulty_available",
    4: "can_increase_difficulty",
    5: "is_fight_in_progress",
    6: "is_competitive_cancelled",
    8: "min_level",
}
_BOOL_FIELDS = {3, 4, 5, 6}
_INT32_FIELDS = {1, 2, 8}
_DEFAULTS = {
    "max_level": 0,
    "difficulty_level": 2,
    "is_difficulty_available": False,
    "can_increase_difficulty": True,
    "is_fight_in_progress": False,
    "is_competitive_cancelled": False,
    "allowed_ids": (),
    "min_level": 0,
}


def _varint(value):
    if type(value) is not int or value < 0:
        raise ValueError("ProtoDungeon varints must be nonnegative integers")
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _read_varint(data, offset):
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError("ProtoDungeon varint exceeds 64 bits")
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise ValueError("Malformed ProtoDungeon varint")


def _validate(context):
    if not isinstance(context, dict):
        raise ValueError("ProtoDungeon context must be a mapping")
    values = dict(_DEFAULTS)
    values.update(context)
    unknown = set(values) - set(_DEFAULTS)
    if unknown:
        raise ValueError("Unknown ProtoDungeon fields")
    for key in ("max_level", "min_level"):
        value = values[key]
        if type(value) is not int or not 0 <= value <= 0x7FFFFFFF:
            raise ValueError(f"Invalid ProtoDungeon {key}")
    difficulty = values["difficulty_level"]
    if type(difficulty) is not int or not 1 <= difficulty <= 10:
        raise ValueError("Invalid ProtoDungeon difficulty_level")
    for key in (
        "is_difficulty_available",
        "can_increase_difficulty",
        "is_fight_in_progress",
        "is_competitive_cancelled",
    ):
        if type(values[key]) is not bool:
            raise ValueError(f"Invalid ProtoDungeon {key}")
    allowed_ids = values["allowed_ids"]
    if not isinstance(allowed_ids, (list, tuple)):
        raise ValueError("ProtoDungeon allowed_ids must be a sequence")
    for identity in allowed_ids:
        if (
            type(identity) is not int
            or not -(1 << 63) <= identity <= 0x7FFFFFFFFFFFFFFF
        ):
            raise ValueError("Invalid ProtoDungeon allowed id")
    values["allowed_ids"] = tuple(allowed_ids)
    return values


def encode(context):
    """Encode known fields in field-number order using protobuf varints."""
    values = _validate(context)
    fields = []
    for number in (1, 2, 3, 4, 5, 6):
        key = _SINGULAR_FIELDS[number]
        value = values[key]
        if number in _BOOL_FIELDS:
            value = int(value)
        fields.append(_varint((number << 3) | 0) + _varint(value))
    for identity in values["allowed_ids"]:
        # Protobuf int64 represents negative values as a sign-extended 64-bit
        # varint, which takes ten bytes.
        fields.append(_varint((7 << 3) | 0) + _varint(identity & 0xFFFFFFFFFFFFFFFF))
    fields.append(_varint((8 << 3) | 0) + _varint(values["min_level"]))
    return b"".join(fields)


def decode(data):
    """Decode ProtoDungeon varint fields; unknown protobuf fields are skipped."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("ProtoDungeon payload must be bytes")
    data = bytes(data)
    values = dict(_DEFAULTS)
    allowed_ids = []
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("Invalid ProtoDungeon field number")
        if wire_type == 0:
            value, offset = _read_varint(data, offset)
            if number in _SINGULAR_FIELDS:
                key = _SINGULAR_FIELDS[number]
                if number in _INT32_FIELDS and value > 0x7FFFFFFF:
                    raise ValueError("ProtoDungeon int32 is out of range")
                if number in _BOOL_FIELDS:
                    value = bool(value)
                values[key] = value
            elif number == 7:
                allowed_ids.append(value - (1 << 64) if value >= (1 << 63) else value)
        elif wire_type == 1:
            offset += 8
        elif wire_type == 2:
            length, offset = _read_varint(data, offset)
            offset += length
        elif wire_type == 5:
            offset += 4
        else:
            raise ValueError("Unsupported ProtoDungeon wire type")
        if offset > len(data):
            raise ValueError("Truncated ProtoDungeon field")
    values["allowed_ids"] = tuple(allowed_ids)
    # Reuse outbound validation to keep the decoded public shape within the
    # supported domain (notably difficulty 1–10 and exact booleans).
    return _validate(values)
