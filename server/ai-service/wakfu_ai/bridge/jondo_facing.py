"""Source-bound visibility for World's existing defensive NPC orientation.

The compact selector does not certify incoming damage. Its observed actor
positions and visibility can still select fresh native defensive heuristics
after the real end callbacks. NativeOracle validates the current source and
World owns the actual orientation, packet and post-callback reevaluation.
"""
from collections.abc import Mapping


def defensive_facing(request):
    """Return observed current-snapshot evidence, or no claim for partial DTOs."""
    if not isinstance(request, Mapping):
        return None
    source, board = request.get("source"), request.get("board")
    if not isinstance(source, Mapping) or not isinstance(board, Mapping):
        return None
    actor_id, turn_id, revision = (
        source.get(key) for key in ("actorId", "turnId", "stateRevision")
    )
    if (
        any(type(value) is not int for value in (actor_id, turn_id, revision))
        or actor_id == 0
        or turn_id < 0
        or revision < 0
    ):
        return None
    cells, actors = board.get("cells"), board.get("actors")
    if not isinstance(cells, list) or not isinstance(actors, list):
        return None
    coordinates = {}
    for cell in cells:
        if not isinstance(cell, Mapping):
            return None
        identity, xyz = cell.get("id"), cell.get("xyz")
        if (
            type(identity) is not int
            or identity in coordinates
            or not isinstance(xyz, (list, tuple))
            or len(xyz) != 3
            or any(type(value) is not int for value in xyz)
        ):
            return None
        coordinates[identity] = list(xyz)
    visible, positions, seen = [], [], set()
    for actor in actors:
        if not isinstance(actor, Mapping):
            return None
        identity, cell = actor.get("id"), actor.get("cell")
        if (
            type(identity) is not int
            or identity == 0
            or identity in seen
            or type(cell) is not int
            or cell not in coordinates
            or type(actor.get("hidden")) is not bool
        ):
            return None
        seen.add(identity)
        if actor["hidden"]:
            continue
        visible.append(identity)
        positions.append(dict(id=identity, position=list(coordinates[cell])))
    if actor_id not in visible:
        return None
    return dict(
        actorId=actor_id,
        turnId=turn_id,
        stateRevision=revision,
        visibleActorIds=visible,
        actors=positions,
        rivals=[],
    )
