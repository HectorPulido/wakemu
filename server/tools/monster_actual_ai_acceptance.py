"""Actual first-action execution followed by fresh planning, bounded to three actions."""
from copy import deepcopy


def execute_replanned(*, choose, commit, damaged, maximum_actions=3):
    """Never consume a later action from an earlier, now stale decision."""
    if type(maximum_actions) is not int or not 1 <= maximum_actions <= 3:
        raise ValueError("Invalid actual AI action bound")
    receipts = []
    for _ in range(maximum_actions):
        action, decision = choose()
        if action == dict(type="end_turn"):
            return dict(
                status="pending",
                error="Actual replanned AI ended turn before enemy damage",
                steps=receipts,
            )
        receipt = commit(action)
        receipts.append(
            dict(action=deepcopy(action), decision=decision, transaction=receipt)
        )
        if damaged():
            return dict(status="validated_ordinary_ai", steps=receipts)
    return dict(
        status="pending",
        error="No actual enemy damage within three replanned actions",
        steps=receipts,
    )


def prove_scene(reference, level, enemy_cell, scenario, validator):
    from wakfu_server.combat_tactical_ai import (
        NativeProvider,
        build_request,
        validate_response,
    )
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_geometry_snapshot import source_snapshot
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.monsters import native_abilities
    import planner

    fight, character, monsters, deck = validator.fixture(
        reference, level, tuple(enemy_cell), scenario=scenario
    )
    runtime = RuntimeMessages(fight)
    provider = NativeProvider(character, monsters, deck)
    owned = native_abilities(reference, level)
    owned_ids = {row["spell_id"] for row in owned}
    enemy_hp = {
        identity: actor.hp
        for identity, actor in fight.actors.items()
        if actor.team != fight.current.team
    }
    provider.capabilities(fight)

    def choose():
        before = snapshot(fight, runtime=runtime)
        geometry = source_snapshot(fight)
        request = build_request(
            runtime, provider, max_previews=48, budget_ms=5000, depth=2
        )
        if (
            snapshot(fight, runtime=runtime) != before
            or source_snapshot(fight) != geometry
        ):
            raise ValueError("Actual AI forecast mutated source")
        decision = planner.decide(request)
        action = validate_response(runtime, request, decision, provider)
        if action["type"] == "cast" and action["spellId"] not in owned_ids:
            raise ValueError("Foreign owned spell selected")
        return action, dict(
            actual_decision=decision,
            producer_trace=request["producerTrace"],
            forecast_source_unchanged=True,
        )

    def serialize(actor, state):
        kw = dict(wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4])
        return (
            actual_actor_stats(character, actor, state.id, fight=state, **kw)
            if actor.controlled
            else actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, fight=state, **kw
            )
        )

    def commit(action):
        checkpoint = snapshot(fight, runtime=runtime)
        identities = dict(fight.actors)

        def broken(actor, state):
            raise ValueError("actual multi-action injected serializer failure")

        try:
            provider.commit(runtime, action, broken)
        except ValueError as error:
            if str(error) != "actual multi-action injected serializer failure":
                raise
        else:
            raise ValueError("Injected serializer failure did not reject commit")
        if snapshot(fight, runtime=runtime) != checkpoint:
            raise ValueError("Serializer failure changed checkpoint")
        packets = provider.commit(runtime, action, serialize)
        if (
            not packets
            or runtime.fight is not fight
            or any(fight.actors.get(k) is not actor for k, actor in identities.items())
        ):
            raise ValueError("Actual commit lost packets or identities")
        if snapshot(fight, runtime=runtime) == checkpoint:
            raise ValueError("Actual committed action did not change state")
        return dict(
            packets=len(packets),
            serializer_failure_rolled_back=True,
            committed_state_changed=True,
            owned_object_identities_preserved=True,
        )

    result = execute_replanned(
        choose=choose,
        commit=commit,
        damaged=lambda: any(
            identity in fight.actors and fight.actors[identity].hp < hp
            for identity, hp in enemy_hp.items()
        ),
    )
    result.update(
        reference=reference,
        level=level,
        owned_book=owned,
        enemy_cell=list(enemy_cell),
        scenario=scenario,
        action_limit=3,
        actual_enemy_hp_before=enemy_hp,
        actual_enemy_hp_after={
            identity: fight.actors[identity].hp
            for identity in enemy_hp
            if identity in fight.actors
        },
    )
    return result


def attach_scene_diagnostics(proof, prior):
    """Preserve a final failed proof without creating a self-referential receipt."""
    return dict(proof, prior_bounded_scene_diagnostics=deepcopy(prior))
