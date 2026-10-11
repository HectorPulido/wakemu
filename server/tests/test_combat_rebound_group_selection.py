"""Fresh server rebound selection stays separate from native chosen-PV replay."""
from dataclasses import replace
import unittest
import test_combat_effect_resolver as fixtures


class ReboundGroupSelectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeResolverTests()
        self.fixture.setUp()
        self.fixture.effect.update(
            effect_class=330,
            parameters=[],
            parameter_count=0,
            criteria='HasEffectWithSpecificId("target", 123)',
            area_class="anD",
            area_native="point",
        )
        self.fixture.effect["native_target_selector"]["mask"] = 0
        self.fixture.resolver.direct_target_policies = {"50": [330, False, False]}
        self.invocation = replace(
            self.fixture.invocation,
            target_id=2,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
            wakemu_rebound_child_selection=True,
        )

    def selected(self, invocation=None):
        return [
            row.target_id
            for row in self.fixture.resolver(
                self.fixture.effect,
                self.invocation if invocation is None else invocation,
            )
        ]

    def test_fresh_swapped_source_enumerates_native_criterion_candidates(self):
        self.assertEqual(self.selected(), [1, 2, 3])
        # Both native templates differ only in zero versus one parameter.
        self.fixture.effect.update(parameters=[0, 0], parameter_count=1)
        self.assertEqual(self.selected(), [1, 2, 3])

    def test_replay_and_nonrebound_children_preserve_transmitted_pv(self):
        for field in ("wakemu_fresh_child_selection", "wakemu_rebound_child_selection"):
            with self.subTest(field=field):
                self.assertEqual(
                    self.selected(replace(self.invocation, **{field: False})), [2]
                )

    def test_swap_owning_group_preserves_cunejo_recipient(self):
        self.fixture.effect.update(
            parameters=[0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 2, 0],
            parameter_count=6,
        )
        self.assertEqual(self.selected(), [2])

    def test_no_criterion_and_leaf_runners_stay_bound(self):
        self.fixture.effect["criteria"] = ""
        self.assertEqual(self.selected(), [2])
        self.fixture.effect.update(criteria="True", effect_class=400)
        self.fixture.resolver.direct_target_policies = {"50": [400, False, False]}
        self.assertEqual(self.selected(), [2])
