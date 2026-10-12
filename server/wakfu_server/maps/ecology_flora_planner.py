"""Native habitat and terrain planning for administrative flora genesis."""
from collections import Counter
from functools import lru_cache
import random

from .planting import RESOURCES, SEEDS
from .planting_cells import cells, suitability
from .planting_context import region
from .combat_terrain import map_geometry

FLORA_PROFESSIONS = frozenset((64, 71, 72))


@lru_cache(maxsize=2)
def _walkable(map_id):
    return frozenset(tuple(point) for point in map_geometry(map_id)["cells"])


def is_flora(reference):
    """Identify trees, herbs and crops through actual native harvesting actions."""
    definition = RESOURCES.get(reference)
    return bool(
        definition
        and not definition["monster_resource"]
        and any(
            action.get("profession_id") in FLORA_PROFESSIONS
            for stage in definition.get("stage_definitions", ())
            for action in stage.get("actions", ())
        )
    )


def _mature_stage(definition):
    choices = []
    for stage in definition.get("stage_definitions", ()):
        actions = [
            action
            for action in stage.get("actions", ())
            if action.get("profession_id") in FLORA_PROFESSIONS
            and action.get("product_references")
        ]
        if actions and stage["stage_id"] not in (0, 16):
            choices.append((len(actions), stage["stage_id"]))
    return max(choices)[1] if choices else None


def prepare(map_id, region_id):
    """Read native catalogs only; runtime occupation is supplied at commit time."""
    habitat = region(map_id, region_id)
    families = {
        row["family_id"]: row
        for row in habitat["plant_families"]
        if row["family_id"] > 0
    }
    result = dict(
        map_id=map_id,
        region_id=region_id,
        cells=[],
        targets={},
        definitions={},
        warnings=[],
    )
    capacity = max(0, habitat.get("plant_capacity", 0))
    if not capacity or not families:
        return result
    # Ground suitability admits transplanting; it does not identify a habitat's
    # native species. cdK.lVQ carries the native resource references separately
    # from broad ecological plant families and monster families (lVR).
    native_references = {
        reference
        for spawn in habitat.get("native_spawn_definitions", ())
        for reference in spawn.get("lVQ", ())
        if type(reference) is int and reference > 0
    }
    if not native_references:
        result["warnings"].append(
            f"Map {map_id}, region {region_id}: no native flora species declared."
        )
        return result
    seed_refs = {row["resource_reference"] for row in SEEDS.values()}
    for reference, definition in RESOURCES.items():
        if (
            reference not in native_references
            or reference not in seed_refs
            or not is_flora(reference)
        ):
            continue
        stage = _mature_stage(definition)
        if definition["family_id"] in families and stage is not None:
            result["definitions"][reference] = dict(
                family_id=definition["family_id"], stage=stage
            )
    walkable = _walkable(map_id)
    ground_refs = {}
    for (x, y), surfaces in cells(map_id).items():
        for surface in surfaces:
            z = surface["z"]
            if surface["region_id"] != region_id or (x, y, z) not in walkable:
                continue
            ground = surface["ground_id"]
            if ground not in ground_refs:
                ground_refs[ground] = tuple(
                    reference
                    for reference in result["definitions"]
                    if suitability(ground, RESOURCES[reference]) > 0
                )
            if ground_refs[ground]:
                result["cells"].append((x, y, z, ground_refs[ground]))
    supported = {
        result["definitions"][reference]["family_id"]
        for *_, references in result["cells"]
        for reference in references
    }
    for family in sorted(supported):
        row = families[family]
        bounds = [
            row.get(key, 0)
            for key in ("parameter_bKR", "parameter_bKQ")
            if row.get(key, 0) > 0
        ]
        result["targets"][family] = (
            max(1, round(sum(bounds) / len(bounds)))
            if bounds
            else max(1, capacity // len(supported))
        )
    total = sum(result["targets"].values())
    budget = min(
        capacity, max(1, len({(x, y) for x, y, _, _ in result["cells"]}) // 50)
    )
    if total > budget:
        base = int(budget >= len(result["targets"]))
        remaining = budget - base * len(result["targets"])
        shares = {
            family: target * remaining / total
            for family, target in result["targets"].items()
        }
        allocated = {family: base + int(share) for family, share in shares.items()}
        remainder = budget - sum(allocated.values())
        for family in sorted(
            shares, key=lambda family: (shares[family] % 1, family), reverse=True
        )[:remainder]:
            allocated[family] += 1
        result["targets"] = allocated
    if not result["cells"]:
        result["warnings"].append(
            f"Map {map_id}, region {region_id}: no suitable native flora terrain."
        )
    return result


def plan(prepared, existing, occupied):
    """Fill bounded native family targets without replacing established flora."""
    occupied = set(occupied)
    counts = Counter()
    positions = {(x, y) for x, y, _, _ in prepared["cells"]}
    for resource in existing:
        reference = resource["resource_reference"]
        if not is_flora(reference):
            continue
        if (resource["x"], resource["y"]) in positions:
            counts[RESOURCES[reference]["family_id"]] += 1
    rows = []
    candidates = list(prepared["cells"])
    random.shuffle(candidates)
    definitions = prepared["definitions"]
    for x, y, z, references in candidates:
        if (x, y) in occupied:
            continue
        eligible = [
            reference
            for reference in references
            if counts[definitions[reference]["family_id"]]
            < prepared["targets"].get(definitions[reference]["family_id"], 0)
        ]
        if not eligible:
            continue
        families = sorted(
            {definitions[reference]["family_id"] for reference in eligible}
        )
        family = random.choice(families)
        reference = random.choice(
            [
                reference
                for reference in eligible
                if definitions[reference]["family_id"] == family
            ]
        )
        rows.append(
            dict(
                resource_reference=reference,
                stage=definitions[reference]["stage"],
                x=x,
                y=y,
                z=z,
            )
        )
        counts[family] += 1
        occupied.add((x, y))
    warnings = list(prepared["warnings"])
    if any(counts[family] < target for family, target in prepared["targets"].items()):
        warnings.append(
            f"Map {prepared['map_id']}, region {prepared['region_id']}: occupied or unsuitable terrain limits native flora genesis."
        )
    return dict(rows=rows, warnings=warnings)
