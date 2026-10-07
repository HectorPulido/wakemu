"""Generate an offline candidate; never mutate population or infer map scope.

Run with PYTHONPATH=server. Map/region/reference/level must be chosen from
verified native metadata. The emitted plan still requires explicit catalog
inclusion; this tool does not start the server or access its database.
"""
import argparse
import json
from pathlib import Path

from wakfu_server.combat_terrain import map_geometry
from wakfu_server.monster_initial_population import REGIONS
from wakfu_server.monsters import owned_instance, reference
from wakfu_server.planting_cells import surface


def cell(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(type(n) is not int for n in value)
        or not -(2**31) <= value[0] < 2**31
        or not -(2**31) <= value[1] < 2**31
        or not -(2**15) <= value[2] < 2**15
    ):
        raise ValueError("Invalid habitat cell coordinates")
    return tuple(value)


def candidate(
    map_id,
    region_id,
    monster_reference,
    level,
    *,
    excluded=(),
    geometry=None,
    locate=surface,
    minimum_component=2
):
    if type(minimum_component) is not int or not 2 <= minimum_component <= 10000:
        raise ValueError("Invalid minimum habitat component size")
    habitat = REGIONS.get((map_id, region_id))
    if habitat is None or habitat.get("monster_capacity", 0) < 2:
        raise ValueError("Region has no capacity for the initial pair")
    family = reference(monster_reference)["family_id"]
    if family not in {row["family_id"] for row in habitat["monster_families"]}:
        raise ValueError("Monster family is not native to this habitat")
    owned_instance(monster_reference, level, -1, map_id=map_id, x=0, y=0, z=0)
    data = map_geometry(map_id) if geometry is None else geometry
    if data.get("map_id") != map_id:
        raise ValueError("Geometry map identity mismatch")
    cells = {cell(point) for point in data["cells"]}
    edges = {(cell(a), cell(b)) for a, b in data["edges"]}
    excluded = {cell(point) for point in excluded}
    usable = set()
    for point in sorted(cells - excluded):
        try:
            native_region = locate(map_id, *point)["region_id"]
        except ValueError:
            continue
        if native_region == region_id:
            usable.add(point)
    neighbors = {}
    for a, b in edges:
        if a in usable and b in usable and (b, a) in edges:
            neighbors.setdefault(a, set()).add(b)
    rejected = set()
    for a, b in sorted(edges):
        if (
            a in usable
            and b in usable
            and a != b
            and a[2] == b[2]
            and abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            and (b, a) in edges
        ):
            if a in rejected:
                continue
            reached, pending = {a}, [a]
            while pending and len(reached) < minimum_component:
                point = pending.pop()
                for neighbor in neighbors.get(point, ()):
                    if neighbor not in reached:
                        reached.add(neighbor)
                        pending.append(neighbor)
            if len(reached) < minimum_component:
                rejected.update(reached)
                continue
            return {
                "map_id": map_id,
                "instance_id": 0,
                "region_id": region_id,
                "members": [
                    dict(
                        reference=monster_reference, level=level, x=p[0], y=p[1], z=p[2]
                    )
                    for p in (a, b)
                ],
            }
    raise ValueError("No bidirectional adjacent pair in the native habitat")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=int, required=True)
    parser.add_argument("--region", type=int, required=True)
    parser.add_argument("--reference", type=int, required=True)
    parser.add_argument("--level", type=int, required=True)
    parser.add_argument(
        "--excluded-cells",
        type=Path,
        help="JSON list of cells to avoid (entrances, transports, etc.)",
    )
    parser.add_argument(
        "--minimum-component",
        type=int,
        default=24,
        help="Required connected walkable cells (CLI default24)",
    )
    args = parser.parse_args()
    excluded = (
        json.loads(args.excluded_cells.read_text()) if args.excluded_cells else ()
    )
    print(
        json.dumps(
            candidate(
                args.map,
                args.region,
                args.reference,
                args.level,
                excluded=excluded,
                minimum_component=args.minimum_component,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
