"""Pure, bounded area-uniform monster placement for an unoccupied scope.

The caller owns last-player departure, durable scheduling and fresh SQL CAS.
Every other group's original physical cells remain reserved, making interrupted
or reordered durable chunk delivery safe.
"""
from collections import Counter, deque
from copy import deepcopy
import random
from functools import lru_cache


COHESION_RADIUS = 4


def _point(value):
    cell = tuple(value)
    if len(cell) != 3 or any(type(coordinate) is not int for coordinate in cell):
        raise ValueError("Idle monster placement requires exact native coordinates")
    return cell


def _member_point(member):
    return _point(member[key] for key in ("x", "y", "z"))


@lru_cache(maxsize=4096)
def native_physical_radius(reference):
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    profile = native_actor_catalog()["npc_profiles"].get(str(reference))
    radius = None if profile is None else profile.get("physical_radius")
    if type(radius) is not int or not -128 <= radius <= 127:
        raise ValueError("Missing native monster physical radius")
    return radius


def footprint_cells(member, *, position=None, actor_radii=None):
    """Return the authoritative physical footprint at one exact native height."""
    from wakfu_server.combat_obstacle_condition import footprint

    cell = _member_point(member) if position is None else _point(position)
    try:
        radius = (
            native_physical_radius(member["ref"])
            if actor_radii is None
            else actor_radii[member["ref"]]
        )
    except KeyError as error:
        raise ValueError("Missing native monster physical radius") from error
    return tuple((x, y, cell[2]) for x, y in footprint(cell, radius))


def _compact_cells(
    anchor, members, adjacent, occupied, native, max_search_cells, actor_radii
):
    """Find free native endpoints within a bounded directed walk neighborhood."""
    own_footprint = set(
        footprint_cells(members[0], position=anchor, actor_radii=actor_radii)
    )
    if not own_footprint <= native or own_footprint & occupied:
        return None
    if len(members) == 1:
        return [anchor]
    if len(members) > max_search_cells:
        return None
    queue = deque([anchor])
    visited = {anchor}
    candidates = []
    while queue:
        cell = queue.popleft()
        candidates.append(cell)
        for destination in adjacent.get(cell, ()):
            if (
                destination in visited
                or destination not in native
                or max(abs(destination[0] - anchor[0]), abs(destination[1] - anchor[1]))
                > COHESION_RADIUS
            ):
                continue
            if len(visited) >= max_search_cells:
                break
            visited.add(destination)
            queue.append(destination)
    result = [anchor]
    for member in members[1:]:
        for cell in candidates:
            physical = set(
                footprint_cells(member, position=cell, actor_radii=actor_radii)
            )
            if (
                physical <= native
                and not physical & occupied
                and not physical & own_footprint
            ):
                result.append(cell)
                own_footprint.update(physical)
                break
        else:
            return None
    return result


def plan(
    groups,
    geometry,
    *,
    limit=4096,
    rng=None,
    occupied=(),
    max_attempts=12,
    max_search_cells=128,
    actor_radii=None,
    home_regions=None,
    region_at=None,
):
    """Return ordered position-only group moves without mutating any input.

    Stratify the actual native cell inventory, rather than a rectangular map or
    equal-sized coordinate bins. A group's stratum is proportional to its actor
    count, spreading actor density over usable area without pushing to corners.
    A few bounded uniform retries handle blocked or undersized native patches.
    Each group's endpoints remain compact and natively connected; heights are
    copied from the geometry, never inferred from another cell or flat grid.
    """
    if any(
        type(value) is not int or value <= 0
        for value in (limit, max_attempts, max_search_cells)
    ):
        raise ValueError("Invalid idle monster planning budget")
    if limit > 4096 or max_attempts > 64 or max_search_cells > 1024:
        raise ValueError("Idle monster planning budget exceeds its bound")
    if home_regions is not None and not callable(region_at):
        raise ValueError("Birth-home placement requires exact native territory lookup")
    rng = rng or random.Random()
    cells = sorted({_point(cell) for cell in geometry["cells"]})
    if not cells:
        return []
    native = set(cells)
    adjacent = {}
    for raw_origin, raw_destination in geometry["edges"]:
        origin, destination = _point(raw_origin), _point(raw_destination)
        if origin not in native or destination not in native:
            raise ValueError("Idle placement walk edge leaves native geometry")
        adjacent.setdefault(origin, set()).add(destination)
    adjacent = {
        origin: sorted(destinations) for origin, destinations in adjacent.items()
    }

    living = [group for group in groups if group["status"] != "defeated"]
    candidates = [
        group for group in living if group["status"] == "available" and group["members"]
    ]
    if home_regions is not None:
        candidates = [
            group
            for group in candidates
            if type(home_regions.get(group["group_id"])) is int
            and home_regions[group["group_id"]] > 0
        ]
    rng.shuffle(candidates)
    candidates = candidates[:limit]
    if not candidates:
        return []
    home_cells = {}
    if home_regions is not None:
        wanted = {home_regions[group["group_id"]] for group in candidates}
        home_cells = {home: [] for home in wanted}
        for cell in cells:
            try:
                home = region_at(cell)
            except (ValueError, KeyError):
                continue
            if home in wanted:
                home_cells[home].append(cell)
    home_native = {home: set(points) for home, points in home_cells.items()}
    reserved = {_point(cell) for cell in occupied}
    originals = Counter(
        cell
        for group in living
        for member in group["members"]
        for cell in footprint_cells(member, actor_radii=actor_radii)
    )
    targets = set()
    blocked = set(originals) | reserved

    totals = Counter()
    for group in candidates:
        home = None if home_regions is None else home_regions[group["group_id"]]
        totals[home] += len(group["members"])
    cumulative = Counter()
    moves = []
    for group in candidates:
        expected = group["members"]
        count = len(expected)
        home = None if home_regions is None else home_regions[group["group_id"]]
        available_cells = cells if home_regions is None else home_cells[home]
        available_native = native if home_regions is None else home_native[home]
        if not available_cells:
            continue
        lower = cumulative[home] * len(available_cells) // totals[home]
        cumulative[home] += count
        upper = max(lower + 1, cumulative[home] * len(available_cells) // totals[home])
        upper = min(len(available_cells), upper)
        lower = min(lower, upper - 1)
        own_cells = Counter(
            cell
            for member in expected
            for cell in footprint_cells(member, actor_radii=actor_radii)
        )
        released = {
            cell
            for cell, count in own_cells.items()
            if originals[cell] == count and cell not in reserved and cell not in targets
        }
        blocked.difference_update(released)
        destinations = None
        tried = set()
        for attempt in range(max_attempts):
            # Prefer the group's own area stratum; retries stay uniform over
            # actual native cells when local terrain cannot fit the formation.
            index = (
                rng.randrange(lower, upper)
                if attempt < max_attempts // 2
                else rng.randrange(len(available_cells))
            )
            anchor = available_cells[index]
            if anchor in tried:
                continue
            tried.add(anchor)
            destinations = _compact_cells(
                anchor,
                expected,
                adjacent,
                blocked,
                available_native,
                max_search_cells,
                actor_radii,
            )
            if destinations is not None:
                break
        if destinations is None:
            blocked.update(released)
            continue
        moved = deepcopy(expected)
        for member, destination in zip(moved, destinations):
            member.update(zip(("x", "y", "z"), destination))
        group_targets = {
            cell
            for member in moved
            for cell in footprint_cells(member, actor_radii=actor_radii)
        }
        targets.update(group_targets)
        blocked.update(released)
        blocked.update(group_targets)
        if any(
            _member_point(before) != _member_point(after)
            for before, after in zip(expected, moved)
        ):
            moves.append(
                dict(
                    group_id=group["group_id"],
                    expected_members=deepcopy(expected),
                    moved_members=moved,
                )
            )
    return moves
