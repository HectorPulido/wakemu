"""Optional source-qualified native area cures on an original story roster.

The ordinary victory reducer owns membership, roster and result validation.
These rules additionally require a native lethal effect from an actual declared
area constructor, preserving its identity even after normal area retirement.
"""


def policy(selected):
    rules = selected.get("victory_qualification", [])
    if not isinstance(rules, list):
        raise ValueError("Story victory qualification must be a finite list")
    seen = set()
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or set(rule)
            != {
                "room_order",
                "original_monster_reference",
                "native_effect_reference",
                "native_area_reference",
                "evidence",
            }
            or any(
                type(rule[key]) is not int or rule[key] <= 0
                for key in (
                    "room_order",
                    "original_monster_reference",
                    "native_effect_reference",
                    "native_area_reference",
                )
            )
            or rule["room_order"] in seen
            or not isinstance(rule["evidence"], str)
            or not rule["evidence"].strip()
            or not any(
                step["kind"] == "room_victory"
                and step["reference"] == rule["room_order"]
                for step in selected["steps"]
            )
        ):
            raise ValueError("Malformed native area victory qualification")
        seen.add(rule["room_order"])
    return rules


def qualified(selected, fight, character_id, original_monsters, room_order):
    rule = next(
        (row for row in policy(selected) if row["room_order"] == room_order), None
    )
    if rule is None:
        return True
    targets = {
        row["id"]
        for row in original_monsters
        if row["ref"] == rule["original_monster_reference"]
    }
    owner = fight.actors.get(character_id)
    if (
        not targets
        or owner is None
        or owner.hp <= 0
        or fight.phase != "finished"
        or fight.winner != owner.team
    ):
        return False
    sources = {
        row["uid"]
        for row in getattr(fight, "native_environment_glyph_constructors", ())
        if row.get("reference") == rule["native_area_reference"]
        and row.get("neutral_faw_constructor") is not None
    }
    events = tuple(fight.events)
    for target_id in targets:
        target = fight.actors.get(target_id)
        if target is None or target.hp > 0 or target.team == owner.team:
            return False
        if not any(
            event.get("kind") == "kill_hp_minimum_update"
            and event.get("effect_class") == 28
            and event.get("generic_effect") == rule["native_effect_reference"]
            and event.get("source_id") in sources
            and event.get("target_id") == target_id
            and type(event.get("hp_before")) is int
            and event["hp_before"] > 0
            and event.get("hp") == 0
            and any(
                later.get("kind") == "death" and later.get("actor_id") == target_id
                for later in events[index + 1 :]
            )
            for index, event in enumerate(events)
        ):
            return False
    return True
