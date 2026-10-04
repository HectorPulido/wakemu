"""Native csZ13046 owned actor refresh envelope (i64 + signed i16 + blob)."""
import struct


def actor_refresh(actor_id, blob):
    if (
        type(actor_id) is not int
        or actor_id == 0
        or not -(1 << 63) < actor_id < (1 << 63)
    ):
        raise ValueError("Invalid actor refresh identity")
    if not isinstance(blob, bytes) or not 0 < len(blob) < (1 << 15):
        raise ValueError("Invalid native actor refresh length")
    return 13046, struct.pack(">qh", actor_id, len(blob)) + blob
