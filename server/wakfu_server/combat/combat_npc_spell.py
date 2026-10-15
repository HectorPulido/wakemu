"""Generic NPC spell transaction using native ownership and common effects.

Separate entry point: never impersonates a player or grants a class deck.
Unknown mandatory branches reject the entire private preview.
"""
from copy import deepcopy
import random


def owned_spells(fight, monsters, *, character=None, player_characters=None):
    from wakfu_server.monsters import native_abilities

    actor = fight.current
    if actor is None or actor.hp <= 0:
        raise ValueError("Missing current owned NPC")
    from .combat_npc_summon_actions import registered_server_summon_book

    if getattr(actor, "native_summon_source", None) is not None:
        _, spells = registered_server_summon_book(
            fight,
            actor,
            monsters,
            character=character,
            player_characters=player_characters,
        )
    else:
        if actor.controlled or actor.id not in monsters:
            raise ValueError("Missing current owned NPC")
        monster = monsters[actor.id]
        if monster["id"] != actor.id:
            raise ValueError("NPC source identity mismatch")
        spells = {
            entry["spell_id"]: entry["spell_level"]
            for entry in native_abilities(monster["ref"], actor.effective_level)
        }
    from .combat_morph_spellbook import morph_record

    morph = morph_record(fight, actor.id)
    if morph is not None:
        # big.a switches dok() to the temporary fyR; original NPC actions vanish.
        spells = {
            reference: level
            for reference, level in morph["levels"].items()
            if reference not in morph["removed_raw_uids"]
        }
    from .combat_spell_grant import granted_spells

    for spell, record in granted_spells(fight, actor.id).items():
        if record["uid"] != spell:
            raise ValueError("Unknown native NPC temporary spell UID")
        spells[spell] = record["level"]
    return spells


def prepare_npc_spell(
    fight,
    action,
    character,
    monsters,
    deck_blob,
    *,
    action_id,
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    from .combat_server_spell import server_runtime
    from .combat_npc_attack import npc_runtime_catalog
    from .combat_native_spell_casting import definition
    from .combat_cast import _validate_target

    if type(action_id) is not int or not 0 < action_id < 1 << 31:
        raise ValueError("Invalid NPC action sequence")
    spells = owned_spells(
        fight, monsters, character=character, player_characters=player_characters
    )
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
    from .combat_native_spell_casting import native_casting_table

    from .combat_npc_activation import imports_enabled
    from .combat_npc_attack import npc_spell_catalog

    summon_context = None
    if getattr(actor, "native_summon_source", None) is not None:
        from .combat_npc_summon_actions import registered_server_summon_book

        summon_context, _ = registered_server_summon_book(
            fight,
            actor,
            monsters,
            character=character,
            player_characters=player_characters,
        )
    # Registered construction supplies its exact book independently of wild
    # activation. Ordinary NPCs retain their existing import policy.
    imported = summon_context is not None or imports_enabled(
        npc_spell_catalog().get("activation_policy"),
        monsters[actor.id]["ref"],
        actor.effective_level,
        spell,
    )
    map_id = (
        summon_context["map_id"]
        if summon_context is not None
        else monsters[actor.id]["map_id"]
    )
    compiled = npc_runtime_catalog(imported=imported)
    casting, index = native_casting_table(spell, spells[spell])
    roots = casting["levels"][index][2]
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
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    from .combat_npc_area_preflight import npc_cast_condition

    context = npc_cast_condition(
        adapter,
        fight,
        request,
        factory=factory,
        enabled=imported,
    )
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
            map_id,
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
        from .combat_qi_fight import current_registry

        registry = current_registry(fight)
        occupants = [
            registry.slots[slot]["identity"]
            for slot in registry.ordered_U(*request["target"][:2])
            if registry.slots[slot] is not None
        ]
        error = ValueError("NPC target identity differs from native cell target")
        error.native_target_diagnostic = dict(
            requested_target_id=action.get("targetId"),
            native_target_id=plan["target_id"],
            target_cell=list(request["target"]),
            ordered_qi_occupants=occupants,
        )
        raise error
    return prepare_validated_npc_spell(
        fight,
        plan,
        rule,
        # The wire encoders consume only this actual registered actor ID;
        # no independent encounter descriptor, stats or book is synthesized.
        {"id": actor.id} if summon_context is not None else monsters[actor.id],
        factory=factory,
        action_id=action_id,
    )


def prepare_validated_npc_spell(fight, plan, rule, descriptor, *, factory, action_id):
    """Execute an owned, validated NPC cast on a private transaction snapshot."""
    from .combat_spell_usage import consume_usage
    from .combat_spell_transaction import SpellTransaction
    from .combat_geometry_snapshot import source_snapshot
    from .combat_effect_dispatch import EffectInvocation
    from .combat_active_spell import active_spell_scope
    from .combat_cast_facing import (
        finish_mirrored_cast_facing,
        mirror_cast_facing,
    )
    from .combat_spells import cast_animation, cast_notification

    actor = fight.current
    spell, level = plan["spell_id"], plan["evaluation_level"]
    # Cheap native validation precedes deep copy/effect dispatch.
    source = source_snapshot(fight)
    preview = deepcopy(fight)
    caster = preview.actors[actor.id]
    start = len(preview.events)
    if getattr(caster, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import shift_resource_current

        shift_resource_current(preview, caster, 2, rule["costs"]["ap"], subtract=True)
        shift_resource_current(preview, caster, 3, rule["costs"]["mp"], subtract=True)
    else:
        before_ap = caster.ap
        caster.ap -= rule["costs"]["ap"]
        caster.effect_stats[2] = caster.ap
        from .combat_resource_pa_notifications import notify_resource_pa

        notify_resource_pa(preview, caster, 2, before_current=before_ap)
        caster.mp -= rule["costs"]["mp"]
    caster.effect_stats[4] -= rule["costs"]["wp"]
    preview._sync_resources(caster)
    mirror_cast_facing(caster, plan, fight=preview)
    from .combat_ai_cast_history import record_authorized_cast

    record_authorized_cast(preview, caster.id, spell)
    from .combat_normal_execution_origin import (
        normal_execution_origin,
        normal_root_context,
    )

    execution_origin = normal_execution_origin(plan)
    dispatcher, effect_packets = factory(preview, plan)
    with active_spell_scope(preview, spell), preview.effect_resolution():
        outcomes = tuple(
            dispatcher.execute(
                EffectInvocation(
                    reference,
                    level,
                    caster.id,
                    plan["target_id"],
                    plan["target"],
                    native_context_hex=normal_root_context(
                        execution_origin,
                        caster_id=caster.id,
                        spell_id=spell,
                        level=level,
                    ).hex(),
                )
            )
            for reference in rule["roots"]
        )
    finish_mirrored_cast_facing(caster, plan, fight=preview)
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
                descriptor,
                spell,
                plan["target"],
                native_uid=spell,
                native_level=level,
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
