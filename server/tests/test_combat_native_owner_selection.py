"""Fresh ordinary resolution follows the native virtual owner flags."""
import unittest
from random import Random
from types import SimpleNamespace

from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_resolver import NativeEffectResolver


class NativeOwnerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.authority = ordinary_cast_authority(
            actors=lambda *args: None,
            timing=SimpleNamespace(state=lambda *args: None),
            rng=Random(7),
            critical=False,
        )
        self.invocation = EffectInvocation(901, 20, 12, 13, (4, 5, 0))

    def effect(self, family):
        return dict(effect_class=family, variant=0, target_masks=[None] * 7)

    def test_native_cell_only_families_never_query_actor_candidates(self):
        def no_actor_query(*args):
            raise AssertionError("Native cell route queried actor candidates")

        for family in (302, 305, 307, 315, 339, 402, 949, 1076):
            effect = self.effect(family)
            resolver = NativeEffectResolver(
                actors=no_actor_query,
                native_context=no_actor_query,
                context=lambda effect, invocation: self.authority.resolution(
                    None, {}, effect, invocation
                ),
                cell_eligible=lambda effect, invocation: self.authority.cell_eligible(
                    None, {}, effect, invocation
                ),
            )
            with self.subTest(family=family):
                selected = resolver(effect, self.invocation)
                self.assertEqual(len(selected), 1)
                self.assertIsNone(selected[0].target_id)
                self.assertEqual(selected[0].cell, (4, 5, 0))

    def test_both_flags_and_actor_only_families_keep_actor_selection(self):
        for family in (1, 303, 314, 316, 338, 340, 859):
            with self.subTest(family=family):
                effect = self.effect(family)
                context = self.authority.resolution(None, {}, effect, self.invocation)
                self.assertEqual(context.selection, "actors")
                self.assertTrue(context.eligible)
                self.assertFalse(
                    self.authority.cell_eligible(None, {}, effect, self.invocation)
                )

    def test_raw_group_neither_flag_does_not_get_fresh_actor_fallback(self):
        effect = dict(
            self.effect(330), parameter_count=3, parameters=[0, 0, 0, 0, 2, 0]
        )
        context = self.authority.resolution(None, {}, effect, self.invocation)
        self.assertFalse(context.eligible)
        self.assertFalse(
            self.authority.cell_eligible(None, {}, effect, self.invocation)
        )

    def test_random_group_native_owner_flags_select_actor_or_cell(self):
        for count, raw, expected_selection, expected_eligible in (
            (1, None, "actors", True),
            (2, 1, "actors", True),
            (2, 0, "cell", True),
            (2, 7, "actors", False),
        ):
            effect = dict(self.effect(341), parameter_count=count)
            if raw is not None:
                effect["parameters"] = [3, raw]
            resolver = NativeEffectResolver(
                actors=lambda *args: (),
                native_context=lambda *args: None,
                context=lambda effect, invocation: self.authority.resolution(
                    None, {}, effect, invocation
                ),
                cell_eligible=lambda effect, invocation: self.authority.cell_eligible(
                    None, {}, effect, invocation
                ),
            )
            with self.subTest(count=count, raw=raw):
                context = self.authority.resolution(None, {}, effect, self.invocation)
                self.assertEqual(context.selection, expected_selection)
                self.assertEqual(context.eligible, expected_eligible)
                self.assertEqual(
                    self.authority.cell_eligible(None, {}, effect, self.invocation),
                    expected_selection == "cell" and expected_eligible,
                )
                if expected_selection == "cell" and expected_eligible:
                    selected = resolver(effect, self.invocation)
                    self.assertEqual(len(selected), 1)
                    self.assertIsNone(selected[0].target_id)

    def test_unknown_owner_proof_rejects_instead_of_inventing_actor_route(self):
        with self.assertRaisesRegex(
            ValueError, "Missing native delivery owner routing"
        ):
            self.authority.resolution(None, {}, self.effect(-1), self.invocation)
