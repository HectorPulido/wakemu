"""Native client request codecs for social/contact actions.

The wire layouts are taken from the installed Wakfu client classes:
``Nx.a`` frames requests as length + flags + opcode + body; the individual
request subclasses define the remaining fields.  Friend-list state itself is
server-to-client opcode 630 and is intentionally not encoded here.
"""

import struct


CONTACT_FIELDS = {
    "account_id": (1, "int64"),
    "account_name": (2, "string"),
    "is_online": (4, "bool"),
    "character_name": (50, "string"),
    "notify": (51, "bool"),
    "breed_id": (52, "int32"),
    "sex": (53, "int32"),
    "commentary": (54, "string"),
    "xp": (55, "int64"),
}


def _frame(opcode, flags, payload=b""):
    if type(opcode) is not int or not 0 <= opcode <= 0xFFFF:
        raise ValueError("invalid social opcode")
    if type(flags) is not int or not 0 <= flags <= 0xFF:
        raise ValueError("invalid social flags")
    payload = bytes(payload)
    length = 7 + len(payload)
    if length > 0x7FFFFFFF:
        raise ValueError("social frame too large")
    return struct.pack(">IBH", length, flags, opcode) + payload


def _contact_name(name):
    if not isinstance(name, str) or not name:
        raise ValueError("contact name must be a non-empty string")
    encoded = name.encode("utf-8")
    # Native NG/NH store the UTF-8 byte count in one byte. Reject values the
    # client would truncate in that field instead of producing an invalid frame.
    if len(encoded) > 0xFF:
        raise ValueError("contact name exceeds native one-byte length")
    return bytes((len(encoded),)) + encoded


def _contact_id(account_id):
    if type(account_id) is not int or not -(1 << 63) <= account_id < (1 << 63):
        raise ValueError("contact id must be a signed 64-bit integer")
    return struct.pack(">q", account_id)


def do_not_disturb_request():
    """Encode native csI request 12449 (flag 3, empty body).

    The client command sends a fixed action with no boolean value. This codec
    does not interpret it as an explicit set/clear operation.
    """
    return _frame(12449, 3)


def add_friend_request(name):
    """Encode NG request 784: flag 4, u8 UTF-8 byte length, name."""
    return _frame(784, 4, _contact_name(name))


def add_ignore_request(name):
    """Encode NH request 657: flag 4, u8 UTF-8 byte length, name."""
    return _frame(657, 4, _contact_name(name))


def remove_friend_request(account_id):
    """Encode NL request 672 with its raw big-endian i64 account ID."""
    return _frame(672, 4, _contact_id(account_id))


def remove_ignore_request(account_id):
    """Encode NM request 799 with its raw big-endian i64 account ID."""
    return _frame(799, 4, _contact_id(account_id))


def _varint(value):
    if type(value) is not int:
        raise ValueError("protobuf integer must be an int")
    if value < 0:
        value &= (1 << 64) - 1
    if value >= 1 << 64:
        raise ValueError("protobuf integer is outside uint64 encoding range")
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _encode_contact(contact):
    if not isinstance(contact, dict) or set(contact) - CONTACT_FIELDS.keys():
        raise ValueError("invalid social contact fields")
    if "account_name" not in contact or "is_online" not in contact:
        raise ValueError("native contact requires account_name and is_online")
    out = bytearray()
    for name, (number, kind) in CONTACT_FIELDS.items():
        if name not in contact:
            continue
        value = contact[name]
        wire_type = 2 if kind == "string" else 0
        out.extend(_varint((number << 3) | wire_type))
        if kind == "string":
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
            encoded = value.encode("utf-8")
            out.extend(_varint(len(encoded)))
            out.extend(encoded)
        elif kind == "bool":
            if type(value) is not bool:
                raise ValueError(f"{name} must be bool")
            out.extend(_varint(int(value)))
        else:
            low, high = (
                (-(1 << 31), (1 << 31) - 1)
                if kind == "int32"
                else (
                    -(1 << 63),
                    (1 << 63) - 1,
                )
            )
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} is outside its native {kind} range")
            out.extend(_varint(value))
    return bytes(out)


def encode_friend_lists(friends=(), ignored=()):
    """Encode opcode-630's protobuf body (fa: repeated friends and ignored).

    This creates a bootstrap payload only; it does not imply a database
    ownership scope or that the client sends an equivalent list request.
    """
    out = bytearray()
    for field_number, contacts in ((1, friends), (2, ignored)):
        for contact in contacts:
            encoded = _encode_contact(contact)
            out.extend(_varint((field_number << 3) | 2))
            out.extend(_varint(len(encoded)))
            out.extend(encoded)
    return bytes(out)


def _read_varint(data, offset):
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise ValueError("truncated protobuf varint")
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise ValueError("protobuf varint overflows uint64")
        value |= (byte & 0x7F) << (7 * index)
        if byte < 0x80:
            return value, offset
    raise ValueError("invalid protobuf varint")


def _read_contact(data):
    result = {}
    offset = 0
    by_number = {spec[0]: (name, spec[1]) for name, spec in CONTACT_FIELDS.items()}
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("invalid protobuf field number")
        known = by_number.get(number)
        if known is None:
            offset = _skip_field(data, offset, wire_type)
            continue
        name, kind = known
        expected_wire = 2 if kind == "string" else 0
        if wire_type != expected_wire:
            raise ValueError(f"wrong protobuf wire type for {name}")
        if kind == "string":
            length, offset = _read_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise ValueError("truncated protobuf string")
            try:
                value = data[offset:end].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("invalid protobuf UTF-8 string") from exc
            offset = end
        else:
            value, offset = _read_varint(data, offset)
            if kind == "bool":
                value = value != 0
            elif kind == "int32":
                value &= 0xFFFFFFFF
                if value & 0x80000000:
                    value -= 1 << 32
            elif value & (1 << 63):
                value -= 1 << 64
        result[name] = value
    if "account_name" not in result or "is_online" not in result:
        raise ValueError("native contact is missing required fields")
    return result


def _skip_field(data, offset, wire_type):
    if wire_type == 0:
        _, offset = _read_varint(data, offset)
        return offset
    if wire_type == 1:
        end = offset + 8
    elif wire_type == 2:
        length, offset = _read_varint(data, offset)
        end = offset + length
    elif wire_type == 5:
        end = offset + 4
    else:
        raise ValueError("unsupported protobuf wire type")
    if end > len(data):
        raise ValueError("truncated protobuf field")
    return end


def decode_friend_lists(payload):
    """Decode opcode-630 protobuf body into repeated friend/ignored records."""
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ValueError("social list payload must be bytes")
    data = bytes(payload)
    result = {"friends": [], "ignored": []}
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("invalid protobuf field number")
        if number not in (1, 2):
            offset = _skip_field(data, offset, wire_type)
            continue
        if wire_type != 2:
            raise ValueError("wrong protobuf wire type for social list")
        length, offset = _read_varint(data, offset)
        end = offset + length
        if end > len(data):
            raise ValueError("truncated social contact")
        result["friends" if number == 1 else "ignored"].append(
            _read_contact(data[offset:end])
        )
        offset = end
    return result


def _read_byte_string(data, offset):
    if offset >= len(data):
        raise ValueError("truncated native string length")
    length = data[offset]
    offset += 1
    end = offset + length
    if end > len(data):
        raise ValueError("truncated native string")
    try:
        value = data[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid native UTF-8 string") from exc
    return value, end


def _read_i64(data, offset):
    end = offset + 8
    if end > len(data):
        raise ValueError("truncated native i64")
    return struct.unpack_from(">q", data, offset)[0], end


def _finish(data, offset):
    if offset != len(data):
        raise ValueError("unexpected trailing social response bytes")


def _response_bytes(payload):
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ValueError("social response payload must be bytes")
    return bytes(payload)


def decode_add_friend_ack(payload):
    """Decode native NS/opcode 718 add-friend success contact."""
    data = _response_bytes(payload)
    account_name, offset = _read_byte_string(data, 0)
    character_name, offset = _read_byte_string(data, offset)
    account_id, offset = _read_i64(data, offset)
    if offset + 3 > len(data):
        raise ValueError("truncated add-friend breed/sex")
    breed_id, sex = struct.unpack_from(">hb", data, offset)
    offset += 3
    xp, offset = _read_i64(data, offset)
    _finish(data, offset)
    return {
        "account_id": account_id,
        "account_name": account_name,
        "character_name": character_name,
        "breed_id": breed_id,
        "sex": sex,
        "xp": xp,
    }


def decode_add_ignore_ack(payload):
    """Decode native NX/opcode 641 add-ignore success contact."""
    data = _response_bytes(payload)
    account_id, offset = _read_i64(data, 0)
    account_name, offset = _read_byte_string(data, offset)
    character_name, offset = _read_byte_string(data, offset)
    _finish(data, offset)
    return {
        "account_id": account_id,
        "account_name": account_name,
        "character_name": character_name,
    }


def decode_remove_friend_ack(payload):
    """Decode native NU/opcode 719, the removed account ID."""
    data = _response_bytes(payload)
    account_id, offset = _read_i64(data, 0)
    _finish(data, offset)
    return {"account_id": account_id}


def decode_remove_ignore_ack(payload):
    """Decode native NY/opcode 765: removed account ID and account name."""
    data = _response_bytes(payload)
    account_id, offset = _read_i64(data, 0)
    account_name, offset = _read_byte_string(data, offset)
    _finish(data, offset)
    return {"account_id": account_id, "account_name": account_name}


def decode_do_not_disturb_status(payload):
    """Decode Om/opcode 711's first byte as observed status, not a setter."""
    data = _response_bytes(payload)
    if len(data) != 1:
        raise ValueError("DND status must contain exactly one byte")
    return data[0] == 1
