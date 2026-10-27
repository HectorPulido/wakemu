"""Bounded native routes returning displaced monsters to their birth territory.

These ordinary movements retain World's existing actor-occupancy guard. No new
wire marker, teleportation or family-based habitat rule is involved.
"""
from collections import OrderedDict, deque
import random
import threading

from .monster_wander import COHESION_RADIUS, _path_result, movement_packet, point


_FIELDS = OrderedDict()
_FIELDS_LOCK = threading.Lock()
MAX_MAPS = 4
MAX_FIELDS_PER_MAP = 16
MAX_FIELD_CELLS = 65536
MAX_HOME_DISTANCE = 1024


def _distance_field(indexed, home, region_at, map_id, max_distance):
    edges = indexed[0]
    key = (map_id, id(edges), None if map_id is not None else id(region_at))
    field_key = (home, max_distance)
    with _FIELDS_LOCK:
        cached = _FIELDS.get(key)
        if cached is not None and field_key in cached[2]:
            _FIELDS.move_to_end(key)
            cached[2].move_to_end(field_key)
            return cached[2][field_key]
    reverse = {}
    cells = set()
    for origin, destination in edges:
        reverse.setdefault(destination, []).append(origin)
        cells.add(origin)
        cells.add(destination)
    distances = {}
    for cell in sorted(cells):
        try:
            belongs = region_at(cell) == home
        except (ValueError, KeyError):
            belongs = False
        if belongs:
            distances[cell] = 0
            if len(distances) >= MAX_FIELD_CELLS:
                break
    queue = deque(distances)
    while queue:
        cell = queue.popleft()
        if distances[cell] >= max_distance:
            continue
        for origin in reverse.get(cell, ()):
            if origin in distances or len(distances) >= MAX_FIELD_CELLS:
                continue
            distances[origin] = distances[cell] + 1
            queue.append(origin)
    with _FIELDS_LOCK:
        # Keep the edge source and callback alive to prevent identity-key reuse.
        if key not in _FIELDS:
            _FIELDS[key] = (edges, region_at, OrderedDict())
        fields = _FIELDS[key][2]
        fields[field_key] = distances
        fields.move_to_end(field_key)
        while len(fields) > MAX_FIELDS_PER_MAP:
            fields.popitem(last=False)
        _FIELDS.move_to_end(key)
        while len(_FIELDS) > MAX_MAPS:
            _FIELDS.popitem(last=False)
    return distances


def homing_path(
    members,
    players,
    indexed,
    home,
    region_at,
    *,
    occupied=(),
    radius=20,
    min_steps=1,
    max_steps=3,
    rng=None,
    destination_allowed=None,
    map_id=None,
    max_distance=MAX_HOME_DISTANCE,
):
    """Return position/packet movement with strictly decreasing home distance.

    Already-home members may wander inside their home. Outside actors take native directed steps
    decreasing their shortest route to home, never crossing another actor's
    occupied cell. Blocked/disconnected groups wait for a later cadence or the
    existing absent-scope redistribution. ``destination_allowed`` validates
    physical surfaces, not home membership of the intermediate return route.
    """
    if not members or not players or radius <= 0:
        return None
    if type(home) is not int or home <= 0 or not callable(region_at):
        raise ValueError("Homing requires an exact persisted birth territory")
    if type(max_steps) is not int or not 1 <= max_steps <= 255:
        raise ValueError("Invalid native homing step budget")
    if type(max_distance) is not int or not 1 <= max_distance <= 1024:
        raise ValueError("Invalid native homing distance budget")
    if not any(
        max(abs(player["x"] - member["x"]), abs(player["y"] - member["y"])) <= radius
        for player in players
        for member in members
    ):
        return None
    distances = _distance_field(indexed, home, region_at, map_id, max_distance)
    if all(distances.get(point(member)) == 0 for member in members):
        return None
    rng = rng or random
    adjacent = indexed[1]
    paths = [[point(member)] for member in members]
    external = set(occupied) | {point(player) for player in players}
    anchor = point(members[0])
    cohesion = max(
        COHESION_RADIUS,
        max(
            max(abs(member["x"] - anchor[0]), abs(member["y"] - anchor[1]))
            for member in members
        ),
    )
    for _ in range(rng.randint(min_steps, max_steps)):
        origins = [path[-1] for path in paths]
        if not any(
            max(abs(player["x"] - cell[0]), abs(player["y"] - cell[1])) <= radius
            for player in players
            for cell in origins
        ):
            break
        blocked = external | {cell for path in paths for cell in path}
        selected = None
        for _attempt in range(4):
            destinations = []
            reserved = set()
            for member, origin in zip(members, origins):
                distance = distances.get(origin)
                choices = []
                if distance is not None:
                    for destination in adjacent.get(origin, ()):
                        after = distances.get(destination)
                        if (
                            after is None
                            or (after != 0 if distance == 0 else after >= distance)
                            or destination in blocked
                            or destination in reserved
                            or (
                                destination_allowed is not None
                                and not destination_allowed(destination)
                            )
                        ):
                            continue
                        try:
                            movement_packet(member["id"], origin, destination)
                        except ValueError:
                            continue
                        choices.append(destination)
                destination = rng.choice(choices) if choices else origin
                destinations.append(destination)
                reserved.add(destination)
            if destinations == origins or len(set(destinations)) < len(set(origins)):
                continue
            actual_anchor = destinations[0]
            if any(
                max(abs(cell[0] - actual_anchor[0]), abs(cell[1] - actual_anchor[1]))
                > cohesion
                for cell in destinations
            ):
                continue
            selected = destinations
            break
        if selected is None:
            break
        for path, destination in zip(paths, selected):
            path.append(destination)
    if not any(path[-1] != path[0] for path in paths):
        return None
    endpoints = [path[-1] for path in paths]
    if len(set(endpoints)) != len(endpoints) or any(
        cell in external for cell in endpoints
    ):
        return None
    return _path_result(members, paths)
