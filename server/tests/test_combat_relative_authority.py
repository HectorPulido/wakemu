import unittest
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from wakfu_server.combat_relative_probability import RelativeGroupAuthority
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority


class RelativeAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        self.npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        for a in (self.player, self.npc):
            a.physical_radius = 0
        self.fight = Fight(
            8,
            [self.player, self.npc],
            {(0, 0, 0), (1, 0, 0), (3, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(3)
        self.actors = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=16)},
            monsters={-7: dict(id=-7, ref=5525)},
            decks={7: []},
            excluded_decks={7: []},
        )
        self.child = dict(
            effect_class=20,
            minimum_level=0,
            maximum_level=200,
            criteria="",
            native_target_selector={"class": "fcE", "mask": 1},
            area_class="anD",
            area_native="point",
            probability_base=100.0,
            probability_per_level=0.0,
            target_masks=[None] * 7,
        )
        self.calls = []
        self.authority = RelativeGroupAuthority(
            effects={"344012": self.child},
            actor_authority=self.actors,
            condition_context=lambda *a: self.calls.append(("condition", a)) or None,
            draw_integer=lambda n: self.calls.append(("integer", n)) or 1,
            draw_fraction=lambda f: self.calls.append(("fraction", f)) or True,
        )
        self.inv = EffectInvocation(344011, 60, 7, 7, (0, 0, 0))

    def test_occupied_native_point_excludes_before_rng_but_empty_admits(self):
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, self.inv, (344012,)), ()
        )
        self.assertEqual(self.calls, [])
        self.inv = replace(self.inv, cell=(3, 0, 0))
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, self.inv, (344012,)), (344012,)
        )
        self.assertEqual(self.calls, [("integer", 100)])

    def test_null_selector_uses_caster_instead_of_shifted_cell(self):
        self.child["native_target_selector"] = None
        self.assertEqual(
            self.authority(
                self.fight, {}, {}, {}, replace(self.inv, cell=(3, 0, 0)), (344012,)
            ),
            (),
        )
        self.assertEqual(self.calls, [])

    def test_parent_level_filters_and_subscriptions_skip_criterion(self):
        self.child.update(minimum_level=61)
        empty = replace(self.inv, cell=(3, 0, 0))
        self.assertEqual(self.authority(self.fight, {}, {}, {}, empty, (344012,)), ())
        self.child.update(
            minimum_level=0,
            criteria="UnknownNativeCriterion()",
            target_masks=[[1], None, None, None, None, None, None],
        )
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, empty, (344012,)), (344012,)
        )
        self.assertEqual(self.calls, [("integer", 100)])

    def test_unknown_roster_never_becomes_empty_or_mutates_fight(self):
        self.player.physical_radius = 1
        hp = self.player.hp
        with self.assertRaises(ValueError):
            self.authority(self.fight, {}, {}, {}, self.inv, (344012,))
        self.assertEqual(self.player.hp, hp)
        self.assertEqual(self.calls, [])
