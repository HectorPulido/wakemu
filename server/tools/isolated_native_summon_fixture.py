"""User-authorized isolated native summons with an independent dummy owner.

Constructor and child behavior are separate proof obligations. This fixture uses
original native profile, initial states, stats, action book and controller flags;
it never executes or requires a creator spell, grants resources or creates areas.
"""
from copy import deepcopy
from random import Random


def validate_request(reference, level, native):
    if type(reference) is not int or type(level) is not int or reference not in native:
        raise ValueError("Missing native isolated summon descriptor")
    row = native[reference]
    if not max(1, row["min_level"]) <= level <= row["max_level"]:
        raise ValueError("Isolated summon level is outside its positive native bounds")
    return row


def fixture(
    validator,
    reference,
    level,
    enemy_cell=(-10, -7, -1),
    *,
    dummy_reference=6,
    dummy_level=4
):
    """Build and register the real fresh child, without a creator-cast gate."""
    validate_request(reference, level, validator.NATIVE_SOURCE_MONSTERS)
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_summon import SummonSpecification, fresh_summon_insertion
    from wakfu_server.combat_summon_creation import NativeSummonBuilder
    from wakfu_server.combat_summon_initialization import summon_initializer
    from wakfu_server.combat_summon_stats import registered_summon_stats

    fight, character, monsters, deck = validator.fixture(
        dummy_reference, dummy_level, tuple(enemy_cell), native_lifecycle=True
    )
    owner = fight.current
    if owner is None or owner.id not in monsters:
        raise ValueError("Dummy native owner is not current")
    runtime_factory, _ = server_runtime(
        character, monsters, deck, action_id=1, critical=False, rng=Random(0)
    )
    authority = runtime_factory.summon_authority
    occupied = {a.position for a in fight.actors.values() if a.hp > 0}
    cell = next(
        (
            c
            for c in sorted(
                fight.walkable,
                key=lambda c: (
                    abs(c[0] - owner.position[0]) + abs(c[1] - owner.position[1]),
                    c,
                ),
            )
            if c not in occupied
        ),
        None,
    )
    if cell is None:
        raise ValueError("No free native isolated child cell")
    identity = max([0, *fight.actors]) + 1
    spec = SummonSpecification(
        reference, level, False, owner.direction, owner.team, "caster", 1
    )
    builder = NativeSummonBuilder(
        authority, initialize_states=summon_initializer(runtime_factory, [])
    )
    actor, registration = builder(fight, spec, owner.id, identity, cell)
    order, current = fresh_summon_insertion(
        fight, spec, caster_id=owner.id, actor_id=identity
    )
    authority.register(
        fight, actor, registration, new_order=order, new_turn_index=current
    )
    registered_summon_stats(actor, fight, character["map_id"])
    receipt = dict(
        status="isolated_native_child_constructed",
        reference=reference,
        descriptor_level=level,
        actor_id=identity,
        dummy_owner_id=owner.id,
        dummy_owner_reference=dummy_reference,
        dummy_owner_level=dummy_level,
        creator_cast_required=False,
        native_summon_context=True,
        source=deepcopy(actor.native_summon_source),
        native_action_book=deepcopy(actor.native_summon_action_book),
        native_ai_flag=actor.native_controlled_by_ai,
        resources={
            str(k): dict(current=actor.effect_stats[k], maximum=actor.effect_maxima[k])
            for k in (2, 3, 4)
        },
        resources_granted=False,
        original_profile_and_book_unchanged=True,
        admission=False,
    )
    return fight, character, monsters, deck, receipt


def prove(validator, arguments):
    """Reach the isolated child's own turn and commit a useful native AI action."""
    from wakfu_server.combat_server_spell import prepare_server_turn_end
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_tactical_ai import NativeProvider, build_request
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.combat_summon_stats import registered_summon_stats
    from wakfu_server.fight_checkpoint_store import snapshot
    from monster_actual_ai_gameplay import snapshot_gameplay, committed_gameplay_delta
    import planner

    fight, character, monsters, deck, receipt = fixture(
        validator,
        arguments["reference"],
        arguments["level"],
        tuple(arguments.get("enemy_cell", (-10, -7, -1))),
        dummy_reference=arguments.get("dummy_reference", 6),
        dummy_level=arguments.get("dummy_level", 4),
    )
    child = receipt["actor_id"]
    for step in range(len(fight.actors) * 2 + 1):
        if fight.current is not None and fight.current.id == child:
            break
        if fight.current is None:
            raise ValueError("Encounter ended before isolated child turn")
        current = fight.current
        preview, _ = prepare_server_turn_end(
            character,
            monsters,
            fight,
            deck,
            actor_id=current.id,
            action_id=10 + step,
            rng=Random(0),
        )
        current = preview.actors[current.id]
        if effective_server_controlled(preview, current):
            preview.end_server_turn(current.id, preview.turn_id)
        else:
            preview.end_turn(current.owner_id, current.id, current.turn_count)
        RuntimeMessages(preview).turn_started()
        fight = preview
    else:
        raise ValueError("Isolated child turn was not reached")
    runtime = RuntimeMessages(fight)
    provider = NativeProvider(character, monsters, deck)
    provider.capabilities(fight)

    def serialize(actor, state):
        if getattr(actor, "native_summon_source", None):
            return registered_summon_stats(actor, state, character["map_id"])
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        return (
            actual_actor_stats(character, actor, state.id, **values)
            if actor.controlled
            else actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, **values
            )
        )

    actions = []
    for _ in range(3):
        fight = runtime.fight
        before = snapshot(fight, runtime=runtime)
        request = build_request(
            runtime, provider, max_previews=48, budget_ms=5000, depth=2
        )
        if snapshot(fight, runtime=runtime) != before:
            raise ValueError("Child forecast mutated source")
        decision = planner.decide(request)
        action = decision["decision"]["actions"][0]
        if action["type"] == "end_turn":
            break

        def broken(actor, state):
            raise ValueError("isolated summon serializer failure")

        try:
            provider.commit(runtime, action, broken)
        except ValueError as error:
            if str(error) != "isolated summon serializer failure":
                raise
        else:
            raise ValueError("Serializer failure did not reject commit")
        if snapshot(fight, runtime=runtime) != before:
            raise ValueError("Child rollback failed")
        identities = dict(fight.actors)
        game_before = snapshot_gameplay(fight)
        packets = provider.commit(runtime, action, serialize)
        game_after = snapshot_gameplay(runtime.fight)
        delta = committed_gameplay_delta(
            game_before, game_after, caster_id=child, action=action
        )
        if any(runtime.fight.actors.get(i) is not a for i, a in identities.items()):
            raise ValueError("Child commit lost owned actor identity")
        actions.append(
            dict(
                action=action,
                packets=len(packets),
                gameplay_delta=delta,
                forecast_source_unchanged=True,
                serializer_failure_rolled_back=True,
                owned_object_identities_preserved=True,
            )
        )
        if action["type"] == "cast" and packets and delta["effectful_committed_cast"]:
            return dict(
                status="validated_isolated_native_summon",
                constructor=receipt,
                actions=actions,
                creator_proof_required=False,
                admission=False,
            )
    return dict(
        status="pending",
        constructor=receipt,
        actions=actions,
        error="No useful isolated native child action in three decisions",
        admission=False,
    )


def direct_prove(validator, arguments):
    """Isolate the original intended action; planner preference is not a gate.

    Source-pinned post-constructor304 effects are part of descriptor preparation,
    not fabricated characteristic/resource assignments or a creator cast test.
    """
    from wakfu_server.combat_server_spell import server_runtime, prepare_server_turn_end
    from wakfu_server.combat_summon import SummonSpecification, fresh_summon_insertion
    from wakfu_server.combat_summon_creation import NativeSummonBuilder
    from wakfu_server.combat_summon_initialization import summon_initializer
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_npc_spell import owned_spells
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.combat_summon_stats import registered_summon_stats
    from wakfu_server.fight_checkpoint_store import snapshot
    from monster_actual_ai_gameplay import snapshot_gameplay, committed_gameplay_delta

    reference, level = arguments["reference"], arguments["level"]
    fight, character, monsters, deck, receipt = fixture(
        validator,
        reference,
        level,
        tuple(arguments.get("enemy_cell", (-10, -7, -1))),
        dummy_reference=arguments.get("dummy_reference", 6),
        dummy_level=arguments.get("dummy_level", 4),
    )
    owner = fight.current
    child = receipt["actor_id"]
    factory, _ = server_runtime(
        character, monsters, deck, action_id=2, critical=False, rng=Random(0)
    )
    if arguments.get("same_profile_ally"):
        occupied = {a.position for a in fight.actors.values() if a.hp > 0}
        cell = next(
            c
            for c in sorted(
                fight.walkable,
                key=lambda c: (
                    abs(c[0] - fight.actors[child].position[0])
                    + abs(c[1] - fight.actors[child].position[1]),
                    c,
                ),
            )
            if c not in occupied
        )
        spec = SummonSpecification(
            reference, level, False, owner.direction, owner.team, "caster", 1
        )
        identity = max([0, *fight.actors]) + 1
        ally, registration = NativeSummonBuilder(
            factory.summon_authority, initialize_states=summon_initializer(factory, [])
        )(fight, spec, owner.id, identity, cell)
        order, current = fresh_summon_insertion(
            fight, spec, caster_id=owner.id, actor_id=identity
        )
        factory.summon_authority.register(
            fight, ally, registration, new_order=order, new_turn_index=current
        )
        receipt["native_same_profile_ally_id"] = identity
    preparation = []
    for effect_id in arguments.get("native_post_constructor_effects", []):
        effect = factory.effects.get(str(effect_id), factory.effects.get(effect_id))
        if (
            not effect
            or effect.get("effect_class") != 304
            or "IsOwnSummon" not in effect.get("criteria", "")
            or str(reference) not in effect["criteria"]
        ):
            raise ValueError("Preparation is not an original own-summon304 effect")
        for actor in list(fight.actors.values()):
            if getattr(actor, "native_summon_source", {}).get("ref") != reference:
                continue
            dispatcher, outbox = factory(
                fight, {"native_retained_container": {"present": False}}
            )
            with fight.effect_resolution():
                result = dispatcher.execute(
                    EffectInvocation(
                        effect_id,
                        level,
                        owner.id,
                        actor.id,
                        actor.position,
                        native_explicit_target=True,
                        native_preselected_target=True,
                    )
                )
            from wakfu_server.combat_conditions import evaluate_condition

            probe = EffectInvocation(
                effect_id,
                level,
                owner.id,
                actor.id,
                actor.position,
                native_explicit_target=True,
                native_preselected_target=True,
            )
            condition = dispatcher.condition_context(probe)
            preparation.append(
                dict(
                    effect_id=effect_id,
                    target_id=actor.id,
                    result=str(result),
                    packets=len(outbox),
                    original_criterion=effect.get("criteria"),
                    criterion_result=evaluate_condition(
                        effect.get("criteria", ""), condition
                    ),
                    resolved_recipient_ids=[
                        i.target_id for i in dispatcher.resolve(effect, probe)
                    ],
                    target_hp=actor.hp,
                    target_max_hp=actor.max_hp,
                    target_states=[
                        dict(reference=e.reference, level=e.level)
                        for e in actor.state_ledger.entries
                    ],
                    caster_root=condition.actors["caster"].summon_root_id,
                    target_root=condition.actors["target"].summon_root_id,
                )
            )
    receipt["native_post_constructor_preparation"] = preparation
    if arguments.get("diagnostic_only"):
        return dict(
            status="isolated_preparation_diagnostic",
            constructor=receipt,
            actor_states={
                str(a.id): dict(
                    hp=a.hp,
                    max_hp=a.max_hp,
                    states=[
                        dict(reference=e.reference, level=e.level)
                        for e in a.state_ledger.entries
                    ],
                )
                for a in fight.actors.values()
            },
            admission=False,
        )
    receipt["prepared_resources"] = {
        str(k): dict(
            current=fight.actors[child].effect_stats[k],
            maximum=fight.actors[child].effect_maxima[k],
        )
        for k in (2, 3, 4)
    }
    for step in range(len(fight.actors) * 2 + 1):
        if fight.current is not None and fight.current.id == child:
            break
        if fight.current is None:
            raise ValueError("Encounter ended before isolated child turn")
        current = fight.current
        preview, _ = prepare_server_turn_end(
            character,
            monsters,
            fight,
            deck,
            actor_id=current.id,
            action_id=10 + step,
            rng=Random(0),
        )
        current = preview.actors[current.id]
        if effective_server_controlled(preview, current):
            preview.end_server_turn(current.id, preview.turn_id)
        else:
            preview.end_turn(current.owner_id, current.id, current.turn_count)
        RuntimeMessages(preview).turn_started()
        fight = preview
    else:
        raise ValueError("Isolated child turn was not reached")
    runtime = RuntimeMessages(fight)
    provider = NativeProvider(character, monsters, deck)
    spells = owned_spells(fight, monsters, character=character)
    selected = arguments.get("spell_ids", list(spells))
    if any(s not in spells for s in selected):
        raise ValueError("Requested direct action is not in native child book")

    def serialize(actor, state):
        if getattr(actor, "native_summon_source", None):
            return registered_summon_stats(actor, state, character["map_id"])
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        return (
            actual_actor_stats(character, actor, state.id, **values)
            if actor.controlled
            else actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, **values
            )
        )

    targets = sorted(
        fight.walkable,
        key=lambda c: (
            c not in [a.position for a in fight.actors.values() if a.id != child],
            abs(c[0] - fight.current.position[0])
            + abs(c[1] - fight.current.position[1]),
            c,
        ),
    )
    errors = []
    for spell in selected:
        for cell in targets[:24]:
            target = next(
                (
                    a.id
                    for a in fight.actors.values()
                    if a.position == cell and a.hp > 0
                ),
                None,
            )
            action = dict(
                type="cast",
                spellId=spell,
                level=spells[spell],
                target=list(cell),
                targetId=target,
            )
            before = snapshot(fight, runtime=runtime)

            def broken(actor, state):
                raise ValueError("isolated direct serializer failure")

            try:
                try:
                    provider.commit(runtime, action, broken)
                except ValueError as error:
                    if str(error) != "isolated direct serializer failure":
                        raise
                else:
                    raise ValueError("Serializer failure did not reject commit")
                if snapshot(fight, runtime=runtime) != before:
                    raise RuntimeError("Direct child rollback failed")
                game_before = snapshot_gameplay(fight)
                identities = dict(fight.actors)
                packets = provider.commit(runtime, action, serialize)
                delta = committed_gameplay_delta(
                    game_before,
                    snapshot_gameplay(runtime.fight),
                    caster_id=child,
                    action=action,
                )
                if any(
                    runtime.fight.actors.get(i) is not a for i, a in identities.items()
                ):
                    raise RuntimeError("Direct child lost owned identity")
                if packets and delta["effectful_committed_cast"]:
                    return dict(
                        status="validated_isolated_native_summon_action",
                        constructor=receipt,
                        action=action,
                        gameplay_delta=delta,
                        packets=len(packets),
                        serializer_failure_rolled_back=True,
                        owned_object_identities_preserved=True,
                        planner_selection_required=False,
                        creator_cast_required=False,
                        prior_native_rejections=errors,
                        admission=False,
                    )
                return dict(
                    status="pending",
                    constructor=receipt,
                    action=action,
                    gameplay_delta=delta,
                    error="Committed direct cast had no useful gameplay",
                    admission=False,
                )
            except ValueError as error:
                if snapshot(fight, runtime=runtime) != before:
                    raise RuntimeError(
                        "Rejected child direct action changed source"
                    ) from error
                errors.append(dict(action=action, error=str(error)))
    return dict(
        status="pending",
        constructor=receipt,
        prior_native_rejections=errors,
        error="No legal useful direct child action in bounded native targets",
        admission=False,
    )
