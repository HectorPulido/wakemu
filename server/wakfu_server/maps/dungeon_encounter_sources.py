"""Reviewed native encounter kinds override dated/generated source sections.

Native eQM count conflicts require an explicit recipe. This module never guesses
which heading is optional, drops source evidence, or creates a phase actor.
"""
from copy import deepcopy
import hashlib
import json

SCHEMA = "reviewed-native-encounter-source-recipe-v1"
NATIVE_COUNTS = {
    "DUNGEON_2_ROOMS": 2,
    "DUNGEON_3_ROOMS": 3,
    "DUNGEON_4_ROOMS": 4,
    "ULTIMATE_BOSS": 1,
}


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def native_required_count(definition):
    """Use explicit eQM type only; cng/player count and level are not counts."""
    kind = definition.get("native_type", definition.get("type"))
    if (
        definition.get("native_type")
        and definition.get("type")
        and definition["native_type"] != definition["type"]
    ):
        raise ValueError("Conflicting native dungeon type authorities")
    if kind is not None and type(kind) is not str:
        raise ValueError("Malformed native dungeon type")
    return NATIVE_COUNTS.get(kind)


def _proof(record):
    return (
        isinstance(record, dict)
        and type(record.get("authority")) is str
        and record["authority"].strip()
        and isinstance(record.get("source_hashes"), dict)
        and bool(record["source_hashes"])
        and all(
            type(v) is str and len(v) == 64 and set(v) <= set("0123456789abcdef")
            for v in record["source_hashes"].values()
        )
    )


def reconcile(plan, definition, recipe=None):
    """Return a source-preserving draft, or reject an unreviewed count conflict."""
    count = native_required_count(definition)
    rooms = plan.get("rooms", [])
    if recipe is None:
        if rooms and count is not None and len(rooms) != count:
            raise ValueError(
                "Native eQM count conflicts with guide sections; a reviewed typed source recipe is required"
            )
        return deepcopy(plan)
    if (
        recipe.get("schema") != SCHEMA
        or recipe.get("reviewed") is not True
        or count is None
        or type(recipe.get("definition_id")) is not int
        or recipe.get("definition_id") != definition.get("id")
        or recipe.get("source_plan_sha256") != digest(plan)
        or type(recipe.get("native_required_count")) is not int
        or recipe.get("native_required_count") != count
        or not _proof(recipe.get("proof"))
    ):
        raise ValueError("Unqualified native encounter source recipe")
    indexed = {room["order"]: room for room in rooms}
    if len(indexed) != len(rooms) or any(type(k) is not int or k <= 0 for k in indexed):
        raise ValueError("Ambiguous source room orders")
    stages = recipe.get("stages")
    excluded = recipe.get("excluded_sections")
    if (
        not isinstance(stages, list)
        or len(stages) != count
        or not isinstance(excluded, list)
    ):
        raise ValueError("Typed recipe must account for every native encounter")
    selected = []
    for order, stage in enumerate(stages, 1):
        source = stage.get("source_room_order")
        if (
            stage.get("source_kind") != "initial_encounter"
            or type(stage.get("order")) is not int
            or stage.get("order") != order
            or type(source) is not int
            or source not in indexed
        ):
            raise ValueError(
                "Only reviewed initial encounters become progression rooms"
            )
        row = deepcopy(indexed[source])
        row.update(order=order, source_order=source)
        selected.append(row)
    omitted = []
    for section in excluded:
        source = section.get("source_room_order")
        kind = section.get("source_kind")
        if (
            kind
            not in (
                "superseded_guide_encounter_section",
                "noncombat_native_transit_section",
            )
            or type(source) is not int
            or source not in indexed
            or not section.get("reason")
            or not _proof(section.get("proof"))
        ):
            raise ValueError(
                "Excluded source sections require explicit source-kind evidence"
            )
        if kind == "noncombat_native_transit_section":
            regions = section.get("native_region_ids")
            transports = section.get("native_transport_source_ids")
            if (
                section.get("standalone_encounter") is not False
                or not isinstance(regions, list)
                or not regions
                or any(type(n) is not int or n < 0 for n in regions)
                or not isinstance(transports, list)
                or not transports
                or any(type(n) is not int or n <= 0 for n in transports)
            ):
                raise ValueError(
                    "Noncombat transit requires reviewed native regions and transport sources"
                )
        omitted.append(source)
    assigned = [stage["source_room_order"] for stage in stages] + omitted
    if len(set(assigned)) != len(assigned) or set(assigned) != set(indexed):
        raise ValueError("Recipe cannot silently drop or duplicate source sections")
    pool = definition.get("raw_cno")
    if pool is not None:
        if not isinstance(pool, list) or any(
            type(ref) is not int or ref <= 0 for ref in pool
        ):
            raise ValueError("Malformed native initial species pool")
        if any(
            row.get("ref_id") not in pool
            for room in selected
            for row in room["monsters"]
        ):
            raise ValueError(
                "Initial actor lies outside native source pool; phase births are a separate source kind"
            )
    phases = recipe.get("native_phases", [])
    if not isinstance(phases, list):
        raise ValueError("Malformed native phase provenance")
    for phase in phases:
        target = phase.get("encounter_order")
        if (
            phase.get("source_kind") != "native_spawn_only_phase"
            or type(target) is not int
            or not 1 <= target <= count
            or not _proof(phase.get("proof"))
        ):
            raise ValueError(
                "Native phases require an initial encounter and captured source proof"
            )
        refs = {r.get("ref_id") for r in selected[target - 1]["monsters"]}
        initial, born = phase.get("initial_reference"), phase.get("spawn_reference")
        if (
            type(initial) is not int
            or type(born) is not int
            or initial not in refs
            or born <= 0
            or born in refs
        ):
            raise ValueError("A spawn-only phase cannot duplicate an initial actor")
    result = deepcopy(plan)
    result["rooms"] = selected
    result["encounter_source_recipe"] = deepcopy(recipe)
    result["preserved_source_sections"] = deepcopy(rooms)
    result["source_kind_conflict"] = dict(
        native_type=definition.get("native_type", definition.get("type")),
        native_required_count=count,
        parsed_guide_sections=len(rooms),
        excluded_source_orders=omitted,
        excluded_sections_are_optional=False,
        excluded_sections_are_native_phases=False,
    )
    if "document_sha256" in result:
        result["parent_document_sha256"] = result["document_sha256"]
        result["document_sha256"] = digest(
            dict(parent=result["parent_document_sha256"], recipe=recipe, rooms=selected)
        )
    return result
