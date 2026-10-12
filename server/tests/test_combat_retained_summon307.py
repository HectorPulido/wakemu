"""Real eZl handler/registration/central removal; descriptor builder is controlled."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from test_combat_summon_effect_phases import FreshSummonPhaseTests
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation


class RetainedSummonTests(unittest.TestCase):
    def test_retained_creation_removal_preserves_actual_summon_registration(self):
        fixture = FreshSummonPhaseTests()
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = fixture.make_handler()
        source = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual389097.json"
            ).read_text()
        )
        effect.update(source)
        effect["parameters"] = [999.0, 0.0]
        original_context = handler.context
        handler.context = lambda *args: replace(original_context(*args), retained=True)
        fight.native_retained_tracking = True
        metadata = {
            "effects": {
                "313167": json.loads(
                    (
                        Path(__file__).parent
                        / "fixtures/next_central_recovery"
                        / "actual389097-metadata.json"
                    ).read_text()
                )
            }
        }
        metadata["effects"]["313167"]["parameters"] = [999.0, 0.0]
        retention = NativeRetainedRuntime(
            fight,
            handler.packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=9,
            timing=None,
            metadata=metadata,
        )
        retention.stat_handler = SimpleNamespace(fight=fight, registry={})
        handler.retained_application = retention.register_applied_summon
        patches = fixture._native_dependencies()
        with patches[0], patches[1]:
            prepared = handler.prepare(effect, values, invocation)
            self.assertTrue(retention.wrap(handler)(effect, values, prepared))
        self.assertEqual(allocated, [201, 202])
        self.assertIn(202, fight.actors)
        self.assertEqual(fight.native_retained_order, [201])
        self.assertEqual(
            fight.native_owned_group_effects[201]["native_summon_actor_id"], 202
        )
        before_actor = fight.actors[202]
        before_order = list(fight.order)
        before_registration = dict(fight.native_summon_registrations[202])
        removal = retention.removal(retention.view())
        removal.remove((201,))
        self.assertIs(fight.actors[202], before_actor)
        self.assertEqual(fight.order, before_order)
        self.assertEqual(fight.native_summon_registrations[202], before_registration)
        self.assertEqual(fight.native_owned_group_effects, {})
        self.assertEqual(fight.native_retained_records, {})
        self.assertEqual(handler.packets[-1][0], 13560)

    def test_retained_direct_handler_without_central_authority_stays_rejected(self):
        fixture = FreshSummonPhaseTests()
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = fixture.make_handler()
        original_context = handler.context
        handler.context = lambda *args: replace(original_context(*args), retained=True)
        before = set(fight.actors)
        patches = fixture._native_dependencies()
        with patches[0], patches[1]:
            prepared = handler.prepare(effect, values, invocation)
            with self.assertRaisesRegex(
                ValueError, "retained/subscribed summon lifecycle"
            ):
                handler(effect, values, prepared)
        self.assertEqual(set(fight.actors), before)
        self.assertEqual(handler.packets, [])

    def test_replayed_unprepared_summon_stays_rejected_with_registration_callback(self):
        fixture = FreshSummonPhaseTests()
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = fixture.make_handler()
        handler.retained_application = lambda *a, **kw: self.fail("unprepared callback")
        before = set(fight.actors)
        with self.assertRaisesRegex(ValueError, "retained/subscribed summon lifecycle"):
            handler(effect, values, replace(invocation, native_running_uid=999))
        self.assertEqual(set(fight.actors), before)

    def test_cell307_removal_requires_actual_native_actor_additional_data(self):
        from wakfu_server.combat_stat_effects import owned_effect_payload
        from wakfu_server.combat_effect_removal import running_effect_removal

        payload = owned_effect_payload(
            uid=901,
            base_uid=901,
            generic_effect=313167,
            caster_id=7,
            target_id=7,
            value=999,
        )
        with self.assertRaises(ValueError):
            running_effect_removal(
                77,
                9,
                effect_class=307,
                target_id=7,
                uid=901,
                running_effect_payload=payload,
            )

    def test_subscribed_retained_creation_rejects_before_build_even_with_callback(self):
        fixture = FreshSummonPhaseTests()
        (
            fight,
            handler,
            builder,
            effect,
            values,
            invocation,
            observations,
            allocated,
        ) = fixture.make_handler()
        original_context = handler.context
        handler.context = lambda *args: replace(original_context(*args), retained=True)
        handler.retained_application = lambda *a, **kw: self.fail("subscribed callback")
        effect["target_masks"][5] = [1001]
        before = set(fight.actors)
        patches = fixture._native_dependencies()
        with patches[0], patches[1]:
            prepared = handler.prepare(effect, values, invocation)
            with self.assertRaisesRegex(ValueError, "subscribed summon lifecycle"):
                handler(effect, values, prepared)
        self.assertEqual(set(fight.actors), before)
        self.assertEqual(builder.created, [])
        self.assertEqual(handler.packets, [])

    def test_duplicate_native_actor_message_cannot_attest_retained_summon(self):
        from wakfu_server.combat_retained_summon import retained_summon_actor
        from wakfu_server.combat_summon import summon_additional_payload

        one = summon_additional_payload(202)
        self.assertEqual(retained_summon_actor(one), 202)
        with self.assertRaisesRegex(ValueError, "exactly one native iR"):
            retained_summon_actor(one + one)
