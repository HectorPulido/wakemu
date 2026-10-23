"""Native eMU no-argument path predicate, without movement or resource mutation.

The default constructor selects Sn/Sp with bpz=-1 and bpy=256. Physical Vy
columns, QI passability and actual mover physics are independent authorities.
This is not a paid movement witness and never invokes Fight._move_actor.
"""
from math import sqrt
from struct import pack, unpack

from .combat_sn_path import NativePhysicalSurface, native_sm_transitions


def _float(value):
    return unpack("!f", pack("!f", value))[0]


class NativeValidPathSearch:
    """Cardinal Sn search with the default Sp flags selected by eMU."""

    def __init__(self, *, column, blocked, contains, height, radius, jump):
        if (
            not all(callable(f) for f in (column, blocked, contains))
            or type(height) is not int
            or height <= 0
            or type(radius) is not int
            or not 0 <= radius <= 127
            or type(jump) is not int
            or not 0 <= jump <= 32767
        ):
            raise ValueError("Missing actual native valid-path movement authority")
        self.column_source = column
        self.blocked = blocked
        self.contains = contains
        self.height, self.radius, self.jump = height, radius, jump

    def __call__(self, source, target):
        for cell in (source, target):
            if (
                not isinstance(cell, (tuple, list))
                or len(cell) != 3
                or any(type(value) is not int for value in cell)
                or any(not -(1 << 31) <= v < (1 << 31) for v in cell[:2])
                or not -32768 <= cell[2] <= 32767
            ):
                raise ValueError("Missing actual native valid-path endpoint")
        source, target = tuple(source), tuple(target)
        columns = {}
        surface_count = 0

        def column(x, y):
            nonlocal surface_count
            if (x, y) not in columns:
                rows = self.column_source(x, y)
                if rows is None:
                    rows = ()
                if not isinstance(rows, (tuple, list)) or any(
                    not isinstance(r, NativePhysicalSurface) for r in rows
                ):
                    raise ValueError("Missing ordered native valid-path Vy column")
                surface_count += len(rows)
                if surface_count > 3072:
                    raise IndexError("Native Sn physical buffer exceeded")
                columns[x, y] = tuple(rows)
            return columns[x, y]

        def index(cell):
            return next(
                (i for i, row in enumerate(column(*cell[:2])) if row.z == cell[2]), None
            )

        def fits(cell):
            rows = column(*cell[:2])
            i = index(cell)
            if i is None or rows[i].bld == -1 or rows[i].through:
                return False
            ceiling = cell[2] + self.height
            return all(
                row.through for row in rows[i + 1 :] if row.z - row.thickness < ceiling
            )

        def flagged(cell, flag):
            return any(row.z == cell[2] and row.blf & flag for row in column(*cell[:2]))

        def blocked(cell, previous):
            # Sn.a(IISIIS): QI.g precedes the physical ladder restrictions.
            value = self.blocked(*cell)
            if type(value) is not bool:
                raise ValueError("Missing native valid-path QI.g boolean")
            if value:
                return True
            ladder = flagged(cell, 8)
            if ladder and (
                not flagged(previous, 16)
                or (cell[0] != previous[0] and cell[1] != previous[1])
            ):
                return True
            if (
                flagged(previous, 8)
                and cell[0] != previous[0]
                and cell[1] != previous[1]
            ):
                return True
            return ladder and cell == target

        def footprint_clear(cell, previous):
            for dx in range(-self.radius, self.radius + 1):
                for dy in range(-self.radius, self.radius + 1):
                    point = (cell[0] + dx, cell[1] + dy, cell[2])
                    prior = (previous[0] + dx, previous[1] + dy, previous[2])
                    if not self.contains(*point[:2]) or blocked(point, prior):
                        return False
            return True

        def heuristic(cell, initial=False):
            dx, dy = abs(cell[0] - target[0]), abs(cell[1] - target[1])
            if initial or not (dx or dy):
                return float(dx + dy)
            return _float(
                _float(dx + dy)
                + _float(_float(sqrt(_float(dx * dx + dy * dy))) * _float(0.01))
            )

        try:
            if (
                index(target) is None
                or not fits(target)
                or not footprint_clear(target, target)
            ):
                return False
            if source == target:
                return (
                    True  # Endpoint passability is checked before zero-length success.
                )
            if index(source) is None or not fits(source):
                return False
            if self.radius and source[2] != target[2]:
                return False  # Default Sp.bpF is false for the large-mover branch.
            # Mutable nodes mirror So; stable insertion preserves equal-score order.
            # Sn.bgn allocates the goal So before allocating any start node.
            # It must retain its reserved slot even when MAX_NODES is reached
            # before a route first discovers the goal.
            nodes = {
                target: dict(g=float("inf"), h=0.0, direction=-1),
                source: dict(
                    g=0.0, h=heuristic(source, True), depth=0, direction=-1, parent=None
                ),
            }
            opened = [source]
            for _ in range(256):
                if not opened:
                    return False
                current = opened.pop(0)
                if current == target:
                    depth = 0
                    cursor = current
                    while cursor is not None:
                        depth += 1
                        cursor = nodes[cursor]["parent"]
                    return depth <= 128  # Sn.c default Sp.bpA includes source.
                old = nodes[current]
                rows = column(*current[:2])
                current_index = index(current)
                surface = rows[current_index]
                for direction, (dx, dy) in enumerate(
                    ((1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    nx, ny = current[0] + dx, current[1] + dy
                    if not -(1 << 31) <= nx < (1 << 31) or not -(1 << 31) <= ny < (
                        1 << 31
                    ):
                        raise ValueError(
                            "Unsupported native valid-path coordinate overflow"
                        )
                    following = column(nx, ny)
                    if not following:
                        continue
                    if self.radius:
                        candidate = (nx, ny, target[2])
                        if not footprint_clear(candidate, current):
                            continue
                        accepted = True
                        for ox in range(-self.radius, self.radius + 1):
                            for oy in range(-self.radius, self.radius + 1):
                                start = (current[0] + ox, current[1] + oy, target[2])
                                end = (nx + ox, ny + oy, target[2])
                                start_index = index(start)
                                if start_index is None or not any(
                                    column(*end[:2])[i].z == target[2]
                                    for i in native_sm_transitions(
                                        start_index,
                                        column(*start[:2]),
                                        column(*end[:2]),
                                        height=self.height,
                                        jump=self.jump,
                                    )
                                ):
                                    accepted = False
                                    break
                            if not accepted:
                                break
                        destinations = (candidate,) if accepted else ()
                    else:
                        if blocked((nx, ny, current[2]), current):
                            continue
                        destinations = tuple(
                            (nx, ny, following[i].z)
                            for i in native_sm_transitions(
                                current_index,
                                rows,
                                following,
                                height=self.height,
                                jump=self.jump,
                            )
                        )
                    for candidate in destinations:
                        if candidate == old["parent"]:
                            continue
                        candidate_surface = column(*candidate[:2])[index(candidate)]
                        if not self.radius:
                            # Default bpJ/bpL/bpK/bpM are false; bpI is true.
                            if (
                                candidate_surface.blf & (8 | 512)
                                or surface.blf & 128
                                or surface.blf & candidate_surface.blf & 64
                                or surface.blf & 512
                                and not candidate_surface.blf & (256 | 512)
                            ):
                                continue
                        cost = old["g"] + 1
                        previous = nodes.get(candidate)
                        if previous is None:
                            if len(nodes) >= 1023:
                                continue
                            previous = dict(
                                g=float("inf"), h=heuristic(candidate), direction=-1
                            )
                            nodes[candidate] = previous
                        if (
                            cost > previous["g"]
                            or cost == previous["g"]
                            and (self.radius or previous["direction"] < direction)
                        ):
                            continue
                        previous.update(
                            g=cost,
                            depth=((old["depth"] + 129) % 256) - 128,
                            direction=direction,
                            parent=current,
                        )
                        if candidate in opened:
                            opened.remove(candidate)
                        score = _float(cost + previous["h"])
                        position = next(
                            (
                                i
                                for i, key in enumerate(opened)
                                if score < _float(nodes[key]["g"] + nodes[key]["h"])
                            ),
                            len(opened),
                        )
                        opened.insert(position, candidate)
            return False  # Native Sp.bpy is 256 popped nodes, including the goal.
        except (IndexError, OverflowError):
            return False  # eMU catches native physical/search buffer exceptions.


def native_default_valid_path(fight, actor, target):
    """Bind the no-argument predicate to the current validated native world."""
    from .combat_qi_fight import current_registry
    from .combat_pointer_qi_registry import registered_population
    from .combat_qi_surface_catalog import native_qi_surface_provenance
    from .combat_sn_path import NativeSnColumns

    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if not isinstance(provenance, dict) or provenance != native_qi_surface_provenance(
        provenance.get("map_id")
    ):
        raise ValueError("Missing matching native valid-path map provenance")
    columns = NativeSnColumns.from_published(provenance["map_id"])
    registry = current_registry(fight)
    # Both complete NativeQIRegistry and canonical pointer registries have
    # already passed current_registry validation. Snapshot once for this pure
    # query; requiring a pointer-only convenience method rejects valid fights.
    terrain, members = registered_population(registry)
    slots = registry.slots
    override = getattr(fight, "native_qi_movement_override", None)
    ignored = getattr(fight, "native_qi_ignored_slots", None)
    if (
        type(override) is not bool
        or not isinstance(ignored, (tuple, list))
        or any(type(byte) is not int or not -128 <= byte <= 127 for byte in ignored)
    ):
        raise ValueError("Missing actual native valid-path movement flags")

    def blocked(x, y, z):
        index = terrain._int32(
            terrain._int32(terrain._int32(y - terrain.y) * terrain.width)
            + terrain._int32(x - terrain.x)
        )
        if not 0 <= index < len(terrain.masks) or terrain.masks[index] & 768:
            return True
        return not override and any(
            byte not in ignored
            and slots[byte] is not None
            and slots[byte]["movement_blocking"]
            for byte in members(x, y)
        )

    return NativeValidPathSearch(
        column=columns.column,
        blocked=blocked,
        contains=terrain.aK,
        height=actor.native_los_height,
        radius=actor.physical_radius,
        jump=actor.native_jump_height,
    )(actor.position, target)
