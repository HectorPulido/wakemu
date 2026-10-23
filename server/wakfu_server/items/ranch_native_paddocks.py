"""Original fBL/fBp enclosed-region discovery, without assigning owned UIDs."""
from wakfu_server.ranch_native_adjacency import _DIRECTIONS, _groups


def _neighbors(point):
    x, y = point
    return {(x + dx, y + dy) for _, dx, dy in _DIRECTIONS}


def _regions(plane, walls):
    remaining = set(plane) - walls
    regions = []
    while remaining:
        seed = min(remaining)
        pending, interior, enclosed = [seed], {seed}, True
        while pending:
            point = pending.pop()
            remaining.discard(point)
            if point not in plane:
                enclosed = False
                break
            for neighbor in _neighbors(point) - interior - walls:
                interior.add(neighbor)
                pending.append(neighbor)
        if not enclosed:
            # Original fBL stops this component immediately on escape. Consume
            # the rest once here; it cannot produce an enclosed subcomponent.
            pending = list(interior & plane)
            visited = set(pending)
            while pending:
                point = pending.pop()
                remaining.discard(point)
                for neighbor in (_neighbors(point) & plane) - walls - visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
            continue
        boundary = set().union(*(_neighbors(point) for point in interior)) - interior
        # Original n(Set) followed by a(Set,Set): absorb boundary cells whose
        # entire neighborhood already belongs to this region or its boundary.
        for point in sorted(boundary):
            if _neighbors(point) <= interior | boundary:
                boundary.remove(point)
                interior.add(point)
        regions.append((interior, boundary))
    # Original by/bz repeatedly merges a region whose boundary neighborhoods
    # are wholly contained by that region and another region.
    for _ in range(max(0, len(regions) - 1)):
        merged = False
        for i, (inside, edge) in enumerate(regions):
            for j, (other_inside, other_edge) in enumerate(regions):
                if i == j:
                    continue
                union = inside | edge | other_inside | other_edge
                if all(_neighbors(point) <= union for point in edge):
                    regions[j] = (other_inside | inside | edge, other_edge - edge)
                    del regions[i]
                    merged = True
                    break
            if merged:
                break
        if not merged:
            break
    return regions


def enclosed_regions(biome_id, sector_id, rows):
    """Return canonical original fBS geometry; the custody owner assigns UIDs."""
    from wakfu_server.ranch_native_geometry import (
        building_footprint_cells,
        sector_chunks,
    )

    chunks = sector_chunks(biome_id)
    if type(sector_id) is not int or sector_id not in chunks:
        raise ValueError("Unknown native Ranch paddock sector")
    plane = {
        (cx * 18 + x, cy * 18 + y)
        for cx, cy in chunks[sector_id]
        for x in range(18)
        for y in range(18)
    }
    groups, walls, seen = _groups(), {}, set()
    for row in rows:
        if not isinstance(row, dict) or row.get("sector_id") != sector_id:
            raise ValueError("Ranch paddock snapshot contains another sector")
        uid = row.get("uid")
        if type(uid) is not int or uid <= 0 or uid in seen:
            raise ValueError("Invalid owned Ranch paddock building UID")
        seen.add(uid)
        group = groups.get(row.get("building_ref"))
        cells = set(building_footprint_cells(biome_id, [row]))
        if not cells <= plane:
            raise ValueError("Owned Ranch paddock building leaves its native sector")
        if group is not None:
            walls.setdefault(group, set()).update(cells)
    result = []
    for group, occupied in sorted(walls.items()):
        for interior, boundary in _regions(plane, occupied):
            result.append(
                {
                    "sector_id": sector_id,
                    "group": group,
                    "interior": tuple(sorted(interior)),
                    "boundary": tuple(sorted(boundary)),
                }
            )
    return tuple(
        sorted(result, key=lambda row: (row["group"], row["interior"], row["boundary"]))
    )
