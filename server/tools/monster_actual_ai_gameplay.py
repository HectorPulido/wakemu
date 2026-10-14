"""Actual replanned AI acceptance for damage, support and native owned producers."""
from copy import deepcopy
from types import SimpleNamespace


def snapshot_gameplay(fight):
    from native_triggered_spell_observation import gameplay_snapshot

    data = gameplay_snapshot(fight)
    data["hp_states"] = {
        identity: dict(
            hp=actor.hp,
            states=sorted(
                (entry.reference, entry.level) for entry in actor.state_ledger.entries
            ),
        )
        for identity, actor in fight.actors.items()
    }
    return data


def committed_gameplay_delta(before, after, *, caster_id, action):
    """Resource payment or a movement-only action never qualifies a native cast."""
    from native_triggered_spell_observation import gameplay_delta

    delta = gameplay_delta(
        before, after, SimpleNamespace(caster_id=caster_id, native_rhe=True)
    )
    changes = [
        dict(
            actor_id=identity,
            before=before["hp_states"][identity],
            after=after["hp_states"][identity],
        )
        for identity in sorted(set(before["hp_states"]) & set(after["hp_states"]))
        if before["hp_states"][identity] != after["hp_states"][identity]
    ]
    delta["hp_state_changes"] = changes
    delta["effectful_committed_cast"] = action.get("type") == "cast" and bool(
        delta["effectful_gameplay"] or changes
    )
    return delta


def execute_replanned(*, choose, commit, maximum_actions=3):
    if type(maximum_actions) is not int or not 1 <= maximum_actions <= 3:
        raise ValueError("Invalid actual AI action bound")
    steps = []
    required_morph_uid = None
    for _ in range(maximum_actions):
        action, decision = choose()
        if action.get("type") == "end_turn":
            break
        transaction = commit(action)
        steps.append(
            dict(action=deepcopy(action), decision=decision, transaction=transaction)
        )
        # A switched native book needs a subsequent owned action, not just its installation.
        if transaction.get("native_temporary_book_changed"):
            required_morph_uid = transaction.get("native_temporary_book_uid")
            if required_morph_uid is not None:
                continue
        source = decision.get("ownership", {}).get("native_morph_source")
        if required_morph_uid is not None and (
            not isinstance(source, dict) or source.get("book_uid") != required_morph_uid
        ):
            continue
        if transaction["gameplay"]["effectful_committed_cast"]:
            return dict(
                status="validated_ordinary_ai",
                steps=steps,
                forecast_source_unchanged=True,
                serializer_failure_rolled_back=True,
                committed_state_changed=True,
                owned_object_identities_preserved=True,
            )
    return dict(
        status="pending",
        error="No committed native gameplay cast in three actual replans",
        steps=steps,
    )


def current_owned_action_witness(fight, provider, action):
    """Bind each decision to the actual current book, including native forms."""
    from wakfu_server.combat_morph_spellbook import (
        build_morph_book,
        morph_record,
        native_morph_profiles,
    )
    import hashlib
    import json

    actor = fight.current
    if actor is None:
        raise ValueError("Missing current AI owned-book actor")
    record = morph_record(fight, actor.id)
    morph_source = None
    if record is not None:
        profile = native_morph_profiles().get(str(record.get("profile_id")))
        if not isinstance(profile, dict) or type(record.get("own_level")) is not bool:
            raise ValueError("Missing actual native morph book source")
        level = (
            actor.effective_level if record["own_level"] else profile["minimum_level"]
        )
        expected = build_morph_book(profile, level)
        if record["levels"] != expected or not record["removed_raw_uids"] <= set(
            expected
        ):
            raise ValueError("Current morph book differs from native constructor")
        morph_source = dict(
            profile_id=record["profile_id"],
            book_uid=record["book_uid"],
            constructor_level=level,
            profile_sha256=hashlib.sha256(
                json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
    capabilities = provider.capabilities(fight)
    owned = {row["spellId"]: row["level"] for row in capabilities}
    if action.get("type") == "cast" and (
        action.get("spellId") not in owned
        or action.get("level") != owned[action["spellId"]]
    ):
        raise ValueError("Actual planner selected a foreign native ability")
    return dict(
        actor_id=actor.id, current_owned_book=owned, native_morph_source=morph_source
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
    provider.capabilities(fight)

    def choose():
        before, geometry = snapshot(fight, runtime=runtime), source_snapshot(fight)
        request = build_request(
            runtime, provider, max_previews=48, budget_ms=5000, depth=2
        )
        if (
            snapshot(fight, runtime=runtime) != before
            or source_snapshot(fight) != geometry
        ):
            raise ValueError("Actual AI forecast mutated authoritative source")
        decision = planner.decide(request)
        action = validate_response(runtime, request, decision, provider)
        ownership = current_owned_action_witness(fight, provider, action)
        return action, dict(
            actual_decision=decision,
            producer_trace=request["producerTrace"],
            ownership=ownership,
        )

    def serialize(actor, state):
        values = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        return (
            actual_actor_stats(character, actor, state.id, fight=state, **values)
            if actor.controlled
            else actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, fight=state, **values
            )
        )

    def commit(action):
        checkpoint = snapshot(fight, runtime=runtime)
        identities = dict(fight.actors)
        before = snapshot_gameplay(fight)
        caster_id = fight.current.id
        from wakfu_server.combat_morph_spellbook import morph_record

        previous_morph = deepcopy(morph_record(fight, caster_id))

        def broken(_actor, _state):
            raise ValueError("actual gameplay AI injected serializer failure")

        try:
            provider.commit(runtime, action, broken)
        except ValueError as error:
            if str(error) != "actual gameplay AI injected serializer failure":
                raise
        else:
            raise ValueError("Injected serializer failure did not reject commit")
        if snapshot(fight, runtime=runtime) != checkpoint:
            raise ValueError(
                "Serializer failure did not roll back authoritative checkpoint"
            )
        packets = provider.commit(runtime, action, serialize)
        if (
            not packets
            or runtime.fight is not fight
            or any(
                fight.actors.get(key) is not actor for key, actor in identities.items()
            )
        ):
            raise ValueError("Actual commit lost packets or existing owned identities")
        if snapshot(fight, runtime=runtime) == checkpoint:
            raise ValueError(
                "Actual committed action did not change authoritative state"
            )
        return dict(
            packets=len(packets),
            serializer_failure_rolled_back=True,
            committed_state_changed=True,
            owned_object_identities_preserved=True,
            native_temporary_book_changed=(
                previous_morph != morph_record(fight, caster_id)
            ),
            native_temporary_book_uid=(morph_record(fight, caster_id) or {}).get(
                "book_uid"
            ),
            gameplay=committed_gameplay_delta(
                before, snapshot_gameplay(fight), caster_id=caster_id, action=action
            ),
        )

    result = execute_replanned(choose=choose, commit=commit)
    result.update(
        reference=reference,
        level=level,
        owned_book=owned,
        enemy_cell=list(enemy_cell),
        scenario=scenario,
        action_limit=3,
    )
    return result


def prove(reference, cases, validator):
    import json

    seen, diagnostics = set(), []
    for case in cases:
        if case.get("status") != "validated":
            continue
        for target in case.get("successful_targets", []):
            if target.get("effectful") is not True:
                continue
            key = json.dumps(
                [target["enemy_cell"], target.get("scenario")], sort_keys=True
            )
            if key in seen:
                continue
            if len(seen) >= 4:
                break
            seen.add(key)
            proof = prove_scene(
                reference,
                case["level"],
                target["enemy_cell"],
                target.get("scenario"),
                validator,
            )
            if proof["status"] == "validated_ordinary_ai":
                return dict(proof, prior_bounded_scene_diagnostics=diagnostics)
            diagnostics.append(proof)
    return dict(
        status="pending",
        error="No committed gameplay cast in bounded witnessed scenes",
        attempted_scenes=len(seen),
        diagnostics=diagnostics,
    )
