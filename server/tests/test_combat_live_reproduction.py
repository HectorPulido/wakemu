"""Observed providers use actual native serializers and strict source reads."""
import copy
import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_input_observation import (
    observe_combat_inputs,
    observe_fact,
    replay_combat_inputs,
)
from wakfu_server.combat_live_reproduction import (
    RECIPE,
    LiveProviderReplayError,
    prepare_live_context,
)


LOCAL_STATS = {
    "module": "local_game_server",
    "qualname": "session.<locals>.current_combat_stats",
}
READY_STATS = {
    "module": "wakfu_server.combat_session_adapter",
    "qualname": "CombatSessionAdapter.ready_transition.<locals>.stats_serializer",
}


def evidence(events=()):
    return dict(
        schema="wakemu-combat-observed-inputs-v1",
        events=[
            dict(sequence=index, kind="fact", label=label, value=value)
            for index, (label, value) in enumerate(events, 1)
        ],
        rng_streams=[],
        incomplete=[],
    )


class LiveProviderContractTests(unittest.TestCase):
    def runtime(self):
        return SimpleNamespace(fight=SimpleNamespace(sequence=0), action_id=1)

    def test_ack_only_context_needs_no_fabricated_character_or_deck(self):
        runtime = self.runtime()
        context = prepare_live_context(
            runtime, None, {"live_provider_identity": {}}, lambda: 1.0, evidence()
        )
        self.assertIsNone(runtime.turn_start_provider)
        context.assert_complete()
        clone = copy.deepcopy(runtime)
        self.assertIs(context.rebind_copy(clone), clone)
        self.assertIs(context.runtime, clone)
        context.assert_complete()

    def test_unknown_oracle_and_missing_identity_are_infrastructure_errors(self):
        for inputs in (
            {},
            {
                "live_provider_identity": {
                    "turn_start_provider": {
                        "module": "wakfu_ai.native.native_oracle",
                        "qualname": "NativeOracle.live_start_boundary",
                    }
                }
            },
        ):
            with self.subTest(inputs=inputs), self.assertRaises(
                LiveProviderReplayError
            ):
                prepare_live_context(
                    self.runtime(), None, inputs, lambda: 1.0, evidence()
                )

    def test_incomplete_receipt_is_not_a_gameplay_rejection(self):
        snapshot = evidence()
        snapshot["incomplete"] = ["event_limit_exceeded"]
        with self.assertRaises(LiveProviderReplayError) as caught:
            prepare_live_context(
                self.runtime(),
                None,
                {"live_provider_identity": {}},
                lambda: 1.0,
                snapshot,
            )
        self.assertNotIsInstance(caught.exception, ValueError)

    def test_source_reads_preserve_order_and_unused_facts_are_not_ignored(self):
        snapshot = evidence([("current_combat_stats.player_source", {"id": 7})])
        context = prepare_live_context(
            self.runtime(), None, {"live_provider_identity": {}}, lambda: 1.0, snapshot
        )
        with self.assertRaises(LiveProviderReplayError):
            context._sources()
        with self.assertRaises(LiveProviderReplayError):
            context.assert_complete()

    def test_actual_player_sources_probe_adds_no_store_reads(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        class Store:
            def __init__(self):
                self.calls = []

            def character(self, owner, actor):
                self.calls.append((owner, actor))
                return dict(id=actor, builds={0: {"deck": b"exact".hex()}})

        store = Store()
        adapter = CombatSessionAdapter(store)
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, owner_id=3, controlled=True)},
            native_summon_registrations={},
        )
        with observe_combat_inputs() as observed:
            characters, decks = adapter.player_sources(fight)
        self.assertEqual(store.calls, [(3, 7)])
        self.assertEqual(decks, {7: b"exact"})
        row = next(
            event
            for event in observed.snapshot()["events"]
            if event["label"] == "combat.player_sources"
        )
        self.assertEqual(row["value"], (characters, decks))


class NativeLiveProviderTests(unittest.TestCase):
    def test_actual_ready_callbacks_replay_turn_end_and_start_with_frozen_sources(self):
        import test_combat_reproduction_actions as fixtures
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        initial, base = fixtures.ReproductionActionTests().fixture()
        character = dict(
            base["character"], builds={0: {"deck": base["deck_blob"].hex()}}
        )

        class Store:
            def character(self, owner, identity):
                return character

        adapter = CombatSessionAdapter(Store())

        def bind_initialized(fight, owner, ready, **providers):
            # The fixture already ran real class/fight-start initialization.
            # Intercept only the placement builder to obtain the actual
            # ready_transition closures without initializing that fight twice.
            fields = (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_end_provider",
                "turn_start_provider",
                "expiration_runtime_factory",
            )
            bound = RuntimeMessages(
                fight,
                **{field: providers[field] for field in fields},
                clock=lambda: 1.0
            )
            bound.action_id = initial.action_id
            return fight, bound, ()

        with patch(
            "wakfu_server.combat_ready.prepare_ready", side_effect=bind_initialized
        ):
            transition = adapter.ready_transition(
                SimpleNamespace(account_id=3, character_id=7),
                initial.fight,
                initial,
                True,
                base["monsters"],
                fight_start=True,
                area_callbacks=True,
            )
        runtime = transition.runtime
        private = copy.deepcopy(runtime)
        identities = {
            field: dict(
                module=getattr(getattr(runtime, field), "__module__"),
                qualname=getattr(getattr(runtime, field), "__qualname__"),
            )
            for field in (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_end_provider",
                "turn_start_provider",
                "expiration_runtime_factory",
                "clock",
            )
        }
        action = dict(
            type="end_turn",
            owner_id=3,
            actor_id=7,
            turn_id=current_wire_turn(runtime.fight),
        )
        with observe_combat_inputs() as observed:
            packets = runtime.end_turn(3, 7, action["turn_id"])
        snapshot = observed.snapshot()
        inputs = dict(
            authority_recipe=RECIPE,
            live_provider_identity=identities,
            native_events=True,
            area_callbacks=True,
        )
        context = prepare_live_context(private, action, inputs, lambda: 1.0, snapshot)
        with replay_combat_inputs(snapshot) as tape:
            result = context.execute(private, action)
            context.assert_complete()
        self.assertTrue(tape.ownership_known)
        self.assertEqual(result["packets"], packets)
        self.assertEqual(private.awaiting_ack, runtime.awaiting_ack)
        self.assertEqual(private.pending, runtime.pending)
        self.assertEqual(private.fight.current.id, runtime.fight.current.id)

    def capture(self):
        import test_combat_reproduction_actions as fixtures
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible

        runtime, initial = fixtures.ReproductionActionTests().fixture()
        private = copy.deepcopy(runtime)
        character = dict(
            initial["character"], builds={0: {"deck": initial["deck_blob"].hex()}}
        )

        class Store:
            def __init__(self):
                self.calls = 0

            def character(self, owner, actor):
                self.calls += 1
                # Preserve a concurrent source change actually seen at the
                # serializer, independently of the earlier cast authority.
                return (
                    character
                    if self.calls == 1
                    else dict(character, level=character["level"] + 1)
                )

        store = Store()
        adapter = CombatSessionAdapter(store)

        def current(actor, fight):
            kwargs = dict(
                wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
            )
            if actor.controlled:
                source = store.character(actor.owner_id, actor.id)
                observe_fact("current_combat_stats.player_source", source)
                stats = actual_actor_stats(source, actor, runtime.fight.id, **kwargs)
                observe_fact("current_combat_stats.player", stats)
            else:
                source = initial["monsters"][actor.id]
                observe_fact("current_combat_stats.monster_source", source)
                stats = actual_monster_actor_stats(
                    source, actor, runtime.fight.id, direction=3, **kwargs
                )
                observe_fact("current_combat_stats.monster", stats)
            return stats

        target = runtime.fight.actors[-7].position
        action = dict(
            type="player_spell",
            body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            owner_id=3,
            critical=None,
        )
        with observe_combat_inputs() as observed:
            characters, decks = adapter.player_sources(runtime.fight)
            inputs = dict(
                initial,
                authority_recipe=RECIPE,
                character=characters[7],
                player_characters=characters,
                deck_blobs=decks,
                live_provider_identity={},
            )
            transaction = prepare_server_spell(
                action["body"],
                characters[7],
                inputs["monsters"],
                runtime.fight,
                3,
                decks[7],
                action_id=runtime.action_id + 1,
                critical=None,
                player_characters=characters,
                deck_blobs=decks,
                line_of_sight=lambda origin, target, state: authoritative_visible(
                    inputs["map_id"],
                    origin,
                    target,
                    state,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in state.actors.values()
                        if actor.hp > 0
                    },
                ),
            )
            packets = commit_spell_transaction(
                runtime, transaction, stats_serializer=current
            )
        return private, action, inputs, observed.snapshot(), packets, transaction

    def test_native_cast_recomputes_exact_per_read_live_serializer_sources(self):
        private, action, inputs, snapshot, packets, transaction = self.capture()
        context = prepare_live_context(private, action, inputs, lambda: 1.0, snapshot)
        with replay_combat_inputs(snapshot) as tape:
            result = context.execute(private, action)
            context.assert_complete()
        self.assertTrue(tape.ownership_known)
        self.assertEqual(result["packets"], packets)
        self.assertEqual(result["plan"], transaction.plan)
        player_sources = [
            event["value"]
            for event in snapshot["events"]
            if event["label"] == "current_combat_stats.player_source"
        ]
        self.assertEqual(player_sources[0]["level"], inputs["character"]["level"] + 1)

    def test_serialized_bytes_are_an_assertion_not_a_replayed_output(self):
        private, action, inputs, snapshot, _, _ = self.capture()
        row = next(
            event
            for event in snapshot["events"]
            if event["label"] == "current_combat_stats.player"
        )
        row["value"] = b"invented serialization"
        context = prepare_live_context(private, action, inputs, lambda: 1.0, snapshot)
        with self.assertRaisesRegex(LiveProviderReplayError, "snapshot differs"):
            with replay_combat_inputs(snapshot):
                context.execute(private, action)

    def test_ready_and_local_serializers_preserve_their_distinct_fight_kwargs(self):
        import test_combat_reproduction_actions as fixtures
        from wakfu_server.combat_actor import actual_actor_stats

        runtime, inputs = fixtures.ReproductionActionTests().fixture()
        actor = runtime.fight.actors[7]
        source = inputs["character"]
        kwargs = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        for ready in (False, True):
            with self.subTest(ready=ready):
                prefix = "ready_stats_serializer" if ready else "current_combat_stats"
                expected = actual_actor_stats(
                    source,
                    actor,
                    runtime.fight.id,
                    **dict(kwargs, **({"fight": runtime.fight} if ready else {}))
                )
                snapshot = evidence(
                    [
                        (prefix + ".player_source", source),
                        (prefix + ".player", expected),
                    ]
                )
                context = prepare_live_context(
                    runtime,
                    None,
                    {
                        "live_provider_identity": {
                            "runtime_stats_serializer": READY_STATS
                            if ready
                            else LOCAL_STATS
                        }
                    },
                    lambda: 1.0,
                    snapshot,
                )
                with patch(
                    "wakfu_server.combat_actor.actual_actor_stats",
                    wraps=actual_actor_stats,
                ) as real_serializer:
                    self.assertEqual(
                        context.serialize_runtime(actor, runtime.fight), expected
                    )
                self.assertEqual("fight" in real_serializer.call_args.kwargs, ready)
                context.assert_complete()
