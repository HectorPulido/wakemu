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
