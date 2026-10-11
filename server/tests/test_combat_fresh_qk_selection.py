"""Fresh child QK selectors reselect indexed recipients; chosen-PV replay does not."""
from dataclasses import replace
import unittest
import test_combat_effect_resolver as helpers
from wakfu_server.combat_effect_targets import UnsupportedTargetSelector


class FreshQKSelectionTests(unittest.TestCase):
    def fixture(self):
        f = helpers.NativeResolverTests()
        f.setUp()
        f.effect.update(
            effect_class=330,
            parameter_count=0,
            parameters=[],
            area_class="anD",
            area_native="point",
        )
        f.effect["native_target_selector"]["mask"] = 1 | (1 << 50)
        f.resolver.direct_target_policies = {"50": [330, False, False]}
        for actor in f.actors[1:]:
            actor.position = (1, 0, 0)
        for identity in (1, 2, 3):
            f.native[identity]["bcN"] = identity
        f.native[3].update(is_eGj=False, is_Qq=True, bcR=False, bcN=-1)
        invocation = replace(
            f.invocation,
            target_id=3,
            cell=(1, 0, 0),
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        return f, invocation

    def test_fresh_area_parent_selects_colocated_indexed_fighter_but_replay_stays_bound(
        self,
    ):
        f, invocation = self.fixture()
        self.assertEqual([i.target_id for i in f.resolver(f.effect, invocation)], [2])
        self.assertEqual(
            [
                i.target_id
                for i in f.resolver(
                    f.effect, replace(invocation, wakemu_fresh_child_selection=False)
                )
            ],
            [3],
        )

    def test_no_indexed_recipient_has_no_effect(self):
        f, invocation = self.fixture()
        f.native[2]["bcN"] = -1
        self.assertEqual(f.resolver(f.effect, invocation), ())

    def test_fresh_self_child_selects_caster_while_replay_keeps_selected_pv(self):
        f, invocation = self.fixture()
        f.effect["native_target_selector"]["mask"] = 2 | 8192
        self.assertEqual([i.target_id for i in f.resolver(f.effect, invocation)], [1])
        self.assertEqual(
            [
                i.target_id
                for i in f.resolver(
                    f.effect, replace(invocation, wakemu_fresh_child_selection=False)
                )
            ],
            [3],
        )

    def test_missing_actual_qk_slot_authority_rejects(self):
        f, invocation = self.fixture()
        del f.native[2]["bcN"]
        with self.assertRaises(UnsupportedTargetSelector):
            f.resolver(f.effect, invocation)
