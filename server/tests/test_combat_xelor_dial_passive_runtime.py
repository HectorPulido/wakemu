"""Owned Xelor clock layouts against independent native point definitions."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers


# Actual anE points exported from 313199's ordered children 313201..313223.
# The 7189 branch 313226 exports each corresponding coordinate doubled.
HOUR_POINTS = (
    (2, 1),
    (1, 2),
    (0, 3),
    (-1, 2),
    (-2, 1),
    (-3, 0),
    (-2, -1),
    (-1, -2),
    (0, -3),
    (1, -2),
    (2, -1),
    (3, 0),
)


class XelorDialPassiveRuntimeTests(unittest.TestCase):
    def test_time_slowdown_selects_native_reversed_hour_layout_with_control(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        center = (-11, -7, -1)
        results, traces = {}, {}
        execute = EffectDispatcher.execute
        for enabled in (False, True):
            data = helper.fixture(passives=(7189,) if enabled else ())
            origin = data[2].actors[7].position
            self.assertEqual(origin, (-8, -7, -1))
            # Native anE west orientation rotates (x,y) to (-x,-y).
            # eYg.at admits only actual QI.R/X/aK selected columns. Read their
            # attested heights without calling the production group helper.
            columns = {}
            for x, y, z in data[2].walkable:
                if z != -32768:
                    self.assertNotIn((x, y), columns)
                    columns[x, y] = z
            scale = 2 if enabled else 1
            expected, excluded = {}, {}
            for reference, (x, y) in zip(range(1546, 1558), HOUR_POINTS):
                xy = (center[0] - scale * x, center[1] - scale * y)
                if xy in columns:
                    expected[reference] = (*xy, columns[xy])
                else:
                    excluded[reference] = xy
            trace, delivered = [], {}

            def observe(dispatcher, invocation, **kwargs):
                effect = dispatcher.effects.get(str(invocation.reference), {})
                result = execute(dispatcher, invocation, **kwargs)
                if invocation.reference in (313199, 313226, 313460, 313485):
                    trace.append((invocation.reference, result))
                if effect.get("effect_class") == 315:
                    area = int(effect["parameters"][0])
                    if 1546 <= area <= 1557:
                        delivered[area] = (invocation.cell, result)
                return result

            with patch.object(EffectDispatcher, "execute", observe):
                tx = helper.cast(data, 5345, center)
            actual = {
                r["reference"]: tuple(r["cell"])
                for r in tx.fight.native_effect_areas.values()
                if r.get("owner_id") == 7 and 1546 <= r["reference"] <= 1557
            }
            evidence = dict(
                enabled=enabled,
                expected=expected,
                excluded=excluded,
                delivered=delivered,
                trace=trace,
            )
            self.assertEqual(actual, expected, evidence)
            self.assertEqual(set(delivered), set(expected), evidence)
            self.assertTrue(all(ok for _, ok in delivered.values()), evidence)
            self.assertTrue(set(excluded).isdisjoint(actual), evidence)
            selected = {ref for ref, ok in trace if ok}
            self.assertTrue(
                selected & ({313226, 313485} if enabled else {313199, 313460}), evidence
            )
            self.assertFalse(
                selected & ({313199, 313460} if enabled else {313226, 313485}), evidence
            )
            results[enabled], traces[enabled] = actual, evidence
        self.assertEqual(len(results[False]), 12, traces)
        self.assertTrue(traces[True]["excluded"], traces)
        self.assertNotEqual(results[False], results[True], traces)
