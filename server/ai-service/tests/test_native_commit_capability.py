from types import SimpleNamespace
import random
import unittest
from unittest.mock import patch

import test_native_oracle as fixtures
from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_ai.native.native_commit_capability import _WORLD_NATIVE_RUNNER
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_retained_gc_authority import certify_ready_runtime
from wakfu_ai.bridge.world_sources import bind_private_sources


class NativeCommitCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeOracleTests.setUpClass()

    def _source(self):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import default_deck

        fixture = fixtures.NativeOracleTests.wonejo_fixture()
        deck = default_deck(fixture.character)
        fight, _ = prepare_server_initialization(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            fixture.fight,
            fixture.character["account_id"],
            deck,
            action_id=1,
            fight_start=True,
        )
        fixture.fight = fight
        fixture.pc = fight.actors[fixture.pc.id]
        fixture.npc = fight.actors[fixture.npc.id]
        characters = {fixture.pc.id: fixture.character}
        monsters = {fixture.npc.id: fixture.monster}
        decks = {fixture.pc.id: deck}
        factory = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=fixture.pc.id,
            fight_start=True,
        )
        from wakfu_ai.native.native_stats import NativeStats

        serializer = NativeStats(
            characters=characters,
            monsters=monsters,
            fight_id=fight.id,
            registrations=getattr(fight, "native_summon_registrations", {}),
        )
        runtime = RuntimeMessages(
            fight,
            stats_serializer=serializer,
            runtime_stats_serializer=serializer,
            turn_start_provider=factory.turn_start,
            turn_end_provider=factory.turn_end,
            expiration_runtime_factory=factory,
        )
        runtime.action_id = 1
        adapter = CombatSessionAdapter.__new__(CombatSessionAdapter)
        certify_ready_runtime(adapter, runtime, serializer, factory)
        session = SimpleNamespace(
            account_id=fixture.character["account_id"],
            character_id=fixture.pc.id,
        )
        bind_private_sources(runtime, session)
        self.assertTrue(fight.native_start_event_delivered)
        self.assertIs(runtime.fight.current, fixture.npc)
        return fixture, runtime, deck

    @staticmethod
    def _oracle(runtime, fixture, deck):
        return fixtures.NativeOracleTests.oracle_for(
            runtime, fixture.character, fixture.monster, deck
        )

    @staticmethod
    def _shared(runtime, fixture):
        one = Session(
            fixture.character["account_id"],
            fixture.character["id"],
            "owner",
            fixture.character["map_id"],
            0,
        )
        registry = Registry(lambda session: session is one)
        shared = registry.register(runtime.fight, one, runtime=runtime)
        return one, registry, shared

    def test_end_turn_owner_scope_skips_full_graphs_and_stale_work_stays_unpublished(
        self,
    ):
        oracle_module = __import__(
            "wakfu_ai.native.native_oracle", fromlist=["complete_fingerprint"]
        )
        original_fingerprint = oracle_module.complete_fingerprint

        fixture, runtime, deck = self._source()
        session, registry, shared = self._shared(runtime, fixture)
        serializer = runtime.stats_serializer
        admitted_counts = []

        def runner(native):
            oracle = self._oracle(native, fixture, deck)
            admitted_counts.append(0)
            packets = oracle.commit(
                {"type": "end_turn"}, stats_serializer=native.stats_serializer
            )
            yield packets, {"action": {"type": "end_turn"}}

        with patch.object(
            oracle_module,
            "complete_fingerprint",
            side_effect=lambda value: self._counted(
                original_fingerprint, admitted_counts, value
            ),
        ):
            published = list(
                run_shared_turn(
                    runtime,
                    SimpleNamespace(registry=registry),
                    session,
                    runner,
                    native_runner_authority=_WORLD_NATIVE_RUNNER,
                )
            )
        self.assertEqual(admitted_counts, [0])
        self.assertEqual(len(published), 1)
        shared_packets = registry.drain(fixture.fight.id, session)[0].packets
        self.assertTrue(shared_packets)

        # Direct calls do not inherit a shared-turn claim and retain both
        # complete source checks while producing the same gameplay outcome.
        fixture2, runtime2, deck2 = self._source()
        direct_oracle = self._oracle(runtime2, fixture2, deck2)
        direct_counts = [0]
        with patch.object(
            oracle_module,
            "complete_fingerprint",
            side_effect=lambda value: self._counted(
                original_fingerprint, direct_counts, value
            ),
        ):
            direct_packets = direct_oracle.commit(
                {"type": "end_turn"}, stats_serializer=runtime2.stats_serializer
            )
        self.assertEqual(direct_counts, [2])
        self.assertEqual(shared_packets, tuple(direct_packets))
        self.assertEqual(
            fixtures.NativeOracleTests.effects(shared.fight),
            fixtures.NativeOracleTests.effects(runtime2.fight),
        )

        # A caller-supplied serializer is not enough to authorize the skip.
        fixture3, runtime3, deck3 = self._source()
        custom_oracle = self._oracle(runtime3, fixture3, deck3)
        runtime3.turn_start_provider = lambda *_args, **_kwargs: (runtime3.fight, ())
        custom_counts = [0]
        with patch.object(
            oracle_module,
            "complete_fingerprint",
            side_effect=lambda value: self._counted(
                original_fingerprint, custom_counts, value
            ),
        ):
            custom_oracle.commit(
                {"type": "end_turn"}, stats_serializer=lambda *_args: b""
            )
        self.assertEqual(custom_counts, [2])

        # Reuse the focused existing concurrency regression: a real concurrent
        # publication advances sequence while a private native result is
        # staged, and the stale packet is never published.
        from test_world_shared import SharedNativeAiTests

        stale_case = SharedNativeAiTests()
        stale_case.setUp()
        stale_case.test_runner_is_lock_free_and_stale_private_result_is_replanned()

        self.assertFalse(hasattr(shared, "native_ai_turn_claim"))
        self.assertEqual(shared.sequence, 1)

    def test_cast_and_move_owner_scope_matches_direct_packets_and_state(self):
        oracle_module = __import__(
            "wakfu_ai.native.native_oracle", fromlist=["complete_fingerprint"]
        )
        original_fingerprint = oracle_module.complete_fingerprint
        base_random = random.Random

        class FixedRandom(base_random):
            def __init__(self, *_args, **_kwargs):
                super().__init__(1729)

        def make_case(kind):
            fixture, runtime, deck = self._source()
            oracle = self._oracle(runtime, fixture, deck)
            serializer = runtime.stats_serializer
            if kind == "cast":
                action = dict(
                    type="cast",
                    spellId=7962,
                    level=1,
                    targetId=fixture.pc.id,
                    target=list(fixture.pc.position),
                )
            return fixture, runtime, oracle, serializer, action

        with patch.object(oracle_module.random, "Random", FixedRandom):
            for kind in ("cast",):
                with self.subTest(action=kind):
                    (
                        direct_fixture,
                        direct_runtime,
                        direct_oracle,
                        direct_stats,
                        action,
                    ) = make_case(kind)
                    direct_count = [0]
                    with patch.object(
                        oracle_module,
                        "complete_fingerprint",
                        side_effect=lambda value: self._counted(
                            original_fingerprint, direct_count, value
                        ),
                    ):
                        direct_packets = direct_oracle.commit(
                            action, stats_serializer=direct_stats
                        )
                    self.assertEqual(direct_count, [2])
                    direct_runtime.end_server_turn(
                        direct_runtime.fight.current.id,
                        direct_runtime.fight.turn_id,
                    )

                    (
                        shared_fixture,
                        shared_runtime,
                        _,
                        shared_stats,
                        shared_action,
                    ) = make_case(kind)
                    self.assertEqual(action, shared_action)
                    session, registry, _ = self._shared(shared_runtime, shared_fixture)
                    shared_count = [0]

                    def runner(native):
                        shared_oracle = self._oracle(
                            native,
                            shared_fixture,
                            direct_oracle.decks[shared_fixture.pc.id],
                        )
                        packets = shared_oracle.commit(
                            shared_action, stats_serializer=shared_stats
                        )
                        yield packets, {"action": {"type": kind}}

                    with patch.object(
                        oracle_module,
                        "complete_fingerprint",
                        side_effect=lambda value: self._counted(
                            original_fingerprint, shared_count, value
                        ),
                    ):
                        shared_turn = run_shared_turn(
                            shared_runtime,
                            SimpleNamespace(registry=registry),
                            session,
                            runner,
                            native_runner_authority=_WORLD_NATIVE_RUNNER,
                        )
                        next(shared_turn)
                        shared_turn.close()
                    self.assertEqual(shared_count, [0])
                    shared_packets = registry.drain(shared_fixture.fight.id, session)[
                        0
                    ].packets
                    self.assertEqual(shared_packets, tuple(direct_packets))
                    self.assertEqual(
                        fixtures.NativeOracleTests.effects(
                            registry.lookup(shared_fixture.fight.id).fight
                        ),
                        fixtures.NativeOracleTests.effects(direct_runtime.fight),
                    )

    @staticmethod
    def _counted(fingerprint, counts, value):
        counts[0] += 1
        return fingerprint(value)


if __name__ == "__main__":
    unittest.main()
