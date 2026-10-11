"""Bounded protobuf/Spin codec derived from the installed intergame descriptors."""
import json
import struct
from pathlib import Path


SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "protocol/native_intergame_descriptors.json"
    ).read_text()
)
MESSAGES = SCHEMA["messages"]
IDS = {row["message"]: row["id"] for row in SCHEMA["identifiers"]}
NAMES = {value: key for key, value in IDS.items()}
MAX_FRAME = 1048576


def varint(value):
    if type(value) is not int or not -(1 << 63) <= value < 1 << 64:
        raise ValueError("Invalid protobuf integer")
    value &= (1 << 64) - 1
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result) + bytes((value,))


def _integer(data, offset):
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise ValueError("Truncated protobuf integer")
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise ValueError("Oversized protobuf integer")
        value |= (byte & 127) << (7 * index)
        if not byte & 128:
            return value, offset
    raise ValueError("Oversized protobuf integer")


def encode(name, value, _depth=0):
    if _depth > 16 or type(value) is not dict or name not in MESSAGES:
        raise ValueError("Invalid intergame message")
    fields = {field["name"]: field for field in MESSAGES[name]}
    if set(value) - fields.keys():
        raise ValueError("Unknown intergame field")
    result = bytearray()
    oneofs = set()
    for key, field in fields.items():
        if key not in value:
            continue
        if "oneof" in field:
            if field["oneof"] in oneofs:
                raise ValueError("Conflicting protobuf oneof")
            oneofs.add(field["oneof"])
        values = value[key] if field["repeated"] else [value[key]]
        if type(values) is not list or len(values) > 4096:
            raise ValueError("Invalid repeated intergame field")
        for item in values:
            kind = field["type"]
            if kind in ("STRING", "BYTES", "MESSAGE"):
                if kind == "STRING":
                    if type(item) is not str:
                        raise ValueError("Invalid protobuf text")
                    content = item.encode("utf-8")
                elif kind == "MESSAGE":
                    content = encode(field["message"], item, _depth + 1)
                else:
                    if type(item) is not bytes:
                        raise ValueError("Invalid protobuf bytes")
                    content = item
                result.extend(
                    varint(field["number"] << 3 | 2) + varint(len(content)) + content
                )
            elif kind in ("INT32", "INT64", "UINT32", "UINT64", "ENUM", "BOOL"):
                if kind == "BOOL":
                    if type(item) is not bool:
                        raise ValueError("Invalid protobuf boolean")
                    item = int(item)
                if type(item) is not int:
                    raise ValueError("Invalid protobuf integer")
                if kind in ("INT32", "ENUM") and not -(1 << 31) <= item < 1 << 31:
                    raise ValueError("Invalid protobuf int32")
                if kind.startswith("UINT") and item < 0:
                    raise ValueError("Invalid protobuf unsigned integer")
                result.extend(varint(field["number"] << 3) + varint(item))
            else:
                raise ValueError("Unsupported installed protobuf field")
            if len(result) > MAX_FRAME - 5:
                raise ValueError("Intergame message too large")
    return bytes(result)


def decode(name, data, _depth=0):
    if (
        _depth > 16
        or type(data) is not bytes
        or len(data) > MAX_FRAME - 5
        or name not in MESSAGES
    ):
        raise ValueError("Invalid intergame message")
    fields = {field["number"]: field for field in MESSAGES[name]}
    result, offset, count = {}, 0, 0
    while offset < len(data):
        count += 1
        if count > 4096:
            raise ValueError("Too many protobuf fields")
        tag, offset = _integer(data, offset)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid protobuf field zero")
        if wire == 0:
            item, offset = _integer(data, offset)
        elif wire in (1, 2, 5):
            size = {1: 8, 5: 4}.get(wire)
            if wire == 2:
                size, offset = _integer(data, offset)
            if size > len(data) - offset:
                raise ValueError("Truncated protobuf field")
            item, offset = data[offset : offset + size], offset + size
        else:
            raise ValueError("Unsupported protobuf wire type")
        field = fields.get(number)
        if field is None:
            continue
        kind = field["type"]
        expected = 2 if kind in ("STRING", "BYTES", "MESSAGE") else 0
        if wire != expected:
            raise ValueError("Incorrect protobuf wire type")
        if kind == "STRING":
            item = item.decode("utf-8")
        elif kind == "MESSAGE":
            item = decode(field["message"], item, _depth + 1)
        elif kind in ("INT32", "ENUM"):
            item &= 0xFFFFFFFF
            if item >= 1 << 31:
                item -= 1 << 32
        elif kind == "INT64" and item >= 1 << 63:
            item -= 1 << 64
        elif kind == "BOOL":
            item = bool(item)
        if "oneof" in field:
            for other in fields.values():
                if other.get("oneof") == field["oneof"]:
                    result.pop(other["name"], None)
        if field["repeated"]:
            result.setdefault(field["name"], []).append(item)
        else:
            result[field["name"]] = item
    return result


def spin(kind, body=b""):
    if type(kind) is not int or kind not in (0, 1, 2, 3) or type(body) is not bytes:
        raise ValueError("Invalid Spin frame")
    if len(body) > MAX_FRAME - 5 or (kind and body):
        raise ValueError("Invalid Spin frame length")
    return struct.pack(">IB", len(body) + 5, kind) + body


def response(correlation, *, name=None, value=None, status=1):
    payload = {} if name is None else {"id": IDS[name], "data": encode(name, value)}
    return encode(
        "transport.Frame",
        {
            "response": {
                "correlation_id": correlation,
                "status": status,
                "payload": payload,
            }
        },
    )


def event(name, value):
    return encode(
        "transport.Frame", {"event": {"id": IDS[name], "data": encode(name, value)}}
    )
