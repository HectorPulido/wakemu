"""Actual detached SELF eWN construction, without roster insertion."""
from dataclasses import replace
import unittest

import test_combat_maximum_resource as fixture
from wakfu_server.combat_summon_creation import native_fresh_summon_authority
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_maximum_resource import (
    remove_maximum_resource,
    NativeMaximumReductionHandler,
    NativePercentageHPHandler,
    remove_maximum_reduction,
    remove_percentage_hp,
)


class DetachedMaximumConstructorTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.MaximumResourceTests()
        self.f.setUp()
        self.actor = self.f.actor
        del self.f.fight.actors[self.actor.id]
        self.actor.team = -1
        self.actor.native_summon_action_book = {"profile": 3798, "actions": []}
        self.actor.native_fight_property_counts = {0: 1}
        self.authority = native_fresh_summon_authority(self.actor, 3798)
        self.f.fight.phase = "placement"

    def scope(self):
        return detached_summon_scope(self.f.fight, self.actor, self.authority)

    def test_self_constructor_changes_actual_detached_actor_and_removes_effect(self):
        roster = dict(self.f.fight.actors)
        with self.scope():
            self.assertTrue(self.f.apply(kind=31, amount=2))
            self.assertEqual((self.actor.ap, self.actor.max_ap), (8, 8))
            self.assertNotIn(self.actor.id, self.f.fight.actors)
            self.assertEqual(
                self.f.fight.owned_stat_effects[101]["target_id"], self.actor.id
            )
            remove_maximum_resource(self.f.handler, 101)
            self.assertEqual((self.actor.ap, self.actor.max_ap), (6, 6))
        self.assertEqual(self.f.fight.actors, roster)
        self.assertEqual([packet[0] for packet in self.f.packets], [12613, 13560])

    def test_absent_constructor_scope_is_rejected_without_mutation(self):
        with self.assertRaisesRegex(ValueError, "actors/fight"):
            self.f.apply(kind=31)
        self.assertEqual((self.actor.ap, self.actor.max_ap, self.f.uid), (6, 6, 100))
        self.assertEqual(self.f.packets, [])

    def test_constructor_does_not_grant_cross_actor_effects(self):
        with self.scope():
            self.f.invocation = replace(self.f.invocation, target_id=-7)
            with self.assertRaisesRegex(ValueError, "actors/fight"):
                self.f.apply(kind=31)
        self.assertEqual(self.f.packets, [])

    def test_detached_target_is_not_legal_for_registered_caster_in_active_fight(self):
        self.f.fight.phase = "active"
        with self.scope():
            self.f.invocation = replace(self.f.invocation, caster_id=-7)
            with self.assertRaisesRegex(ValueError, "actors/fight"):
                self.f.apply(kind=31)
        self.assertEqual(self.actor.ap, 6)

    def test_detached_constructor_still_requires_verified_stat_guards(self):
        self.f.handler.context = lambda *args: replace(
            fixture.StatExecutionContext(True, True, None, True, None, None),
            source_guards_verified=False,
        )
        with self.scope(), self.assertRaisesRegex(ValueError, "guards"):
            self.f.apply(kind=31)
        self.assertEqual(self.f.packets, [])

    def test_registered_actor_in_placement_still_rejected(self):
        self.f.fight.actors[self.actor.id] = self.actor
        with self.assertRaisesRegex(ValueError, "actors/fight"):
            self.f.apply(kind=31)
        self.assertEqual(self.f.packets, [])


class DetachedReductionPercentageConstructorTests(unittest.TestCase):
    def setUp(self):
        self.f = DetachedMaximumConstructorTests()
        self.f.setUp()
        actor = self.f.actor
        for name, value in (
            ("effect_stats", 60),
            ("effect_maxima", 60),
            ("effect_base_maxima", 60),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            getattr(actor, name)[1] = value

    def handler(self, kind):
        cls = (
            NativePercentageHPHandler if kind == 986 else NativeMaximumReductionHandler
        )
        return cls(
            self.f.f.fight,
            self.f.f.packets,
            action_id=1,
            allocate_uid=self.f.f.handler.allocate_uid,
            context=self.f.f.handler.context,
        )

    def apply(self, kind, invocation=None):
        handler = self.handler(kind)
        parameters = [50, 0, 0, 0, 0, 0] if kind == 986 else [1, 0]
        result = handler(
            dict(effect_class=kind, parameters=parameters),
            {},
            invocation or self.f.f.invocation,
        )
        return handler, result

    def test_constructor_percentage_hp_applies_and_reverses_actual_actor(self):
        with self.f.scope():
            handler, result = self.apply(986)
            self.assertTrue(result)
            self.assertEqual((self.f.actor.hp, self.f.actor.max_hp), (60, 90))
            self.assertNotIn(self.f.actor.id, self.f.f.fight.actors)
            remove_percentage_hp(handler, 101)
            self.assertEqual((self.f.actor.hp, self.f.actor.max_hp), (60, 60))

    def test_constructor_reduction_applies_and_reverses_actual_actor(self):
        with self.f.scope():
            handler, result = self.apply(57)
            self.assertTrue(result)
            self.assertEqual((self.f.actor.mp, self.f.actor.max_mp), (2, 2))
            self.assertNotIn(self.f.actor.id, self.f.f.fight.actors)
            remove_maximum_reduction(handler, 101)
            self.assertEqual((self.f.actor.mp, self.f.actor.max_mp), (3, 3))

    def test_missing_scope_is_rejected_for_both_families(self):
        for kind in (57, 986):
            with self.subTest(kind=kind), self.assertRaisesRegex(
                ValueError, "actor.*fight"
            ):
                self.apply(kind)
        self.assertEqual(self.f.f.packets, [])

    def test_cross_target_is_rejected_for_both_families(self):
        with self.f.scope():
            for kind in (57, 986):
                with self.subTest(kind=kind), self.assertRaisesRegex(
                    ValueError, "actor.*fight"
                ):
                    self.apply(kind, replace(self.f.f.invocation, target_id=-7))
        self.assertEqual(self.f.f.packets, [])

    def test_foreign_caster_in_active_fight_is_rejected_for_both_families(self):
        self.f.f.fight.phase = "active"
        with self.f.scope():
            for kind in (57, 986):
                with self.subTest(kind=kind), self.assertRaisesRegex(
                    ValueError, "actor.*fight"
                ):
                    self.apply(kind, replace(self.f.f.invocation, caster_id=-7))
        self.assertEqual(self.f.f.packets, [])

    def test_unverified_constructor_guards_rejected_for_both_families(self):
        self.f.f.handler.context = lambda *args: replace(
            fixture.StatExecutionContext(True, True, None, True, None, None),
            source_guards_verified=False,
        )
        with self.f.scope():
            for kind in (57, 986):
                with self.subTest(kind=kind), self.assertRaisesRegex(
                    ValueError, "guards"
                ):
                    self.apply(kind)
        self.assertEqual(self.f.f.packets, [])

    def test_dead_percentage_constructor_still_rejected(self):
        self.f.actor.hp = 0
        with self.f.scope(), self.assertRaisesRegex(ValueError, "actor/fight"):
            self.apply(986)
        self.assertEqual(self.f.f.packets, [])


if __name__ == "__main__":
    unittest.main()
