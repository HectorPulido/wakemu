"""Coverage audit for every resource with a native mining action."""
import json
from pathlib import Path
import unittest

from wakfu_server import native_catalog
from wakfu_server.mining_products import supports_action
from wakfu_server.paths import DATA_ROOT


class NativeMiningCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = native_catalog.load(DATA_ROOT / "plant-resources.json")
        cls.by_reference = {row["resource_reference"]: row for row in cls.resources}
        cls.mining = {}
        for resource in cls.resources:
            actions = [
                (stage["stage_id"], action)
                for stage in resource["stage_definitions"]
                for action in stage["actions"]
                if action["profession_id"] == 73
            ]
            if actions:
                cls.mining[resource["resource_reference"]] = actions

    @staticmethod
    def harvestable(actions):
        return [
            (stage, action)
            for stage, action in actions
            if action["item_reference"] > 0
            and not action["criteria"].strip()
            and action["raw_getters"]["cvF"] == 0
        ]

    def test_all_native_mining_references_have_a_supported_or_unresolved_fixed_output_class(
        self,
    ):
        supported = {
            reference
            for reference, actions in self.mining.items()
            if self.harvestable(actions)
        }
        unsupported = set(self.mining) - supported

        self.assertEqual(len(self.mining), 51)
        self.assertEqual(len(supported), 50)
        self.assertEqual(unsupported, {643})
        self.assertTrue(
            all(action["item_reference"] == 0 for _, action in self.mining[643]),
            "resource643 has no fixed product that the current harvest path can grant",
        )
        self.assertTrue(
            all(action["product_references"] for _, action in self.mining[643]),
            "resource643 does expose alternatives whose selection rule is unverified",
        )

    def test_backend_has_a_supported_harvest_action_for_each_of_the_51_native_references(
        self,
    ):
        supported = {
            reference
            for reference, actions in self.mining.items()
            if any(supports_action(action) for _, action in actions)
        }
        self.assertEqual(set(self.mining), supported)

    def test_every_surface_evidence_reference_belongs_to_the_native_audit(self):
        evidence_path = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/mining/NATIVE-MINING-SURFACES.json"
        )
        evidence = json.loads(evidence_path.read_text())
        surface_references = {
            reference
            for row in evidence["candidate_surfaces"]
            for reference in row["eligible_resource_references"]
        }

        self.assertTrue(surface_references)
        self.assertLessEqual(surface_references, set(self.mining))
        self.assertIn(643, surface_references)
        unsupported_fixed_output = {
            reference
            for reference, actions in self.mining.items()
            if not self.harvestable(actions)
        }
        self.assertEqual(surface_references & unsupported_fixed_output, {643})
