"""Actual native glyph1697 receives eWR129 without inventing PC48."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

import test_combat_fake_fighter_area as area_fixture
import test_combat_maximum_reduction_area as reduction_fixture
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_runner_callbacks import runner_value_scope
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_state_managers import registered_area_pv
from wakfu_server.combat_maximum_resource import _reduction_area_lacks_characteristic


class PlainAreaCurrentStatTests(unittest.TestCase):
    def create(self):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        self.assertTrue(
            creator(
                {"effect_class": 314},
                {"parameters": [1697, 75]},
                EffectInvocation(328687, 75, 7, None, (2, 3, 0)),
            )
        )
        fight.phase = "active"
        fight.current = fight.actors[7]
        fight.owned_stat_effects = {}
        fight._event = lambda *_args, **_kwargs: None
        packets.clear()
        self.assertEqual(fight.native_effect_areas[901]["native_area_contract"], "faY")
        registered_area_pv(fight, 901)
        handler = NativeStatHandler(
            fight,
            packets,
            native_catalog.load(DATA_ROOT / "effect-characteristic-registry.json"),
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *_: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0.5,
        )
        return fight, handler, packets

    def test_actual_glyph_eWR129_preserves_calculated_amount_and_no_pa(self):
        fight, handler, packets = self.create()
        snapshot = reduction_fixture.MaximumReductionAreaTests().snapshot
        area = fight.native_effect_areas[901]
        before = snapshot(area)
        observed, values = [], []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda _e, _i, **kw: observed.append(kw["channel"])
        )
        effect = dict(effect_class=129, parameters=[10.0, 0.0], target_masks=[None] * 7)
        invocation = EffectInvocation(328687, 75, 7, 901, (2, 3, 0))
        with runner_value_scope(lambda _source, value: values.append(value)) as token:
            prepared = handler.prepare(
                effect, {}, replace(invocation, native_value_scope=token)
            )
            self.assertTrue(handler(effect, {}, prepared))
        self.assertEqual(observed, [1, 2, 3, 4])
        self.assertEqual(values, [10])
        self.assertEqual(snapshot(area), before)
        self.assertNotIn(901, fight.actors)
        self.assertEqual(packets, [])
        for uid, row in tuple(fight.owned_stat_effects.items()):
            self.assertTrue(row["native_absent_characteristic"])
            self.assertEqual(row["stat_id"], 48)
            handler.remove(uid)
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual(snapshot(area), before)

    def test_unknown_or_changed_area_identity_still_rejects(self):
        fight, _, _ = self.create()
        with self.assertRaises(ValueError):
            _reduction_area_lacks_characteristic(fight, 9999, 48)
        fight.native_effect_areas[901]["native_area_contract"] = "unknown"
        with self.assertRaises(ValueError):
            _reduction_area_lacks_characteristic(fight, 901, 48)
