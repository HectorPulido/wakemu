"""Bounded KO witnesses produced exclusively by ordinary owned hostile casts."""


def knock_out_ally(
    fight,
    character,
    monsters,
    deck,
    *,
    attacker_id,
    ally_id,
    caster_id,
    spell_id,
    spell_level,
    maximum_casts=16,
):
    """Retain an actual player corpse for a later native resurrection preview.

    No HP, state, resource or fdy assignment occurs here. The normal native
    provider owns eligibility, damage, death delivery and transaction commit.
    Failure leaves this private fixture unqualified and must be discarded.
    """
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.combat_controller_registry import current_native_team
    from wakfu_server.combat_global_pv_collections import global_fighter_guards
    from wakfu_server.combat_ordinary_death import registered_ordinary_death
    from wakfu_server.combat_qi_fight import current_registry
    from wakfu_server.monsters import native_abilities

    if type(maximum_casts) is not int or not 1 <= maximum_casts <= 64:
        raise ValueError("Invalid bounded native KO cast budget")
    attacker, ally, caster = (
        fight.actors[i] for i in (attacker_id, ally_id, caster_id)
    )
    if (
        len({attacker_id, ally_id, caster_id}) != 3
        or not ally.controlled
        or getattr(ally, "native_summon_source", None) is not None
        or ally.hp <= 0
        or caster.hp <= 0
        or current_native_team(fight, attacker_id)
        == current_native_team(fight, ally_id)
        or current_native_team(fight, ally_id) != current_native_team(fight, caster_id)
    ):
        raise ValueError(
            "Native KO scene requires hostile attacker and living player ally"
        )
    if attacker.controlled or attacker_id not in monsters:
        raise ValueError("Native KO preparation requires an owned native NPC attacker")
    abilities = native_abilities(monsters[attacker_id]["ref"], attacker.effective_level)
    if not any(
        a["spell_id"] == spell_id and a["spell_level"] == spell_level for a in abilities
    ):
        raise ValueError("KO preparation spell is not natively owned at this level")
    provider = NativeProvider(character, monsters, deck)

    def serialize(actor, state):
        keywords = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **keywords)
        return actual_monster_actor_stats(
            monsters[actor.id], actor, state.id, **keywords
        )

    before_hp, preparations = ally.hp, []
    for _ in range(maximum_casts):
        advance_to(fight, attacker_id)
        ally = fight.actors[ally_id]
        hp = ally.hp
        runtime = RuntimeMessages(fight)
        packets = provider.commit(
            runtime,
            dict(
                type="cast",
                spellId=spell_id,
                level=spell_level,
                target=list(ally.position),
                targetId=ally_id,
            ),
            serialize,
        )
        ally = fight.actors[ally_id]
        if not packets or not 0 <= ally.hp < hp:
            raise ValueError("Owned hostile preparation did not damage the actual ally")
        preparations.append(
            dict(
                spell_id=spell_id,
                spell_level=spell_level,
                hp_before=hp,
                hp_after=ally.hp,
                packets=len(packets),
            )
        )
        if ally.hp == 0:
            # Spell commit leaves death publication to its owning session.
            # Deliver the real registered corpse through that same boundary.
            from wakfu_server.combat_death import death_messages

            delivered = runtime.prepare_delivery(death_messages(runtime, ally_id))
            preparations[-1]["ko_delivery"] = [
                dict(opcode=opcode, payload_hex=payload.hex())
                for opcode, payload in delivered
            ]
            break
        finish_current_turn(fight)
    else:
        raise ValueError("Native KO preparation exhausted its cast budget")
    guards = global_fighter_guards(fight, ally_id)
    registered = registered_ordinary_death(fight, ally)
    writer = getattr(ally, "native_death_status", {}).get("last_writer")
    if (
        guards != dict(baF=False, baG=True, baK=False)
        or not registered
        or writer != "owned.aTS.F.type0"
    ):
        raise ValueError(
            "Owned hostile casts did not deliver reversible native KO: "
            f"guards={guards}, registered_death={registered}, writer={writer}"
        )
    slot = ally.native_obstacle_id
    registry = current_registry(fight)
    if (
        type(slot) is not int
        or not 0 <= slot < len(registry.slots)
        or registry.slots[slot] is None
        or registry.slots[slot]["identity"] != ["actor", ally_id]
        or registry.slots[slot]["position"] != list(ally.position[:2])
    ):
        raise ValueError("Native KO scene lost its retained QI identity")
    advance_to(fight, caster_id)
    return dict(
        schema="native-monster-scenario-v1",
        kind="native_ko_ally",
        attacker_id=attacker_id,
        ally_id=ally_id,
        caster_id=caster_id,
        hp_before=before_hp,
        hp_after=ally.hp,
        preparations=preparations,
        caster_turn_id=fight.turn_id,
    )
