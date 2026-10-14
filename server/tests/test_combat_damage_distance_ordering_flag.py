"""Source-qualified faF flag14 is consumed by targeting, not damage arithmetic."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_combat_damage_handler as fixture_module
from wakfu_server.combat_target_ordering import order_native_targets
from wakfu_server.fight_checkpoint_store import snapshot

NATIVE = {"99427": dict(effect_class=1, maximum_targets=1, native_effect_flags=[14])}
LOOKUP = "wakfu_server.combat_target_ordering.native_target_ordering"


class DamageDistanceOrderingFlagTests(unittest.TestCase):
    def fixture(self, flags=(14,)):
        fixture = fixture_module.DamageHandlerTests()
        fixture.setUp()
        effect = dict(fixture.effect, effect_class=1, native_effect_flags=list(flags))
        invocation = replace(fixture.invocation, reference=99427)
        return fixture, effect, invocation

    def execute(self, flags):
        fixture, effect, invocation = self.fixture(flags)
        with patch(LOOKUP, return_value=NATIVE):
            self.assertTrue(fixture.handler(effect, {}, invocation))
        return snapshot(fixture.fight), fixture.packets

    def test_actual_native_flag14_keeps_damage_arithmetic_and_wire(self):
        self.assertEqual(self.execute((14,)), self.execute(()))

    def test_missing_or_conflicting_identity_rejects_before_mutation(self):
        for metadata in (
            {},
            {"99427": dict(NATIVE["99427"], effect_class=2)},
            {"99427": dict(NATIVE["99427"], native_effect_flags=[])},
        ):
            fixture, effect, invocation = self.fixture()
            before = snapshot(fixture.fight)
            with patch(LOOKUP, return_value=metadata), self.assertRaisesRegex(
                ValueError, "identity"
            ):
                fixture.handler(effect, {}, invocation)
            self.assertEqual(snapshot(fixture.fight), before)
            self.assertEqual(fixture.packets, [])

    def test_native_distance_sort_uses_requested_cell_then_target_cap(self):
        _, effect, invocation = self.fixture()
        invocation = replace(invocation, cell=(10, 10, 0))
        far = SimpleNamespace(position=(0, 0, 0))
        near = SimpleNamespace(position=(10, 11, 0))
        self.assertEqual(
            order_native_targets(effect, invocation, (far, near), metadata=NATIVE),
            (near,),
        )

    def test_ordering_identity_does_not_admit_other_unknown_flags(self):
        fixture, effect, invocation = self.fixture((14, 123))
        data = {"99427": dict(NATIVE["99427"], native_effect_flags=[14, 123])}
        with patch(LOOKUP, return_value=data), self.assertRaisesRegex(
            ValueError, "Unsupported native damage flags"
        ):
            fixture.handler(effect, {}, invocation)
        self.assertEqual(fixture.packets, [])
