"""Native Wonejo5525 ability7962, a simple earth hit with no side effects.

Ownership comes from aMb.csd[aMk] -> bbo -> blj.du -> bPD.a. Native
bPD uses reference7962 as the spell UID, and tL=-1 selects actor level.
One attack per actor turn is this local AI's policy, not an official AI port.
"""
from wakfu_server import native_catalog as protocol_catalog
import struct
from copy import deepcopy
from .combat_effects import direct_damage
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_los import static_visible
from wakfu_server.monsters import native_abilities


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
    mitigate,
    monsters=None,
    rng=None,
):
    rule = ability(monster)
    if type(effect_uid) is not int or not 0 < effect_uid < (1 << 63) - 1:
        raise ValueError("Invalid authoritative NPC running UID")
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
    # The owned native spell runs through the same eXt dispatcher as player
    # casts. The old direct-HP primitive skipped armor and lifecycle events.
    from .combat_server_spell import server_runtime
    from .combat_effect_dispatch import EffectInvocation
    from wakfu_server.spells import default_deck

    preview = deepcopy(fight)
    npc, pc = preview.actors[actor.id], preview.actors[target.id]
    previous = len(preview.events)
    if preview.native_effect_uid_next is None:
        if type(effect_uid) is not int or not 0 < effect_uid < (1 << 63) - 1:
            raise ValueError("Invalid authoritative NPC running UID")
        preview.native_effect_uid_next = effect_uid
    deck_hex = character.get("builds", {}).get(0, {}).get("deck")
    deck = bytes.fromhex(deck_hex) if deck_hex else default_deck(character)
    factory, adapter = server_runtime(
        character,
        monsters or {monster["id"]: monster},
        deck,
        action_id=action_id,
        critical=False,
        rng=rng,
        compiled=npc_runtime_catalog(),
    )
    plan = dict(
        actor_id=npc.id,
        spell_id=rule["spell_id"],
        evaluation_level=rule["spell_level"],
        target_id=pc.id,
        target=pc.position,
        costs={k: rule[k] for k in ("ap", "mp", "wp")},
    )
    dispatcher, effect_packets = factory(preview, plan)
    before_hp = pc.hp
    with preview.effect_resolution():
        for reference in npc_spell_catalog()["spells"][str(rule["spell_id"])]["levels"][
            rule["spell_level"] - 1
        ][2]:
            dispatcher.execute(
                EffectInvocation(
                    reference,
                    rule["spell_level"],
                    npc.id,
                    pc.id,
                    pc.position,
                    native_explicit_target=True,
                )
            )
    dealt = before_hp - pc.hp
    packets = (
        attack_packets(
            fight.id,
            action_id,
            monster,
            pc.position,
            effect_uid=effect_uid,
            target_id=pc.id,
            damage=0,
        )[:2]
        + effect_packets
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


from functools import lru_cache


@lru_cache(maxsize=1)
def npc_spell_catalog():
    import json
    from wakfu_server.paths import DATA_ROOT

    return protocol_catalog.load(DATA_ROOT / "native-npc-spell-effect-trees.json")


@lru_cache(maxsize=2)
def npc_runtime_catalog(*, imported=True):
    from .combat_server_spell import compiled_runtime_catalog
    from .combat_static_catalogs import CompiledEffects
    from .combat_effect_runtime import _merge_effects

    base = compiled_runtime_catalog()
    document = npc_spell_catalog()
    if not imported and document.get("activation_policy") is not None:
        effects = document.get("baseline_effects")
        if not isinstance(effects, dict):
            raise ValueError("Missing preserved native NPC baseline effects")
        document = {"effects": effects}
    return CompiledEffects(
        _merge_effects(base.source_effects, document), base.source_states
    )
