"""Optional original-cause guards for story objectives earned by a defeat.

Normal defeat handling still owns roster, membership, terminal result and
withdrawal checks. This guard additionally distinguishes a scripted lethal
native effect from an early ordinary death in the same encounter.
"""


def policy(selected):
    rows = selected.get("defeat_qualification", [])
    if not isinstance(rows, list):
        raise ValueError("Story defeat qualification must be a finite list")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row)
            - {
                "room_order",
                "original_monster_reference",
                "native_effect_reference",
                "native_effect_references",
                "minimum_actor_turn",
                "evidence",
                "cause_kind",
            }
            or not {
                "room_order",
                "original_monster_reference",
                "minimum_actor_turn",
                "evidence",
            }
            <= set(row)
            or ("native_effect_reference" in row) == ("native_effect_references" in row)
            or any(
                type(row[key]) is not int or row[key] <= 0
                for key in (
                    "room_order",
                    "original_monster_reference",
                    "minimum_actor_turn",
                )
            )
            or row.get("cause_kind", "native_kill")
            not in ("native_kill", "native_damage")
            or not isinstance(row["evidence"], str)
            or not row["evidence"].strip()
            or row["room_order"] in seen
            or not any(
                step["kind"] == "room_defeat" and step["reference"] == row["room_order"]
                for step in selected["steps"]
            )
        ):
            raise ValueError("Malformed original-cause story defeat qualification")
        references = row.get(
            "native_effect_references", [row.get("native_effect_reference")]
        )
        if (
            not isinstance(references, list)
            or not references
            or any(type(ref) is not int or ref <= 0 for ref in references)
            or len(references) != len(set(references))
        ):
            raise ValueError(
                "Story defeat requires exact distinct native effect identities"
            )
        seen.add(row["room_order"])
    return rows


def qualified(selected, fight, character_id, original_monsters, room_order):
    """Require the original caster's accepted lethal effect and real death."""
    rule = next(
        (row for row in policy(selected) if row["room_order"] == room_order), None
    )
    if rule is None:
        return True
    original = {
        row["id"]
        for row in original_monsters
        if row["ref"] == rule["original_monster_reference"]
    }
    if len(original) != 1:
        return False
    caster_id = next(iter(original))
    actor = fight.actors.get(character_id)
    caster = fight.actors.get(caster_id)
    if (
        actor is None
        or caster is None
        or actor.hp > 0
        or actor.team == caster.team
        or fight.phase != "finished"
        or fight.winner != caster.team
    ):
        return False
    events = tuple(fight.events)
    references = rule.get(
        "native_effect_references", [rule.get("native_effect_reference")]
    )
    if rule.get("cause_kind", "native_kill") == "native_damage":
        return _qualified_damage(
            fight, events, rule, references, caster_id, character_id
        )
    for index, event in enumerate(events):
        if not (
            event.get("kind") == "kill_hp_minimum_update"
            and event.get("effect_class") == 28
            and event.get("generic_effect") in references
            and event.get("source_id") == caster_id
            and event.get("target_id") == character_id
            and type(event.get("hp_before")) is int
            and event["hp_before"] > 0
            and event.get("hp") == 0
        ):
            continue
        turn = next(
            (
                item
                for item in reversed(events[:index])
                if item.get("kind") == "turn_started"
            ),
            None,
        )
        if not (
            turn is not None
            and turn.get("actor_id") == caster_id
            and type(turn.get("actor_turn")) is int
            and turn["actor_turn"] >= rule["minimum_actor_turn"]
        ):
            continue
        if any(
            item.get("kind") == "death" and item.get("actor_id") == character_id
            for item in events[index + 1 :]
        ):
            return True
    return False


def _qualified_damage(fight, events, rule, references, caster_id, character_id):
    deliveries = getattr(fight, "native_death_event_deliveries", {})
    for index, death in enumerate(events):
        if (
            death.get("kind") != "death"
            or death.get("actor_id") != character_id
            or index == 0
        ):
            continue
        damage = events[index - 1]
        if not (
            damage.get("kind") == "damage"
            and damage.get("source_id") == caster_id
            and damage.get("target_id") == character_id
            and type(damage.get("amount")) is int
            and damage["amount"] > 0
            and damage.get("hp") == 0
        ):
            continue
        witness = deliveries.get(str(death.get("sequence")))
        if not (
            isinstance(witness, dict)
            and witness.get("policy") == "wakemu.owned-ko-and-death-v3"
            and witness.get("actor_id") == character_id
            and witness.get("source_id") == caster_id
            and witness.get("generic_effect") in references
            and witness.get("event_id") == 1013
            and witness.get("channel") == 6
        ):
            continue
        from wakfu_server.combat_damage_healing import DAMAGE_FAMILIES

        if witness.get("effect_class") not in DAMAGE_FAMILIES:
            continue
        turn = next(
            (
                item
                for item in reversed(events[:index])
                if item.get("kind") == "turn_started"
            ),
            None,
        )
        if (
            turn is not None
            and turn.get("actor_id") == caster_id
            and type(turn.get("actor_turn")) is int
            and turn["actor_turn"] >= rule["minimum_actor_turn"]
        ):
            return True
    return False
