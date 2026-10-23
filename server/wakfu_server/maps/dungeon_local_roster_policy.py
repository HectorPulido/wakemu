"""Draft deterministic local rosters without altering reviewed guide evidence.

Native species pools do not contain official group quantities. Generated slots
are explicit server policy and never become reviewed extraction evidence.
"""
import copy
import re

POLICY_MODE = "generated_native_species_policy"
NON_ORDINARY_PROPERTIES = frozenset((13, 43, 45, 49, 99, 115))
BOSS_PROPERTIES = frozenset((43, 49, 99))


def draft(
    plan,
    definition,
    native_monsters,
    *,
    room_count=None,
    capacity=121,
    generation_target=8,
    generation_targets=None,
    boss_references=(),
    admission_policy=None,
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
    from wakfu_server.dungeon_monster_admission import admitted, current_policy, require

    admission_policy = (
        current_policy() if admission_policy is None else admission_policy
    )
    eligible = {
        ref
        for ref in pool
        if admitted(
            admission_policy,
            ref,
            catalog[ref]["min_level"],
            catalog[ref]["max_level"],
            native=catalog[ref],
        )
    }
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
    targets = {} if generation_targets is None else generation_targets
    if not isinstance(targets, dict) or any(
        type(order) is not int
        or not 1 <= order <= count
        or type(target) is not int
        or not 1 <= target <= capacity
        for order, target in targets.items()
    ):
        raise ValueError("Invalid per-room local generation targets")
    # Boss identity must come from reviewed roles, explicit policy, or a single-
    # species ultimate-boss definition. A species pool is never a room roster.
    bosses = set(boss_references)
    # Species pools include bosses without assigning them to a room. Native
    # BOSS43, ULTIMATE49 and RAID99 are role evidence, unlike reference ordering
    # or level. Keep these actors out of generated ordinary-room slots even
    # when the preparation caller has no separate reviewed boss list.
    native_role_properties = {
        ref: set(catalog[ref]["raw_visual_arrays"]["csc"])
        for ref in pool
        if isinstance(catalog[ref].get("raw_visual_arrays"), dict)
        and isinstance(catalog[ref]["raw_visual_arrays"].get("csc"), list)
        and all(
            type(value) is int for value in catalog[ref]["raw_visual_arrays"]["csc"]
        )
    }
    native_specials = {
        ref
        for ref, properties in native_role_properties.items()
        if properties & NON_ORDINARY_PROPERTIES
    }
    native_bosses = {
        ref
        for ref, properties in native_role_properties.items()
        if properties & BOSS_PROPERTIES and not properties & {45, 115}
    }
    if any(type(ref) is not int or ref not in pool for ref in bosses):
        raise ValueError("Explicit boss identity is outside the native species pool")
    bosses.update(
        row["ref_id"]
        for room in known_rooms
        for row in room.get("monsters", ())
        if row.get("role") == "boss" and row.get("ref_id") in pool
    )
    if not bosses:
        if len(native_bosses) > 1:
            ordinary_families = {
                catalog[ref]["family_id"]
                for ref, properties in native_role_properties.items()
                if not properties & NON_ORDINARY_PROPERTIES
                and type(catalog[ref].get("family_id")) is int
            }
            matching = {
                ref
                for ref in native_bosses
                if type(catalog[ref].get("family_id")) is int
                and catalog[ref]["family_id"] in ordinary_families
            }
            if len(matching) != 1:
                raise ValueError(
                    "Multiple native bosses require explicit final-boss selection"
                )
            bosses.update(matching)
        else:
            bosses.update(native_bosses)
    ultimate = definition.get("type") == "ULTIMATE_BOSS"
    if ultimate and not bosses and len(pool) == 1:
        bosses.update(pool)
    for ref in bosses:
        require(
            admission_policy,
            ref,
            catalog[ref]["min_level"],
            catalog[ref]["max_level"],
            native=catalog[ref],
        )
    for room in known_rooms:
        for row in room.get("monsters", ()):
            ref = row.get("ref_id")
            if ref in catalog:
                require(
                    admission_policy,
                    ref,
                    catalog[ref]["min_level"],
                    catalog[ref]["max_level"],
                    native=catalog[ref],
                )
    regular_pool = [
        ref for ref in pool if ref in eligible and ref not in bosses | native_specials
    ]
    if ultimate and len(bosses) != 1:
        raise ValueError("Ultimate boss requires one resolved boss identity")
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
                candidates = (
                    sorted(bosses)
                    if bosses and order == count and monster.get("role") == "boss"
                    else regular_pool
                )
                if ultimate and order == count:
                    candidates = sorted(bosses)
                if not candidates:
                    raise ValueError(
                        "Unresolved intermediate encounter cannot substitute the final boss"
                    )
                ref = candidates[(order - 1 + index) % len(candidates)]
                monster["ref_id"] = ref
                monster["name"] = catalog[ref].get("name", str(ref))
                # A replacement species is not evidence for a boss identity.
                monster["role"] = "boss" if ref in bosses else "monster"
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
        # Ultimate encounters never receive synthetic padding to eight actors.
        target = 1 if ultimate else targets.get(order, generation_target)
        final_boss_missing = (
            bool(bosses)
            and order == count
            and not any(monster["ref_id"] in bosses for monster in monsters)
        )
        slots = max(0, target - total)
        if final_boss_missing and slots == 0:
            if total >= capacity:
                raise ValueError("Final boss would exceed local combat capacity")
            slots = 1
        for index in range(slots):
            reserve_boss = final_boss_missing and index == slots - 1
            candidates = sorted(bosses) if reserve_boss else regular_pool
            if ultimate and order == count:
                candidates = sorted(bosses)
            if not candidates:
                raise ValueError("Generated encounter has no resolved non-boss species")
            ref = candidates[(order - 1 + len(monsters)) % len(candidates)]
            native = catalog[ref]
            monsters.append(
                {
                    "name": native.get("name", str(ref)),
                    "ref_id": ref,
                    "count": 1,
                    "role": "boss" if ref in bosses else "monster",
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
        "boss_references": sorted(bosses),
        "ultimate_boss_singleton_policy": ultimate,
        "room_count": count,
        "room_count_source": count_source,
        "species_pool": pool,
        "admitted_species_pool": sorted(eligible),
        "excluded_unadmitted_references": sorted(set(pool) - eligible),
        "admission_policy": "native-npc-activation-v1",
        "species_pool_provenance": "guide_verified_native_references"
        if legacy
        else "native_aKU_raw_cno",
        "native_species_pool": [] if legacy else pool,
        "native_definition_id": None if legacy else definition["id"],
        "identity_policy": definition.get("policy_mode", "native_aKU_definition"),
        "original_plan": original,
        "rooms": rooms,
        "policy": "Preserve complete rooms and known quantities; generated fillers exclude resolved bosses except one final boss; ultimate encounters have no synthetic padding.",
    }
