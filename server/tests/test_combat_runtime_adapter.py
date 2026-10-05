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

    def test_melee_reads_actual_source_pair_and_physical_radii(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        self.preview.actors[7].position = (0, 0, 0)
        self.preview.actors[-7].position = (5, 0, 0)
        inv = EffectInvocation(339526, 1, 7, 7, (0, 0, 0))
        source = {"caster_id": 7, "target_id": -7, "effect_flags": []}
        context = self.adapter.condition(
            self.preview, {}, None, replace(inv, native_trigger_context=source)
        )
        self.assertFalse(evaluate_condition("IsTriggeredByMeleeEffect()", context))
        self.preview.actors[7].physical_radius = 1
        self.preview.actors[-7].physical_radius = 2
        context = self.adapter.condition(
            self.preview, {}, None, replace(inv, native_trigger_context=source)
        )
        self.assertTrue(evaluate_condition("IsTriggeredByMeleeEffect()", context))
        source["target_id"] = 999
        context = self.adapter.condition(
            self.preview, {}, None, replace(inv, native_trigger_context=source)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsTriggeredByMeleeEffect()", context)

    def test_same_trigger_caster_compares_registered_objects_not_listener_target(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        inv = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        for source, expected in (
            (None, False),
            ({"caster_id": None}, False),
            ({"caster_id": 7}, True),
            ({"caster_id": -7}, False),
        ):
            current = replace(inv, native_trigger_context=source)
            context = self.adapter.condition(self.preview, {}, None, current)
            self.assertEqual(
                evaluate_condition(
                    "GetTriggeringEffectCasterIsSameAsCaster()", context
                ),
                expected,
            )
        for source in ({}, {"caster_id": 999}):
            context = self.adapter.condition(
                self.preview, {}, None, replace(inv, native_trigger_context=source)
            )
            with self.assertRaises(UnknownCondition):
                evaluate_condition("GetTriggeringEffectCasterIsSameAsCaster()", context)

    def test_summon_breed_reads_live_direct_owner_without_ko_or_recursive_filters(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        original = self.adapter.actor_authority
        owners = {identity: None for identity in self.preview.actors}
        owners[-7] = 7

        def authority(preview, actor):
            metadata = original(preview, actor)
            return replace(
                metadata, targeting=dict(metadata.targeting, dpu_id=owners[actor.id])
            )

        self.adapter.actor_authority = authority
        context = self.adapter.condition(
            self.preview, {}, None, EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        )
        self.assertTrue(evaluate_condition("HasSummonWithBreed(1)", context))
        self.preview.actors[-7].hp = 0
        self.assertTrue(evaluate_condition("HasSummonWithBreed(1)", context))
        owners[-7] = -7
        self.assertFalse(evaluate_condition("HasSummonWithBreed(1)", context))
        owners[-7] = 999
        with self.assertRaisesRegex(UnknownCondition, "registered native dpu"):
            evaluate_condition("HasSummonWithBreed(1)", context)

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

    def test_distance_to_empty_cell_uses_native_radius_and_not_target_actor(self):
        from wakfu_server.combat_conditions import evaluate_condition

        self.preview.actors[7].position = (0, 0, 0)
        self.preview.actors[7].physical_radius = 1
        context = self.adapter.condition(
            self.preview, {}, None, EffectInvocation(339526, 1, 7, None, (3, 3, 9))
        )
        self.assertEqual(context.caster_target_distance, 4)
        self.assertTrue(
            evaluate_condition("GetDistanceBetweenCasterAndTarget() == 4", context)
        )
        self.assertNotIn("target", context.actors)

    def test_coordinates_follow_live_actor_or_explicit_cell_target(self):
        from wakfu_server.combat_conditions import evaluate_condition

        actor = self.preview.actors[-7]
        actor.position = (17, -8, -2)
        invocation = EffectInvocation(339526, 1, 7, -7, (99, 99, 0))
        context = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition('GetX("target") == 17 and GetZ("target") == -2', context)
        )
        actor.position = (-3, 8, 1)
        changed = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(evaluate_condition('GetX("target") == -3', changed))
        cell = replace(invocation, target_id=None, cell=(12, -4, -1))
        context = self.adapter.condition(self.preview, {}, None, cell)
        self.assertTrue(
            evaluate_condition('GetX("target") == 12 and GetY("target") == -4', context)
        )

    def test_backstabbed_uses_live_orientation_instead_of_clicked_cell(self):
        from wakfu_server.combat_conditions import evaluate_condition

        self.preview.actors[7].position = (0, 0, 0)
        self.preview.actors[7].direction = 1
        self.preview.actors[-7].position = (-1, 0, 0)
        self.preview.actors[-7].direction = 5
        self.preview.actors[7].native_fight_properties = frozenset()
        self.preview.actors[-7].native_fight_properties = frozenset()
        invocation = EffectInvocation(339526, 1, 7, -7, (99, 99, 0))
        context = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition('IsBackstabbed() and IsBackstabbed("target")', context)
        )
        self.preview.actors[7].direction = 5
        self.assertFalse(evaluate_condition("IsBackstabbed()", context))
        cell = replace(invocation, target_id=None)
        self.assertFalse(
            evaluate_condition(
                "IsBackstabbed()", self.adapter.condition(self.preview, {}, None, cell)
            )
        )

    def test_controller_deck_comes_from_explicit_controller_actor(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        ordinary = self.adapter.actor_authority
        self.adapter.actor_authority = lambda p, a: replace(
            ordinary(p, a), native_controller_id=7 if a.id == -7 else None
        )
        invocation = EffectInvocation(339526, 1, -7, 8, (1, 0, 0))
        context = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition('IsSpellInDeck(6266, "casterController")', context)
        )
        self.assertFalse(evaluate_condition('IsSpellInDeck(6266, "caster")', context))
        self.adapter.actor_authority = ordinary
        context = self.adapter.condition(self.preview, {}, None, invocation)
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsSpellInDeck(6266, "casterController")', context)

    def test_team_selector_uses_trigger_source_and_preserves_unknown(self):
        from dataclasses import replace
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        original = EffectInvocation(1, 1, 7, -7, (1, 0, 0))
        context = self.adapter.condition(
            self.preview,
            {},
            None,
            replace(original, native_trigger_context={"caster_id": -7, "target_id": 7}),
        )
        self.assertTrue(
            evaluate_condition(
                'GetTeamId("triggeringCaster") == GetTeamId("target")', context
            )
        )
        self.assertTrue(
            evaluate_condition(
                'GetTeamId("triggeringTarget") == GetTeamId("caster")', context
            )
        )
        self.assertTrue(evaluate_condition('GetTeamId("unknown") == -1', context))
        absent = self.adapter.condition(self.preview, {}, None, original)
        self.assertTrue(
            evaluate_condition('GetTeamId("triggeringCaster") == -1', absent)
        )
        unknown = self.adapter.condition(
            self.preview,
            {},
            None,
            replace(original, native_trigger_context={"caster_id": 99999}),
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetTeamId("triggeringCaster") == 0', unknown)

    def test_trigger_identity_reads_source_not_rebound_listener(self):
        from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition

        original = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        invocation = replace(
            original, native_trigger_context={"caster_id": -7, "target_id": 8}
        )
        context = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringEffectCaster() == -7 and GetTriggeringEffectTarget() == 8",
                context,
            )
        )
        null_target = replace(
            invocation, native_trigger_context={"caster_id": -7, "target_id": None}
        )
        context = self.adapter.condition(self.preview, {}, None, null_target)
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectTarget() == -1", context)
        )
        unknown = replace(
            invocation, native_trigger_context={"caster_id": 99999, "target_id": 8}
        )
        context = self.adapter.condition(self.preview, {}, None, unknown)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectCaster() == 99999", context)

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

    def test_original_controller_query_can_keep_listener_target_while_arguments_rebind(
        self,
    ):
        from wakfu_server.combat_conditions import evaluate_condition

        previous = self.adapter.actor_authority
        self.adapter.actor_authority = lambda p, a: replace(
            previous(p, a), native_controller_id=a.id
        )
        invocation = EffectInvocation(
            339526, 1, 7, -7, (1, 0, 0), native_trigger_context={"target_id": 8}
        )
        ordinary = self.adapter.condition(self.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition("GetEffectTargetOriginalController() == -7", ordinary)
        )
        clone = self.adapter.condition(
            self.preview, {}, None, invocation, native_original_target_id=7
        )
        self.assertTrue(
            evaluate_condition("GetEffectTargetOriginalController() == 7", clone)
        )
        self.assertEqual(clone.actors["target"].actor_id, -7)
        self.assertEqual(clone.triggering_effect_target_id, 8)
        empty = self.adapter.condition(
            self.preview, {}, None, invocation, native_original_target_id=None
        )
        self.assertTrue(
            evaluate_condition("GetEffectTargetOriginalController() == 0", empty)
        )
