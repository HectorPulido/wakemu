"""Explicit Wakemu route-witness policy, not native Sn search equivalence.

Only HasValidPathToTarget(2), without option strings, is supported. Every true
result replays an actual bounded route through the same Fight._move_actor
movement domain used by player and NPC execution, on an isolated fight copy.
The native eMU constructor signature is preserved by the condition bridge.
"""
from copy import deepcopy

POLICY = "wakemu_actual_movement_path_witness_v1_not_native_Sn_equivalence"


def admitted_route(fight, actor_id, target, *, limit):
    """Return an admitted route or None; missing authority always raises."""
    from .combat_qi_fight import current_registry

    if type(limit) is not int or limit != 2:
        raise ValueError("Unsupported Wakemu path-witness limit")
    actor = fight.actors.get(actor_id)
    if actor is None:
        raise ValueError("Missing actual path-witness caster")
    if (
        type(getattr(actor, "physical_radius", None)) is not int
        or actor.physical_radius != 0
    ):
        raise ValueError("Unsupported path-witness actor footprint")
    if (
        not isinstance(target, (tuple, list))
        or len(target) != 3
        or any(type(value) is not int for value in target)
    ):
        raise ValueError("Missing actual path-witness target")
    target = tuple(target)
    if fight.edges is None:
        raise ValueError("Missing actual directed movement edges")
    if (
        target not in fight.walkable
        or abs(target[0] - actor.position[0]) + abs(target[1] - actor.position[1])
        > limit
    ):
        return None  # Canonical movement has exactly one planar unit per step.
    if not fight._in_play(actor):
        raise ValueError("Path-witness caster is not currently in play")
    # Work from a copy even for registry validation: native pointer bridges may
    # perform internal consistency bookkeeping. Observation never touches live.
    isolated = deepcopy(fight)
    registry = current_registry(isolated)
    source = isolated.actors[actor_id]
    slot = source.native_obstacle_id
    if registry.slots[slot] is None or registry.slots[slot]["identity"] != [
        "actor",
        actor_id,
    ]:
        raise ValueError("Missing registered path-witness caster identity")
    if target == tuple(source.position):
        # A zero-step path is rejected by the canonical movement domain.
        return None
    adjacency = {}
    for start, end in isolated.edges:
        adjacency.setdefault(tuple(start), []).append(tuple(end))
    frontier = [()]
    for _ in range(limit):
        following = []
        for path in frontier:
            previous = path[-1] if path else tuple(source.position)
            for cell in sorted(adjacency.get(previous, ())):
                if cell in path or cell == tuple(source.position):
                    continue
                if cell not in isolated.walkable:
                    continue
                occupants = registry.snapshot().U(*cell[:2])
                if any(
                    registered != slot
                    and registry.slots[registered] is not None
                    and registry.slots[registered]["movement_blocking"]
                    for registered in (() if occupants is None else occupants)
                ):
                    continue
                route = (*path, cell)
                if cell != target:
                    following.append(route)
                    continue
                candidate = deepcopy(isolated)
                try:
                    event = candidate._move_actor(candidate.actors[actor_id], route)
                except ValueError as error:
                    # Only canonical route/resource rejection means no witness.
                    # Missing authority, malformed native state and producer
                    # failures must remain unsupported rather than become false.
                    if str(error) not in (
                        "Invalid combat movement path",
                        "Terrain transition is not walkable",
                        "Altitude transition requires validated terrain edge",
                        "Empty path or insufficient AP/MP for combat movement",
                        "Native movement is restricted to rails",
                    ):
                        raise
                    continue
                if (
                    candidate.actors[actor_id].position != target
                    or tuple(map(tuple, event["path"])) != route
                    or event["actor_id"] != actor_id
                ):
                    raise ValueError("Canonical movement did not admit the exact route")
                return route
        frontier = following
    return None
