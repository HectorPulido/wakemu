"""Ordinary visibility must update the real QI even with a registered summon."""
import unittest
from types import SimpleNamespace

from test_combat_fight_property import TIME
import test_combat_summon as summon_tests
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_fight_property import (
    NativeFightPropertyHandler,
    remove_fight_property,
)
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_stat_handler import StatExecutionContext


class VisibilityOrdinary(summon_tests.Ordinary):
    def __call__(self, fight, actor):
        super().__call__(fight, actor)
        result = summon_tests.metadata()
        result.targeting.update(is_eGj=True, bcN=actor.team)
        return result

    def property_counts(self, fight, actor):
        self(fight, actor)
        return dict(getattr(actor, "native_fight_property_counts", {}))


class SramVisibilityWithSummonsTests(unittest.TestCase):
    def fixture(self):
        fight, summon, registration = summon_tests.SummonTests().fixture()
        authority = RegisteredSummonAuthority(VisibilityOrdinary())
        authority.register(
            fight, summon, registration, new_order=[7, 901, -7], new_turn_index=0
        )
        fight.native_los_ignored_affiliations = frozenset({1})
        fight.native_walk_ignored_affiliations = frozenset({0, 1})
        actor = fight.actors[7]
        actor.direction = 3
        return fight, actor, summon, authority

    def test_visibility_apply_and_retire_with_summon_preserve_other_affiliations(self):
        for prop in (5, 18):
            with self.subTest(property=prop):
                fight, actor, summon, authority = self.fixture()
                packets = []
                handler = NativeFightPropertyHandler(
                    fight,
                    packets,
                    action_id=3,
                    allocate_uid=lambda: 903,
                    context=lambda *args: StatExecutionContext(
                        True, True, None, True, TIME
                    ),
                    authority=authority,
                )
                resources = (actor.ap, actor.mp, actor.hp)
                order = list(fight.order)
                self.assertTrue(
                    handler(
                        {"effect_class": 447},
                        {"parameters": [prop]},
                        EffectInvocation(120855, 1, actor.id, actor.id, actor.position),
                    )
                )
                self.assertEqual(actor.native_fight_property_counts, {prop: 1})
                self.assertEqual(
                    fight.native_los_ignored_affiliations, frozenset({0, 1})
                )
                self.assertEqual(
                    fight.native_walk_ignored_affiliations, frozenset({0, 1})
                )
                remove_fight_property(
                    SimpleNamespace(fight=fight, action_id=3, packets=packets), 903
                )
                self.assertEqual(actor.native_fight_property_counts, {})
                self.assertEqual(fight.native_los_ignored_affiliations, frozenset({1}))
                self.assertEqual(fight.native_walk_ignored_affiliations, frozenset({1}))
                self.assertEqual([opcode for opcode, _ in packets], [12613, 13560])
                self.assertEqual((actor.ap, actor.mp, actor.hp), resources)
                self.assertEqual(fight.order, order)
                self.assertIs(fight.actors[summon.id], summon)
                self.assertIn(summon.id, fight.native_summon_registrations)

    def test_unsupported_combined_callbacks_and_summoned_targets_stay_rejected(self):
        fight, actor, summon, authority = self.fixture()
        for prop in (10, 25, 37):
            with self.assertRaisesRegex(ValueError, "Combined property/summon"):
                authority.property_side_effect(fight, actor, prop, applying=True)
        with self.assertRaisesRegex(ValueError, "summoned property callbacks"):
            authority.property_side_effect(fight, summon, 5, applying=True)

    def test_extra_unregistered_actor_still_fails_ordinary_roster_validation(self):
        fight, actor, _, authority = self.fixture()
        fight.actors[999] = SimpleNamespace(id=999)
        with self.assertRaisesRegex(ValueError, "Ordinary roster changed"):
            authority.property_side_effect(fight, actor, 5, applying=True)
