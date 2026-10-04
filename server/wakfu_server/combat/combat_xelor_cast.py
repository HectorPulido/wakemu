"""Complete bare Xelor754 branch with at least4AP and no state6759.

All seven native conditional rules are false in this branch: their predicates
require AP1..3 or passive5352 together with state6759. Effect98124 is the
sole normal direct fire damage, native primary geometry 'point'. Caller must
provide authoritative LOS including dynamic obstacles; static LOS alone is
insufficient for this ranged attack.
"""
from .paths import DATA_ROOT
import json
from copy import deepcopy
from pathlib import Path
from .combat_cast import decode_cast
from .combat_execute import selected_monster
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_effects import direct_damage
from .combat_spells import cast_animation, cast_notification
from .spells import validate_deck

_RULE = json.loads((DATA_ROOT / "xelor754-combat.json").read_text())


def execute_xelor754(
    body,
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    wp_current,
    wp_maximum,
    action_id,
    effect_uid,
    critical_chance,
    caster_running_effects,
    target_running_effects,
    caster_bonuses,
    target_bonuses,
    line_of_sight,
    mitigate
):
    request = decode_cast(body)
    pc = fight._current_owned(owner_id, request["actor_id"])
    if (
        pc.id != character["id"]
        or character["breed"] != 5
        or request["spell_uid"] != ((pc.id << 32) | 754)
    ):
        raise ValueError("Cast is not the owned Xelor754 spell")
    deck = validate_deck(deck_blob, character["breed"], pc.effective_level)
    if 754 not in deck["active"]:
        raise ValueError("Xelor754 is absent from current deck")
    if (
        critical_chance != 0
        or caster_running_effects is None
        or tuple(caster_running_effects)
        or target_running_effects is None
        or tuple(target_running_effects)
        or caster_bonuses is None
        or any(caster_bonuses.values())
        or target_bonuses is None
        or any(target_bonuses.values())
    ):
        raise ValueError("Xelor754 requires explicitly bare caster and target")
    if pc.ap < 4:
        raise ValueError("Xelor754 AP below4 requires conditional rules")
    minimum, maximum, base = _RULE["levels"][pc.effective_level - 1]
    cell = request["target"]
    distance = abs(pc.position[0] - cell[0]) + abs(pc.position[1] - cell[1])
    if cell not in fight.walkable or not minimum <= distance <= maximum:
        raise ValueError("Target is outside native Xelor754 range")
    npc = next(
        (a for a in fight.actors.values() if a.hp > 0 and a.position == cell), None
    )
    if npc is None or npc.controlled or npc.team == pc.team:
        raise ValueError("Target is not a living enemy NPC")
    monster = selected_monster(monsters, npc.id)
    if line_of_sight(pc.position, cell, fight) is not True:
        raise ValueError("Authoritative ranged LOS rejected")
    damage = mitigate(base, 2, pc, npc, fight)
    if type(damage) is not int or not 0 <= damage < (1 << 31):
        raise ValueError("Invalid authoritative damage")
    preview = deepcopy(fight)
    pc = preview.actors[pc.id]
    npc = preview.actors[npc.id]
    previous = len(preview.events)
    preview.spend(owner_id, pc.id, ap=4)
    dealt = preview.apply_damage(pc.id, npc.id, damage)
    packets = [
        (
            12588,
            cast_animation(
                fight.id,
                action_id,
                dict(character, level=pc.effective_level),
                754,
                cell,
            ),
        ),
        (
            12678,
            cast_notification(
                fight.id,
                action_id,
                dict(character, level=pc.effective_level),
                754,
                cell,
            ),
        ),
        (
            12613,
            direct_damage(
                fight.id,
                action_id,
                uid=effect_uid,
                generic_effect=98124,
                element=2,
                caster_id=pc.id,
                target_id=npc.id,
                damage=dealt,
            ),
        ),
    ]
    snapshots = {
        pc.id: actual_actor_stats(
            character, pc, fight.id, wp_current=wp_current, wp_maximum=wp_maximum
        ),
        npc.id: actual_monster_actor_stats(
            monster,
            npc,
            fight.id,
            wp_current=monster["wp"],
            wp_maximum=monster.get("max_wp", monster["wp"]),
            direction=monster.get("direction", 3),
        ),
    }
    preview._event("cast", actor_id=pc.id, target_id=npc.id, spell_id=754, ap_cost=4)
    for identity, copy in preview.actors.items():
        fight.actors[identity].__dict__.update(copy.__dict__)
    for key, value in preview.__dict__.items():
        if key != "actors":
            setattr(fight, key, value)
    return dict(
        damage=dealt,
        packets=packets,
        snapshots=snapshots,
        events=preview.events[previous:],
    )
