from copy import deepcopy
from dataclasses import replace
import unittest
import test_combat_effect_runtime as fixture_module
from wakfu_server.combat_runtime_adapter import (
    NativeServerRuntimeAdapter,
    NativeActorAuthority,
    NativeCastAuthority,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


class ServerAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_module.NativeRuntimeFactoryTests.setUpClass()

    def setUp(self):
        self.fixture = fixture_module.NativeRuntimeFactoryTests()
        self.fixture.setUp()
        self.preview = deepcopy(self.fixture.fight)
        self.preview.native_effect_uid_next = 200
        c = self.fixture.contexts
        self.cast = NativeCastAuthority(
            c.resolution,
            c.cell_eligible,
            c.group_cells,
            c.damage,
            c.healing,
            c.stat,
            c.state,
            lambda *a: False,
            c.probability,
            c.rounding,
        )

        def authority(p, a):
            return NativeActorAuthority(
                c.native_targets(p, {}, None, None)[a.id],
                a.controlled,
                frozenset({6266}) if a.controlled else frozenset(),
                frozenset(),
                False,
                15 if a.controlled else 1,
                0,
                {},
                True,
            )

        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=authority, cast=self.cast
        )

    def test_real_damage_uses_complete_roster_and_preview_uid(self):
        runtime = self.fixture.factory(contexts=self.adapter.contexts())
        dispatcher, packets = runtime(self.preview, {})
        dispatcher.execute(EffectInvocation(339526, 1, 7, -7, (1, 0, 0)))
        self.assertLess(self.preview.actors[-7].hp, 20)
        self.assertEqual(self.preview.actors[7].hp, 60)
        self.assertEqual(
            self.preview.actors[8].hp, 35
        )  # Native area includes this ally.
        self.assertEqual(self.preview.native_effect_uid_next, 202)
        self.assertEqual(self.fixture.fight.actors[-7].hp, 20)
        self.assertEqual(len(packets), 2)

    def test_conditions_read_mutated_preview_stats_and_deck(self):
        actor = self.preview.actors[7]
        actor.ap = 2
        actor.effect_stats[2] = 2
        context = self.adapter.condition(
            self.preview, {}, None, EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        )
        self.assertEqual(context.actors["caster"].characteristics["AP"], 2)
        self.assertEqual(context.actors["caster"].deck_spell_ids, frozenset({6266}))
        self.assertEqual(context.actors["target"].deck_spell_ids, frozenset())
        self.assertEqual(context.caster_target_distance, 1)
        self.assertTrue(context.is_in_alignment)

    def test_enemy_and_properties_read_live_actor_context(self):
        from wakfu_server.combat_conditions import evaluate_condition

        source = self.preview.actors[7]
        target = self.preview.actors[-7]
        source.native_fight_properties = frozenset({28})
        target.native_fight_properties = frozenset({1})
        invocation = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        context = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(evaluate_condition("IsEnemy()", context))
        self.assertTrue(evaluate_condition('HasFightProperty("target",1)', context))
        target.native_fight_affiliation = source.team
        target.native_fight_properties = frozenset()
        changed = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertFalse(evaluate_condition("IsEnnemy()", changed))
        self.assertFalse(evaluate_condition('HasFightProperty("target",1)', changed))
        self.assertEqual(target.team, 1)  # bcM override is independent from bcN.

    def test_missing_metadata_counter_and_rng_reject(self):
        self.preview.native_effect_uid_next = None
        with self.assertRaisesRegex(ValueError, "Initialize"):
            self.adapter.uid(self.preview, {})
        adapter = NativeServerRuntimeAdapter(
            actor_authority=lambda p, a: None, cast=self.cast
        )
        with self.assertRaisesRegex(ValueError, "property authority"):
            adapter.targets(self.preview, {}, None, None)
        for value in (True, None, -0.1, 1, float("nan")):
            adapter = NativeServerRuntimeAdapter(
                actor_authority=self.adapter.actor_authority,
                cast=replace(self.cast, random_fraction=lambda p, plan, v=value: v),
            )
            with self.assertRaises(ValueError):
                adapter.random(self.preview, {})

    def test_unknown_native_selector_and_subscription_still_fail(self):
        effect = dict(
            self.fixture.effects["339526"],
            native_target_selector={"class": "fcE", "mask": 1 << 20},
        )
        self.fixture.effects["339526"] = effect
        dispatcher, packets = self.fixture.factory(contexts=self.adapter.contexts())(
            self.preview, {}
        )
        with self.assertRaisesRegex(ValueError, "Unaudited"):
            dispatcher.execute(EffectInvocation(339526, 1, 7, -7, (1, 0, 0)))
        self.assertEqual(packets, [])

    def test_unknown_cell_metadata_does_not_block_unrelated_condition(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        adapter = NativeServerRuntimeAdapter(
            actor_authority=self.adapter.actor_authority,
            cast=replace(self.cast, cell_obstacle=lambda *args: None),
        )
        context = adapter.condition(
            self.preview, {}, None, EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        )
        self.assertTrue(evaluate_condition('GetCharac("AP", "caster") >= 1', context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsTargetCellFree()", context)


if __name__ == "__main__":
    unittest.main()
