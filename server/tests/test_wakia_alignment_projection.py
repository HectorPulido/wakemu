import unittest

from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
    direct_alignment_diagonal,
    direct_allow_self,
)


class AlignmentProjectionTests(unittest.TestCase):
    def test_native_3931_and_8286_alignment_facts_are_certified(self):
        line_or_diagonal_3931 = {
            "linear": True,
            "diagonal": True,
            "conditional": [],
            "categories": [],
        }
        diagonal_only_8286 = {
            "linear": False,
            "diagonal": True,
            "conditional": [],
            "categories": [],
        }
        self.assertTrue(direct_alignment_diagonal(line_or_diagonal_3931))
        self.assertTrue(direct_alignment_diagonal(diagonal_only_8286))

    def test_old_conditional_and_category_tables_do_not_emit_a_certificate(self):
        self.assertIsNone(
            direct_alignment_diagonal(
                {"linear": True, "conditional": [], "categories": []}
            )
        )
        self.assertIsNone(
            direct_alignment_diagonal(
                {
                    "linear": True,
                    "diagonal": True,
                    "conditional": [{}],
                    "categories": [],
                }
            )
        )
        self.assertIsNone(
            direct_alignment_diagonal(
                {"linear": True, "diagonal": True, "conditional": [], "categories": [1]}
            )
        )
        self.assertIsNone(
            direct_alignment_diagonal(
                {"linear": 1, "diagonal": True, "conditional": [], "categories": []}
            )
        )

    def test_allow_self_requires_complete_unconditional_native_rule(self):
        self.assertTrue(
            direct_allow_self({"allow_self": True, "conditional": [], "categories": []})
        )
        self.assertIsNone(direct_allow_self({"conditional": [], "categories": []}))
        self.assertIsNone(
            direct_allow_self(
                {"allow_self": True, "conditional": [{}], "categories": []}
            )
        )
        self.assertIsNone(
            direct_allow_self(
                {"allow_self": True, "conditional": [], "categories": [1]}
            )
        )


if __name__ == "__main__":
    unittest.main()
