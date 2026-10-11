"""Native eWt.bbR removes QI exclusions even while another property remains."""
import unittest
from types import SimpleNamespace

import test_combat_fight_property as property_tests
from wakfu_server.combat_fight_property import remove_fight_property
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority


class SramStackedVisibilityNativeTests(unittest.TestCase):
    fixture = property_tests.NativeFightPropertyTests.fixture
    apply = property_tests.NativeFightPropertyTests.apply

    def test_native_removal_keeps_counter_but_clears_qi_exclusions(self):
        class VisibilityAuthority(property_tests.Authority):
            property_side_effect = OrdinaryActorAuthority.property_side_effect

            def __call__(self, fight, actor):
                return SimpleNamespace(targeting={"is_eGj": True, "bcN": actor.team})

        for properties in ((5, 5), (5, 18), (18, 5), (18, 18)):
            with self.subTest(properties=properties):
                fight, actor, packets, handler = self.fixture()
                handler.authority = VisibilityAuthority()
                actor.team = 1
                actor.position = (2, -3, 4)
                actor.direction = 3
                fight.native_los_ignored_affiliations = frozenset()
                fight.native_walk_ignored_affiliations = frozenset({1})
                for prop in properties:
                    self.apply(handler, prop)
                self.assertEqual(fight.native_los_ignored_affiliations, frozenset({1}))
                remove_fight_property(
                    SimpleNamespace(fight=fight, action_id=3, packets=packets), 903
                )
                self.assertEqual(actor.native_fight_property_counts, {properties[1]: 1})
                self.assertIn(properties[1], actor.native_fight_properties)
                self.assertEqual(fight.native_los_ignored_affiliations, frozenset())
                self.assertEqual(fight.native_walk_ignored_affiliations, frozenset())
