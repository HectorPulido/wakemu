"""Routes for exploration actor interactions using the native directed terrain."""

from collections import deque
import struct

from protocol_codec import DIRECTIONS


class ApproachUnavailable(ValueError):
    """The exploration planner cannot provide a walk to the interaction."""


def approach_path(geometry, start, accepts, *, blocked=(), max_steps=255):
    """Find a shortest valid approach without crossing walls or occupied bodies."""
    start = tuple(start)
    blocked = set(blocked)
    if start not in geometry.cells:
        raise ApproachUnavailable("No puedes acercarte desde esta casilla.")
    pending = deque([start])
    previous = {start: None}
    depth = {start: 0}
    while pending:
        cell = pending.popleft()
        if cell not in blocked and accepts(cell):
            path = []
            while cell is not None:
                path.append(cell)
                cell = previous[cell]
            return tuple(reversed(path))
        if depth[cell] == max_steps:
            continue
        for neighbor in geometry.outgoing.get(cell, ()):
            if neighbor in previous or neighbor in blocked:
                continue
            dz = neighbor[2] - cell[2]
            if not -16 <= dz <= 15:
                continue
            previous[neighbor] = cell
            depth[neighbor] = depth[cell] + 1
            pending.append(neighbor)
    raise ApproachUnavailable("No hay un camino disponible para acercarte.")


def movement_request(path):
    """Pack a native WALK request, preserving directed steps and heights."""
    if not 2 <= len(path) <= 256:
        raise ValueError("Invalid interaction approach length")
    directions = {(dx, dy): index for index, (_, dx, dy) in DIRECTIONS.items()}
    steps = []
    for start, end in zip(path, path[1:]):
        dx, dy, dz = (b - a for a, b in zip(start, end))
        if (dx, dy) not in directions or not -16 <= dz <= 15:
            raise ValueError("Invalid interaction approach step")
        steps.append((directions[dx, dy] << 5) | (dz & 31))
    return struct.pack(">iiihB", 0, *path[0], len(steps)) + bytes(steps)


def combat_approach(geometry, members, target, profiles, *, final_cell_allowed=None):
    """Reserve real monster bodies and return edge-connected attack approaches."""
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_geometry import reachable

    target_member = next(member for member in members if member["id"] == target)
    bodies = set()
    target_body = set()
    for member in members:
        radius = profiles["npc_profiles"][str(member["ref"])]["physical_radius"]
        xy = set(footprint((member["x"], member["y"]), radius))
        body = {
            cell
            for cell in geometry.cells
            if cell[:2] in xy and abs(cell[2] - member["z"]) <= 1
        }
        bodies.update(body)
        if member is target_member:
            target_body = body
    player_radius = profiles["default_actor_radius"]
    blocked = {
        cell
        for cell in geometry.cells
        if any((x, y, cell[2]) in bodies for x, y in footprint(cell, player_radius))
    }
    if not target_body:
        return set(), blocked
    target_surface = min(
        target_body,
        key=lambda cell: (
            abs(cell[0] - target_member["x"]) + abs(cell[1] - target_member["y"]),
            abs(cell[2] - target_member["z"]),
            cell,
        ),
    )
    # A directed drop towards the monster is a walking step, not an attack
    # position. Admission needs mutually reachable terrain after descending.
    component = reachable(
        target_surface, geometry.cells, geometry.outgoing
    ) & reachable(target_surface, geometry.cells, geometry.incoming)
    cells = {
        cell
        for cell in component - blocked
        if abs(cell[2] - target_surface[2]) <= 1
        and any(neighbor in target_body for neighbor in geometry.outgoing.get(cell, ()))
        and (final_cell_allowed is None or final_cell_allowed(cell))
    }
    return cells, blocked
