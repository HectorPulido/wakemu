"""Local family progression respects actual deterministic native grade policy."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_family_linear_dungeons import (
    audit_configuration_progression,
    eligible_family_refs,
    progressive_family_roster,
)


def native(levels):
    return dict(
        native_species_pool=[
            dict(
                ref_id=i + 1, name_es=str(i + 1), min_level=level, max_level=level + 20
            )
            for i, level in enumerate(levels)
        ]
    )


class FamilyProgressionTests(unittest.TestCase):
    def test_equal_grade_family_uses_strictly_increasing_counts(self):
        result = progressive_family_roster(
            native([10, 10, 10, 10]), 4, [4], eligible_refs={1, 2, 3, 4}
        )
        self.assertEqual(
            [r["quantity"] for r in result["progression_policy"]["rooms"]], [2, 4, 6, 8]
        )
        self.assertEqual(
            [r["native_minimum_threat"] for r in result["progression_policy"]["rooms"]],
            [20, 40, 60, 80],
        )
        for room in result["rooms"][:-1]:
            self.assertNotIn(4, [m["ref_id"] for m in room["monsters"]])
        self.assertEqual(
            sum(
                m["count"]
                for m in result["rooms"][-1]["monsters"]
                if m["role"] == "boss"
            ),
            1,
        )

    def test_single_actor_capacity_can_progress_through_native_grades(self):
        result = progressive_family_roster(
            native([158, 160, 164, 173]), 3, [4], capacity=1, eligible_refs={1, 2, 3, 4}
        )
        self.assertEqual(
            [r["native_minimum_threat"] for r in result["progression_policy"]["rooms"]],
            [158, 160, 173],
        )

    def test_impossible_strict_progression_fails_instead_of_equal_stages(self):
        with self.assertRaisesRegex(ValueError, "Strict"):
            progressive_family_roster(
                native([10, 10]), 3, [2], capacity=1, eligible_refs={1, 2}
            )

    def test_role_metadata_excludes_arch_dominant_unknown_and_unselected_boss(self):
        record = native([10] * 7)
        catalog = {
            i: dict(ref=i, raw_visual_arrays=dict(csc=flags))
            for i, flags in (
                (1, []),
                (2, [43]),
                (3, [45]),
                (4, [115]),
                (5, [43]),
                (6, [43, 115]),
            )
        }
        self.assertEqual(eligible_family_refs(record, catalog, [2]), {1, 2})

    def test_multiple_final_bosses_each_once_and_no_early_boss(self):
        result = progressive_family_roster(
            native([10, 10, 15, 20]), 3, [3, 4], eligible_refs={1, 2, 3, 4}
        )
        self.assertEqual(
            {
                m["ref_id"]: m["count"]
                for m in result["rooms"][-1]["monsters"]
                if m["role"] == "boss"
            },
            {3: 1, 4: 1},
        )
        self.assertTrue(
            all(
                m["role"] == "monster"
                for r in result["rooms"][:-1]
                for m in r["monsters"]
            )
        )

    def test_role_evidence_is_mandatory(self):
        with self.assertRaisesRegex(ValueError, "eligibility"):
            progressive_family_roster(native([10, 20]), 2, [2])

    def test_release_audit_rejects_early_boss_and_equal_actual_levels(self):
        catalog = {
            1: dict(ref=1, min_level=10, max_level=30, raw_visual_arrays=dict(csc=[])),
            2: dict(
                ref=2, min_level=10, max_level=30, raw_visual_arrays=dict(csc=[43])
            ),
        }
        monster = lambda ref: dict(
            ref_id=ref,
            count=1,
            role="boss" if ref == 2 else "monster",
            native_min_level=10,
            native_max_level=30,
        )
        config = dict(
            compiled_plan=dict(
                boss_references=[2],
                rooms=[
                    dict(order=1, monsters=[monster(2)]),
                    dict(order=2, monsters=[monster(1)]),
                ],
            ),
            topology=dict(rooms=[dict(order=1), dict(order=2)]),
            level_policy=dict(mode="native_minimum"),
        )
        violations = audit_configuration_progression(config, catalog)["violations"]
        self.assertIn("room_1:boss_before_final:2", violations)
        self.assertIn("room_2:composition_strength_not_strictly_increasing", violations)

    def test_release_audit_rejects_empty_roster_and_unknown_native_role(self):
        config = dict(
            compiled_plan=dict(
                boss_references=[2],
                rooms=[
                    dict(order=1, monsters=[]),
                    dict(
                        order=2,
                        monsters=[
                            dict(
                                ref_id=2,
                                count=1,
                                role="boss",
                                native_min_level=20,
                                native_max_level=20,
                            )
                        ],
                    ),
                ],
            ),
            topology=dict(rooms=[dict(order=1), dict(order=2)]),
            level_policy=dict(mode="native_minimum"),
        )
        violations = audit_configuration_progression(
            config, {2: dict(ref=2, min_level=20, max_level=20)}
        )["violations"]
        self.assertIn("room_1:missing_combat_roster", violations)
        self.assertIn("room_2:prohibited_native_role:2:unknown", violations)


if __name__ == "__main__":
    unittest.main()
