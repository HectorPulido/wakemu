"""Real eZl handler/registration/central removal; descriptor builder is controlled."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from test_combat_summon_effect_phases import FreshSummonPhaseTests
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation


class RetainedSummonEventMetadataTests(unittest.TestCase):
    def test_actual_retained_creation_event_replay_uses_native_empty_masks(self):
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
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeCloneAuthority,
        )
        from test_combat_event_replay import NativeEventReplayTests

        NativeEventReplayTests.setUpClass()
        original = NativeEventReplayTests()
        original.effects = original.fixture["effects"]
        event = original.source()
        row = fight.native_owned_group_effects[201]
        self.assertEqual(row["native_subscription_masks"], effect["target_masks"])
        self.assertIsNot(row["native_subscription_masks"], effect["target_masks"])
        self.assertEqual(row["native_effect_flags"], effect["native_effect_flags"])
        replay = NativeEventReplay(SimpleNamespace(), retention)
        authority = NativeCloneAuthority(
            executable=lambda *args: self.fail("non-subscribed summon executed"),
            condition_context=lambda *args: self.fail(
                "non-subscribed summon evaluated"
            ),
        )
        self.assertEqual(
            replay(
                replace(event, manager_actor_id=prepared.caster_id), authority=authority
            ),
            (),
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
