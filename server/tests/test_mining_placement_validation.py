"""Placement validation uses native world approaches, including nonwalkable targets."""
import json
from pathlib import Path
import unittest

from wakfu_server.mining_veins import validate_placements


class MiningPlacementValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/mining/NATIVE-MINING-SURFACES-COMPLETE.json"
        )
        cls.candidates = json.loads(report.read_text())["candidate_surfaces"]
        row = next(
            row
            for row in cls.candidates
            if row["map_id"] == 527
            and row["x"] == 74
            and row["y"] == -53
            and row["z"] == 3
            and 37 in row["eligible_resource_references"]
        )
        cls.placement = {
            "resource_uid": 781_527,
            "map_id": row["map_id"],
            "instance_id": 0,
            "x": row["x"],
            "y": row["y"],
            "z": row["z"],
            "resource_reference": 37,
            "stage": 1,
            "respawn_seconds": None,
            "provenance": {
                "evidence_kind": row["evidence_kind"],
                "chunk": row["chunk"],
                "ground_id": row["ground_id"],
                "environment_chunk_sha256": row["environment_chunk_sha256"],
            },
        }

    def surface(self, *, refs=(37,), approaches=((75, -53, 0),), ground_id=161):
        return lambda _map, _x, _y, _z: {
            "ground_id": ground_id,
            "eligible_refs": frozenset(refs),
            "approaches": frozenset(approaches),
        }

    def test_nonwalkable_resource_target_is_valid_with_adjacent_native_approach(self):
        accepted = validate_placements(
            [self.placement], navigation_surface=self.surface()
        )
        self.assertEqual([self.placement], accepted)

    def test_ground_fallback_requires_explicit_local_provenance_and_verified_mineral_ground(
        self,
    ):
        fallback = {
            **self.placement,
            "resource_reference": 242,
            "provenance": {
                **self.placement["provenance"],
                "species_ground_policy": "local-mineral-ground-fallback",
            },
        }
        accepted = validate_placements(
            [fallback], navigation_surface=self.surface(refs=(433,))
        )
        self.assertEqual([fallback], accepted)

    def test_ground_fallback_without_policy_or_mineral_native_ground_is_rejected(self):
        fallback = {**self.placement, "resource_reference": 242}
        with self.assertRaisesRegex(ValueError, "incompatible with native terrain"):
            validate_placements(
                [fallback], navigation_surface=self.surface(refs=(433,))
            )
        marked = {
            **fallback,
            "provenance": {
                **fallback["provenance"],
                "species_ground_policy": "local-mineral-ground-fallback",
            },
        }
        with self.assertRaisesRegex(ValueError, "incompatible with native terrain"):
            validate_placements([marked], navigation_surface=self.surface(refs=()))

    def test_unknown_native_surface_and_missing_native_approach_are_rejected(self):
        def unknown(*_args):
            raise ValueError("Unknown native mining surface")

        with self.assertRaisesRegex(ValueError, "Unknown native mining surface"):
            validate_placements([self.placement], navigation_surface=unknown)
        with self.assertRaisesRegex(ValueError, "no native harvesting approach"):
            validate_placements(
                [self.placement], navigation_surface=self.surface(approaches=())
            )


if __name__ == "__main__":
    unittest.main()
