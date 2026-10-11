import unittest
from tools.extract_dungeon_family_bosses import identify


def monster(ref, family, boss=False):
    return {
        "ref": ref,
        "family_id": family,
        "raw_visual_arrays": {"csc": [43] if boss else []},
    }


class FamilyBossEvidenceTests(unittest.TestCase):
    def test_unrelated_guest_boss_excluded(self):
        result = identify([monster(1, 10), monster(2, 10, True), monster(99, 90, True)])
        self.assertEqual(result["boss_references"], [2])
        self.assertEqual(result["excluded_nonfamily_references"], [99])

    def test_single_boss_different_family_allowed(self):
        self.assertEqual(
            identify([monster(1, 10), monster(2, 20, True)])["boss_references"], [2]
        )

    def test_same_family_multi_boss_preserved(self):
        self.assertEqual(
            identify([monster(1, 10, True), monster(2, 10, True)])["boss_references"],
            [1, 2],
        )

    def test_empty_pool_fails_closed(self):
        self.assertEqual(identify([])["status"], "unresolved_no_native_boss")

    def test_highest_reference_not_automatically_boss(self):
        self.assertEqual(identify([monster(9999, 10)])["boss_references"], [])


class NativeRolePolicyTests(unittest.TestCase):
    def test_archmonster_rejected_even_when_boss_tagged(self):
        from tools.extract_dungeon_family_bosses import role_allowed

        value = monster(2, 10, True)
        value["raw_visual_arrays"]["csc"].append(45)
        self.assertFalse(
            role_allowed(value, final_room=True, allowed_boss_references=[2])
        )

    def test_dominant_rejected(self):
        from tools.extract_dungeon_family_bosses import role_allowed

        value = monster(2, 10)
        value["raw_visual_arrays"]["csc"] = [115]
        self.assertFalse(role_allowed(value, final_room=True))

    def test_boss_final_only_and_selected(self):
        from tools.extract_dungeon_family_bosses import role_allowed

        value = monster(2, 10, True)
        self.assertFalse(role_allowed(value, allowed_boss_references=[2]))
        self.assertFalse(role_allowed(value, final_room=True))
        self.assertTrue(
            role_allowed(value, final_room=True, allowed_boss_references=[2])
        )

    def test_missing_metadata_fails_closed(self):
        from tools.extract_dungeon_family_bosses import role_allowed

        self.assertFalse(role_allowed(None))
        self.assertFalse(role_allowed({"ref": 1}))
        self.assertFalse(role_allowed({"ref": 1, "raw_visual_arrays": {"csc": ["45"]}}))

    def test_ordinary_is_allowed(self):
        from tools.extract_dungeon_family_bosses import role_allowed

        self.assertTrue(role_allowed(monster(1, 10)))
