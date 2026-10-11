"""Regression checks for decoded native activation frontiers, not marker centers."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from audit_classic_dungeon_hybrid_structure import audit_trigger_frontiers


class NativeActivationFrontierAuditTests(unittest.TestCase):
    def fixture(self, key, report):
        records = json.loads(
            (ROOT / "docs/reports/dungeons/inventory.json").read_text()
        )["records"]
        native = next(row for row in records if row["key"] == key)
        prepared = json.loads((ROOT / "docs/reports/dungeons" / report).read_text())[
            "records"
        ][0]
        config = json.loads((ROOT / prepared["path"]).read_text())
        return native, config["topology"], config["topology"]["exploration_geometry"]

    def test_riktus_literal_activation_cell_passes_actual_runtime_frontier(self):
        native, topology, geometry = self.fixture(
            "native:139", "RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json"
        )
        evidence, issues = audit_trigger_frontiers(native, topology, geometry)
        self.assertEqual(issues, [])
        self.assertEqual(evidence["configured_frontiers"][0]["position"], [-3, -67, 0])
        self.assertEqual(
            [
                c["status"]
                for c in evidence["configured_frontiers"][0]["runtime_checks"]
            ],
            ["rejected", "accepted"],
        )

    def test_zone_interior_cells_share_native_identity_and_all_validate(self):
        native, topology, geometry = self.fixture(
            "native:53", "BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json"
        )
        evidence, issues = audit_trigger_frontiers(native, topology, geometry)
        self.assertEqual(issues, [])
        self.assertEqual(len(evidence["configured_frontiers"]), 9)
        self.assertEqual(
            {r["source_id"] for r in evidence["configured_frontiers"]}, {16538}
        )
        self.assertTrue(
            all(
                [c["status"] for c in row["runtime_checks"]] == ["rejected", "accepted"]
                for row in evidence["configured_frontiers"]
            )
        )

    def test_same_native_object_cannot_repeat_identical_activation_binding(self):
        native, topology, geometry = self.fixture(
            "native:53", "BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json"
        )
        topology["position_trigger_gates"].append(
            copy.deepcopy(topology["position_trigger_gates"][0])
        )
        evidence, issues = audit_trigger_frontiers(native, topology, geometry)
        self.assertEqual(len(issues), 1)
        self.assertIn(
            "duplicate_trigger_binding", evidence["configured_frontiers"][-1]["reasons"]
        )

    def test_unknown_activation_position_does_not_gain_native_authority(self):
        native, topology, geometry = self.fixture(
            "native:139", "RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json"
        )
        topology["position_trigger_gates"][0]["position"] = [-4, -67, 0]
        evidence, issues = audit_trigger_frontiers(native, topology, geometry)
        self.assertTrue(issues)
        self.assertIn(
            "binding_not_exact_native_trigger",
            evidence["configured_frontiers"][0]["reasons"],
        )
