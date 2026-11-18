"""Optional native capture-cause qualification for owned training victories.

The ordinary settlement owns membership, original roster and the actual win.
This additional guard distinguishes the original capture spell's native lethal
effect from ordinary damage, an administrative win or an unrelated creature.
The original executor remains responsible for endurance, panic, exhaustion,
range and harness conditions; this module does not simulate those systems.
"""


def policy(selected):
    rows = selected.get("capture_qualification", [])
    if not isinstance(rows, list):
        raise ValueError("Story capture qualification must be a finite list")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "room_order",
                "original_monster_reference",
                "native_effect_reference",
                "evidence",
            }
            or type(row["room_order"]) is not int
            or row["room_order"] <= 0
            or row["room_order"] in seen
            or selected.get("map_id") != 879
            or row["original_monster_reference"] != 3173
            or row["native_effect_reference"] != 117956
            or not isinstance(row["evidence"], str)
            or not row["evidence"].strip()
            or not any(
                step["kind"] == "room_victory"
                and step["reference"] == row["room_order"]
                for step in selected["steps"]
            )
        ):
            raise ValueError("Malformed original Dragoturkey capture qualification")
        seen.add(row["room_order"])
    return rows


def qualified(selected, fight, character_id, original_monsters, room_order):
    """Require native117956 to kill the one original training Dragoturkey."""
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
    if len(targets) != 1:
        return False
    target_id = next(iter(targets))
    owner = fight.actors.get(character_id)
    target = fight.actors.get(target_id)
    if (
        owner is None
        or target is None
        or owner.controlled is not True
        or not owner.owner_id
        or owner.hp <= 0
        or target.hp > 0
        or owner.team == target.team
        or fight.phase != "finished"
        or fight.winner != owner.team
        or target_id in getattr(fight, "native_summon_registrations", {})
        or getattr(target, "native_summon_source", None) is not None
    ):
        return False
    events = tuple(fight.events)
    for index, event in enumerate(events):
        if not (
            event.get("kind") == "kill_hp_minimum_update"
            and event.get("effect_class") == 28
            and event.get("generic_effect") == rule["native_effect_reference"]
            and event.get("source_id") == character_id
            and event.get("target_id") == target_id
            and type(event.get("hp_before")) is int
            and event["hp_before"] > 0
            and event.get("hp") == 0
        ):
            continue
        if any(
            item.get("kind") == "death" and item.get("actor_id") == target_id
            for item in events[index + 1 :]
        ):
            return True
    return False
