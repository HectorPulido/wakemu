"""Flow preparation must not silently certify boss gameplay."""
import unittest
from server.tools.audit_dungeon_activation_readiness import audit


class DungeonActivationReadinessTests(unittest.TestCase):
    def test_valid_flow_without_native_boss_casts_remains_gameplay_incomplete(self):
        candidate = dict(
            route="native_dungeon_1",
            name="Dungeon",
            path="candidate.json",
            status="offline_configuration_prepared",
            exits=[{"source_id": 4}],
        )
        composition = dict(
            route="native_dungeon_1",
            placement_validation={"status": "candidate_validated"},
        )
        result = audit(
            {"records": [candidate]}, {"records": [composition]}, {"records": []}
        )["records"][0]
        self.assertTrue(result["roster_identity_and_formation_validated"])
        self.assertFalse(result["boss_ability_catalog_complete"])
        self.assertFalse(result["full_boss_mechanics_verified"])
        self.assertEqual(result["runtime_activation"], "not_performed")

    def test_all_native_spell_roots_still_do_not_prove_special_mechanics(self):
        candidate = dict(
            route="native_dungeon_1",
            name="Dungeon",
            path="candidate.json",
            status="offline_configuration_prepared",
            exits=[{"source_id": 4}],
        )
        boss = dict(
            route="native_dungeon_1",
            bosses=[{"spells": [{"status": "catalog_roots_present"}]}],
        )
        result = audit({"records": [candidate]}, {"records": []}, {"records": [boss]})[
            "records"
        ][0]
        self.assertTrue(result["boss_ability_catalog_complete"])
        self.assertFalse(result["full_boss_mechanics_verified"])
        self.assertIn(
            "special_boss_mechanics_not_verified", result["full_gameplay_blockers"]
        )
