import unittest
from wakfu_server.combat_self_cast import allows_self
from wakfu_server.combat_conditions import UnknownCondition


class NativeSelfCastTests(unittest.TestCase):
    def test_policy_is_explicit_and_missing_is_not_false(self):
        for permitted in (True, False):
            self.assertEqual(
                allows_self(
                    7, None, policies={"7": {"allowed": permitted, "conditional": []}}
                ),
                permitted,
            )
        with self.assertRaises(UnknownCondition):
            allows_self(7, None, policies={})

    def test_original_heart_self_exception_and_conditional_table(self):
        from wakfu_server.combat_self_cast import catalog

        row = catalog()["6065"]
        self.assertTrue(row["allowed"])
        self.assertTrue(row["conditional"][0]["allowed"])
        self.assertTrue(allows_self(6065, None))

    def test_conditional_self_cast_requires_real_context_when_flag_changes(self):
        policies = {
            "7": {
                "allowed": True,
                "conditional": [{"criteria": "IsSpellInDeck(5051)", "allowed": False}],
            }
        }
        with self.assertRaises(UnknownCondition):
            allows_self(7, None, policies=policies)
