"""Reviewed encounter preservation and equivalent exterior-exit regression gates."""
import copy
import json
from pathlib import Path
import unittest
from prepare_reviewed_open_arenas import reviewed_roster

ROOT = Path(__file__).resolve().parents[2]


class ReviewedOpenArenaTests(unittest.TestCase):
    def setUp(self):
        inventory = json.loads(
            (ROOT / "docs/reports/dungeons/inventory.json").read_text()
        )["records"]
        self.native = next(n for n in inventory if n["key"] == "native:133")

    def test_preserves_three_reviewed_adds_and_singleton_boss(self):
        roster = reviewed_roster(self.native)
        self.assertEqual(
            {m["ref_id"]: m["count"] for m in roster},
            {4651: 1, 4649: 1, 4648: 1, 4650: 1},
        )
        self.assertEqual([m["ref_id"] for m in roster if m["role"] == "boss"], [4651])

    def test_never_infer_unknown_add_quantity(self):
        native = copy.deepcopy(self.native)
        native["guides"][0]["rooms"][0]["monsters"][1]["count"] = None
        with self.assertRaisesRegex(ValueError, "Non-boss"):
            reviewed_roster(native)

    def test_never_collapse_multiple_encounters(self):
        native = copy.deepcopy(self.native)
        native["guides"][0]["rooms"] *= 2
        with self.assertRaises(ValueError):
            reviewed_roster(native)

    def test_reject_unresolved_native_identity(self):
        native = copy.deepcopy(self.native)
        native["guides"][0]["rooms"][0]["monsters"][0]["ref_id"] = 999999
        with self.assertRaises(ValueError):
            reviewed_roster(native)

    def test_kali_native_exit_aliases_share_identical_destination(self):
        config = json.loads(
            (
                ROOT
                / ".runtime/local/reviewed-open-arena-configurations/native_dungeon_121.json"
            ).read_text()
        )
        aliases = config["topology"]["equivalent_native_exit_aliases"]
        self.assertEqual({e["source_id"] for e in aliases}, {27522, 27523})
        self.assertEqual(
            len(
                {
                    tuple(e["destination"][k] for k in ("map_id", "x", "y", "z"))
                    for e in aliases
                }
            ),
            1,
        )
        self.assertEqual(len(config["compiled_plan"]["rooms"][0]["monsters"]), 4)

    def test_frozen_configurations_roundtrip_install_validation(self):
        from wakfu_server.dungeon_runtime_config import prepare_configuration

        for identity in (121, 133):
            config = json.loads(
                (
                    ROOT
                    / f".runtime/local/reviewed-open-arena-configurations/native_dungeon_{identity}.json"
                ).read_text()
            )
            reconstructed = prepare_configuration(
                config["compiled_plan"],
                config["topology"],
                config["route"],
                version=config["version"],
                provenance=config["provenance"],
            )
            self.assertEqual(config, reconstructed)
