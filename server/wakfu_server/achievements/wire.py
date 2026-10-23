"""Native version5 state section and absolute achievement notifications."""
import struct
import zlib
from .storage import _state


def section(state, *, activation_dates=None):
    _state(state)
    activation_dates = {} if activation_dates is None else activation_dates
    if not isinstance(activation_dates, dict) or any(
        type(key) is not int
        or key <= 0
        or type(value) is not int
        or not 0 <= value < 2**63
        for key, value in activation_dates.items()
    ):
        raise ValueError("Invalid native achievement activation dates")
    recent = state["recent"][-255:]
    body = struct.pack(">iB", 5, len(recent))
    body += b"".join(struct.pack(">iq", row["id"], row["date_ms"]) for row in recent)
    variables = sorted((int(key), value) for key, value in state["variables"].items())
    body += struct.pack(">i", len(variables))
    body += b"".join(struct.pack(">iq", key, value) for key, value in variables)
    identities = sorted(set(state["running"]) | set(state["completed"]))
    body += struct.pack(">i", len(identities))
    for identity in identities:
        # Original bdD.cCN sets ddP at activation; loader date2 calls hl.
        # Date1 is a distinct cooldown clock and remains absent here.
        activated_at = activation_dates.get(identity)
        body += struct.pack(
            ">iBBBB",
            identity,
            identity in state["running"],
            identity in state["completed"],
            0,
            activated_at is not None,
        )
        if activated_at is not None:
            body += struct.pack(">q", activated_at)
        body += b"\x00"  # Opaque native flagV5.
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
        # Native cto/cEC13312 activates bdD.NO. ctv/cEJ13205 instead resets
        # that flag and completed objectives; it cannot announce a new mission.
        packets.append((13312, struct.pack(">qi", character_id, identity)))
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
