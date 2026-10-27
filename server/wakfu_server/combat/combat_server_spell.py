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
from wakfu_server.spells import validate_deck
from wakfu_server.spell_audit import catalog, states_catalog, costs_catalog
from .combat_ordinary_authority import OrdinaryActorAuthority, ordinary_cast_authority
from .combat_runtime_adapter import NativeServerRuntimeAdapter
from .combat_effect_runtime import NativeEffectRuntimeFactory
from .combat_native_timing_context import NativeEffectTimingProvider
from .combat_spell_transaction import prepare_spell_transaction
from .combat_random_transaction import rollback_external_rng
from .combat_input_observation import observe_rng, observe_authority


@lru_cache(maxsize=1)
def compiled_runtime_catalog():
    from .combat_published_catalogs import compiling_catalog_offline

    if compiling_catalog_offline():
        return compile_runtime_catalog_eager()
    return CompiledEffects.from_published("player")


def compile_runtime_catalog_eager():
    """Original full compiler, invoked explicitly by the offline publisher."""
    from .combat_native_spell_casting import merged_spell_effects

    from .combat_effect_runtime import _merge_effects
    from .combat_effect_area_catalog import area_effect_catalog

    from .combat_aptitude_initialization import effect_catalog
    from .rift_producer_catalog import configured_producer_catalog

    return CompiledEffects(
        _merge_effects(
            _merge_effects(
                _merge_effects(merged_spell_effects(), area_effect_catalog()),
                effect_catalog(),
            ),
            configured_producer_catalog(),
        ),
        states_catalog(),
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
    from .combat_spell_resource_costs import catalog as native_resource_cost_catalog
    from .combat_casting_context import casting_root_catalog

    from .combat_native_los_ray import ray_program, topology_columns

    compiled = compiled_runtime_catalog()
    from .combat_npc_attack import npc_runtime_catalog

    npc_runtime_catalog()  # Immutable NPC definitions, before the first AI attack.
    # Observation and forecast construction use the preserved baseline even
    # when imported NPC spells are enabled. It has a separate compiled cache.
    npc_runtime_catalog(imported=False)
    from .combat_weapon import weapon_runtime_catalog

    weapon_runtime_catalog()
    for loader in (
        native_resource_cost_catalog,
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
        casting_root_catalog,
    ):
        loader()
    ray_program()
    topology_columns(1134)  # Current native complete topology, before any cast.
    return {"effect_definitions": len(compiled.effects)}


def server_runtime(
    character,
    monsters,
    deck_blob,
    *,
    action_id,
    critical,
    rng=None,
    compiled=None,
    player_characters=None,
    deck_blobs=None,
):
    """One transaction-owned RNG shared by ordinary and relative decisions."""
    transaction_rng = random.Random() if rng is None else rng
    transaction_rng = observe_rng(
        "server_runtime", transaction_rng, external=rng is not None
    )
    if player_characters is None:
        player_characters = {character["id"]: character}
    else:
        player_characters = dict(player_characters)
        if player_characters.get(character["id"]) != character:
            raise ValueError("Caster must match the owned combat character snapshot")
    if deck_blobs is None:
        deck_blobs = {character["id"]: deck_blob}
    else:
        deck_blobs = dict(deck_blobs)
    if set(deck_blobs) != set(player_characters):
        raise ValueError("Every controlled player requires its own deck snapshot")
    observe_authority(
        "server_runtime.authority",
        dict(
            character=character,
            monsters=monsters,
            deck_blob=deck_blob,
            player_characters=player_characters,
            deck_blobs=deck_blobs,
            action_id=action_id,
            critical=critical,
            compiled_is_default=compiled is None,
        ),
    )
    decks = {}
    deck_caps = {}
    for actor_id, source in player_characters.items():
        if type(actor_id) is not int or source.get("id") != actor_id:
            raise ValueError("Invalid controlled player snapshot identity")
        parsed = validate_deck(
            deck_blobs[actor_id], source["breed"], source["level"], character=source
        )
        decks[actor_id] = frozenset(parsed["active"] + parsed["passive"])
        deck_caps[actor_id] = parsed["level_cap"] if parsed["level_cap"] >= 0 else None
    from .combat_npc_spellbook import ordinary_npc_spellbook

    actors = OrdinaryActorAuthority(
        characters=player_characters,
        monsters=monsters,
        decks=decks,
        deck_caps=deck_caps,
        deck_blobs=deck_blobs,
        excluded_decks={actor_id: frozenset() for actor_id in player_characters},
        npc_spellbook=ordinary_npc_spellbook,
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
    from .combat_fight_runtime_catalog import fight_runtime_catalog
    from .combat_npc_attack import npc_runtime_catalog

    compiled = fight_runtime_catalog(
        monsters,
        compiled,
        class_catalog=compiled_runtime_catalog,
        npc_catalog=npc_runtime_catalog,
    )
    factory = NativeEffectRuntimeFactory(
        effects=compiled.source_effects,
        state_catalog=states,
        characteristic_registry=characteristic_registry(),
        compiled_effects=compiled,
        action_id=action_id,
        contexts=adapter.contexts(),
        displacement_authority=actors,
        summon_authority=actors,
        transaction_rng=transaction_rng,
    )
    # The actual factory installs this live provider on every transaction
    # preview; subsequent owned movement reads current PB and carry facts.
    factory.native_rail_movement_authority = actors
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
    from .combat_equipment_external_contracts import bind_owned_equipment_producers

    bind_owned_equipment_producers(factory)
    from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory

    return OwnedEquipmentRuntimeFactory(factory, compiled), adapter


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
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    from .combat_critical import choose_critical, spell_critical_available
    from .combat_cast import decode_cast, resolve_owned_spell_action

    request = decode_cast(body)
    actor, spell_id, level = resolve_owned_spell_action(
        request, character, fight, owner_id, deck_blob
    )
    transaction_rng = random.Random() if rng is None else rng
    transaction_rng = observe_rng(
        "player_spell.before_critical", transaction_rng, external=rng is not None
    )
    if critical is None:
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
        player_characters=player_characters,
        deck_blobs=deck_blobs,
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
    fight_start=False,
    player_characters=None,
    deck_blobs=None,
    attachment_authority=None,
):
    """Install own innates/passives; optionally deliver inferred server fight start.

    The default installs only. fight_start=True applies the documented external
    1003 server lifecycle inference through native subscriber selection.

    Caller commits preview and emits packets only after this returns. Placement
    readiness/lifecycle must be handled by the caller before invoking it.
    """
    from .combat_class_initialization import plan, initialize_transaction

    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
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
    from .combat_owned_equipment_pin import pin_transaction
    from .combat_owned_equipment import initialize_transaction as initialize_equipment

    # Wakemu ordering: snapshot-owned flat gear first, qualified permanent
    # equipment states, class and aptitude initialization, then fight-start1003.
    # No claim is made about an unrecovered original server ordering caller.
    from .combat_protector_fight_condition import bind_condition_capability

    bind_condition_capability(factory, fight)
    equipment_capability = factory.equipment_operation_capability()
    preview, equipment = pin_transaction(
        fight,
        owned,
        attachment_authority,
        compiled_runtime_catalog(),
        characteristic_registry(),
        owner_id=owner_id,
        ordinary_only=True,
        include_attachments=attachment_authority is not None,
        runtime_capability=equipment_capability,
    )
    from wakfu_server.characters.owned_social_context import pin as pin_social_context

    pin_social_context(preview, character)
    equipment_factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
        compiled=equipment["compiled"],
    )
    preview, equipment_packets = initialize_equipment(
        preview,
        actor.id,
        equipment,
        equipment_factory,
        owner_id=owner_id,
    )
    from .combat_consumable_states import install as install_consumable_states
    from .combat_input_observation import wall_time_ns

    # Wakemu ordering for owned bHE actors: player equipment first, then each
    # selected companion's ordinary passive roots, before consumables/class/
    # aptitude initialization. The companion remains its attested NPC actor;
    # only its current selected owner supplies the custody/criterion snapshot.
    companion_sources = getattr(preview, "native_companion_sources", {})
    if not isinstance(companion_sources, dict):
        raise ValueError("Malformed owned companion source roster during Ready")
    owned_companions = sorted(
        (
            (int(key), source)
            for key, source in companion_sources.items()
            if isinstance(source, dict)
            and source.get("owner_character_id") == character["id"]
        ),
        key=lambda row: row[0],
    )
    if owned_companions:
        from .combat_companion_owned_equipment_adapter import (
            initialize_companion,
            pin_companion,
        )

        for companion_id, source in owned_companions:
            if str(source.get("id")) != str(companion_id):
                raise ValueError(
                    "Companion source key differs from its native actor ID"
                )
            preview, companion_equipment = pin_companion(
                preview,
                companion_id,
                character,
                equipment_factory,
                # Each pin starts from the immutable base catalog. The
                # preparation helper composes every existing player/NPC pin;
                # feeding its already-composed result back here duplicates
                # prior owned definitions as more companions are processed.
                compiled_runtime_catalog(),
                characteristic_registry(),
            )
            # The NPC graph is discovered after the player factory was built.
            # Rebuild through the same production factory constructor with the
            # complete pin-bound catalog; this preserves the transaction RNG,
            # live actor/context providers and normal factory identity checks.
            companion_factory, _ = server_runtime(
                character,
                monsters,
                deck_blob,
                action_id=action_id,
                critical=False,
                rng=rng,
                player_characters=player_characters,
                deck_blobs=deck_blobs,
                compiled=companion_equipment["compiled"],
            )
            bind_condition_capability(companion_factory, preview)
            preview, companion_packets = initialize_companion(
                preview,
                companion_id,
                companion_equipment,
                companion_factory,
                account_id=owner_id,
            )
            equipment_packets += companion_packets

    consumable_packets = install_consumable_states(
        preview,
        character,
        factory,
        owner_id=owner_id,
        now_ms=wall_time_ns("consumable.initialize.realtime") // 1000000,
    )
    preview, packets = initialize_transaction(
        preview, initial, factory, states, owner_id=owner_id
    )
    packets = equipment_packets + consumable_packets + packets
    from .combat_aptitude_initialization import (
        initialize_transaction as initialize_aptitudes,
    )

    preview, aptitude_packets = initialize_aptitudes(
        preview, owned, factory, owner_id=owner_id
    )
    packets += aptitude_packets
    if fight_start:
        from .combat_start_events import deliver_fight_start

        if getattr(preview, "native_abomination_quest_grant", None) is not None:
            from .combat_abomination_scene import apply_start

            scene_packets = []
            apply_start(preview, factory, scene_packets)
            packets += tuple(scene_packets)
        if getattr(preview, "native_aguabrial_story_admission", None) is not None:
            from .combat_aguabrial_scene import bind_aguabrial_start

            bind_aguabrial_start(preview)
        if getattr(preview, "native_spirit_scene_admission", None) is not None:
            from .combat_encounter_objective_spirit import (
                apply_spirit_start,
                freeze_spirit_participants,
            )

            freeze_spirit_participants(
                preview,
                player_characters or {character["id"]: character},
            )
            scene_packets = []
            apply_spirit_start(preview, factory, scene_packets)
            packets += tuple(scene_packets)
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        with preview.effect_resolution():
            rift_state = getattr(preview, "rift_wave_state", None)
            if rift_state is not None:
                from .rift_native_gameplay import (
                    install_wave_state,
                    policy as rift_policy,
                )

                if rift_policy(preview) is not None:
                    from .rift_company_compensation import (
                        company_actor_ids,
                        install_company_compensation,
                    )

                    install_company_compensation(
                        dispatcher,
                        actor_ids=company_actor_ids(preview),
                    )
                    install_wave_state(
                        dispatcher,
                        actor_ids=rift_state["wave_actor_ids"],
                        wave=rift_state["wave"],
                    )
            layout = getattr(preview, "native_encounter_scene_layout", None)
            if layout is not None:
                from .combat_rushu_encounter_setup import install_rushu_encounter_setup

                install_rushu_encounter_setup(
                    dispatcher,
                    map_id=character["map_id"],
                    monsters=monsters,
                    layout=layout,
                )
            deliver_fight_start(dispatcher, initialized_actor_ids=tuple(preview.actors))
            if rift_state is not None:
                from .rift_artifact_generation import spawn_artifacts

                spawn_artifacts(dispatcher, wave=rift_state["wave"])
            from .combat_npc_phase_controller import install_npc_phase_score

            install_npc_phase_score(dispatcher)
            if getattr(preview, "native_spirit_scene_admission", None) is not None:
                from .combat_encounter_objective_spirit import install_spirit_objective

                install_spirit_objective(dispatcher)
        packets += tuple(outbox)
    return preview, packets


@rollback_external_rng
@rollback_external_rng
def prepare_server_turn_end(
    character,
    monsters,
    fight,
    deck_blob,
    *,
    actor_id,
    action_id,
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    """Atomic owned1002/1037 end boundaries before timer expiration."""
    from copy import deepcopy
    from .combat_turn_events import deliver_turn_end, deliver_turn_regeneration

    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        from .combat_npc_phase_controller import deliver_npc_score_result

        from .combat_encounter_turn_end_order import turn_end_event_order

        objective_terminal = None
        if getattr(preview, "native_encounter_objective_policy", None) is not None:
            from .combat_encounter_objective import deliver_objective_score_marker

            deliver_objective_score_marker(dispatcher, actor_id=actor_id)
        deliver_npc_score_result(dispatcher, actor_id=actor_id)
        order = turn_end_event_order(preview, actor_id=actor_id)
        early_regeneration = order[0] == 1037
        if early_regeneration:
            deliver_turn_regeneration(dispatcher, actor_id=actor_id)
        if not early_regeneration or (
            preview.phase == "active" and preview.current is not None
        ):
            deliver_turn_end(dispatcher, actor_id=actor_id)
        if (
            preview.phase == "active"
            and preview.current is not None
            and preview.current.id == actor_id
            and getattr(preview, "native_ogrest_phase_context", None) is not None
        ):
            from .combat_ogrest_phase_controller import finish_ogrest_player_turn

            finish_ogrest_player_turn(dispatcher, actor_id=actor_id)
        if getattr(preview, "native_encounter_objective_policy", None) is not None:
            from .combat_encounter_objective import deliver_owned_objective_boundary

            objective_terminal = deliver_owned_objective_boundary(
                dispatcher, actor_id=actor_id, boundary="owned_player_end"
            )
        if (
            not early_regeneration
            and objective_terminal is None
            and preview.phase == "active"
            and preview.current is not None
        ):
            deliver_turn_regeneration(dispatcher, actor_id=actor_id)
        from .combat_encounter_terminal_cleanup import deliver_terminal_helper_cleanup

        deliver_terminal_helper_cleanup(dispatcher)
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
    area_callbacks=False,
    player_characters=None,
    deck_blobs=None,
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
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        objective_terminal = None
        if native_events:
            from .combat_periodic_aptitude import renew_periodic_aptitudes
            from .combat_npc_phase_controller import (
                deliver_npc_score_result,
                deliver_npc_table_phase,
            )

            from .combat_equipment_external_events import deliver_completed_round

            if getattr(preview, "native_encounter_objective_policy", None) is not None:
                from .combat_encounter_objective import deliver_objective_score_marker

                deliver_objective_score_marker(dispatcher, actor_id=actor_id)
            deliver_completed_round(dispatcher)
            if getattr(preview, "native_encounter_objective_policy", None) is not None:
                from .combat_encounter_objective import deliver_owned_objective_boundary

                objective_terminal = deliver_owned_objective_boundary(
                    dispatcher, actor_id=actor_id, boundary="completed_round"
                )
            if objective_terminal is None:
                renew_periodic_aptitudes(dispatcher, actor_id=actor_id)
                deliver_npc_score_result(dispatcher, actor_id=actor_id)
                if (
                    getattr(preview, "native_encounter_objective_policy", None)
                    is not None
                ):
                    from .combat_encounter_objective import (
                        deliver_owned_objective_boundary,
                    )

                    objective_terminal = deliver_owned_objective_boundary(
                        dispatcher, actor_id=actor_id, boundary="owned_boss_start"
                    )
                deliver_npc_table_phase(dispatcher, actor_id=actor_id)
                if preview.phase == "active" and objective_terminal is None:
                    deliver_turn_start(dispatcher, actor_id=actor_id)
                    if preview.phase == "active":
                        from .combat_ogrest_phase_controller import (
                            deliver_ogrest_post_turn_start,
                        )

                        deliver_ogrest_post_turn_start(dispatcher, actor_id=actor_id)
                    if preview.phase == "active" and preview.current is not None:
                        from .combat_encounter_table_listeners import (
                            deliver_owned_post_start_listeners,
                        )

                        deliver_owned_post_start_listeners(
                            dispatcher, actor_id=actor_id
                        )
        if area_callbacks and preview.phase == "active" and objective_terminal is None:
            dispatcher.native_area_events.turn_start(actor_id)
    return preview, tuple(packets)


@rollback_external_rng
def prepare_server_terminal_cleanup(
    character,
    monsters,
    fight,
    deck_blob,
    *,
    action_id,
    rng=None,
    player_characters=None,
    deck_blobs=None,
):
    """Private post-KO repair using the same authenticated production producer.

    It does not publish END, advance clocks or replay any owner action. A late
    policy adoption must be separately authorized and explicitly attested.
    """
    from copy import deepcopy
    from .combat_encounter_terminal_cleanup import deliver_terminal_helper_cleanup

    preview = deepcopy(fight)
    factory, _ = server_runtime(
        character,
        monsters,
        deck_blob,
        action_id=action_id,
        critical=False,
        rng=rng,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
    )
    dispatcher, packets = factory(
        preview, {"native_retained_container": {"present": False}}
    )
    with preview.effect_resolution():
        deliver_terminal_helper_cleanup(dispatcher)
    return preview, tuple(packets)
