"""Common ordinary PVE cast entry, with no class/spell whitelist.

Critical branch is explicit until its native server roll is reconstructed.
All random draws belong to a fresh transaction; unsupported mandatory effects
reject without committing combat resources or sending partial packets.
"""
import json
import random
from functools import lru_cache
from .combat_static_catalogs import CompiledEffects, characteristic_registry
from wakfu_server.paths import DATA_ROOT
from .spells import validate_deck
from .spell_audit import catalog, states_catalog, costs_catalog
from .combat_ordinary_authority import OrdinaryActorAuthority, ordinary_cast_authority
from .combat_runtime_adapter import NativeServerRuntimeAdapter
from .combat_effect_runtime import NativeEffectRuntimeFactory
from .combat_native_timing_context import NativeEffectTimingProvider
from .combat_spell_transaction import prepare_spell_transaction
from .combat_random_transaction import rollback_external_rng


@lru_cache(maxsize=1)
def compiled_runtime_catalog():
    from .combat_native_spell_casting import merged_spell_effects

    from .combat_effect_runtime import _merge_effects
    from .combat_effect_area_catalog import area_effect_catalog

    return CompiledEffects(
        _merge_effects(merged_spell_effects(), area_effect_catalog()), states_catalog()
    )


def prewarm_runtime_catalogs():
    """Load/validate static assets before opening listeners, never bind a fight."""
    from .combat_spell_usage import native_limits
    from .combat_direct_target import native_direct_target_policies
    from .combat_trigger_identifiers import zone_trigger_policies
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_fight_property import property_registry
    from .combat_life_steal import native_spell_elements
    from .combat_effect_area import native_effect_areas
    from .combat_ordinary_authority import native_property_catalog
    from .combat_retained_runtime import native_retained_metadata
    from .combat_delivery_owners import owner_catalog
    from .combat_event_costs import cost_catalog
    from .combat_characteristic_conditions import native_aliases
    from .combat_conditional_costs import native_catalog
    from .combat_native_pt import null_exclusion_references
    from .combat_spell_grant import native_spell_references
    from .combat_native_spell_casting import catalog as native_casting_catalog

    from .combat_native_los_ray import ray_program, topology_columns

    compiled = compiled_runtime_catalog()
    from .combat_npc_attack import npc_runtime_catalog

    npc_runtime_catalog()  # Immutable NPC definitions, before the first AI attack.
    from .combat_weapon import weapon_runtime_catalog

    weapon_runtime_catalog()
    for loader in (
        native_limits,
        native_direct_target_policies,
        zone_trigger_policies,
        characteristic_registry,
        native_actor_catalog,
        native_effect_areas,
        property_registry,
        native_spell_elements,
        native_property_catalog,
        native_retained_metadata,
        owner_catalog,
        cost_catalog,
        costs_catalog,
        native_aliases,
        native_catalog,
        native_spell_references,
        null_exclusion_references,
        native_casting_catalog,
    ):
        loader()
    ray_program()
    topology_columns(1134)  # Current native complete topology, before any cast.
    return {"effect_definitions": len(compiled.effects)}


def server_runtime(
    character, monsters, deck_blob, *, action_id, critical, rng=None, compiled=None
):
    """One transaction-owned RNG shared by ordinary and relative decisions."""
    transaction_rng = random.Random() if rng is None else rng
    deck = validate_deck(deck_blob, character["breed"], character["level"])
    actors = OrdinaryActorAuthority(
        characters={character["id"]: character},
        monsters=monsters,
        decks={character["id"]: frozenset(deck["active"] + deck["passive"])},
        excluded_decks={character["id"]: frozenset()},
    )
    from .combat_summon import RegisteredSummonAuthority

    actors = RegisteredSummonAuthority(actors)
    states = states_catalog()
    authority = ordinary_cast_authority(
        actors=actors,
        timing=NativeEffectTimingProvider(states),
        rng=transaction_rng,
        critical=critical,
    )
    adapter = NativeServerRuntimeAdapter(
        actor_authority=actors, cast=authority, viewer_id=character["id"]
    )
    compiled = compiled_runtime_catalog() if compiled is None else compiled
    factory = NativeEffectRuntimeFactory(
        effects=compiled.source_effects,
        state_catalog=states,
        characteristic_registry=characteristic_registry(),
        compiled_effects=compiled,
        action_id=action_id,
        contexts=adapter.contexts(),
        displacement_authority=actors,
        summon_authority=actors,
    )
    from .combat_relative_probability import RelativeGroupAuthority

    factory.relative_group_children = RelativeGroupAuthority(
        effects=factory.effects,
        actor_authority=actors,
        condition_context=adapter.condition,
        draw_integer=lambda total: transaction_rng.randint(1, total),
        draw_fraction=lambda fraction: transaction_rng.random() < fraction,
    )
    from .combat_random_group import RandomGroupAuthority

    factory.random_group_children = RandomGroupAuthority(
        effects=factory.effects,
        condition_context=adapter.condition,
        draw_integer=lambda total: transaction_rng.randrange(total),
    )
    return factory, adapter


@rollback_external_rng
def prepare_server_spell(
    body,
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    action_id,
    line_of_sight,
    critical,
    rng=None
):
    from .combat_critical import choose_critical, spell_critical_available
    from .combat_cast import decode_cast
    from .combat_spell_grant import granted_spells

    actor = fight.actors[character["id"]]
    transaction_rng = random.Random() if rng is None else rng
    if critical is None:
        request = decode_cast(body)
        spell_id = request["spell_uid"] & 0xFFFFFFFF
        grant = granted_spells(fight, actor.id).get(spell_id)
        level = (
            grant["level"]
            if grant is not None and request["spell_uid"] == spell_id
            else actor.effective_level
        )
        decision = choose_critical(
            actor,
            rng=transaction_rng,
            mode="auto",
            critical_available=spell_critical_available(spell_id, level),
        )
        critical = decision.critical
    else:
        if type(critical) is not bool:
            raise ValueError("Invalid explicit critical branch")
        decision = choose_critical(
            actor, rng=transaction_rng, mode="critical" if critical else "normal"
        )
    factory, adapter = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=critical,
        rng=transaction_rng,
    )
    if not isinstance(actor.effect_stats, dict) or 4 not in actor.effect_stats:
        raise ValueError("Initialize native characteristics before casting")
    result = prepare_spell_transaction(
        body,
        character,
        fight,
        owner_id,
        deck_blob,
        wp_current=actor.effect_stats[4],
        action_id=action_id,
        line_of_sight=line_of_sight,
        runtime_factory=factory,
        conditional_context=lambda request, preview: adapter.cast_condition(
            preview, request
        ),
        critical=critical,
    )
    result.plan["critical_decision"] = decision.diagnostic()
    return result


@rollback_external_rng
def prepare_server_initialization(
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    action_id,
    rng=None,
    fight_start=False
):
    """Install own innates/passives; optionally deliver inferred server fight start.

    The default installs only. fight_start=True applies the documented external
    1003 server lifecycle inference through native subscriber selection.

    Caller commits preview and emits packets only after this returns. Placement
    readiness/lifecycle must be handled by the caller before invoking it.
    """
    from .combat_class_initialization import plan, initialize_transaction

    factory, _ = server_runtime(
        character, monsters, deck_blob, action_id=action_id, critical=False, rng=rng
    )
    states = states_catalog()
    actor = fight.actors.get(character["id"])
    if actor is None:
        raise ValueError("Missing owned class initialization actor")
    owned = dict(
        character, x=actor.position[0], y=actor.position[1], z=actor.position[2]
    )
    initial = plan(owned, deck_blob, catalog(), states)
    if type(fight_start) is not bool:
        raise ValueError("Explicit fight_start policy must be boolean")
    preview, packets = initialize_transaction(
        fight, initial, factory, states, owner_id=owner_id
    )
    if fight_start:
        from .combat_start_events import deliver_fight_start

        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        with preview.effect_resolution():
            deliver_fight_start(dispatcher, initialized_actor_ids=tuple(preview.actors))
        packets += tuple(outbox)
    return preview, packets


@rollback_external_rng
@rollback_external_rng
def prepare_server_turn_end(
    character, monsters, fight, deck_blob, *, actor_id, action_id, rng=None
):
    """Atomic owned1002 end boundary; execution precedes timer expiration."""
    from copy import deepcopy
    from .combat_turn_events import deliver_turn_end

    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character, monsters, deck_blob, action_id=action_id, critical=False, rng=rng
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        deliver_turn_end(dispatcher, actor_id=actor_id)
    return preview, tuple(packets)


@rollback_external_rng
def prepare_server_turn_start(
    character,
    monsters,
    fight,
    deck_blob,
    *,
    actor_id,
    action_id,
    rng=None,
    native_events=True,
    area_callbacks=False
):
    """One preview for start1001 and optional Qs callbacks, after start expiry.

    The runtime owns expiration and publication; this helper neither advances
    the FSM nor repeats timer cleanup. Callback ordering is server policy.
    """
    from copy import deepcopy
    from .combat_turn_events import deliver_turn_start

    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Turn-start requires the actual active actor")
    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character, monsters, deck_blob, action_id=action_id, critical=False, rng=rng
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        if native_events:
            deliver_turn_start(dispatcher, actor_id=actor_id)
        if area_callbacks and preview.phase == "active":
            dispatcher.native_area_events.turn_start(actor_id)
    return preview, tuple(packets)
