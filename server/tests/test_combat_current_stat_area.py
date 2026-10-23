"""eWW mute-on-absent-PA keeps native Qe lifecycle on real faW targets."""
from dataclasses import replace
import unittest
from types import SimpleNamespace

import test_combat_maximum_reduction_area as area_fixture
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_runner_callbacks import runner_value_scope
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext


class CurrentStatAreaTests(unittest.TestCase):
    def create(self, *, retained=True):
        fixture = area_fixture.MaximumReductionAreaTests()
        fight, creator, allocated, packets = fixture.create()
        fight.current = fight.actors[7]
        events = []
        fight._event = lambda *args, **kwargs: events.append((args, kwargs))
        registry = native_catalog.load(
            DATA_ROOT / "effect-characteristic-registry.json"
        )
        handler = NativeStatHandler(
            fight,
            packets,
            registry,
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *args: StatExecutionContext(
                True, True, None, retained, None
            ),
            rng=lambda: 0.5,
        )
        invocation = EffectInvocation(324818, 200, 7, 901, (2, 3, 0))
        return fixture, fight, handler, invocation, allocated, packets, events

    def test_growl_absent_resistance_retains_amount_lifecycle_without_pa_or_pr(self):
        fixture, fight, handler, invocation, _, packets, events = self.create()
        row = fight.native_effect_areas[901]
        before = fixture.snapshot(row)
        observed, final = [], []

        def phase(effect, source, *, channel, value, runner_modifier, **kwargs):
            observed.append((channel, value))
            if channel == 2:
                runner_modifier.mutate(1, 15, False)
            elif channel == 3:
                runner_modifier.mutate(1, 5, False)

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        effect = dict(
            effect_class=100, parameters=[300.0, 0.0], target_masks=[None] * 7
        )
        with runner_value_scope(lambda source, value: final.append(value)) as token:
            prepared = handler.prepare(
                effect, {}, replace(invocation, native_value_scope=token)
            )
            self.assertTrue(handler(effect, {}, prepared))
        uid = prepared.native_running_uid
        entry = fight.owned_stat_effects[uid]
        self.assertEqual(observed, [(1, 0), (2, 300), (3, 315), (4, 320)])
        self.assertEqual(final, [320])
        self.assertEqual(entry["actual"], 320)
        self.assertTrue(entry["native_absent_characteristic"])
        self.assertIsNone(entry["execution_status"])  # eWR.d(PA)/fc(0) was not called.
        self.assertEqual((packets, events), ([], []))
        self.assertEqual(fixture.snapshot(row), before)
        self.assertNotIn(901, fight.actors)
        handler.remove(uid)
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _ in packets], [13560])
        self.assertEqual(fixture.snapshot(row), before)

    def test_l3_can_remove_absent_pa_receipt_without_recreating_it(self):
        fixture, fight, handler, invocation, _, packets, events = self.create()
        before = fixture.snapshot(fight.native_effect_areas[901])
        channels = []

        def phase(effect, source, *, channel, uid, **kwargs):
            channels.append(channel)
            if channel == 3:
                self.assertTrue(
                    fight.owned_stat_effects[uid]["native_absent_characteristic"]
                )
                handler.remove(uid)

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        effect = dict(effect_class=120, parameters=[30.0, 0.0], target_masks=[None] * 7)
        prepared = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, prepared))
        self.assertEqual(channels, [1, 2, 3, 4])
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _ in packets], [13560])
        self.assertFalse(events)
        self.assertEqual(fixture.snapshot(fight.native_effect_areas[901]), before)

    def test_instant_percent_keeps_calculated_value_without_inventing_target_current(
        self,
    ):
        fixture, fight, handler, invocation, _, packets, events = self.create(
            retained=False
        )
        before = fixture.snapshot(fight.native_effect_areas[901])
        final = []
        with runner_value_scope(lambda source, value: final.append(value)) as token:
            self.assertTrue(
                handler(
                    dict(effect_class=120, parameters=[25.0, 0.0, 1.0, 0.0]),
                    {},
                    replace(invocation, native_value_scope=token),
                )
            )
        self.assertEqual(final, [25])
        self.assertEqual((fight.owned_stat_effects, packets, events), ({}, [], []))
        self.assertEqual(fixture.snapshot(fight.native_effect_areas[901]), before)

    def test_null_qf_area_context_cannot_fabricate_retention(self):
        from unittest.mock import patch
        from wakfu_server.combat_current_stat_consumer import _context

        _, fight, handler, invocation, _, _, _ = self.create()
        from wakfu_server import combat_current_stat_consumer as original

        resolve = original._target_pv
        selected = SimpleNamespace(
            id=901, native_is_area=True, native_running_effect_manager=False
        )
        with patch.object(original, "_target_pv", return_value=selected):
            target, context = _context(handler, {}, invocation)
        self.assertIs(target, selected)
        self.assertFalse(context.retained)
        self.assertTrue(context.executable)
        self.assertTrue(resolve(handler, 901).native_running_effect_manager)

    def test_corrupt_unknown_and_present_pa_do_not_become_absent_area_defaults(self):
        fixture, fight, handler, invocation, allocated, packets, events = self.create()
        before = list(allocated)
        effect = dict(effect_class=100, parameters=[300.0, 0.0])
        with self.assertRaises(ValueError):
            handler(effect, {}, replace(invocation, target_id=999))
        fight.native_effect_areas[901]["native_faw_constructor"][
            "characteristic_ids"
        ] = (1, 27)
        with self.assertRaises(ValueError):
            handler(effect, {}, invocation)
        self.assertEqual(allocated, before)
        self.assertEqual((fight.owned_stat_effects, packets, events), ({}, [], []))
        _, fight, handler, invocation, _, packets, _ = self.create()
        with self.assertRaisesRegex(ValueError, "PA writer"):
            handler(
                dict(effect_class=39, parameters=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0]),
                {},
                invocation,
            )
        self.assertEqual(packets, [])


if __name__ == "__main__":
    unittest.main()
