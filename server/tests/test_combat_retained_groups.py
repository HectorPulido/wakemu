import unittest
import struct
from copy import deepcopy
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime, group_payload
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.fight_checkpoint_store import snapshot
import test_combat_displacement as fixtures


class NativeRetainedGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def setUp(self):
        fixtures.NativeDisplacementTests.setUp(self)

    def test_native_group_payload_matches_three_native_runners(self):
        self.assertEqual(
            group_payload(
                uid=901,
                base_uid=800,
                generic_effect=350552,
                caster_id=7,
                target_id=-7,
                cell=(4, 5, 0),
                container_type=11,
                container_id=6266,
                timing_payload=native_time_payload(),
            ).hex(),
            "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff01480b50fa305a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
        )

    def test_native_state_child_context_bypasses_probability_only_when_explicit(self):
        retention = object.__new__(NativeRetainedRuntime)
        ordinary = EffectInvocation(308265, 1, 7, 7, (0, 0, 0))
        from dataclasses import replace

        self.assertFalse(retention.probability_bypassed(ordinary))
        self.assertTrue(
            retention.probability_bypassed(
                replace(
                    ordinary,
                    native_context_hex="0801100020ffffffffffffffffff0128013000380040004800",
                )
            )
        )
        self.assertFalse(
            retention.probability_bypassed(
                replace(
                    ordinary, native_context_hex="0800100020c80128003000380040004800"
                )
            )
        )

    def factory(self, preview=None):
        import random
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory

        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=self.effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=adapter.contexts(),
        )
        return factory(
            self.preview if preview is None else preview,
            dict(spell_id=6266, evaluation_level=1),
        )

    def test_real_subscription308265_then421_removes_group(self):
        dispatcher, packets = self.factory()
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 13497)
        uid = next(iter(self.preview.native_owned_group_effects))
        self.assertEqual(self.preview.native_retained_order, [uid])
        self.assertEqual(
            self.preview.native_owned_group_effects[uid]["invocation"]["reference"],
            308265,
        )
        # Child308266 would have created a nested group; registration never executes it.
        self.assertEqual(len(self.preview.native_owned_group_effects), 1)
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308271, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(self.preview.native_owned_group_effects, {})
        self.assertEqual(self.preview.native_retained_records, {})
        self.assertEqual([op for op, p in packets], [13497, 13560])
        self.assertEqual(struct.unpack(">qq", packets[-1][1][-16:]), (7, uid))

    def test_native_dynamic_child_context_preserves_200_override_bytes(self):
        from wakfu_server.combat_definitions import effect_profile

        self.preview.actors[7].effective_level = 200
        dispatcher, packets = self.factory()
        retention = dispatcher.group_retention
        definition = self.effects["368107"]
        self.assertEqual(
            retention.child_context(
                definition,
                effect_profile(definition, 1),
                EffectInvocation(368107, 1, 7, 7, (0, 0, 0)),
            ).hex(),
            "0800100020c80128003000380040004800",
        )

    def test_real_844_and999_subscriptions_defer_dynamic_level_and_children(self):
        dispatcher, packets = self.factory()
        for reference in (398146, 368107):
            self.assertTrue(
                dispatcher.execute(EffectInvocation(reference, 1, 7, 7, (0, 0, 0)))
            )
        self.assertEqual(
            [
                row["effect_class"]
                for row in self.preview.native_owned_group_effects.values()
            ],
            [844, 999],
        )
        self.assertEqual(self.preview.native_retained_order, [200, 201])
        self.assertEqual(self.preview.owned_stat_effects, {})

    def test_group_removal_preserves_separately_owned_characteristic(self):
        dispatcher, packets = self.factory()
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308267, 1, 7, 7, (0, 0, 0)))
        )
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(self.preview.native_retained_order, [200, 201])
        self.assertTrue(
            dispatcher.execute(EffectInvocation(308271, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(set(self.preview.owned_stat_effects), {200})
        self.assertEqual(self.preview.native_retained_order, [200])

    def test_due_group_expiration_removes_wire_and_central_record_atomically(self):
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        dispatcher, packets = self.factory()
        dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
        timer = self.preview.native_owned_group_effects[200]["timer"]
        after, outbox = prepare_timed_expiration(
            self.preview,
            actor_id=timer["actor_id"],
            round_number=timer["expiration_round"],
            phase=timer["phase"],
            action_id=2,
            registry=self.fixture.registry,
        )
        self.assertEqual(after.native_owned_group_effects, {})
        self.assertEqual(after.native_retained_records, {})
        self.assertEqual(after.native_retained_order, [])
        self.assertEqual([op for op, p in outbox], [13560])
        self.assertIn(200, self.preview.native_owned_group_effects)

    def test_checkpoint_records_group_order_uid_and_timer(self):
        dispatcher, packets = self.factory()
        dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))
        state = snapshot(self.preview)
        self.assertEqual(state["native_retained_order"], [200])
        self.assertEqual(state["native_effect_uid_next"], 201)
        self.assertEqual(
            state["native_owned_group_effects"]["200"]["timer"]["actor_id"], 7
        )
        self.assertTrue(state["native_retained_tracking"])

    def test_untracked_population_rejected_without_attestation_override(self):
        self.preview.native_retained_tracking = False
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.factory()

    def test_rollback_later_unhandled_keeps_original_uid_group_and_order(self):
        from wakfu_server.combat_effect_dispatch import run_effect_transaction

        original = deepcopy(self.preview)

        def missing_later_handler(preview):
            dispatcher, _ = self.factory(preview)
            # Explicitly omit one runner in this fixture. The rollback contract
            # must not depend on a production family remaining unsupported.
            dispatcher.handlers.pop(421)
            return dispatcher

        with self.assertRaisesRegex(
            ValueError, "No handler for native effect class 421"
        ):
            run_effect_transaction(
                self.preview,
                [
                    EffectInvocation(308265, 1, 7, 7, (0, 0, 0)),
                    EffectInvocation(308271, 1, 7, 7, (0, 0, 0)),
                ],
                missing_later_handler,
            )
        self.assertEqual(
            self.preview.native_owned_group_effects, original.native_owned_group_effects
        )
        self.assertEqual(
            self.preview.native_retained_order, original.native_retained_order
        )
        self.assertEqual(
            self.preview.native_effect_uid_next, original.native_effect_uid_next
        )


if __name__ == "__main__":
    unittest.main()
