"""Full factory wiring for native449 with complete native catalog authority."""
import unittest
from types import SimpleNamespace


class WorldPropertyRuntimeTests(unittest.TestCase):
    def test_factory_dispatches449_to_registered_target_and_preserves_other_actor(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests, definition
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fixture = NativeRuntimeFactoryTests()
        fixture.spells = {"effects": {}}
        fixture.states = {"states": {}, "effects": {}}
        fixture.registry = {"effects": {}}
        fixture.setUp()
        actor = fixture.fight.actors[7]
        actor.native_world_property_counts = {12: 2}
        actor.native_fight_property_counts = {31: 1}

        class Authority:
            def __call__(self, *args):
                return SimpleNamespace(targeting={"is_eGj": True, "bcN": 0})

            def world_property_counts(self, fight, actor):
                return actor.native_world_property_counts

            def property_counts(self, fight, actor):
                return actor.native_fight_property_counts

        effect = definition(449, [83.0, 0.0])
        effect["native_execution_mode"] = 2
        effects = dict(fixture.effects)
        effects["268501"] = effect
        dispatcher, packets = fixture.factory(
            effects=effects, displacement_authority=Authority()
        )(fixture.fight, {})
        before = (actor.hp, actor.ap, actor.mp, fixture.fight.actors[8].hp)
        dispatcher.execute(EffectInvocation(268501, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(actor.native_world_property_counts, {12: 2, 83: 1})
        self.assertEqual(actor.native_fight_property_counts, {31: 1})
        self.assertEqual(
            (actor.hp, actor.ap, actor.mp, fixture.fight.actors[8].hp), before
        )
        self.assertEqual([p[0] for p in packets], [12613])
