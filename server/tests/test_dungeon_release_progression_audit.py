import unittest

from tools.dungeon_release_progression_audit import audit_configuration


def native(ref, level, *, flags=()):
    return {
        "ref": ref,
        "min_level": level,
        "max_level": level + 1,
        "raw_visual_arrays": {"csc": list(flags)},
    }


def config(room_monsters, *, bosses=()):
    rooms = [
        {"order": index, "monsters": monsters}
        for index, monsters in enumerate(room_monsters, start=1)
    ]
    return {
        "level_policy": {"mode": "native_minimum"},
        "compiled_plan": {"rooms": rooms, "boss_references": list(bosses)},
        "topology": {"rooms": [{"order": r["order"]} for r in rooms]},
    }


def actor(ref, level, *, count=1, role="monster"):
    return {
        "ref_id": ref,
        "count": count,
        "role": role,
        "native_min_level": level,
        "native_max_level": level + 1,
    }


class DungeonReleaseProgressionAuditTests(unittest.TestCase):
    def test_requires_strictly_increasing_spawn_level_sum(self):
        catalog = {1: native(1, 10), 2: native(2, 11)}
        value = config([[actor(1, 10, count=2)], [actor(2, 11, count=3)]])
        result = audit_configuration(value, catalog)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            [
                r["sum_count_times_native_minimum"]
                for r in result["room_spawn_level_sums"]
            ],
            [20, 33],
        )

    def test_rejects_flat_or_decreasing_spawn_level_sum(self):
        catalog = {1: native(1, 10), 2: native(2, 10)}
        value = config([[actor(1, 10, count=2)], [actor(2, 10, count=2)]])
        result = audit_configuration(value, catalog)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("room_2_threat_not_increasing_after_1", result["violations"])

    def test_rejects_dominant_and_archmonster_roles(self):
        for ref, flag, label in ((1, 115, "dominant"), (2, 45, "archmonster")):
            with self.subTest(role=label):
                catalog = {ref: native(ref, 10, flags=(flag,))}
                result = audit_configuration(config([[actor(ref, 10)]]), catalog)
                self.assertTrue(
                    any(
                        issue.endswith(f"forbidden_role_{label}_{ref}")
                        for issue in result["violations"]
                    )
                )

    def test_allows_identified_family_boss_only_in_final_room(self):
        catalog = {1: native(1, 10), 2: native(2, 20, flags=(43,))}
        valid = config([[actor(1, 10)], [actor(2, 20, role="boss")]], bosses=(2,))
        self.assertEqual(audit_configuration(valid, catalog)["status"], "passed")
        early = config([[actor(2, 20, role="boss")], [actor(1, 10)]], bosses=(2,))
        result = audit_configuration(early, catalog)
        self.assertIn("room_1_boss_before_final_2", result["violations"])
        self.assertIn("room_2_threat_not_increasing_after_1", result["violations"])

    def test_single_encounter_arena_is_marked_without_multiroom_progression(self):
        catalog = {1: native(1, 10), 2: native(2, 20, flags=(43,))}
        value = config([[actor(1, 10), actor(2, 20, role="boss")]], bosses=(2,))
        result = audit_configuration(value, catalog)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["progression_policy"], "no_multiroom_progression")


if __name__ == "__main__":
    unittest.main()
