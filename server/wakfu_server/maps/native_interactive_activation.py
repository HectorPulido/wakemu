"""Literal Re.bkT native interactive activation positions, without radius guesses."""

import struct


def decode(record):
    """Decode exact i32/i32/i16 members from the installed bEH content frame."""
    raw = bytes.fromhex(record["payload_hex"])
    identity = struct.pack(
        ">hiih", record["map_id"], int(record["x"]), int(record["y"]), int(record["z"])
    )
    starts = [index for index in range(len(raw)) if raw.startswith(identity, index)]
    if len(starts) != 1:
        raise ValueError("Native interactive map/position frame is not unique")
    start = starts[0]
    if len(raw) < start + 21:
        raise ValueError("Truncated native interactive content frame")
    count = struct.unpack_from(">h", raw, start + 19)[0]
    if not 0 <= count <= 4096 or len(raw) < start + 21 + count * 10 + 2:
        raise ValueError("Invalid native activation-position count")
    return [
        list(struct.unpack_from(">iih", raw, start + 21 + index * 10))
        for index in range(count)
    ]
