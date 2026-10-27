"""Original eYP272/983 calculation with the real shared eWQ/PA engine."""
from dataclasses import replace
from itertools import count
from types import SimpleNamespace
import unittest

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_resource_fill import (
    NativeResourceFillHandler,
    resource_fill_amount,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_resource_pa_notifications import (
    RAW_SOURCE,
    set_resource_current,
    attach_ap_listener,
)


class ResourceFillTests(unittest.TestCase):
    def fixture(self, family=983, *, retained=True):
        from test_combat_stat_handler import StatHandlerTests

        original = StatHandlerTests()
        original.setUp()
        fight = original.fight
        for actor in fight.actors.values():
            actor.effect_stats = {2: 2, 3: 1}
            actor.effect_minima = {2: 0, 3: 0}
            actor.effect_maxima = {2: 6, 3: 3}
            actor.effect_base_minima = {2: 0, 3: 0}
            actor.effect_base_maxima = {2: 6, 3: 3}
            actor.effect_percentages = {2: 0, 3: 0}
            actor.effect_resource_raw_currents = {2: 2, 3: 1}
            actor.native_resource_raw_current_source = RAW_SOURCE
            actor.effect_frozen = frozenset()
            actor.ap, actor.mp, actor.max_ap, actor.max_mp = 2, 1, 6, 3
        packets, uids = [], count(100)
        handler = NativeResourceFillHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: next(uids),
            context=lambda *_: StatExecutionContext(True, True, None, retained, None),
            rng=lambda: 0.5,
        )
        reference = {272: 410224, 983: 410225}[family]
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", reference
        )
        self.assertIsNotNone(
            effect, "Original Spirit refill definition must be published"
        )
        self.assertEqual(
            (effect["effect_class"], effect["parameter_count"], effect["parameters"]),
            (family, 0, []),
        )
        invocation = EffectInvocation(reference, 1, 7, 7, (0, 0, 0))
        return fight, fight.actors[7], handler, effect, invocation, packets

    def test_signed_native_calculation_including_negative_and_wrap(self):
        for maximum, current, expected in (
            (6, 2, 4),
            (6, 6, 0),
            (6, 8, -2),
            (2147483647, -2147483648, -1),
            (-2147483648, 2147483647, 1),
        ):
            self.assertEqual(resource_fill_amount(maximum, current), expected)
        with self.assertRaises(ValueError):
            resource_fill_amount(True, 0)

    def test_original_both_families_fill_effective_max_and_reverse_owned_delta(self):
        for family, stat, field in ((272, 3, "mp"), (983, 2, "ap")):
            with self.subTest(family=family):
                fight, actor, handler, effect, invocation, packets = self.fixture(
                    family
                )
                initial, maximum = getattr(actor, field), actor.effect_maxima[stat]
                self.assertTrue(handler(effect, {}, invocation))
                self.assertEqual(getattr(actor, field), maximum)
                row = fight.owned_stat_effects[100]
                self.assertEqual(
                    (row["effect_class"], row["family"], row["actual"]),
                    (family, "eWQ", maximum - initial),
                )
                extra = {}
                _identity_fields(bytes.fromhex(row["payload"]), messages=extra)
                self.assertEqual(
                    _identity_fields(extra[8], integer_fields=(12, 25)),
                    {12: stat, 25: 0},
                )
                self.assertEqual([opcode for opcode, _ in packets], [12613])
                set_resource_current(fight, actor, stat, 1)
                handler.remove(100)
                self.assertEqual(getattr(actor, field), 0)
                self.assertEqual([opcode for opcode, _ in packets], [12613, 13560])
                self.assertFalse(fight.owned_stat_effects)

    def test_dynamic_percent_maximum_is_used_instead_of_base(self):
        fight, actor, handler, effect, invocation, _ = self.fixture()
        actor.effect_percentages[2] = 50
        actor.effect_maxima[2] = actor.max_ap = 9
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(
            (actor.ap, actor.max_ap, actor.effect_base_maxima[2]), (9, 9, 6)
        )
        self.assertEqual(fight.owned_stat_effects[100]["actual"], 7)

    def test_already_full_rejects_before_apply_and_does_not_lower_hidden_raw(self):
        fight, actor, handler, effect, invocation, packets = self.fixture()
        actor.ap = actor.effect_stats[2] = 6
        actor.effect_resource_raw_currents[2] = 9
        channels = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *a, channel, **k: channels.append(channel)
        )
        prepared = handler.prepare(effect, {}, invocation)
        self.assertFalse(handler(effect, {}, prepared))
        self.assertEqual((actor.ap, actor.effect_resource_raw_currents[2]), (6, 9))
        self.assertEqual(channels, [1])
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_frozen_positive_calculation_retains_actual_zero_and_native_phases(self):
        fight, actor, handler, effect, invocation, packets = self.fixture()
        actor.effect_frozen = frozenset({2})
        phases = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *a, channel, value, _event_ids, **k: phases.append(
                (channel, value, _event_ids)
            )
        )
        prepared = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, prepared))
        self.assertEqual(actor.ap, 2)
        self.assertEqual([p[0] for p in phases], [1, 2, 3, 4])
        self.assertTrue(all(51 in p[2] and 0 in p[2] for p in phases))
        self.assertEqual(fight.owned_stat_effects[100]["actual"], 0)
        self.assertEqual([opcode for opcode, _ in packets], [12613])
        handler.remove(100)
        self.assertEqual(actor.ap, 2)

    def test_l2_changes_clamp_actual_delta_and_ap_observer_uses_real_setter(self):
        fight, actor, handler, effect, invocation, _ = self.fixture()
        actor.mp = actor.effect_stats[3] = actor.effect_resource_raw_currents[3] = 0
        attach_ap_listener(fight, actor, 77)
        seen = []

        def phase(*args, channel, value, **kwargs):
            seen.append((channel, value))
            if channel == 2:
                set_resource_current(fight, actor, 2, 5)

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        prepared = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, prepared))
        self.assertEqual(fight.owned_stat_effects[100]["actual"], 1)
        self.assertEqual((actor.ap, actor.mp), (6, 3))
        self.assertEqual(seen, [(1, 0), (2, 4), (3, 1), (4, 1)])
        handler.remove(100)
        self.assertEqual((actor.ap, actor.mp), (5, 2))

    def test_native_context_overrides_calculated_amount_but_wire_request_stays_zero(
        self,
    ):
        from wakfu_server.combat_value_transfer import transfer_value_context

        fight, actor, handler, effect, invocation, _ = self.fixture()
        invocation = replace(
            invocation, native_context_hex=transfer_value_context(b"", 2).hex()
        )
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual((actor.ap, fight.owned_stat_effects[100]["actual"]), (4, 2))
        data = {}
        _identity_fields(
            bytes.fromhex(fight.owned_stat_effects[100]["payload"]), messages=data
        )
        self.assertEqual(_identity_fields(data[8], integer_fields=(25,))[25], 0)

    def test_real_absent_area_pa_is_zero_rejected_not_assumed_present(self):
        from test_combat_current_stat_area import CurrentStatAreaTests

        (
            fixture,
            fight,
            old_handler,
            invocation,
            _,
            packets,
            events,
        ) = CurrentStatAreaTests().create()
        handler = NativeResourceFillHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=old_handler.allocate_uid,
            context=old_handler.context,
            rng=lambda: 0.5,
        )
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 410224
        )
        before = fixture.snapshot(fight.native_effect_areas[901])
        self.assertFalse(handler(effect, {}, replace(invocation, reference=410224)))
        self.assertEqual(fixture.snapshot(fight.native_effect_areas[901]), before)
        self.assertEqual((fight.owned_stat_effects, packets, events), ({}, [], []))

    def test_malformed_prototype_and_missing_snapshot_fail_without_mutating_pa(self):
        fight, actor, handler, effect, invocation, packets = self.fixture()
        bad = dict(effect, parameter_count=1, parameters=[1, 0])
        with self.assertRaises(ValueError):
            handler(bad, {}, invocation)
        del actor.effect_base_minima[2]
        with self.assertRaises(ValueError):
            handler(effect, {}, invocation)
        self.assertEqual((actor.ap, actor.mp), (2, 1))
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))


if __name__ == "__main__":
    unittest.main()
