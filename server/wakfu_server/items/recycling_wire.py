"""Strict native layouts for item recycling, without inventory side effects.

The client sends cnz/12787: a signed-short count followed by that many i64
item UIDs. The client consumes cwS/12890 as two i32 values. Their domain
meaning is intentionally left to the recycling service.
"""
import struct


def _uid(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid recycling item UID")
    return value


def decode_request(opcode, body):
    if opcode != 12787:
        raise ValueError("Unsupported recycling request opcode")
    if not isinstance(body, bytes) or len(body) < 2:
        raise ValueError("Invalid recycling request length")
    count = struct.unpack_from(">h", body)[0]
    if count <= 0 or len(body) != 2 + count * 8:
        raise ValueError("Invalid recycling item count or length")
    uids = [entry[0] for entry in struct.iter_unpack(">q", body[2:])]
    uids = [_uid(uid) for uid in uids]
    if len(set(uids)) != count:
        raise ValueError("Duplicate recycling item UID")
    return {"uids": uids}


def request(uids):
    if not isinstance(uids, (list, tuple)) or not 1 <= len(uids) <= 32767:
        raise ValueError("Invalid recycling item count")
    checked = [_uid(uid) for uid in uids]
    if len(set(checked)) != len(checked):
        raise ValueError("Duplicate recycling item UID")
    return 12787, struct.pack(">h", len(checked)) + b"".join(
        struct.pack(">q", uid) for uid in checked
    )


def decode_result(opcode, body):
    if opcode != 12890:
        raise ValueError("Unsupported recycling result opcode")
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Invalid recycling result length")
    first, second = struct.unpack(">ii", body)
    return {"first": first, "second": second}


def result(first, second):
    if (
        type(first) is not int
        or not -(2**31) <= first < 2**31
        or type(second) is not int
        or not -(2**31) <= second < 2**31
    ):
        raise ValueError("Invalid recycling result fields")
    return 12890, struct.pack(">ii", first, second)
