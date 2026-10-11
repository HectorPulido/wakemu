"""Full-factory integration; requires the complete installed native catalog."""
import unittest
from test_combat_hp_maximum_reduction import SOURCE, snapshot


class HPMaximumReductionRuntimeTests(unittest.TestCase):
    def test_factory_dispatches_family21_and_preserves_other_actor(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests, definition
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fixture = NativeRuntimeFactoryTests()
        fixture.spells = {"effects": {}}
        fixture.states = {"states": {}, "effects": {}}
        fixture.registry = {"effects": {}}
        fixture.setUp()
        a = fixture.fight.actors[7]
        a.effect_base_maxima = dict(a.effect_maxima)
        a.effect_base_minima = dict(a.effect_minima)
        a.effect_percentages = {key: 0 for key in a.effect_stats}
        a.max_hp = a.effect_maxima[1] = a.effect_base_maxima[1] = 100
        a.native_hp_raw_current_source = SOURCE
        a.effect_hp_raw_current = 60
        effect = definition(21, [25.0, 0.0])
        effect["native_execution_mode"] = 2
        effects = dict(fixture.effects)
        effects["111893"] = effect
        dispatcher, packets = fixture.factory(effects=effects)(fixture.fight, {})
        dispatcher.execute(EffectInvocation(111893, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(snapshot(a), [35, 75, 0, 35])
        self.assertEqual(fixture.fight.actors[8].hp, 40)
        self.assertEqual([p[0] for p in packets], [12613])
