"""Explicit action-specific dialogue contracts for native NPC placements.

Native action criteria do not identify a dialogue root or graph. Add a contract
only when its placement and action are qualified; inferred edges remain marked.
"""

_CONTRACTS = {
    (5461, -1706442046308322, 1385, 0, 1241): {
        "root": 5757,
        "edges": {
            (5757, 13263): 5758,
            (5757, 13267): 5759,
            (5757, 13264): 0,
            (5758, 13266): 5757,
            (5759, 13286): 5771,
            (5759, 13268): 5760,
            (5759, 13272): 5761,
            (5759, 13269): 0,
            (5760, 13270): 5759,
            (5760, 13271): 0,
            (5761, 13273): 5759,
            (5761, 13274): 0,
            (5771, 13284): 5759,
            (5771, 13285): 0,
        },
        "edge_authority": "inferred_from_native_text",
    },
}


def resolve(row, action_id):
    """Return only a contract for the exact placement and action."""
    if row is None:
        return None
    key = (
        row.get("reference_id"),
        row.get("actor_id"),
        row.get("map_id"),
        row.get("instance_id"),
        action_id,
    )
    return _CONTRACTS.get(key)
