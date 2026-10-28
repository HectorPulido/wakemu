"""Deterministic native habitat proposals, without population mutations.

The caller must revalidate counts and occupied cells under its transaction
before registering these proposals. Catalog readers use the process-pinned
published native release, including its ordinary geometry cache semantics.
"""


from functools import lru_cache
from types import MappingProxyType


def prepare(map_id, region_id):
    """Prewarm immutable native habitat data outside world gameplay fences."""
    from wakfu_server import native_catalog

    if any(
        type(value) is not int or not 0 < value < 2**31
        for value in (map_id, region_id)
    ):
        raise ValueError("Invalid administrative population scope")
    return _prepare(native_catalog.release(), map_id, region_id)


@lru_cache(maxsize=64)
def _prepare(revision, map_id, region_id):
    from .monster_initial_population import REGIONS
    from .monster_maturation import CATALOG
    from .monsters import owned_instance, reference
    from .combat_terrain import map_geometry
    from .planting_cells import cells

    region = REGIONS.get((map_id, region_id))
    if region is None or region.get("monster_capacity", 0) <= 0:
        from .ecology_admin_errors import EcologyAdminFailure

        raise EcologyAdminFailure("no_monster_habitat")
    allowed = {row["family_id"] for row in region["monster_families"]}
    candidates, all_candidates = {}, {}
    for family in CATALOG["families"]:
        if family["family_id"] not in allowed:
            continue
        for tier in sorted(family["tiers"], key=lambda row: row["rank"]):
            ordinary = sorted(
                (
                    row
                    for row in tier["candidates"]
                    if row["boss_classification"] == "regular"
                ),
                key=lambda row: row["reference"],
            )
            valid = []
            for row in ordinary:
                try:
                    name = reference(row["reference"]).get("name")
                    if (
                        not isinstance(name, str)
                        or not name
                        or len(name.encode("utf-8")) > 65535
                    ):
                        continue
                    owned_instance(
                        row["reference"],
                        row["min_level"],
                        -1,
                        map_id=map_id,
                        x=0,
                        y=0,
                        z=0,
                    )
                except (ValueError, UnicodeEncodeError):
                    continue
                valid.append(
                    MappingProxyType(
                        dict(
                            reference=row["reference"],
                            min_level=row["min_level"],
                        )
                    )
                )
            if valid:
                candidates.setdefault(family["family_id"], tuple(valid))
                all_candidates.setdefault(family["family_id"], []).extend(valid)
    surfaces = (
        {
            (x, y, row["z"])
            for (x, y), rows in cells(map_id).items()
            for row in rows
            if row["region_id"] == region_id
        }
        if candidates
        else set()
    )
    geometry = map_geometry(map_id) if candidates else {}
    positions = (
        tuple(sorted(surfaces.intersection(tuple(row) for row in geometry["cells"])))
        if candidates
        else ()
    )
    native_cells = set(positions)
    edges = {(tuple(start), tuple(end)) for start, end in geometry.get("edges", ())}
    adjacency = {position: [] for position in positions}
    for start, end in edges:
        if start in native_cells and end in native_cells and (end, start) in edges:
            adjacency[start].append(end)
    adjacency = MappingProxyType(
        {
            position: tuple(sorted(neighbors))
            for position, neighbors in adjacency.items()
        }
    )
    # A bounded spatial sample keeps live planning independent of map size.
    connected = [position for position in positions if adjacency[position]]
    step = max(1, (len(connected) + 255) // 256)
    anchors = tuple(connected[::step])
    return MappingProxyType(
        dict(
            revision=revision,
            map_id=map_id,
            region_id=region_id,
            capacity=region["monster_capacity"],
            candidates=MappingProxyType(candidates),
            cells=positions,
            all_candidates=MappingProxyType(
                {family: tuple(rows) for family, rows in all_candidates.items()}
            ),
            adjacency=adjacency,
            anchors=anchors,
        )
    )


def plan(map_id, region_id, counts, occupied, *, target, capacity, prepared=None):
    """Fill regional family quotas up to a total initial-population target.

    ``counts`` contains every living regional family, including foreign ones.
    ``occupied`` contains map-wide blocked XYZ cells (actors and resources).
    Unsupported native families receive no invented reference. Bosses and
    archmonsters are excluded from administrative initial population.
    """
    from .monster_initial_population import REGIONS

    if (
        type(map_id) is not int
        or not 0 < map_id < 2**31
        or type(region_id) is not int
        or not 0 < region_id < 2**31
        or type(target) is not int
        or target < 0
        or type(capacity) is not int
        or capacity < 0
        or not isinstance(counts, dict)
        or any(
            type(family) is not int or type(number) is not int or number < 0
            for family, number in counts.items()
        )
    ):
        raise ValueError("Invalid administrative population scope")
    blocked = set()
    for position in occupied:
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 3
            or any(type(value) is not int for value in position)
        ):
            raise ValueError("Invalid administrative occupied cell")
        blocked.add(tuple(position))
    region = REGIONS.get((map_id, region_id))
    if region is None or region.get("monster_capacity", 0) <= 0:
        raise ValueError("No native monster habitat for administrative population")
    limit = min(capacity, region["monster_capacity"])
    room = max(0, limit - sum(counts.values()))
    if not room or not target:
        return []
    native = prepare(map_id, region_id) if prepared is None else prepared
    if (native["map_id"], native["region_id"]) != (map_id, region_id):
        raise ValueError("Prepared administrative habitat belongs to another region")
    from wakfu_server import native_catalog

    if native["revision"] != native_catalog.release():
        raise ValueError("Prepared administrative habitat catalog is stale")
    candidates = native["candidates"]
    if not candidates:
        return []
    families = sorted(candidates)
    quotient, remainder = divmod(min(target, limit), len(families))
    deficits = {
        family: max(0, quotient + (index < remainder) - counts.get(family, 0))
        for index, family in enumerate(families)
    }
    needed = min(room, sum(deficits.values()))
    if not needed:
        return []
    available = [position for position in native["cells"] if position not in blocked]
    proposals = []
    positions = iter(available[:needed])
    # Round-robin allocation avoids starving later families when capacity or
    # free terrain cannot accommodate the full requested initial population.
    while len(proposals) < min(needed, len(available)):
        for family in families:
            if not deficits[family]:
                continue
            if len(proposals) >= min(needed, len(available)):
                break
            row = candidates[family][0]
            x, y, z = next(positions)
            proposals.append(
                dict(
                    reference=row["reference"],
                    level=row["min_level"],
                    x=x,
                    y=y,
                    z=z,
                )
            )
            deficits[family] -= 1
    return proposals


def plan_groups(
    map_id,
    region_id,
    counts,
    occupied,
    *,
    group_counts,
    target_groups=10,
    min_members=2,
    max_members=5,
    capacity,
    max_groups,
    member_budget,
    prepared=None,
    rng=None,
):
    """Fill missing native family group quotas using connected nearby cells.

    ``group_counts`` is living regional groups by family, including foreign
    groups. ``max_groups`` and ``member_budget`` are remaining map capacities.
    """
    import random
    from collections import deque
    from wakfu_server import native_catalog

    integers = (
        target_groups,
        min_members,
        max_members,
        capacity,
        max_groups,
        member_budget,
    )
    if (
        any(type(value) is not int or value < 0 for value in integers)
        or not 2 <= min_members <= max_members <= 8
        or not isinstance(counts, dict)
        or not isinstance(group_counts, dict)
        or any(
            type(k) is not int or type(v) is not int or v < 0
            for values in (counts, group_counts)
            for k, v in values.items()
        )
    ):
        raise ValueError("Invalid administrative group population policy")
    blocked = set()
    for point in occupied:
        if (
            not isinstance(point, (tuple, list))
            or len(point) != 3
            or any(type(v) is not int for v in point)
        ):
            raise ValueError("Invalid administrative occupied cell")
        blocked.add(tuple(point))
    native = prepare(map_id, region_id) if prepared is None else prepared
    if (native["map_id"], native["region_id"], native["revision"]) != (
        map_id,
        region_id,
        native_catalog.release(),
    ):
        raise ValueError("Prepared administrative habitat is stale or foreign")
    candidates = native["all_candidates"]
    if not candidates:
        return []
    slots = min(max_groups, max(0, target_groups - sum(group_counts.values())))
    room = min(
        member_budget, max(0, min(capacity, native["capacity"]) - sum(counts.values()))
    )
    families = sorted(candidates)
    quota, extra = divmod(target_groups, len(families))
    deficits = {
        family: max(0, quota + (index < extra) - group_counts.get(family, 0))
        for index, family in enumerate(families)
    }
    if slots <= 0 or room < min_members or not any(deficits.values()):
        return []
    rng = random.SystemRandom() if rng is None else rng
    anchors = list(native["anchors"])
    rng.shuffle(anchors)
    previous = []
    groups = []
    adjacency = native["adjacency"]
    while len(groups) < slots and room >= min_members and any(deficits.values()):
        family = max(families, key=lambda value: deficits[value])
        remaining_groups = min(
            slots - len(groups),
            sum(deficits.values()),
            room // min_members,
        )
        upper = min(max_members, room - min_members * (remaining_groups - 1))
        desired = rng.randint(min_members, upper)
        if previous:
            anchors.sort(
                key=lambda point: min(
                    (point[0] - other[0]) ** 2 + (point[1] - other[1]) ** 2
                    for other in previous
                ),
                reverse=True,
            )
        cluster = None
        for anchor in anchors:
            if anchor in blocked:
                continue
            queue, seen, points = deque([anchor]), {anchor}, []
            while queue and len(points) < desired and len(seen) <= 64:
                point = queue.popleft()
                if point in blocked:
                    continue
                points.append(point)
                neighbors = list(adjacency.get(point, ()))
                rng.shuffle(neighbors)
                for neighbor in neighbors:
                    if neighbor not in seen and neighbor not in blocked:
                        seen.add(neighbor)
                        queue.append(neighbor)
            if len(points) >= min_members:
                cluster = points
                previous.append(anchor)
                break
        if cluster is None:
            break
        forms = list(candidates[family])
        rng.shuffle(forms)
        members = []
        for index, (x, y, z) in enumerate(cluster):
            row = forms[index % len(forms)]
            members.append(
                dict(reference=row["reference"], level=row["min_level"], x=x, y=y, z=z)
            )
        groups.append(members)
        blocked.update(cluster)
        room -= len(members)
        deficits[family] -= 1
    return groups
