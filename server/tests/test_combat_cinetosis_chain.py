"""Legitimate native innates/casts; no injected state or inflated NPC health."""
import importlib.util
from pathlib import Path
import unittest


class CinetosisChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).resolve().parents[1]
            / "tools/audit_displacement_spell_reactions.py"
        )
        spec = importlib.util.spec_from_file_location(
            "native_movement_reactions_audit", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.report = module.run()

    def test_normal_reaction_two_original_listeners(self):
        rows = [
            r
            for r in self.report["cases"]
            if r["spell_id"] == 5041 and r["scenario"] == "normal"
        ]
        self.assertEqual(len(rows), 2)
        for row, expected_hp in zip(rows, (80, 56)):
            self.assertEqual(row["status"], "executed")
            self.assertEqual(row["after"]["-7"]["hp"], 84)
            self.assertEqual(row["after_pull"]["-7"]["hp"], expected_hp)
            self.assertNotEqual(
                row["after"]["-7"]["position"], row["after_pull"]["-7"]["position"]
            )
            self.assertTrue(row["rollback_preserved"])
            self.assertTrue(row["pull_rollback_preserved"])

    def test_legitimate_berserker_innate_also_hits_on_cast(self):
        for row in self.report["cases"]:
            if row["scenario"] != "berserker":
                continue
            self.assertEqual(row["status"], "executed")
            self.assertIn(9315, [s["reference"] for s in row["before"]["7"]["states"]])
            self.assertLess(row["after"]["-7"]["hp"], row["before"]["-7"]["hp"])
            self.assertTrue(row["rollback_preserved"])
            self.assertTrue(row["pull_rollback_preserved"])

    def test_without_state_displacement_does_not_invent_damage(self):
        for row in self.report["cases"]:
            if row["scenario"] != "without_state":
                continue
            self.assertEqual(row["status"], "executed")
            self.assertNotEqual(
                row["before"]["-7"]["position"], row["after"]["-7"]["position"]
            )
            self.assertEqual(row["before"]["-7"]["hp"], row["after"]["-7"]["hp"])

    def test_fulgor_teleport_and_armor_both_levels(self):
        for row in self.report["cases"]:
            if row["spell_id"] != 5042:
                continue
            self.assertEqual(row["status"], "executed")
            self.assertNotEqual(
                row["before"]["7"]["position"], row["after"]["7"]["position"]
            )
            self.assertGreater(row["after"]["7"]["armor"], row["before"]["7"]["armor"])
            self.assertTrue(row["rollback_preserved"])
        self.assertTrue(self.report["sources_stable"])
