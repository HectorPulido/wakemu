"""Contradictory relation branches remain inert beside real NPC area roots."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_npc_area_preflight import qualified_roots


class DormantNpcAreaRootsTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=-200, controlled=False, hp=100, position=(0, 0, 0), direction=0
        )
        self.fight = SimpleNamespace(actors={-200: self.actor})
        self.request = dict(actor_id=-200, target=(0, 0, 0))
        self.rule = dict(minimum=0, maximum=0, roots=[1, 2])
        self.active = dict(
            effect_class=4,
            children=[],
            native_target_selector=dict(class_="fcE"),
            area_class="anH",
            area_native="ring-1-1",
            application_flag="NONE",
            removal_flag="NONE",
        )
        self.active["native_target_selector"] = {"class": "fcE", "mask": 9}
        self.dormant = dict(
            self.active,
            effect_class=304,
            native_target_selector={"class": "fcE", "mask": 12},
        )
        self.effects = {"1": self.active, "2": self.dormant}

    def test_impossible_relation_branch_does_not_hide_real_damage_root(self):
        self.assertEqual(
            qualified_roots(self.fight, self.request, self.rule, self.effects),
            {1: self.active},
        )
        self.assertEqual(self.rule["roots"], [1, 2])
        self.assertEqual(self.effects["2"]["native_target_selector"]["mask"], 12)

    def test_only_impossible_branches_supply_no_cast_authority(self):
        self.rule["roots"] = [2]
        self.assertFalse(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )

    def test_dormant_subscribed_branch_stays_outside_immediate_policy(self):
        self.dormant["application_flag"] = "TURN_START"
        self.assertIsNone(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )

    def test_live_self_branch_is_not_misclassified_as_dormant(self):
        self.dormant["native_target_selector"]["mask"] = 2
        self.assertIsNone(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )
