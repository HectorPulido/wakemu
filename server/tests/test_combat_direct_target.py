from dataclasses import replace
import unittest
from wakfu_server.combat_direct_target import (
    native_direct_target_policies,
    explicit_native_target,
)
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
