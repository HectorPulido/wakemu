"""Independent local acceptance checks for dungeon room progression and roles."""

from tools.extract_dungeon_family_bosses import native_role


def audit_configuration(config, native_catalog):
    """Audit one frozen config using its deterministic native-minimum spawn level."""
    violations = []
    plan = config.get("compiled_plan", {})
    rooms = plan.get("rooms", [])
    orders = [room.get("order") for room in rooms]
    expected = list(range(1, len(rooms) + 1))
    topology_orders = [
        room.get("order") for room in config.get("topology", {}).get("rooms", [])
    ]
    if not rooms or orders != expected or topology_orders != expected:
        violations.append("room_order_or_topology_invalid")
    if config.get("level_policy", {}).get("mode") != "native_minimum":
        violations.append("spawn_level_policy_unverified")

    final_order = len(rooms)
    scores = []
    for room in rooms:
        order = room.get("order")
        monsters = room.get("monsters")
        if not isinstance(monsters, list) or not monsters:
            violations.append(f"room_{order}_empty")
            scores.append((order, 0))
            continue
        score = 0
        for monster in monsters:
            ref = monster.get("ref_id")
            count = monster.get("count")
            native = native_catalog.get(ref)
            role = native_role(native)
            if role in ("archmonster", "dominant", "unknown"):
                violations.append(f"room_{order}_forbidden_role_{role}_{ref}")
            if native is None:
                violations.append(f"room_{order}_native_metadata_missing_{ref}")
                continue
            if type(count) is not int or count <= 0:
                violations.append(f"room_{order}_invalid_count_{ref}")
                continue
            if (monster.get("native_min_level"), monster.get("native_max_level")) != (
                native.get("min_level"),
                native.get("max_level"),
            ):
                violations.append(f"room_{order}_native_level_drift_{ref}")
            if role == "boss":
                if order != final_order:
                    violations.append(f"room_{order}_boss_before_final_{ref}")
            level = native.get("min_level")
            if type(level) is not int or level <= 0:
                violations.append(f"room_{order}_native_spawn_level_missing_{ref}")
            else:
                score += count * level
        scores.append((order, score))

    if len(rooms) <= 1:
        progression = "no_multiroom_progression"
    else:
        progression = "strictly_increasing_sum_count_times_native_minimum"
        for (previous_order, previous), (order, current) in zip(scores, scores[1:]):
            if current <= previous:
                violations.append(
                    f"room_{order}_threat_not_increasing_after_{previous_order}"
                )
    return {
        "status": "passed" if not violations else "blocked",
        "violations": violations,
        "progression_policy": progression,
        "room_spawn_level_sums": [
            {"order": order, "sum_count_times_native_minimum": score}
            for order, score in scores
        ],
    }
