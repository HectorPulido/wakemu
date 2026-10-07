"""Build all native habitat plans offline, preserving established plans.

Native ecological habitats define this population policy. Missing geometry,
regular references or connected cells are reported rather than guessed.
No database access or population mutation takes place here.
"""
import argparse
import json
from pathlib import Path

from plan_initial_monster_habitat import candidate
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.monster_initial_population import REGIONS
from wakfu_server.monsters import reference, statistics
from wakfu_server.paths import DATA_ROOT

MARKER_TYPES = {
    "Teleporter",
    "Door",
    "Zaap",
    "Drago",
    "Boat",
    "BattlegroundEntrance",
    "HavenWorldEntrance",
    "DungeonLadderStatue",
    "PositionTrigger",
    "RespawnPoint",
    "GenericTeleporter",
}


def regular_candidates(habitat, growth):
    allowed = {r["family_id"] for r in habitat["monster_families"]}
    result = []
    for family in growth["families"]:
        if family["family_id"] not in allowed:
            continue
        for tier in family["tiers"]:
            for row in tier["candidates"]:
                if row["boss_classification"] != "regular" or row["world_properties"]:
                    continue
                ref = row["reference"]
                monster = reference(ref)
                level = monster["min_level"]
                stats = statistics(ref, level)
                if stats["HP"] > 0 and stats["MP"] > 0:
                    result.append((level, ref))
    return sorted(set(result))


def generate(existing, *, excluded_maps=(), occupancy=None):
    plans = list(existing["plans"])
    keys = {(p["map_id"], p["instance_id"], p["region_id"]) for p in plans}
    growth = json.loads((DATA_ROOT / "monster-growth-catalog.json").read_text())
    markers = {}
    for filename in (
        "native-map-objects.json",
        "native-generic-teleporters.json",
        "native-transport-objects.json",
    ):
        for row in json.loads((DATA_ROOT / filename).read_text()):
            if (
                filename == "native-generic-teleporters.json"
                or row.get("type") in MARKER_TYPES
            ):
                x, y = int(round(row["x"])), int(round(row["y"]))
                protected = markers.setdefault(row["map_id"], set())
                for dx in range(-4, 5):
                    for dy in range(-4 + abs(dx), 5 - abs(dx)):
                        protected.add((x + dx, y + dy))
    outcomes = []
    current_map, current_geometry = None, None
    for (map_id, region_id), habitat in sorted(REGIONS.items()):
        if habitat.get("monster_capacity", 0) < 2:
            continue
        scope = dict(map_id=map_id, region_id=region_id)
        if (map_id, 0, region_id) in keys:
            outcomes.append(dict(scope, status="preserved"))
            continue
        if map_id in excluded_maps:
            outcomes.append(
                dict(scope, status="excluded", reason="Explicit private/interior map")
            )
            continue
        try:
            refs = regular_candidates(habitat, growth)
            if not refs:
                raise ValueError(
                    "No mobile regular reference without special properties"
                )
            if current_map != map_id:
                current_geometry = map_geometry(map_id)
                current_map = map_id
            geometry = current_geometry
            protected = markers.get(map_id, set())
            excluded = {
                tuple(p) for p in geometry["cells"] if tuple(p[:2]) in protected
            }
            excluded.update(tuple(p) for p in (occupancy or {}).get(str(map_id), ()))
            # Earlier selected plans also reserve cells, even across boundaries.
            for plan in plans:
                if plan["map_id"] == map_id:
                    excluded.update(
                        tuple(m[k] for k in ("x", "y", "z")) for m in plan["members"]
                    )
            level, ref = refs[0]
            plan = candidate(
                map_id,
                region_id,
                ref,
                level,
                excluded=excluded,
                geometry=geometry,
                minimum_component=24,
            )
        except (ValueError, FileNotFoundError) as error:
            outcomes.append(dict(scope, status="skipped", reason=str(error)))
        else:
            plans.append(plan)
            keys.add((map_id, 0, region_id))
            outcomes.append(dict(scope, status="generated", reference=ref, level=level))
    return {
        "version": 1,
        "scope": "Automatic native ecological habitats; regular mobile references, verified geometry, reserved-cell exclusions and durable one-time seeding.",
        "plans": plans,
    }, outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing", type=Path, default=DATA_ROOT / "initial-monster-population.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--excluded-maps", type=Path, help="JSON integer map ID list")
    parser.add_argument(
        "--occupied-cells", type=Path, help="JSON map ID to occupied xyz cells"
    )
    args = parser.parse_args()
    excluded = json.loads(args.excluded_maps.read_text()) if args.excluded_maps else [9]
    occupied = (
        json.loads(args.occupied_cells.read_text()) if args.occupied_cells else {}
    )
    catalog, outcomes = generate(
        json.loads(args.existing.read_text()),
        excluded_maps=excluded,
        occupancy=occupied,
    )
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")
    args.report.write_text(json.dumps(outcomes, indent=2) + "\n")
    print(
        json.dumps(
            {
                "plans": len(catalog["plans"]),
                "members": sum(len(p["members"]) for p in catalog["plans"]),
                "outcomes": {
                    status: sum(r["status"] == status for r in outcomes)
                    for status in ("preserved", "generated", "skipped", "excluded")
                },
            }
        )
    )


if __name__ == "__main__":
    main()
