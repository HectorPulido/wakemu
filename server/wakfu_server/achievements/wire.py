"""Native version5 state section and absolute achievement notifications."""
import struct
import zlib
from .storage import _state


def section(state):
    _state(state)
    recent = state["recent"][-255:]
    body = struct.pack(">iB", 5, len(recent))
    body += b"".join(struct.pack(">iq", row["id"], row["date_ms"]) for row in recent)
    variables = sorted((int(key), value) for key, value in state["variables"].items())
    body += struct.pack(">i", len(variables))
    body += b"".join(struct.pack(">iq", key, value) for key, value in variables)
    identities = sorted(set(state["running"]) | set(state["completed"]))
    body += struct.pack(">i", len(identities))
    for identity in identities:
        # Optional native dates and opaque flagV5 remain absent/false.
        body += struct.pack(
            ">iBBBBB",
            identity,
            identity in state["running"],
            identity in state["completed"],
            0,
            0,
            0,
        )
    body += struct.pack(">i", len(state["objectives"]))
    body += b"".join(struct.pack(">i", identity) for identity in state["objectives"])
    body += struct.pack(">B", len(state["tracking"]))
    body += b"".join(struct.pack(">i", identity) for identity in state["tracking"])
    compressed = False
    if len(body) > 65535:
        body, compressed = zlib.compress(body), True
    if len(body) > 65535:
        raise ValueError("Achievement state exceeds native section capacity")
    return struct.pack(">H", len(body)) + body + bytes([compressed])


def changes(character_id, before, after, new_objectives, new_completed, now_ms):
    packets = []
    for identity in sorted(
        set(after["running"]) - set(before["running"]) - set(before["completed"])
    ):
        packets.append((13205, struct.pack(">qi", character_id, identity)))
    for key, value in sorted(after["variables"].items(), key=lambda row: int(row[0])):
        if before["variables"].get(key) != value:
            packets.append((13295, struct.pack(">qiq", character_id, int(key), value)))
    packets.extend(
        (13832, struct.pack(">qi", character_id, identity))
        for identity in new_objectives
    )
    packets.extend(
        (13422, struct.pack(">qiq", character_id, identity, now_ms))
        for identity in new_completed
    )
    return packets
