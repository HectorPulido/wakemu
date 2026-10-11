"""Independent tests for prepared native trigger ownership and runtime frontier checks."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from audit_classic_dungeon_hybrid_structure import audit_trigger_frontiers


def native_trigger(identity, position, *, map_id=1):
    return dict(
        id=identity,
        map_id=map_id,
        type="PositionTrigger",
        x=position[0],
        y=position[1],
        z=position[2],
    )


class PreparedTriggerFrontierAuditTests(unittest.TestCase):
    def test_pischina_frozen_candidate_binds_each_native_trigger_and_parallel_lane(
        self,
    ):
        inventory = json.loads(
            (ROOT / "docs/reports/dungeons/inventory.json").read_text()
        )
        record = next(row for row in inventory["records"] if row["key"] == "native:143")
        config = json.loads(
            (
                ROOT
                / ".runtime/local/pischina-native-trigger-v10-20261010/native_dungeon_143.json"
            ).read_text()
        )
        geometry = json.loads(
            (
                ROOT
                / ".runtime/local/all-native-dungeon-exploration/exploration-912.json"
            ).read_text()
        )
        evidence, issues = audit_trigger_frontiers(record, config["topology"], geometry)
        self.assertEqual(issues, [])
        self.assertEqual(evidence["native_trigger_count"], 4)
        self.assertEqual(evidence["unbound_native_trigger_ids"], [])
        frontiers = evidence["configured_frontiers"]
        self.assertEqual(
            [f["source_id"] for f in frontiers], [31447, 31448, 31449, 31450]
        )
        self.assertTrue(all(not f["reasons"] for f in frontiers))
        for frontier in frontiers:
            self.assertEqual(
                [r["status"] for r in frontier["runtime_checks"]],
                ["rejected", "accepted"],
            )
        parallel = [f for f in frontiers if f["source_room"] == 3]
        self.assertEqual([f["source_id"] for f in parallel], [31449, 31450])

    def test_v3_trigger_inventory_binds_expanded_109_definition_scope(self):
        audit_path = (
            ROOT
            / "docs/reports/dungeons/POST-PISCHINA-ALL-CLASSIC-STRUCTURE-AUDIT-20261010.json"
        )
        trigger_path = (
            ROOT
            / "docs/reports/dungeons/ALL-CLASSIC-POSITION-TRIGGER-CUTS-V3-20261010.json"
        )
        audit_bytes = audit_path.read_bytes()
        audit = json.loads(audit_bytes)
        report = json.loads(trigger_path.read_text())
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(report["scope_report"], str(audit_path.relative_to(ROOT)))
        import hashlib

        self.assertEqual(
            report["scope_sha256"], hashlib.sha256(audit_bytes).hexdigest()
        )
        self.assertEqual(report["definition_count"], audit["inventory_definitions"])
        self.assertEqual(len(report["records"]), 109)
        pischina = next(row for row in report["records"] if row["key"] == "native:143")
        self.assertEqual(
            pischina["configuration_scopes"][0]["scope"], "prepared_latest"
        )
        self.assertEqual(pischina["maps"][0]["status"], "literal_separator_candidates")
        self.assertEqual(pischina["maps"][0]["trigger_count"], 4)
        prior = json.loads(
            (
                ROOT
                / "docs/reports/dungeons/ALL-CLASSIC-POSITION-TRIGGER-CUTS-V2-20261010.json"
            ).read_text()
        )
        self.assertEqual(prior["schema_version"], 2)

    def fixture(self, trigger_room=2):
        point_a, point_t, point_b = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        native = dict(key="native:1", native_objects=[native_trigger(11, point_t)])
        topology = dict(
            policy="native_mixed_victory_policy",
            rooms=[
                dict(order=1, cells=[list(point_a)]),
                dict(order=2, cells=[list(point_t), list(point_b)]),
            ],
            physical_doors=[],
            position_trigger_gates=[
                dict(
                    source_id=11,
                    position=list(point_t),
                    source_room=1,
                    destination_room=trigger_room,
                )
            ],
            exploration_geometry=dict(
                map_id=1,
                cells=[list(point_a), list(point_t), list(point_b)],
                edges=[[list(point_a), list(point_t)], [list(point_t), list(point_b)]],
            ),
        )
        geometry = topology["exploration_geometry"]
        return native, topology, geometry, point_a

    def test_unowned_trigger_cell_is_blocked_even_if_source_id_is_native(self):
        record, topology, geometry, _ = self.fixture()
        topology["rooms"][1]["cells"].remove([1, 0, 0])
        evidence, issues = audit_trigger_frontiers(record, topology, geometry)
        self.assertEqual(len(issues), 1)
        self.assertIn(
            "trigger_cell_not_owned_only_by_destination",
            evidence["configured_frontiers"][0]["reasons"],
        )

    def test_overlapping_trigger_cell_ownership_is_blocked(self):
        record, topology, geometry, _ = self.fixture()
        topology["rooms"][0]["cells"].append([1, 0, 0])
        evidence, issues = audit_trigger_frontiers(record, topology, geometry)
        self.assertEqual(len(issues), 1)
        self.assertIn(
            "trigger_cell_not_owned_only_by_destination",
            evidence["configured_frontiers"][0]["reasons"],
        )

    def test_duplicate_source_binding_is_blocked_and_unbound_native_id_reported(self):
        record, topology, geometry, _ = self.fixture()
        topology["position_trigger_gates"].append(
            dict(
                source_id=11,
                position=[1, 0, 0],
                source_room=1,
                destination_room=2,
            )
        )
        topology["position_trigger_gates"].append(
            dict(
                source_id=12,
                position=[9, 0, 0],
                source_room=1,
                destination_room=2,
            )
        )
        evidence, issues = audit_trigger_frontiers(record, topology, geometry)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn(
            "duplicate_trigger_binding", evidence["configured_frontiers"][1]["reasons"]
        )
        self.assertEqual(evidence["unbound_native_trigger_ids"], [])


if __name__ == "__main__":
    unittest.main()
