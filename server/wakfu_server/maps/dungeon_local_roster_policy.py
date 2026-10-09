"""Draft deterministic local rosters without altering reviewed guide evidence.

Native species pools do not contain official group quantities. Generated slots
are explicit server policy and never become reviewed extraction evidence.
"""
import copy
import re

POLICY_MODE = "generated_native_species_policy"


def draft(
    plan,
    definition,
    native_monsters,
    *,
    room_count=None,
    capacity=121,
    generation_target=8
):
    """Return an optional policy artifact; never an installable configuration."""
    if type(capacity) is not int or not 1 <= capacity <= 121:
        raise ValueError("Local room capacity must be between one and 121")
    if type(generation_target) is not int or not 1 <= generation_target <= capacity:
        raise ValueError("Invalid local generation target")
    if room_count is not None and (
        type(room_count) is not int or not 1 <= room_count <= 100
    ):
        raise ValueError("Invalid explicit local room count")
    if plan.get("definition_id") not in (None, definition["id"]):
        raise ValueError("Conflicting native dungeon identity")
    catalog = {}
    for monster in native_monsters:
        ref = monster.get("ref")
        if type(ref) is not int or ref <= 0 or ref in catalog:
            raise ValueError("Invalid or duplicate native species identity")
        catalog[ref] = monster
    legacy = definition.get("policy_mode") == "local_legacy_map_registry"
    if legacy and (
        definition.get("native_definition_id") is not None
        or definition.get("species_pool_provenance")
        != "guide_verified_native_references"
        or "raw_cno" in definition
    ):
        raise ValueError("Legacy species pool cannot claim native dungeon metadata")
    native_pool = (
        definition.get("local_species_pool", [])
        if legacy
        else definition.get("raw_cno", [])
    )
    if any(type(ref) is not int or ref <= 0 for ref in native_pool):
        raise ValueError("Malformed native dungeon species pool")
    pool = sorted(set(native_pool))
    missing = [ref for ref in pool if ref not in catalog]
    if missing:
        raise ValueError(
            "Native dungeon species pool has unresolved catalog references"
        )
    pool = [
        ref
        for ref in pool
        if type(catalog[ref].get("min_level")) is int
        and type(catalog[ref].get("max_level")) is int
        and 0 < catalog[ref]["min_level"] <= catalog[ref]["max_level"]
    ]
    if not pool:
        raise ValueError("Native dungeon has no usable species grade bounds")
    original = copy.deepcopy(plan)
    known_rooms = tuple(plan.get("rooms", ()))
    if known_rooms:
        count = len(known_rooms)
        count_source = "existing_guide_room_list"
        if room_count is not None and room_count != count:
            raise ValueError("Local room count would overwrite existing guide rooms")
    else:
        native_type = definition.get("type", "")
        match = re.fullmatch(r"DUNGEON_([234])_ROOMS", native_type)
        if room_count is not None:
            count, count_source = room_count, "explicit_local_room_count"
        elif match:
            count, count_source = int(match.group(1)), "native_eQM_room_type"
        else:
            raise ValueError(
                "Explicit local room count required; player count is not room count"
            )
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError("Invalid local room count")
    rooms = []
    for order in range(1, count + 1):
        existing = (
            known_rooms[order - 1]
            if known_rooms
            else {"order": order, "monsters": [], "diagnostics": ["missing_guide_room"]}
        )
        if type(existing["order"]) is not int or existing["order"] != order:
            raise ValueError("Existing guide room orders are not contiguous")
        if not existing.get("diagnostics") and existing.get("monsters"):
            quantities = [row.get("count") for row in existing["monsters"]]
            if (
                any(type(value) is not int or value <= 0 for value in quantities)
                or sum(quantities) > capacity
            ):
                raise ValueError(
                    "Complete guide quantities exceed local combat capacity or are malformed"
                )
            # A complete compiled guide room takes priority, without alteration.
            rooms.append(
                {
                    "order": order,
                    "policy_applied": False,
                    "original_room": copy.deepcopy(existing),
                    "monsters": copy.deepcopy(existing["monsters"]),
                    "generated_fields": [],
                }
            )
            continue
        monsters, generated = [], []
        original_total = 0
        for index, row in enumerate(existing.get("monsters", ())):
            count_value = row.get("count")
            if count_value is not None and (
                type(count_value) is not int or count_value <= 0
            ):
                raise ValueError("Malformed known guide monster count")
            original_total += count_value or 1
        if original_total > capacity:
            raise ValueError("Known guide quantities exceed local combat capacity")
        for index, row in enumerate(existing.get("monsters", ())):
            monster = copy.deepcopy(row)
            ref = monster.get("ref_id")
            if ref is not None and (type(ref) is not int or ref not in catalog):
                raise ValueError("Known guide identity is absent from native catalog")
            if ref is not None and not (
                type(catalog[ref].get("min_level")) is int
                and type(catalog[ref].get("max_level")) is int
                and 0 < catalog[ref]["min_level"] <= catalog[ref]["max_level"]
            ):
                raise ValueError("Known guide species has invalid native grade bounds")
            changes = []
            if ref is None:
                ref = pool[(order - 1 + index) % len(pool)]
                monster["ref_id"] = ref
                monster["name"] = catalog[ref].get("name", str(ref))
                # A replacement species is not evidence for a boss identity.
                monster["role"] = (
                    "boss" if catalog[ref].get("is_boss") is True else "monster"
                )
                changes.extend(("ref_id", "name", "role"))
            if monster.get("count") is None:
                monster["count"] = 1
                changes.append("count")
            monster["native_min_level"] = catalog[ref]["min_level"]
            monster["native_max_level"] = catalog[ref]["max_level"]
            monsters.append(monster)
            if changes:
                generated.append(
                    {
                        "monster_index": index,
                        "fields": changes,
                        "original_monster": copy.deepcopy(row),
                    }
                )
        total = sum(monster["count"] for monster in monsters)
        for index in range(max(0, generation_target - total)):
            ref = pool[(order - 1 + len(monsters)) % len(pool)]
            native = catalog[ref]
            monsters.append(
                {
                    "name": native.get("name", str(ref)),
                    "ref_id": ref,
                    "count": 1,
                    "role": "boss" if native.get("is_boss") is True else "monster",
                    "native_min_level": native["min_level"],
                    "native_max_level": native["max_level"],
                    "guide_min_level": None,
                    "guide_max_level": None,
                }
            )
            generated.append(
                {
                    "monster_index": len(monsters) - 1,
                    "fields": ["local_slot"],
                    "original_monster": None,
                }
            )
        rooms.append(
            {
                "order": order,
                "policy_applied": True,
                "official": False,
                "provenance": POLICY_MODE,
                "original_room": copy.deepcopy(existing),
                "monsters": monsters,
                "generated_fields": generated,
            }
        )
    return {
        "schema_version": 1,
        "artifact_kind": "optional_local_roster_draft",
        "policy_mode": POLICY_MODE,
        "official": False,
        "reviewed_official": False,
        "runtime_imported": False,
        "runtime_ready": False,
        "slug": plan["slug"],
        "definition_id": definition["id"],
        "transport_npc_capacity": capacity,
        "generation_target": generation_target,
        "room_count": count,
        "room_count_source": count_source,
        "species_pool": pool,
        "species_pool_provenance": "guide_verified_native_references"
        if legacy
        else "native_aKU_raw_cno",
        "native_species_pool": [] if legacy else pool,
        "native_definition_id": None if legacy else definition["id"],
        "identity_policy": definition.get("policy_mode", "native_aKU_definition"),
        "original_plan": original,
        "rooms": rooms,
        "policy": "Preserve complete rooms and known quantities; fill unresolved slots deterministically from the native species pool.",
    }
