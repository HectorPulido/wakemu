"""Numeric evidence beyond branch selection for Steamer turret specialization."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_special_passives_runtime as qualified


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerNumericFollowupsRuntimeTests(unittest.TestCase):
    def test_specialization_halves_actual_native_turret_damage_calculation(self):
        from wakfu_server.combat_damage_handler import NativeDamageHandler

        calculate = NativeDamageHandler._calculate
        samples = {False: [], True: []}
        selected = {346072, 346106, 346115, 346121}
        baseline = {346069, 346103, 346112, 346118}

        def observe(handler, effect, invocation, **kwargs):
            result = calculate(handler, effect, invocation, **kwargs)
            if invocation.reference in selected | baseline:
                samples[invocation.reference in selected].append(
                    (invocation.reference, invocation.level, result[2])
                )
            return result

        with patch.object(NativeDamageHandler, "_calculate", observe):
            qualified.SteamerSpecialPassivesRuntimeTests().test_water_turret_specialization_selects_actual_half_damage_state()
        self.assertTrue(samples[False], samples)
        self.assertEqual(len(samples[True]), len(samples[False]), samples)
        for full, half in zip(samples[False], samples[True]):
            self.assertGreater(full[2], 0, samples)
            self.assertIsNotNone(half[2], samples)
            self.assertLess(half[2], full[2], samples)
            self.assertLessEqual(abs(2 * half[2] - full[2]), 2, samples)
