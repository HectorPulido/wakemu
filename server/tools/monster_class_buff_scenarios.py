"""Legitimate class-owned resource preparation for native monster scenarios."""
import struct


CLASS_BUFF_RECIPES = {
    "ap": dict(
        kind="class_buff",
        character_breed=5,
        character_level=3,
        spell_id=2839,
        spell_level=3,
        caster_team=0,
        statistic=2,
    ),
    "mp": dict(
        kind="class_buff",
        character_breed=3,
        character_level=3,
        spell_id=6324,
        spell_level=3,
        caster_team=0,
        statistic=3,
    ),
}


def encounter_buff_recipe(reference, spell):
    """Describe an audited native encounter prerequisite without granting it."""
    if (reference, spell) != (2778, 4019):
        return None
    return dict(
        CLASS_BUFF_RECIPES["ap"],
        opponent=dict(reference=4371, level=68, team=1),
        required_opponent_states=[2324],
    )


def scenario_constructor_references(reference, spell):
    """Return dependency constructors separately from spell activation scope."""
    recipe = encounter_buff_recipe(reference, spell)
    return () if recipe is None else (recipe["opponent"]["reference"],)


def buff_ally(fight, character, monsters, deck, *, ally_id, recipe, line_of_sight):
    """Pay an owned class spell, commit its effects, then take the ally's turn.

    The caller constructs an ordinary class character/deck and supplies the
    verified native LOS callback. No characteristic, state, cost or ownership
    is injected by this preparation helper.
    """
    from wakfu_server.spells import validate_deck
    from wakfu_server.combat_server_spell import (
        prepare_server_spell,
        prepare_server_turn_start,
        prepare_server_turn_end,
        server_runtime,
        prepare_server_initialization,
    )
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_area_boundary import adopt_fight
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats

    if recipe not in CLASS_BUFF_RECIPES.values() or not callable(line_of_sight):
        raise ValueError("Missing verified class buff recipe or native LOS authority")
    if (
        character["breed"] != recipe["character_breed"]
        or character["level"] != recipe["character_level"]
    ):
        raise ValueError("Class buff recipe requires its actual unlocked owner")
    owned = validate_deck(deck, character["breed"], character["level"])
    if recipe["spell_id"] not in owned["active"]:
        raise ValueError("Class buff spell is missing from its actual owned deck")
    caster = fight.actors[character["id"]]
    ally = fight.actors[ally_id]
    if (
        caster.team != recipe["caster_team"]
        or ally.team != caster.team
        or caster.id == ally.id
        or not caster.controlled
    ):
        raise ValueError(
            "Class buff recipe requires a distinct actual allied recipient"
        )
    runtime = RuntimeMessages(
        fight,
        turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
            character, monsters, preview, deck, **boundary
        ),
        turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
            character, monsters, preview, deck, **boundary
        ),
        expiration_runtime_factory=lambda *, action_id: server_runtime(
            character,
            monsters,
            deck,
            action_id=action_id,
            critical=False,
        )[0],
    )
    initialization_packets = 0
    if not fight.native_start_event_delivered:
        initialized, initialization = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=runtime.action_id + 1,
            fight_start=True,
        )
        adopt_fight(fight, initialized)
        runtime.action_id += 1  # The actual initialization transaction above.
        initialization_packets = len(initialization)
    lifecycle_packets = len(runtime.turn_started())
    lifecycle_packets += advance_buff_runtime(runtime, caster.id)
    stat = recipe["statistic"]
    before = fight.actors[ally_id].effect_stats[stat]
    caster_before = {
        key: fight.actors[caster.id].effect_stats[key] for key in (2, 3, 4)
    }
    body = struct.pack(
        ">qqiih",
        caster.id,
        (caster.id << 32) | recipe["spell_id"],
        *fight.actors[ally_id].position
    )
    transaction = prepare_server_spell(
        body,
        character,
        monsters,
        fight,
        character["account_id"],
        deck,
        action_id=runtime.action_id + 1,
        line_of_sight=line_of_sight,
        critical=False,
    )

    def serialize(actor, state):
        keywords = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        if actor.id in getattr(state, "native_summon_registrations", {}):
            from wakfu_server.combat_summon_stats import registered_summon_stats

            return registered_summon_stats(actor, state, character["map_id"])
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **keywords)
        return actual_monster_actor_stats(
            monsters[actor.id], actor, state.id, **keywords
        )

    packets = commit_spell_transaction(runtime, transaction, stats_serializer=serialize)
    adopt_fight(fight, runtime.fight)
    runtime.fight = fight
    if not packets:
        raise ValueError("Native class buff produced no committed presentation")
    # Devotion installs an actual turn-start listener. The current resource
    # may increase only when that native event executes on the ally turn.
    after_cast = fight.actors[ally_id].effect_stats[stat]
    lifecycle_packets += advance_buff_runtime(runtime, ally_id)
    after_turn = fight.actors[ally_id].effect_stats[stat]
    if after_turn <= before:
        raise ValueError("Native class buff did not survive until the recipient's turn")
    return dict(
        schema="native-monster-scenario-v1",
        kind="class_buff",
        recipe=dict(recipe),
        ally_id=ally_id,
        caster_id=caster.id,
        statistic=stat,
        resource_before=before,
        resource_after_cast=after_cast,
        resource_on_recipient_turn=after_turn,
        caster_resources_before=caster_before,
        costs=dict(transaction.plan["costs"]),
        preparation_packets=len(packets),
        lifecycle_packets=lifecycle_packets,
        initialization_packets=initialization_packets,
        native_start_event_delivered=fight.native_start_event_delivered,
        caster_turn_id=fight.turn_id,
    )


def advance_buff_runtime(runtime, actor_id):
    """Use production turn callbacks, timers and ACKs for delayed native buffs."""
    from wakfu_server.combat_timeline_snapshot import current_wire_turn

    packets = 0
    for _ in range(len(runtime.fight.actors) * 2 + 1):
        actor = runtime.fight.current
        if actor is not None and actor.id == actor_id:
            return packets
        if actor is None:
            break
        if actor.controlled:
            packets += len(
                runtime.end_turn(
                    actor.owner_id, actor.id, current_wire_turn(runtime.fight)
                )
            )
        else:
            packets += len(runtime.end_server_turn(actor.id, runtime.fight.turn_id))
        if runtime.awaiting_ack is not None:
            packets += len(
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            )
    raise ValueError("Class buff scenario could not establish recipient turn")
