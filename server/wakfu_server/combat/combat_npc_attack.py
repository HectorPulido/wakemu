"""Native Wonejo5525 ability7962, a simple earth hit with no side effects.

Ownership comes from aMb.csd[aMk] -> bbo -> blj.du -> bPD.a. Native
bPD uses reference7962 as the spell UID, and tL=-1 selects actor level.
One attack per actor turn is this local AI's policy, not an official AI port.
"""
import struct
from copy import deepcopy
from .combat_effects import direct_damage
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_los import static_visible
from .monsters import native_abilities


def ability(monster):
    if monster["ref"] != 5525 or not 1 <= monster["level"] <= 200:
        raise ValueError("No audited attack for this monster reference/level")
    owned = next(
        (
            entry
            for entry in native_abilities(monster["ref"], monster["level"])
            if entry["spell_id"] == 7962
        ),
        None,
    )
    if owned is None or owned["spell_level"] != monster["level"]:
        raise ValueError("Native monster ability ownership/level mismatch")
    return dict(
        spell_id=7962,
        spell_uid=7962,
        spell_level=owned["spell_level"],
        generic_effect=361119,
        element=3,
        damage=5,
        ap=0,
        mp=0,
        wp=0,
        minimum=1,
        maximum=1,
        line_of_sight=True,
        linear=False,
    )


def attack_packets(
    fight_id, action_id, monster, target, *, effect_uid, target_id, damage
):
    rule = ability(monster)
    yy = struct.pack(">qih", rule["spell_uid"], rule["spell_id"], rule["spell_level"])
    header = struct.pack(">iiiq", fight_id, action_id, -1, monster["id"])
    coords = struct.pack(">iih", *target)
    return [
        (12588, header + yy + struct.pack(">iBB", 0, 0, 0) + coords),
        (12678, header + struct.pack(">iBB", rule["spell_id"], 0, 0) + yy + coords),
        (
            12613,
            direct_damage(
                fight_id,
                action_id,
                uid=effect_uid,
                generic_effect=rule["generic_effect"],
                element=3,
                caster_id=monster["id"],
                target_id=target_id,
                damage=damage,
            ),
        ),
    ]


def execute(
    monster,
    character,
    fight,
    target_id,
    *,
    action_id,
    effect_uid,
    player_wp_current,
    player_wp_maximum,
    critical_chance,
    caster_running_effects,
    target_running_effects,
    caster_bonuses,
    target_bonuses,
    mitigate
):
    rule = ability(monster)
    actor = fight.current
    target = fight.actors.get(target_id)
    if (
        actor is None
        or actor.id != monster["id"]
        or actor.controlled
        or actor.hp <= 0
        or target is None
        or not target.controlled
        or target.id != character["id"]
        or target.hp <= 0
        or target.team == actor.team
    ):
        raise ValueError(
            "Attack requires the current owned NPC and living enemy player"
        )
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
        raise ValueError("Only explicitly bare actors have an audited NPC attack")
    if any(
        e["kind"] == "npc_cast"
        and e["actor_id"] == actor.id
        and e["turn_id"] == fight.turn_id
        for e in fight.events
    ):
        raise ValueError("Local AI already attacked this turn")
    distance = abs(actor.position[0] - target.position[0]) + abs(
        actor.position[1] - target.position[1]
    )
    if distance != 1 or not static_visible(
        monster["map_id"], actor.position, target.position
    ):
        raise ValueError("Attack is outside native adjacent range/LOS")
    damage = mitigate(5, 3, actor, target, fight)
    if type(damage) is not int or not 0 <= damage < (1 << 31):
        raise ValueError("Invalid authoritative NPC damage")
    preview = deepcopy(fight)
    npc = preview.actors[actor.id]
    pc = preview.actors[target.id]
    previous = len(preview.events)
    dealt = preview.apply_damage(npc.id, pc.id, damage)
    packets = attack_packets(
        fight.id,
        action_id,
        monster,
        pc.position,
        effect_uid=effect_uid,
        target_id=pc.id,
        damage=dealt,
    )
    snapshots = {
        npc.id: actual_monster_actor_stats(
            monster,
            npc,
            fight.id,
            wp_current=monster["wp"],
            wp_maximum=monster.get("max_wp", monster["wp"]),
            direction=monster.get("direction", 3),
        ),
        pc.id: actual_actor_stats(
            character,
            pc,
            fight.id,
            wp_current=player_wp_current,
            wp_maximum=player_wp_maximum,
        ),
    }
    preview._event(
        "npc_cast",
        actor_id=npc.id,
        target_id=pc.id,
        spell_id=7962,
        turn_id=fight.turn_id,
    )
    for identity, copy in preview.actors.items():
        fight.actors[identity].__dict__.update(copy.__dict__)
    for key, value in preview.__dict__.items():
        if key != "actors":
            setattr(fight, key, value)
    return dict(
        rule=rule,
        damage=dealt,
        packets=packets,
        snapshots=snapshots,
        events=preview.events[previous:],
    )
