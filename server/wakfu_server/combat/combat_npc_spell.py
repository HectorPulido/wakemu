"""Generic NPC spell transaction using native ownership and common effects.

Separate entry point: never impersonates a player or grants a class deck.
Unknown mandatory branches reject the entire private preview.
"""
from copy import deepcopy
import random


def owned_spells(fight, monsters):
    from .monsters import native_abilities

    actor = fight.current
    if actor is None or actor.controlled or actor.hp <= 0 or actor.id not in monsters:
        raise ValueError("Missing current owned NPC")
    monster = monsters[actor.id]
    if monster["id"] != actor.id:
        raise ValueError("NPC source identity mismatch")
    spells = {
        entry["spell_id"]: entry["spell_level"]
        for entry in native_abilities(monster["ref"], actor.effective_level)
    }
    from .combat_spell_grant import granted_spells

    for spell, record in granted_spells(fight, actor.id).items():
        if record["uid"] != spell:
            raise ValueError("Unknown native NPC temporary spell UID")
        spells[spell] = record["level"]
    return spells


def prepare_npc_spell(
    fight, action, character, monsters, deck_blob, *, action_id, rng=None
):
    from .combat_server_spell import server_runtime
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_native_spell_casting import definition
    from .combat_cast import _validate_target
    from .combat_spell_usage import consume_usage
    from .combat_spell_transaction import SpellTransaction
    from .combat_geometry_snapshot import source_snapshot
    from .combat_effect_dispatch import EffectInvocation
    from .combat_active_spell import active_spell_scope
    from .combat_cast_facing import mirror_cast_facing
    from .combat_spells import cast_animation, cast_notification

    if type(action_id) is not int or not 0 < action_id < 1 << 31:
        raise ValueError("Invalid NPC action sequence")
    spells = owned_spells(fight, monsters)
    spell = action.get("spellId")
    if (
        action.get("type") != "cast"
        or type(spell) is not int
        or spell not in spells
        or type(action.get("level")) is not int
        or action["level"] != spells[spell]
    ):
        raise ValueError("NPC does not own spell/level")
    if fight.phase != "active":
        raise ValueError("NPC fight is not active")
    actor = fight.current
    if not isinstance(actor.effect_stats, dict) or 4 not in actor.effect_stats:
        raise ValueError("Missing authoritative NPC resources")
    target = action.get("target")
    if (
        not isinstance(target, (list, tuple))
        or len(target) != 3
        or any(type(n) is not int for n in target)
    ):
        raise ValueError("Invalid NPC target coordinates")
    request = dict(actor_id=actor.id, spell_uid=spell, target=tuple(target))
    from .combat_native_spell_casting import catalog as casting_catalog

    compiled = npc_runtime_catalog()
    casting = casting_catalog().get(str(spell))
    if casting is None or not 1 <= spells[spell] <= len(casting["levels"]):
        raise ValueError("Missing native NPC casting table")
    roots = casting["levels"][spells[spell] - 1][2]
    missing = [root for root in roots if str(root) not in compiled.effects]
    if missing:
        raise ValueError(
            "Unsupported native NPC effect roots: " + ",".join(map(str, missing[:8]))
        )
    scoped = {i: source for i, source in monsters.items() if i in fight.actors}
    factory, adapter = server_runtime(
        character,
        scoped,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=random.Random() if rng is None else rng,
        compiled=compiled,
    )
    context = adapter.cast_condition(fight, request)
    rule = definition(spell, spells[spell], context, actor.spell_ap_cost_modifiers)
    from .combat_los import authoritative_visible
    from .combat_obstacle_condition import footprint

    plan = _validate_target(
        request,
        actor,
        fight,
        actor.effect_stats[4],
        rule["costs"],
        rule,
        rule["roots"],
        spells[spell],
        lambda source, destination, state: authoritative_visible(
            monsters[actor.id]["map_id"],
            source,
            destination,
            state,
            blocking_footprints={
                a.id: footprint(a.position, a.physical_radius)
                for a in state.actors.values()
                if a.hp > 0
            },
        ),
        spell,
        context,
    )
    if action.get("targetId") != plan["target_id"]:
        raise ValueError("NPC target identity differs from native cell target")
    # Cheap native validation precedes deep copy/effect dispatch.
    source = source_snapshot(fight)
    preview = deepcopy(fight)
    caster = preview.actors[actor.id]
    start = len(preview.events)
    caster.ap -= rule["costs"]["ap"]
    caster.mp -= rule["costs"]["mp"]
    caster.effect_stats[4] -= rule["costs"]["wp"]
    preview._sync_resources(caster)
    mirror_cast_facing(caster, plan)
    dispatcher, effect_packets = factory(preview, plan)
    with active_spell_scope(preview, spell), preview.effect_resolution():
        outcomes = tuple(
            dispatcher.execute(
                EffectInvocation(
                    reference,
                    spells[spell],
                    caster.id,
                    plan["target_id"],
                    plan["target"],
                )
            )
            for reference in rule["roots"]
        )
    consume_usage(preview, plan)
    preview._event(
        "npc_cast",
        actor_id=caster.id,
        spell_id=spell,
        target_id=plan["target_id"],
        turn_id=fight.turn_id,
    )
    packets = tuple(
        (
            opcode,
            encoder(
                fight.id,
                action_id,
                monsters[actor.id],
                spell,
                plan["target"],
                native_uid=spell,
                native_level=spells[spell],
                critical=False,
            ),
        )
        for opcode, encoder in ((12588, cast_animation), (12678, cast_notification))
    ) + tuple(effect_packets)
    return SpellTransaction(
        preview,
        plan,
        caster.effect_stats[4],
        outcomes,
        packets,
        tuple(preview.events[start:]),
        source,
        action_id,
    )
