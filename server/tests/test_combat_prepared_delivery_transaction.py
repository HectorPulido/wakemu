"""Prepared-prefix identity and marker-scoped delivery transactions.

Fast cases use actual Fight/RuntimeMessages with explicit server-policy inputs.
Native cases add that policy input over a corpse produced by actual hostile
casts; they do not claim a newly qualified native scheduled-restoration spell.
"""
from copy import deepcopy
import os
import struct
import unittest

import test_combat_native_action_ids as action_fixture
from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID
from wakfu_server.combat_pending_restoration import SOURCE, pending_restoration_uids
from wakfu_server.combat_reproduction_state import encode_state


def runtime_state(runtime):
    return encode_state(runtime)


class PreparedDeliveryTransactionTests(unittest.TestCase):
    def fixture(self):
        runtime = action_fixture.NativeTurnDeliveryTests().runtime()
        runtime.end_turn(1, 100, 1)
        prefix = runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(
            [row["native_action_id"] for row in prefix.native_actions], [2, 3, 4]
        )
        return runtime, prefix

    def marker(self, actor, value=SOURCE):
        # Explicit server-policy input; not fabricated class/catalog authority.
        actor.native_death_status = dict(
            getattr(actor, "native_death_status", {}), pending_restoration=value
        )

    def assert_unchanged(self, runtime, before, fight, actors):
        self.assertEqual(runtime_state(runtime), before)
        self.assertIs(runtime.fight, fight)
        for identity, actor in actors.items():
            self.assertIs(runtime.fight.actors[identity], actor)

    def test_repeat_native_ack_batch_preserves_exact_identity_and_runtime(self):
        runtime, prefix = self.fixture()
        before = runtime_state(runtime)
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertEqual(runtime_state(runtime), before)
        self.assertEqual(runtime.native_action_id, 4)

    def test_earlier_prefix_does_not_regress_advanced_counter_or_latest_metadata(self):
        runtime, prefix = self.fixture()
        newer = runtime.prepare_delivery([prefix[0]])
        self.assertEqual(runtime.native_action_id, 5)
        before = runtime_state(runtime)
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertEqual(runtime_state(runtime), before)
        self.assertEqual(runtime.last_native_delivery, newer.native_actions)

    def test_foreign_prefix_rejects_before_invalid_restoration_policy(self):
        runtime, prefix = self.fixture()
        self.marker(runtime.fight.actors[100], "invalid-policy")
        runtime.fight.id += 1
        before = runtime_state(runtime)
        with self.assertRaisesRegex(ValueError, "another allocator"):
            runtime.prepare_delivery(prefix)
        self.assertEqual(runtime_state(runtime), before)

    def test_future_prefix_rejects_before_invalid_restoration_policy(self):
        runtime, prefix = self.fixture()
        self.marker(runtime.fight.actors[100], "invalid-policy")
        runtime.native_action_id = 1
        before = runtime_state(runtime)
        with self.assertRaisesRegex(ValueError, "another allocator"):
            runtime.prepare_delivery(prefix)
        self.assertEqual(runtime_state(runtime), before)

    def test_positive_hp_cleanup_adopts_without_replacing_batch_or_actor(self):
        runtime, prefix = self.fixture()
        actor, fight = runtime.fight.actors[100], runtime.fight
        self.marker(actor)
        counter, logical, latest = (
            runtime.native_action_id,
            runtime.action_id,
            runtime.last_native_delivery,
        )
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertNotIn("pending_restoration", actor.native_death_status)
        self.assertIs(runtime.fight, fight)
        self.assertIs(runtime.fight.actors[100], actor)
        self.assertEqual(
            (runtime.native_action_id, runtime.action_id, runtime.last_native_delivery),
            (counter, logical, latest),
        )

    def test_empty_tail_at_maximum_counter_preserves_prepared_batch(self):
        runtime, prefix = self.fixture()
        actor = runtime.fight.actors[100]
        self.marker(actor)
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertEqual(runtime.native_action_id, MAX_NATIVE_ACTION_ID)
        self.assertNotIn("pending_restoration", actor.native_death_status)

    def test_raw_foreign_packet_does_not_commit_positive_hp_cleanup(self):
        runtime, prefix = self.fixture()
        self.marker(runtime.fight.actors[100])
        before = runtime_state(runtime)
        fight, actors = runtime.fight, dict(runtime.fight.actors)
        opcode, payload = prefix[0]
        foreign = [(opcode, struct.pack(">i", runtime.fight.id + 1) + payload[4:])]
        with self.assertRaisesRegex(ValueError, "another fight"):
            runtime.prepare_delivery(foreign)
        self.assert_unchanged(runtime, before, fight, actors)

    def test_later_invalid_marker_rolls_back_earlier_actor_cleanup(self):
        runtime, prefix = self.fixture()
        self.marker(runtime.fight.actors[100])
        self.marker(runtime.fight.actors[-200], "invalid-policy")
        before = runtime_state(runtime)
        fight, actors = runtime.fight, dict(runtime.fight.actors)
        with self.assertRaisesRegex(ValueError, "Unknown pending restoration"):
            runtime.prepare_delivery(prefix)
        self.assert_unchanged(runtime, before, fight, actors)

    def test_prepared_revival_is_not_replayed_after_later_death_report(self):
        runtime, _ = self.fixture()
        runtime._reported_deaths = {100}
        revive = [(12727, struct.pack(">iiiqB", runtime.fight.id, 900, -1, 100, 1))]
        prefix = runtime.prepare_delivery(revive)
        self.assertNotIn(100, runtime._reported_deaths)
        runtime._reported_deaths.add(100)
        before = runtime_state(runtime)
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertEqual(runtime_state(runtime), before)
        self.assertIn(100, runtime._reported_deaths)

    def test_empty_tail_cleanup_does_not_replay_old_revival_bookkeeping(self):
        runtime, _ = self.fixture()
        prefix = runtime.prepare_delivery(
            [(12727, struct.pack(">iiiqB", runtime.fight.id, 900, -1, 100, 1))]
        )
        runtime._reported_deaths = {100}
        self.marker(runtime.fight.actors[100])
        self.assertIs(runtime.prepare_delivery(prefix), prefix)
        self.assertIn(100, runtime._reported_deaths)
        self.assertNotIn(
            "pending_restoration", runtime.fight.actors[100].native_death_status
        )


class PreparedSpellDeliveryCompositionTests(unittest.TestCase):
    def fixture(self):
        import test_combat_spell_transaction as spell_fixture
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        fixture = spell_fixture.SpellTransactionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        # Set policy input before preparation so the admitted transaction owns
        # the same source snapshot and carries cleanup into its preview.
        fixture.fight.actors[7].native_death_status = dict(
            getattr(fixture.fight.actors[7], "native_death_status", {}),
            pending_restoration=SOURCE,
        )
        runtime = RuntimeMessages(fixture.fight)
        return runtime, fixture.execute()

    def test_actual_prepared_spell_adopts_cleanup_in_preview_and_preserves_source(self):
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime, transaction = self.fixture()
        source = runtime.fight
        before = encode_state(source)
        preview, actor = transaction.fight, transaction.fight.actors[7]
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda *args: b"stats"
        )
        self.assertTrue(packets)
        self.assertIs(runtime.fight, preview)
        self.assertIs(runtime.fight.actors[7], actor)
        self.assertNotIn("pending_restoration", actor.native_death_status)
        self.assertEqual(runtime.action_id, transaction.action_id)
        self.assertEqual(encode_state(source), before)
        # The detached original retains its policy input and pre-cast resources.
        self.assertEqual(
            source.actors[7].native_death_status["pending_restoration"], SOURCE
        )
        self.assertEqual(source.actors[7].ap, 6)
        self.assertEqual(source.actors[-7].hp, 20)

    def test_allocator_failure_preserves_source_preview_counters_and_actor_identity(
        self,
    ):
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime, transaction = self.fixture()
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        before, preview_before = runtime_state(runtime), encode_state(transaction.fight)
        source, preview = runtime.fight, transaction.fight
        source_actors, preview_actors = dict(source.actors), dict(preview.actors)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=lambda *args: b"stats"
            )
        self.assertEqual(runtime_state(runtime), before)
        self.assertEqual(encode_state(preview), preview_before)
        self.assertIs(runtime.fight, source)
        for identity in source_actors:
            self.assertIs(source.actors[identity], source_actors[identity])
            self.assertIs(preview.actors[identity], preview_actors[identity])

    def test_observer_failure_preserves_both_graphs_after_private_cleanup(self):
        from unittest.mock import patch
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime, transaction = self.fixture()
        before, preview_before = runtime_state(runtime), encode_state(transaction.fight)
        with patch(
            "wakfu_server.combat_invariant_observation.observe_prepared_boundary",
            side_effect=ValueError("observer rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "observer rejected"):
                commit_spell_transaction(
                    runtime, transaction, stats_serializer=lambda *args: b"stats"
                )
        self.assertEqual(runtime_state(runtime), before)
        self.assertEqual(encode_state(transaction.fight), preview_before)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativePreparedRestorationTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_native_player_death_runtime_qualified as native_fixture
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        helper = native_fixture.NativePlayerDeathRuntimeTests()
        _, _, fight = helper.corpse()
        cls.prototype = RuntimeMessages(fight, clock=lambda: 0.0)
        cls.prefix = cls.prototype.prepare_delivery(death_messages(cls.prototype, 8))
        if pending_restoration_uids(fight, 8):
            raise AssertionError(
                "Native tail fixture requires exhausted/cancelled policy input"
            )
        # Native casts/KO own the corpse and QI authority. The explicit server
        # policy marker models an exhausted/cancelled retained restoration.
        fight.actors[8].native_death_status["pending_restoration"] = SOURCE

    def setUp(self):
        self.runtime = deepcopy(self.prototype)
        self.prefix_batch = self.prefix

    def test_preview_delivery_adopts_actual_finality_without_mutating_source(self):
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_qi_fight import current_registry

        runtime = self.runtime
        source = runtime.fight
        before = encode_state(source)
        preview = deepcopy(source)
        actor = preview.actors[8]
        slot = actor.native_obstacle_id
        # This is the shared preview-adoption boundary used by spell commit;
        # the corpse and QI authority come from the existing hostile-cast fixture.
        packets = runtime.prepare_fight_delivery(
            [(12873, struct.pack(">iq", preview.id, 8) + b"stats"), runtime._flush()],
            preview,
            action_id=runtime.action_id + 1,
            operation="prepared_native_corpse_regression",
        )
        self.assertEqual(encode_state(source), before)
        self.assertIs(runtime.fight, preview)
        self.assertIs(preview.actors[8], actor)
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertIsNone(current_registry(preview).slots[slot])
        self.assertEqual(
            global_fighter_guards(preview, 8), dict(baF=False, baG=False, baK=True)
        )
        final_indices = [
            index
            for index, (op, body) in enumerate(packets)
            if op == 12727 and body[-1] == 2
        ]
        self.assertEqual(len(final_indices), 1)
        self.assertGreater(
            final_indices[0],
            next(index for index, (op, _) in enumerate(packets) if op == 12873),
        )

    def test_actual_final_tail_keeps_prefix_ids_and_retires_owned_qi(self):
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_qi_fight import current_registry

        runtime, prefix = self.runtime, self.prefix_batch
        fight, actor = runtime.fight, runtime.fight.actors[8]
        slot = actor.native_obstacle_id
        counter = runtime.native_action_id
        delivered = runtime.prepare_delivery(prefix)
        self.assertEqual(delivered[: len(prefix)], tuple(prefix))
        for original, actual in zip(prefix, delivered):
            self.assertIs(original, actual)
        self.assertEqual(
            delivered.native_actions[: len(prefix.native_actions)],
            prefix.native_actions,
        )
        fresh = delivered.native_actions[len(prefix.native_actions) :]
        self.assertTrue(fresh)
        self.assertEqual(
            [row["native_action_id"] for row in fresh],
            list(range(counter + 1, counter + 1 + len(fresh))),
        )
        self.assertEqual(runtime.native_action_id, counter + len(fresh))
        self.assertTrue(
            any(op == 12727 and body[-1] == 2 for op, body in delivered[len(prefix) :])
        )
        self.assertIs(runtime.fight, fight)
        self.assertIs(runtime.fight.actors[8], actor)
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertIsNone(current_registry(fight).slots[slot])
        self.assertEqual(
            global_fighter_guards(fight, 8), dict(baF=False, baG=False, baK=True)
        )
        before = runtime_state(runtime)
        self.assertIs(runtime.prepare_delivery(delivered), delivered)
        self.assertEqual(runtime_state(runtime), before)

    def test_prepared_tail_exhaustion_preserves_full_state_and_owned_references(self):
        runtime = self.runtime
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        before = runtime_state(runtime)
        fight, actors = runtime.fight, dict(runtime.fight.actors)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            runtime.prepare_delivery(self.prefix_batch)
        self.assertEqual(runtime_state(runtime), before)
        self.assertIs(runtime.fight, fight)
        for identity, actor in actors.items():
            self.assertIs(runtime.fight.actors[identity], actor)

    def test_raw_tail_exhaustion_preserves_actual_qi_and_pending_finality(self):
        runtime = self.runtime
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        before = runtime_state(runtime)
        fight, actor = runtime.fight, runtime.fight.actors[8]
        with self.assertRaisesRegex(ValueError, "exhausted"):
            runtime.prepare_delivery([(13420, struct.pack(">i", runtime.fight.id))])
        self.assertEqual(runtime_state(runtime), before)
        self.assertIs(runtime.fight, fight)
        self.assertIs(runtime.fight.actors[8], actor)

    def test_foreign_prefix_cannot_finalize_actual_pending_corpse(self):
        runtime = self.runtime
        runtime.fight.id += 1
        before = runtime_state(runtime)
        with self.assertRaisesRegex(ValueError, "another allocator"):
            runtime.prepare_delivery(self.prefix_batch)
        self.assertEqual(runtime_state(runtime), before)


if __name__ == "__main__":
    unittest.main()
