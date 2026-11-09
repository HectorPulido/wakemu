"""No-self-heal projection requires complete recipient evidence."""
import unittest

from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
    projected_no_self_heal,
)


class ProjectedNoSelfHealTests(unittest.TestCase):
    def test_real_spell_3140_ally_heal_and_enemy_damage_with_known_conditional(self):
        rows = [
            {"kind": "heal", "target": "ally", "amount": 10, "nativeReference": 80571},
            {
                "kind": "damage",
                "target": "enemy",
                "amount": 20,
                "nativeReference": 80572,
            },
        ]

        self.assertTrue(projected_no_self_heal(rows, ["conditional_effect:80572"]))

    def test_healing_only_ally_is_certified(self):
        rows = [{"kind": "heal", "target": "ally", "amount": 10, "nativeReference": 11}]

        self.assertTrue(projected_no_self_heal(rows, []))

    def test_actual_self_heal_is_not_certified(self):
        rows = [{"kind": "heal", "target": "self", "amount": 10, "nativeReference": 12}]

        self.assertFalse(projected_no_self_heal(rows, []))

    def test_area_self_and_ally_heals_remain_distinct_when_a_row_is_conditional(self):
        rows = [
            {"kind": "heal", "target": "self", "amount": 10, "nativeReference": 21},
            {"kind": "heal", "target": "ally", "amount": 10, "nativeReference": 22},
        ]

        self.assertFalse(projected_no_self_heal(rows, ["conditional_effect:21"]))

    def test_unrecognized_projection_evidence_is_not_certified(self):
        rows = [{"kind": "heal", "target": "ally", "amount": 10, "nativeReference": 13}]

        self.assertFalse(
            projected_no_self_heal(rows, ["unsupported_semantic_family:447"])
        )

    def test_complete_projection_without_healing_is_certified(self):
        rows = [
            {"kind": "damage", "target": "enemy", "amount": 20, "nativeReference": 14}
        ]

        self.assertTrue(projected_no_self_heal(rows, []))


if __name__ == "__main__":
    unittest.main()
