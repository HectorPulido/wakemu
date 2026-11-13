"""Reviewed reachable approaches for native NPCs on inaccessible platforms.

The authoritative actor is unchanged. Each approach is keyed by the complete
native placement so it cannot silently migrate to another actor or scene.
"""

ANCHORS = {
    # Native dojo platform at z=3 borders the reachable floor at z=0. The
    # captured Airyna identity and scene are distinct from the approach cell.
    (-1706442046308339, 5460, 1388, 0, 0, -19, 3): (0, -18, 0),
}


def interaction_anchor(row):
    key = tuple(
        row.get(name)
        for name in ("actor_id", "reference_id", "map_id", "instance_id", "x", "y", "z")
    )
    value = ANCHORS.get(key)
    return dict(zip(("x", "y", "z"), value)) if value is not None else None
