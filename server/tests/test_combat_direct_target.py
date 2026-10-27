from dataclasses import replace
import unittest
from wakfu_server.combat_direct_target import (
    native_direct_target_policies,
    explicit_native_target,
)
from wakfu_server.combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS
from test_combat_effect_resolver import NativeResolverTests


class DirectTargetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NativeResolverTests()
        self.fixture.setUp()
        self.fixture.effect["effect_class"] = 25

    def resolve(self, *, explicit=True, recalculate=False, caster=False):
        f = self.fixture
        f.resolver.direct_target_policies = {"50": [25, recalculate, caster]}
        return f.resolver(
            f.effect,
            replace(f.invocation, target_id=2, native_explicit_target=explicit),
        )

    def test_four_native_explicit_pv_recalculation_branches(self):
        for explicit in (False, True):
            for recalculate in (False, True):
                with self.subTest(explicit=explicit, recalculate=recalculate):
                    selected = self.resolve(explicit=explicit, recalculate=recalculate)
                    expected = [2] if explicit and not recalculate else [1, 2, 3]
                    self.assertEqual([inv.target_id for inv in selected], expected)

    def test_caster_override_and_direct_target_do_not_apply_fcE(self):
        self.fixture.effect["native_target_selector"]["mask"] = 9  # Enemy selector.
        self.assertEqual([inv.target_id for inv in self.resolve(caster=True)], [1])
        self.assertEqual(
            [inv.target_id for inv in self.resolve(explicit=False, caster=True)], [1]
        )
        self.fixture.context = replace(self.fixture.context, eligible=False)
        self.assertEqual(self.resolve(), ())  # Application guards remain authoritative.

    def test_complete_native_metadata_and_invalid_identity(self):
        metadata = native_direct_target_policies()
        self.assertEqual(len(metadata), 178337)
        self.assertEqual(metadata["326007"], [25, False, False])
        inv = replace(self.fixture.invocation, target_id=2, native_explicit_target=True)
        with self.assertRaisesRegex(ValueError, "Missing/conflicting"):
            explicit_native_target(
                self.fixture.effect, inv, metadata={"50": [1, False, False]}
            )

    def test_server_fresh_child_uses_selector_without_rewriting_replay_policy(self):
        self.fixture.effect["native_target_selector"]["mask"] = 2
        self.fixture.resolver.direct_target_policies = {"50": [25, False, False]}
        explicit = replace(
            self.fixture.invocation, target_id=2, native_explicit_target=True
        )
        self.assertEqual(
            [i.target_id for i in self.fixture.resolver(self.fixture.effect, explicit)],
            [2],
        )
        selected = self.fixture.resolver(
            self.fixture.effect, replace(explicit, wakemu_fresh_child_selection=True)
        )
        self.assertEqual([i.target_id for i in selected], [1])
        self.fixture.effect.update(area_class="anD", area_native="point")
        for mask in (0, 1, 3):
            self.fixture.effect["native_target_selector"]["mask"] = mask
            selected = self.fixture.resolver(
                self.fixture.effect,
                replace(explicit, wakemu_fresh_child_selection=True),
            )
            self.assertEqual([i.target_id for i in selected], [2])

    def test_fresh_area_group_enumerates_occupants_before_transmitting_point_pv(self):
        self.fixture.effect["native_target_selector"]["mask"] = 1
        self.fixture.effect.update(
            effect_class=330,
            parameter_count=0,
            parameters=[],
            area_class="anu",
            area_native="circle-2",
        )
        self.fixture.resolver.direct_target_policies = {"50": [330, False, False]}
        invocation = replace(
            self.fixture.invocation,
            target_id=2,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        selected = self.fixture.resolver(self.fixture.effect, invocation)
        self.assertEqual([i.target_id for i in selected], [1, 2, 3])
        replay = self.fixture.resolver(
            self.fixture.effect, replace(invocation, wakemu_fresh_child_selection=False)
        )
        self.assertEqual([i.target_id for i in replay], [2])

    def test_transmitted_nonpoint_leaf_preserves_pv_without_a_second_area_selection(
        self,
    ):
        f = self.fixture
        f.effect.update(area_class="any", area_native="crossRing-1-1")
        explicit = replace(
            f.invocation,
            target_id=2,
            cell=f.actors[1].position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        for family in sorted(set(DAMAGE_FAMILIES) | set(HEAL_ELEMENTS)):
            with self.subTest(family=family):
                f.effect["effect_class"] = family
                f.resolver.direct_target_policies = {"50": [family, False, False]}
                f.effect["native_target_selector"]["mask"] = 1
                self.assertEqual(
                    [i.target_id for i in f.resolver(f.effect, explicit)], [2]
                )
                # Fresh area selection still occurs without a transmitted PV,
                # or when the actual native runner explicitly requests aZX.
                self.assertEqual(
                    [
                        i.target_id
                        for i in f.resolver(
                            f.effect, replace(explicit, native_explicit_target=False)
                        )
                    ],
                    [1],
                )
                f.resolver.direct_target_policies = {"50": [family, True, False]}
                self.assertEqual(
                    [i.target_id for i in f.resolver(f.effect, explicit)], [1]
                )
                # Existing explicit relationship reconstruction is independent.
                f.resolver.direct_target_policies = {"50": [family, False, False]}
                f.effect["native_target_selector"]["mask"] = 2
                self.assertEqual(
                    [i.target_id for i in f.resolver(f.effect, explicit)], [1]
                )

    def test_fresh_qq_selector_replaces_transmitted_actor_with_registered_area(self):
        self.fixture.native[2].update(is_Qq=True, is_amO=False, is_eGj=False)
        self.fixture.effect["native_target_selector"]["mask"] = 64 | (1 << 51)
        self.fixture.effect.update(area_class="anD", area_native="point")
        self.fixture.resolver.direct_target_policies = {"50": [843, False, False]}
        self.fixture.effect["effect_class"] = 843
        invocation = replace(
            self.fixture.invocation,
            target_id=3,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )
        selected = self.fixture.resolver(self.fixture.effect, invocation)
        self.assertEqual([i.target_id for i in selected], [2])
        replay = self.fixture.resolver(
            self.fixture.effect, replace(invocation, wakemu_fresh_child_selection=False)
        )
        self.assertEqual([i.target_id for i in replay], [3])
