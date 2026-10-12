"""NEW real factory controls using unchanged sealed AIR635 definitions.

These are bounded runtime unit fixtures, not monster qualification receipts.
"""
import json, struct, unittest
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import test_combat_random_earth_damage as baseline
from test_combat_ordinary_damage_events import OrdinaryDamageEventsTests
from wakfu_server.combat_effect_dispatch import EffectInvocation, run_effect_transaction
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server import combat_effect_runtime as runtime

W = Path(__file__).resolve().parent / "fixtures/native635"
EFFECTS = json.loads((W / "native635-effects.json").read_text())
METADATA = json.loads((W / "native635-retained-rows.json").read_text())


class Native635ActualRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OrdinaryDamageEventsTests.setUpClass()

    def setUp(self):
        import test_combat_event_replay as native_fixture

        fixture = OrdinaryDamageEventsTests()
        copied = deepcopy(native_fixture.NativeEventReplayTests.fixture)
        for ref, row in copied["retained_metadata"]["effects"].items():
            row["event_execution_count_per_level"] = baseline.SEALED_NATIVE_METADATA[
                ref
            ]["event_execution_count_per_level"]
        with patch.object(native_fixture.NativeEventReplayTests, "fixture", copied):
            fixture.setUp()
        fixture.f.fixture = copied
        from wakfu_server.combat_summon import RegisteredSummonAuthority

        fixture.adapter.actor_authority = RegisteredSummonAuthority(
            fixture.adapter.actor_authority
        )
        self.fixture = fixture
        self.fight = fixture.fight
        self.seen = []
        self.dispatcher, self.packets = self.build(self.fight)
        self.inv = EffectInvocation(272669, 173, 7, -7, (1, 0, 0))

    def build(self, fight):
        effects = deepcopy(self.fixture.f.effects)
        effects.update(deepcopy(EFFECTS))
        metadata = deepcopy(self.fixture.f.fixture["retained_metadata"])
        metadata["effects"].update(deepcopy(METADATA))
        factory = runtime.NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog={"effects": {}, "states": []},
            characteristic_registry={"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            contexts=self.fixture.adapter.contexts(),
            summon_authority=self.fixture.adapter.actor_authority,
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=metadata,
        ):
            return factory(fight, dict(spell_id=6708, evaluation_level=173))

    execute = baseline.RealRuntimeTests.execute

    def prepared_owner(self):
        # Retention forwards this bound method from the real handler instance.
        cancel = self.dispatcher.handlers[635].cancel_prepared
        self.assertTrue(callable(cancel))
        return cancel.__self__

    def test_exact_native_flags22_air_child5_distinct_uid_and_wire(self):
        self.assertEqual(EFFECTS["272669"]["native_effect_flags"], [22])
        self.assertEqual(EFFECTS["272670"]["native_effect_flags"], [22])
        original = deepcopy(EFFECTS)
        self.assertTrue(self.execute())
        parent = [r for r in self.seen if r[2] == 635]
        child = [r for r in self.seen if r[2] == 5]
        self.assertEqual({r[1] for r in parent}, {901})
        self.assertEqual({r[1] for r in child}, {902})
        self.assertEqual({r[3] for r in self.seen}, {272669})
        self.assertEqual({r[5] for r in parent}, {"Qe"})
        self.assertEqual({r[5] for r in child}, {"eXt"})
        self.assertEqual(len(self.packets), 1)
        self.assertEqual(struct.unpack_from(">i", self.packets[0][1], 13)[0], 5)
        self.assertLess(self.fight.actors[-7].hp, 12000)
        self.assertEqual(self.prepared_owner().prepared, {})
        self.assertEqual(EFFECTS, original)

    def test_native272670_inverse_criterion_remains_rejected_without_state(self):
        before = snapshot(self.fight)
        self.assertFalse(self.execute(replace(self.inv, reference=272670)))
        self.assertEqual(self.packets, [])
        # Native preparation allocates Qe before PK criterion evaluation; rejection
        # cancels its local runner without rewinding the persisted monotonic UID.
        # Full transaction failure rollback is checked separately below.
        expected = deepcopy(before)
        expected["native_effect_uid_next"] += 1
        self.assertEqual(snapshot(self.fight), expected)
        self.assertEqual([r[0] for r in self.seen], [10, 1])
        self.assertTrue(all(r[2] == 635 for r in self.seen))
        self.assertEqual(self.prepared_owner().prepared, {})

    def test_actual_pb75_blocks_child_after_calculation(self):
        target = self.fight.actors[-7]
        counts = dict(
            self.fixture.adapter.actor_authority.property_counts(self.fight, target)
        )
        counts[75] = -1
        target.native_fight_property_counts = counts
        self.assertTrue(self.execute())
        self.assertEqual([r[0] for r in self.seen if r[2] == 5], [10, 1])
        self.assertEqual(self.packets, [])
        self.assertEqual(target.hp, 12000)
        self.assertEqual(self.prepared_owner().prepared, {})

    def test_cancelled_parent_has_no_child_damage_or_retained_uid(self):
        from wakfu_server.combat_effects import _integer

        context = b"".join(
            _integer(k, v)
            for k, v in (
                (1, 0),
                (2, 0),
                (4, -1),
                (5, 1),
                (6, 0),
                (7, 0),
                (8, 1),
                (9, 0),
            )
        )
        self.assertFalse(
            self.execute(replace(self.inv, native_context_hex=context.hex()))
        )
        self.assertEqual([r[0] for r in self.seen], [10, 1])
        self.assertTrue(all(r[2] == 635 for r in self.seen))
        self.assertEqual(self.packets, [])
        self.assertEqual(self.prepared_owner().prepared, {})

    def test_factory_preserves_elemental_and_order_hook_registrations(self):
        for family in (635, 636, 327, 328, 342):
            with self.subTest(family=family):
                self.assertIn(family, self.dispatcher.handlers)
                self.assertTrue(callable(self.dispatcher.handlers[family]))

    def test_actual_damage_then_transaction_failure_restores_source_and_identity(self):
        from types import SimpleNamespace

        before = snapshot(self.fight)
        target = self.fight.actors[-7]

        def factory(preview):
            dispatcher, packets = self.build(preview)

            def execute(inv):
                self.assertTrue(dispatcher.execute(inv))
                self.assertEqual(len(packets), 1)
                self.assertLess(preview.actors[-7].hp, 12000)
                raise ValueError("after actual AIR635 child")

            return SimpleNamespace(execute=execute)

        with self.assertRaisesRegex(ValueError, "actual AIR635"):
            run_effect_transaction(self.fight, [self.inv], factory)
        self.assertEqual(snapshot(self.fight), before)
        self.assertIs(self.fight.actors[-7], target)
