"""Installed native planting surfaces and territories (aIl.U/bMh.dV).

Open local-test policy relaxes species territory and ground suitability,
including ground zero. Native height resolution and occupancy still apply.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .planting_context import region, bootstrap, display_families

GROUNDS = {
    r["ground_id"]: r
    for r in protocol_catalog.load(DATA_ROOT / "planting-grounds.json")
}


@lru_cache(maxsize=8)
def cells(map_id):
    path = DATA_ROOT / "planting-maps" / f"{int(map_id)}.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Native planting surfaces unavailable")
    rows = protocol_catalog.load(path)["cells"]
    result = {}
    for x, y, z, partition, ground, territory in rows:
        result.setdefault((x, y), []).append(
            dict(z=z, ground_id=ground, region_id=territory)
        )
    return result


def surface(map_id, x, y, z):
    match = next((c for c in cells(map_id).get((x, y), []) if c["z"] == z), None)
    if match is None:
        raise ValueError("Unknown native planting height")
    return match


def suitability(ground_id, resource):
    ground = GROUNDS.get(ground_id)
    if ground is None:
        return 0
    # ffY.C: explicit resource override (including zero) precedes family.
    value = ground["resources"].get(str(resource["resource_reference"]))
    if value is None:
        value = ground["families"].get(str(resource["family_id"]), 0)
    return max(0, min(1, value / 100))


def position_context(
    character,
    *,
    monster_counts=None,
    plant_counts=None,
    test_monster_families=(),
    open_test_policy=False,
):
    cell = surface(character["map_id"], character["x"], character["y"], character["z"])
    return region_context(
        character,
        cell["region_id"],
        monster_counts=monster_counts,
        plant_counts=plant_counts,
        test_monster_families=test_monster_families,
        open_test_policy=open_test_policy,
    )


def region_context(
    character,
    region_id,
    *,
    monster_counts=None,
    plant_counts=None,
    test_monster_families=(),
    open_test_policy=False,
):
    """Encode a known native region independently of planting-cell availability."""
    definition = region(character["map_id"], region_id)
    allowed_monsters = set(display_families(definition, "monster"))
    allowed_plants = set(display_families(definition, "plant"))
    return bootstrap(
        character["map_id"],
        region_id,
        monster_counts={
            k: v for k, v in (monster_counts or {}).items() if k in allowed_monsters
        },
        plant_counts={
            k: v for k, v in (plant_counts or {}).items() if k in allowed_plants
        },
        test_monster_families=test_monster_families,
    )


def authorize(store, character, request, seed, resource, *, open_test_policy=False):
    # Request has no z. A unique suitable native surface is mandatory: never
    # guess upstairs/downstairs from the actor's present height.
    candidates = [
        c
        for c in cells(character["map_id"]).get((request["x"], request["y"]), [])
        if open_test_policy
        or (c["ground_id"] and suitability(c["ground_id"], resource) > 0)
    ]
    if open_test_policy and len(candidates) > 1:
        candidates = reachable_surfaces(character, request, candidates)
    if len(candidates) != 1:
        raise ValueError("Absent or ambiguous native planting surface")
    cell = candidates[0]
    if not open_test_policy:
        from .planting_context import authorize_family

        authorize_family(character["map_id"], cell["region_id"], resource)
    with store.connection() as db:
        if db.execute(
            "SELECT 1 FROM mining_vein_slots "
            "WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s AND enabled",
            (character["map_id"], character["instance_id"], request["x"], request["y"]),
        ).fetchone():
            raise ValueError("Planting surface is reserved for a mineral vein")
        if db.execute(
            "SELECT 1 FROM fishing_spot_slots "
            "WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s AND enabled",
            (character["map_id"], character["instance_id"], request["x"], request["y"]),
        ).fetchone():
            raise ValueError("Planting surface is reserved for a fishing spot")
        if db.execute(
            "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
            (character["map_id"], character["instance_id"], request["x"], request["y"]),
        ).fetchone():
            raise ValueError("Planting surface is occupied")
    return cell["z"]


def reachable_surfaces(character, request, candidates):
    from collections import deque
    from .combat_terrain import map_geometry

    geometry = map_geometry(character["map_id"])
    edges = {}
    for start, end in geometry["edges"]:
        edges.setdefault(tuple(start), []).append(tuple(end))
    source = (character["x"], character["y"], character["z"])
    targets = {(request["x"], request["y"], c["z"]): c for c in candidates}
    queue = deque([source])
    seen = {source}
    while queue:
        layer = []
        for _ in range(len(queue)):
            point = queue.popleft()
            if point in targets:
                layer.append(targets[point])
            for neighbor in edges.get(point, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        if layer:
            return layer
    return []
