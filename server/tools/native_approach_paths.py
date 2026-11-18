"""Find reachable native interaction approaches for local gameplay probes.

The native player solver export remains authoritative. Teleporter mask0 uses
bEm's exact X/Y callback; other masks use only the exported bEG/VA approach
positions. Object visual altitude and nearest-Manhattan guesses are not paths.
This module emits no packets and never changes character or quest state.
"""

from collections import deque

from wakfu_server.combat_geometry import prepare_geometry

_PLAYER = dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm")


def _integer(value):
    if type(value) is int:
        return value
    if type(value) is float and value.is_integer():
        return int(value)
    raise ValueError("Native approach has a non-integral coordinate")


def source_path(document, source, start):
    """Return the shortest authentic reachable goal and steps excluding start."""
    if (
        document.get("profile") != _PLAYER
        or not document.get("client_sha256")
        or not document.get("topology_sha256")
        or source.get("map_id") != document.get("map_id")
    ):
        raise ValueError(
            "Native source walking requires the matching original player export"
        )
    geometry = prepare_geometry(document)
    start = tuple(start)
    if start not in geometry.cells:
        raise ValueError("Native source path starts outside exported walking terrain")
    mask = source.get("approach_mask")
    if type(mask) is not int or mask < 0:
        raise ValueError("Native source lacks its exact approach mask")
    if mask == 0:
        x, y = (_integer(source[key]) for key in ("x", "y"))
        candidates = {point for point in geometry.cells if point[:2] == (x, y)}
    else:
        declared = source.get("approach_positions")
        if not isinstance(declared, list) or not declared:
            raise ValueError("Native source mask has no exported approach positions")
        candidates = {
            tuple(_integer(point[key]) for key in ("x", "y", "z")) for point in declared
        }
        candidates &= geometry.cells
    if not candidates:
        raise ValueError("Native source approaches leave this exported walking window")
    previous, pending = {start: None}, deque([start])
    goal = None
    while pending:
        point = pending.popleft()
        if point in candidates:
            goal = point
            break
        for target in geometry.outgoing.get(point, ()):
            if target not in previous:
                previous[target] = point
                pending.append(target)
    if goal is None:
        raise ValueError("No native player path reaches this source approach")
    path, point = [], goal
    while point != start:
        path.append(point)
        point = previous[point]
    path.reverse()
    return dict(goal=goal, path=tuple(path))
