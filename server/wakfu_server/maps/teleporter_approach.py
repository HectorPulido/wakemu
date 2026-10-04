"""Conservative bEm.pathEnded gate using authoritative approved movement.

Native bEm compares the path-end X/Y with bEk.bcz()/bcA(), without a
Manhattan radius or altitude comparison. Server Movement approves full paths
before client animation completes, so source crossing can precede its cached
final endpoint. The approved path is valid only in its current world instance.
"""


def callback(movement_state, *, map_id, instance_id=0):
    """Bind the current-world Movement instance; recreate after each transition."""

    def allowed(character, source):
        if character.get("instance_id", 0) != instance_id or instance_id != 0:
            return False
        if character["map_id"] != map_id or source["map_id"] != map_id:
            return False
        sx, sy = source["x"], source["y"]
        if sx != int(sx) or sy != int(sy):
            return False
        # Snapshot the actual approved path, not a client-supplied path or an
        # unvalidated position. bEm's native callback intentionally ignores Z.
        return any(
            x == int(sx) and y == int(sy) for x, y, z in tuple(movement_state.approved)
        )

    return allowed
