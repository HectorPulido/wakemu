"""Audited bare unarmed attack: native item2145, request12889/action13509.

The empty weapon slot selects item2145. Live snapshots supply equipment bonuses
and retained effects; the caller supplies the explicit normal cast policy.
The caller confirms authoritative equipment and serializes access to the fight.
"""
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path
from copy import deepcopy
from .combat_execute import selected_monster, adjacent_native_los
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_random_transaction import rollback_external_rng

_RULE = json.loads((DATA_ROOT / "unarmed-combat.json").read_text())


def decode_request(body):
    if len(body) != 27:
        raise ValueError("Invalid native melee request length")
    actor, item, slot, x, y, z = struct.unpack(">qqbiih", body)
    if item != -1 or slot != 15:
        raise ValueError("Only native unarmed slot15 is audited")
    return dict(actor_id=actor, item_uid=item, slot=slot, target=(x, y, z))


def animation(fight_id, action_id, actor_id, level, target):
    """cvO.dp: header, actor, item reference, level, no spell, success, no crit."""
    if not 1 <= level <= 200:
        raise ValueError("Unsupported melee item level")
    return struct.pack(
        ">iiiqihBBB iih",
        fight_id,
        action_id,
        -1,
        actor_id,
        2145,
        level,
        0,
        0,
        0,
        *target,
    )


@rollback_external_rng
def execute_unarmed(
    body,
    character,
    monsters,
    fight,
    owner_id,
    *,
    unarmed,
    wp_current,
    wp_maximum,
    action_id,
    effect_uid,
    critical_chance,
    caster_running_effects,
    target_running_effects,
    caster_bonuses,
    target_bonuses,
    mitigate,
    rng=None,
    prepare_only=False,
    player_characters=None,
    deck_blobs=None,
):
    request = decode_request(body)
    if unarmed is not True:
        raise ValueError("Authoritative empty weapon slot required")
    caster = fight._current_owned(owner_id, request["actor_id"])
    if caster.id != character["id"]:
        raise ValueError("Character does not own this melee actor")
    level = character.get("effective_level", character["level"])
    if (
        type(level) is not int
        or not 1 <= level <= 200
        or caster.effective_level != level
    ):
        raise ValueError("Unsupported or inconsistent effective melee level")
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
        raise ValueError(
            "Legacy unarmed claims require normal policy and no independent bonuses/effect list; live snapshots own those values"
        )
    target = next(
        (
            a
            for a in fight.actors.values()
            if a.position == request["target"] and a.hp > 0
        ),
        None,
    )
    if target is None or target.controlled or target.team == caster.team:
        raise ValueError("Melee requires a living owned enemy NPC")
    monster = selected_monster(monsters, target.id)
    if not adjacent_native_los(
        character["map_id"], caster.position, target.position, fight
    ):
        raise ValueError("Melee is outside native adjacent range/LOS")
    if caster.ap < 3:
        raise ValueError("Insufficient AP for unarmed attack")
    # Native item2145 uses the same private eXt/eYg runtime as weapons.
    # Its damage table is evidence, not a substitute for mastery/resistance,
    # armor absorption and lifecycle events.
    from .combat_server_spell import server_runtime
    from .combat_weapon import weapon_runtime_catalog
    from .combat_effect_dispatch import EffectInvocation
    from .spells import default_deck

    if type(effect_uid) is not int or not 0 < effect_uid < (1 << 63) - 1:
        raise ValueError("Invalid authoritative unarmed running UID")
    from .combat_geometry_snapshot import source_snapshot

    source = source_snapshot(fight)
    preview = deepcopy(fight)
    pc = preview.actors[caster.id]
    npc = preview.actors[target.id]
    previous = len(preview.events)
    if preview.native_effect_uid_next is None:
        preview.native_effect_uid_next = effect_uid
    deck_hex = character.get("builds", {}).get(0, {}).get("deck")
    deck = bytes.fromhex(deck_hex) if deck_hex else default_deck(character)
    factory, adapter = server_runtime(
        character,
        monsters if isinstance(monsters, dict) else {m["id"]: m for m in monsters},
        deck,
        action_id=action_id,
        critical=False,
        rng=rng,
        compiled=weapon_runtime_catalog(),
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    plan = dict(
        actor_id=pc.id,
        item_reference=2145,
        evaluation_level=level,
        target_id=npc.id,
        target=npc.position,
        costs=dict(ap=3, mp=0, wp=0),
        native_retained_container=dict(
            present=True, type=12, id=2145, is_spell=False, protected=None
        ),
    )
    preview.spend(owner_id, pc.id, ap=3)
    dispatcher, effect_packets = factory(preview, plan)
    before_hp = npc.hp
    with preview.effect_resolution():
        outcome = dispatcher.execute(
            EffectInvocation(158454, level, pc.id, npc.id, npc.position)
        )
    dealt = before_hp - npc.hp
    packets = [
        (13509, animation(fight.id, action_id, pc.id, level, npc.position)),
        *effect_packets,
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
    preview._event(
        "melee", actor_id=pc.id, target_id=npc.id, item_reference=2145, ap_cost=3
    )
    if source_snapshot(fight) != source:
        raise ValueError("Fight changed during unarmed attack preparation")
    if prepare_only:
        from .combat_spell_transaction import SpellTransaction

        return SpellTransaction(
            fight=preview,
            plan=plan,
            wp_remaining=pc.effect_stats[4],
            outcomes=(outcome,),
            packets=tuple(packets),
            events=tuple(preview.events[previous:]),
            source_state=source,
            action_id=action_id,
        )
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


def prepare_server_unarmed(*args, **kwargs):
    """Production preview: publication uses the same commit as spells/weapons."""
    return execute_unarmed(*args, **kwargs, prepare_only=True)
