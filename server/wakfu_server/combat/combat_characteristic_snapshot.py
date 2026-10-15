"""Project native fighter snapshots to characteristics without relocation."""

import struct


_CHARACTERISTIC_OFFSETS = {
    2: 1 + struct.calcsize(">iihqBB") + struct.calcsize(">iBBBBbB"),
    3: 1
    + struct.calcsize(">q")
    + struct.calcsize(">iihqBB")
    + struct.calcsize(">iBBBBbB"),
}


def characteristics_only_snapshot(full_snapshot):
    """Keep the original pl/tA bytes in native ALL_CHARACTERISTICS format40.

    Player format3, NPC format2 and summon format2 share this fight table.
    Full snapshots remain necessary when position, QI, control or other actor
    metadata changes; this projection is for an already published movement.
    """
    if not isinstance(full_snapshot, bytes) or not full_snapshot:
        raise ValueError("Missing native fighter snapshot")
    offset = _CHARACTERISTIC_OFFSETS.get(full_snapshot[0])
    if offset is None or len(full_snapshot) < offset + 2:
        raise ValueError("Unsupported or truncated native fighter snapshot")
    count = struct.unpack_from(">H", full_snapshot, offset)[0]
    end = offset + 2 + count * struct.calcsize(">Biiii")
    if end > len(full_snapshot):
        raise ValueError("Truncated native fighter characteristics")
    return bytes((40,)) + full_snapshot[offset:end]
