"""Original fg component-offset envelope and bEH parameter replacement.

Offsets are absolute positions of component marker bytes, not body lengths.
The original bEH reader assigns bbz and calls virtual dSG after field1.
No client asset, native UID, geometry, flags or item definition is modified.
"""
import struct


def components(payload):
    if type(payload) is not bytes or not payload or not 0 < payload[0] < 128:
        raise ValueError("Invalid native component envelope")
    count = payload[0]
    header = 1 + 5 * count
    if len(payload) < header:
        raise ValueError("Truncated native component header")
    entries = [struct.unpack_from(">BI", payload, 1 + i * 5) for i in range(count)]
    if (
        len({kind for kind, _ in entries}) != count
        or entries[0][1] != header
        or any(offset >= len(payload) for _, offset in entries)
        or any(entries[i][1] >= entries[i + 1][1] for i in range(count - 1))
    ):
        raise ValueError("Invalid native component offsets")
    result = {}
    for index, (kind, offset) in enumerate(entries):
        end = entries[index + 1][1] if index + 1 < count else len(payload)
        if payload[offset] != kind:
            raise ValueError("Native component marker disagrees with header")
        result[kind] = payload[offset + 1 : end]
    return result


def envelope(parts):
    if (
        not isinstance(parts, dict)
        or not 0 < len(parts) < 128
        or any(
            type(kind) is not int or not 0 <= kind <= 255 or type(body) is not bytes
            for kind, body in parts.items()
        )
    ):
        raise ValueError("Invalid native component collection")
    cursor = 1 + 5 * len(parts)
    header = bytearray((len(parts),))
    bodies = bytearray()
    for kind, body in sorted(parts.items()):
        header.extend(struct.pack(">BI", kind, cursor))
        encoded = bytes((kind,)) + body
        bodies.extend(encoded)
        cursor += len(encoded)
    return bytes(header + bodies)


def parameter_bounds(body):
    # bEH: map(i16),XYZ(i32,i32,i16),i16,visible,u8,direction,i16,
    # footprint count(i16), then count-1 XYZ cells, then UTF-8 length(u16).
    if type(body) is not bytes or len(body) < 23:
        raise ValueError("Truncated native bEH component")
    count = struct.unpack_from(">h", body, 19)[0]
    if count < 0:
        raise ValueError("Invalid native bEH footprint count")
    position = 21 + max(0, count - 1) * 10
    if position + 2 > len(body):
        raise ValueError("Truncated native bEH footprint")
    length = struct.unpack_from(">H", body, position)[0]
    start = position + 2
    end = start + length
    if end > len(body):
        raise ValueError("Truncated native bEH parameter")
    return position, start, end


def rebind_definition(baseline, state, *, expected_parameter, replacement_parameter):
    base, live = components(baseline), components(state)
    if set(base) != {0, 1} or set(live) != {2}:
        raise ValueError(
            "Definition reconstruction needs original baseline0/1 and state2"
        )
    if any(
        type(value) is not str or not value
        for value in (expected_parameter, replacement_parameter)
    ):
        raise ValueError("Missing native definition parameter")
    body = base[1]
    position, start, end = parameter_bounds(body)
    if body[start:end].decode("utf-8") != expected_parameter:
        raise ValueError("Original native definition parameter changed")
    replacement = replacement_parameter.encode("utf-8")
    if len(replacement) > 65535:
        raise ValueError("Native definition parameter is too long")
    base[1] = (
        body[:position] + struct.pack(">H", len(replacement)) + replacement + body[end:]
    )
    return envelope({**base, **live})


def packet(object_id, payload):
    if type(object_id) is not int or object_id <= 0 or len(payload) > 32767:
        raise ValueError("Invalid native interactive publication")
    components(payload)
    return 13984, struct.pack(">hqh", 1, object_id, len(payload)) + payload
