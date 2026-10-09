import unittest
from unittest.mock import patch
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from wakfu_server.combat_relative_probability import RelativeGroupAuthority
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state import Actor, Fight


class RelativeAuthorityTests(unittest.TestCase):
    CHILD = 120607  # Published non-null fKX root with point offset [1, 0].

    def setUp(self):
        self.player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        self.npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        self.player.direction = 1  # fKX point [1, 0] faces the actual NPC cell.
        for a in (self.player, self.npc):
            a.physical_radius = 0
        self.fight = Fight(
            8,
            [self.player, self.npc],
            {(0, 0, 0), (1, 0, 0), (3, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.fight.ready(3)
        # These are explicit predicate inputs for the isolated geometry test;
        # ordinary actor construction is covered by its own authority tests.
        targeting = {
            "is_amO": True,
            "is_eGj": True,
            "is_Qq": False,
            "is_eHH": True,
            "bEe": True,
            "UNTARGETTABLE_BY_OTHER": False,
            "buX": False,
            "bcR": False,
        }
        self.actors = lambda _fight, _actor: SimpleNamespace(targeting=targeting)
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
            effects={str(self.CHILD): self.child},
            actor_authority=self.actors,
            condition_context=lambda *a: self.calls.append(("condition", a)) or None,
            draw_integer=lambda n: self.calls.append(("integer", n)) or 1,
            draw_fraction=lambda f: self.calls.append(("fraction", f)) or True,
        )
        self.inv = EffectInvocation(344011, 60, 7, 7, (0, 0, 0))

    def test_occupied_native_point_excludes_before_rng_but_empty_admits(self):
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, self.inv, (self.CHILD,)), ()
        )
        self.assertEqual(self.calls, [])
        self.inv = replace(self.inv, cell=(3, 0, 0))
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, self.inv, (self.CHILD,)),
            (self.CHILD,),
        )
        self.assertEqual(self.calls, [("integer", 100)])

    def test_null_selector_uses_caster_instead_of_shifted_cell(self):
        from wakfu_server.combat_casting_context import casting_root_catalog

        # For this direction, the published point offset rotates onto x=-1.
        self.npc.position = (-1, 0, 0)
        root = dict(casting_root_catalog()["roots"][str(self.CHILD)])
        # Exercise the native null-selector branch while preserving the real
        # published fKX collision shape from this root.
        root["native_target_selector"] = None
        with patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": {str(self.CHILD): root}},
        ):
            self.assertEqual(
                self.authority(
                    self.fight,
                    {},
                    {},
                    {},
                    replace(self.inv, cell=(3, 0, 0)),
                    (self.CHILD,),
                ),
                (),
            )
        self.assertEqual(self.calls, [])

    def test_parent_level_filters_and_subscriptions_skip_criterion(self):
        self.child.update(minimum_level=61)
        empty = replace(self.inv, cell=(3, 0, 0))
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, empty, (self.CHILD,)), ()
        )
        self.child.update(
            minimum_level=0,
            criteria="UnknownNativeCriterion()",
            target_masks=[[1], None, None, None, None, None, None],
        )
        self.assertEqual(
            self.authority(self.fight, {}, {}, {}, empty, (self.CHILD,)), (self.CHILD,)
        )
        self.assertEqual(self.calls, [("integer", 100)])

    def test_unknown_roster_never_becomes_empty_or_mutates_fight(self):
        self.player.physical_radius = 128  # Outside native signed-byte radius.
        hp = self.player.hp
        with self.assertRaises(ValueError):
            self.authority(self.fight, {}, {}, {}, self.inv, (344012,))
        self.assertEqual(self.player.hp, hp)
        self.assertEqual(self.calls, [])

    def test_native_null_fkx_skips_actor_and_radius_authority(self):
        # 185395 is a source-verified null-fKX effect. eYg's amQ sees an
        # empty exclusion iterator, independent of roster geometry.
        self.player.physical_radius = 1
        self.authority.effects["185395"] = dict(self.child)
        self.authority.actors = lambda *_: self.fail(
            "proven null fKX must not inspect actor/radius authority"
        )
        with patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            side_effect=AssertionError("null fKX must not query collision geometry"),
        ):
            self.assertEqual(
                self.authority(
                    self.fight,
                    {},
                    {},
                    {},
                    self.inv,
                    (185395,),
                ),
                (185395,),
            )
        self.assertEqual(self.calls, [("integer", 100)])

    def test_unknown_nonnull_fkx_shape_rejects_before_rng(self):
        self.authority.effects["99999999"] = dict(self.child)
        with self.assertRaisesRegex(ValueError, "fKX geometry"):
            self.authority(self.fight, {}, {}, {}, self.inv, (99999999,))
        self.assertEqual(self.calls, [])
