"""Environmental execution is authorized only by live map/instance occupancy.

Use World's existing occupancy episodes, not persisted character coordinates,
session expiry, database scans or a second simulation/presence registry.
"""
_world = None


def configure(world):
    if not callable(getattr(world, "scope_presence", None)):
        raise ValueError("Environmental execution requires live World presence")
    global _world
    _world = world


def capture(map_id, instance_id, *, world=None):
    authority = _world if world is None else world
    if authority is None:
        return None
    generation = authority.scope_presence(map_id, instance_id)
    return None if generation is None else (authority, generation)


def current(token, map_id, instance_id):
    return (
        token is not None and token[0].scope_presence(map_id, instance_id) == token[1]
    )


def try_positions(token, map_id, instance_id):
    """Read current scoped XYZ without waiting for World's membership lock.

    Population callers can already own SQL account/region/population locks.
    Ecology commits hold World before taking those SQL locks, so a busy World
    must defer this population attempt instead of reversing that lock order.
    No registry, cached positions or stale occupancy episode is introduced.
    """
    if token is None:
        return None
    world = token[0]
    if not world.lock.acquire(blocking=False):
        return None
    try:
        if not current(token, map_id, instance_id):
            return None
        return tuple(
            (row["x"], row["y"], row["z"])
            for _, _, row in world.players.values()
            if world.location(row) == (map_id, instance_id)
        )
    finally:
        world.lock.release()
