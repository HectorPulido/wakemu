"""Replayable native preparation scenarios for offline monster validation.

This module never invents hit points, resource pools, states or target legality.
The wounded-ally scenario requires a normal opposing NPC cast and turn changes.
"""


def finish_current_turn(fight):
    """Use the normal owner or server lifecycle entry for the actual actor."""
    actor = fight.current
    if actor is None:
        raise ValueError("Scenario has no active actor turn")
    if getattr(actor, "controlled", True):
        fight.end_turn(
            getattr(actor, "owner_id", 3),
            actor.id,
            getattr(actor, "turn_count", fight.turn_id),
        )
    else:
        fight.end_server_turn(actor.id, fight.turn_id)


def advance_to(fight, actor_id):
    """Advance real lifecycle boundaries with a finite initiative-cycle bound."""
    for _ in range(len(fight.actors) * 2 + 1):
        if fight.current is not None and fight.current.id == actor_id:
            return
        if fight.current is None:
            break
        finish_current_turn(fight)
    raise ValueError("Scenario could not establish requested native actor turn")


def wound_ally(
    fight,
    character,
    monsters,
    deck,
    *,
    attacker_id,
    ally_id,
    caster_id,
    spell_id,
    spell_level
):
    """Commit one ordinary hostile spell, then establish the healer's turn."""
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats

    attacker, ally = fight.actors[attacker_id], fight.actors[ally_id]
    if attacker.team == ally.team or ally.team != fight.actors[caster_id].team:
        raise ValueError(
            "Wound scenario requires hostile attacker and allied recipient"
        )
    advance_to(fight, attacker_id)
    before_hp = ally.hp
    provider = NativeProvider(character, monsters, deck)
    action = dict(
        type="cast",
        spellId=spell_id,
        level=spell_level,
        target=list(ally.position),
        targetId=ally_id,
    )

    def serialize(actor, state):
        keywords = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **keywords)
        return actual_monster_actor_stats(
            monsters[actor.id], actor, state.id, **keywords
        )

    packets = provider.commit(RuntimeMessages(fight), action, serialize)
    if not packets or not 0 < ally.hp < before_hp:
        raise ValueError("Scenario hostile spell failed to wound a living ally")
    after_hp = ally.hp
    advance_to(fight, caster_id)
    return dict(
        schema="native-monster-scenario-v1",
        kind="wounded_ally",
        attacker_id=attacker_id,
        ally_id=ally_id,
        caster_id=caster_id,
        spell_id=spell_id,
        spell_level=spell_level,
        target=list(ally.position),
        hp_before=before_hp,
        hp_after=after_hp,
        preparation_packets=len(packets),
        caster_turn_id=fight.turn_id,
    )
