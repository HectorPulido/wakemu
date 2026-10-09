"""Native eOr border-cell result over the captured serialized QI masks."""

from .combat_qi_snapshot import NativeQISnapshot


def border_cell_result(arena_snapshot, x, y):
    """Return eOr's 0 for QI.P, otherwise -1, using a validated QI copy."""
    if not isinstance(arena_snapshot, dict):
        raise ValueError("Missing serialized native QI border snapshot")
    qi = NativeQISnapshot(arena_snapshot)
    return 0 if qi.P(x, y) else -1
