import unittest
from wakfu_server.combat_state_application import (
    ExistingState,
    plan_state_application,
)


class StateApplicationTests(unittest.TestCase):
    def test_additive_cap_suppression_and_refresh(self):
        old = ExistingState(390, 400, True, False, False, False)
        result = plan_state_application(30, 400, [old])
        self.assertTrue(result.accepted)
        self.assertEqual((result.level, result.remove_indices), (400, (0,)))
        old = ExistingState(400, 400, True, False, False, False)
        self.assertFalse(plan_state_application(30, 400, [old]).accepted)
        refreshed = ExistingState(400, 400, True, False, True, False)
        self.assertTrue(plan_state_application(30, 400, [refreshed]).accepted)

    def test_replacement_requires_equal_or_higher_level(self):
        old = ExistingState(20, 100, False, True, False, False)
        self.assertFalse(plan_state_application(19, 100, [old]).accepted)
        self.assertEqual(plan_state_application(20, 100, [old]).remove_indices, (0,))
        protected = ExistingState(20, 100, False, True, False, True)
        self.assertFalse(plan_state_application(30, 100, [protected]).accepted)

    def test_later_rejection_cancels_all_removals(self):
        instances = [
            ExistingState(10, 100, True, False, False, False),
            ExistingState(100, 100, False, False, False, False),
        ]
        result = plan_state_application(20, 100, instances)
        self.assertFalse(result.accepted)
        self.assertEqual(result.remove_indices, ())
        self.assertEqual(instances[0].level, 10)

    def test_java_short_addition_precedes_clamp(self):
        old = ExistingState(32760, 32767, True, False, False, False)
        self.assertEqual(plan_state_application(20, 32767, [old]).level, -32756)

    def test_missing_flags_cannot_be_assumed(self):
        with self.assertRaises(ValueError):
            plan_state_application(1, 100, [{}])


if __name__ == "__main__":
    unittest.main()
