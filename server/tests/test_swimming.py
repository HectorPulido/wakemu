import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import swimming
from wakfu_server import native_catalog


class SwimmingTopologyTests(unittest.TestCase):
    def setUp(self):
        swimming.cells.cache_clear()

    def tearDown(self):
        swimming.cells.cache_clear()

    def test_map_1134_native_surface_lookup_uses_full_xyz(self):
        self.assertTrue(
            swimming.at_position({"map_id": 1134, "x": -18, "y": 116, "z": -4})
        )
        self.assertFalse(
            swimming.at_position({"map_id": 1134, "x": 0, "y": 116, "z": 21})
        )
        # Same ground coordinates with a different height are a different cell.
        self.assertFalse(
            swimming.at_position({"map_id": 1134, "x": -18, "y": 116, "z": -3})
        )

    def test_unexported_map_fails_closed_instead_of_inventing_dry_surface(self):
        with self.assertRaisesRegex(ValueError, "topology is unavailable"):
            swimming.at_position({"map_id": 999999, "x": -18, "y": 116, "z": -4})

    def test_invalid_map_and_noninteger_position_are_rejected(self):
        for character in (
            {"map_id": True, "x": -18, "y": 116, "z": -4},
            {"map_id": 1134, "x": -18, "y": 116, "z": -4.0},
        ):
            with self.subTest(character=character), self.assertRaises(ValueError):
                swimming.at_position(character)

    def test_manifest_accounts_for_verified_and_unknown_maps_without_fallback(self):
        manifest_path = swimming.DATA_ROOT / "swimming-maps-manifest.json"
        manifest = json.loads(native_catalog.read_text(manifest_path))
        verified = set(manifest["verified_map_ids"])
        unknown = set(manifest["unverified_map_ids"])
        installed = {
            int(path.stem)
            for path in (swimming.DATA_ROOT / "swimming-maps").glob("*.json")
        }

        self.assertEqual(manifest["verified_map_count"], 742)
        self.assertEqual(manifest["failed_map_count"], 219)
        self.assertEqual(len(verified), 742)
        self.assertEqual(len(unknown), 219)
        self.assertEqual(installed, verified)
        self.assertTrue(verified.isdisjoint(unknown))
        for map_id in sorted(unknown):
            with self.subTest(map_id=map_id), self.assertRaisesRegex(
                ValueError, "topology is unavailable"
            ):
                swimming.cells(map_id)

    def test_verified_empty_catalog_requires_complete_empty_certificate(self):
        valid_empty = {
            "map_id": 811001,
            "surface_count": 0,
            "swimming_cells_xyz": [],
            "native_vf_validation": {
                "mismatches": 0,
                "checked_surfaces": 0,
                "verified_empty": True,
                "checked_chunks": 1,
            },
        }
        rejected = (
            {
                **valid_empty,
                "native_vf_validation": {
                    **valid_empty["native_vf_validation"],
                    "verified_empty": False,
                },
            },
            {
                **valid_empty,
                "native_vf_validation": {
                    **valid_empty["native_vf_validation"],
                    "checked_chunks": 0,
                },
            },
            {**valid_empty, "swimming_cells_xyz": [[1, 2, 3]]},
            {
                **valid_empty,
                "native_vf_validation": {
                    **valid_empty["native_vf_validation"],
                    "checked_surfaces": 1,
                },
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            maps = data_root / "swimming-maps"
            maps.mkdir()
            with patch.object(swimming, "DATA_ROOT", data_root):
                (maps / "811001.json").write_text(json.dumps(valid_empty))
                self.assertEqual(swimming.cells(811001), frozenset())
                for offset, metadata in enumerate(rejected, start=1):
                    map_id = 811001 + offset
                    metadata["map_id"] = map_id
                    (maps / f"{map_id}.json").write_text(json.dumps(metadata))
                    with self.subTest(map_id=map_id), self.assertRaisesRegex(
                        ValueError, "Unverified native swimming topology"
                    ):
                        swimming.cells(map_id)

    def test_boolean_validation_counts_are_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            maps = data_root / "swimming-maps"
            maps.mkdir()
            with patch.object(swimming, "DATA_ROOT", data_root):
                for map_id, validation in (
                    (811100, {"mismatches": False, "checked_surfaces": 0}),
                    (811101, {"mismatches": 0, "checked_surfaces": False}),
                ):
                    record = {
                        "map_id": map_id,
                        "surface_count": 0,
                        "swimming_cells_xyz": [],
                        "native_vf_validation": {
                            **validation,
                            "verified_empty": True,
                            "checked_chunks": 1,
                        },
                    }
                    (maps / f"{map_id}.json").write_text(json.dumps(record))
                    with self.subTest(map_id=map_id), self.assertRaisesRegex(
                        ValueError, "Unverified native swimming topology"
                    ):
                        swimming.cells(map_id)
