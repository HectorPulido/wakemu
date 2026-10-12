"""Hydrate installed bag portal objects for an authorized interior session.

The native 13984 consumer reconstructs an object from an existing raw template
(QY.du), then applies its state. It cannot introduce an absent template or
replace its native type. Ranch entrances retain their original client actions;
this publication does not pretend they are Zaaps.
"""
import struct

from wakfu_server import world_static
from wakfu_server.world_scene_sync import refresh_snapshots


def packets(session, character):
    """Return nearby native portal states for this live owner or guest session."""
    if session is None or not session.owns(character):
        raise ValueError("Native bag scene requires its active interior session")
    allowed = {
        row["id"] for row in world_static.objects(9) if row["type"] == "RanchEntrance"
    }
    result = []
    for body in world_static.snapshots(9, position=character):
        count = struct.unpack_from(">h", body)[0]
        offset, rows = 2, []
        for _ in range(count):
            identity, size = struct.unpack_from(">qh", body, offset)
            offset += 10
            payload = body[offset : offset + size]
            offset += size
            if identity in allowed:
                rows.append(struct.pack(">qh", identity, size) + payload)
        if offset != len(body):
            raise ValueError("Malformed native bag scene snapshot")
        if rows:
            snapshot = struct.pack(">h", len(rows)) + b"".join(rows)
            result.append((13984, snapshot))
            # cEX retains a previously registered object when attachment is
            # repeated. cEY applies state to that retained object, including
            # after a visitor leaves or a private scene is reloaded.
            result.extend((12344, update) for update in refresh_snapshots(snapshot))
    return result
