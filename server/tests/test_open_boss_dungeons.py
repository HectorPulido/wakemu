"""Regression gates for singleton ultimate-boss arena preparation."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "prepare_open_boss_dungeons", ROOT / "server/tools/prepare_open_boss_dungeons.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OpenBossPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (ROOT / "docs/reports/dungeons/inventory.json").read_text()
        )["records"]
        cls.native = next(n for n in cls.inventory if n["key"] == "native:4")
        cls.flow = dict(
            status="open_geometry_no_separator",
            native_internal_teleports=[],
            first_encounter_reachable_cells=[[0, 0, 0]],
            entry=[0, 0, 0],
        )

    def refuse(self, native, flow):
        with self.assertRaises(ValueError):
            module.prepare(native, flow, {}, {}, [], {}, None)

    def test_reject_multispecies_identity(self):
        native = copy.deepcopy(self.native)
        native["native_species_pool"] *= 2
        self.refuse(native, self.flow)

    def test_reject_non_ultimate_boss(self):
        native = copy.deepcopy(self.native)
        native["native"]["type"] = "DUNGEON_3_PLAYERS"
        self.refuse(native, self.flow)

    def test_reject_unproved_internal_transport(self):
        self.refuse(self.native, dict(self.flow, native_internal_teleports=[{}]))

    def test_reject_removing_reviewed_preliminary_encounter(self):
        native = copy.deepcopy(self.native)
        native["guides"][0]["rooms"] *= 2
        self.refuse(native, self.flow)

    def test_reject_entry_outside_component(self):
        self.refuse(self.native, dict(self.flow, entry=[1, 0, 0]))

    def test_all_prepared_arenas_have_single_boss_and_native_exit_witness(self):
        from wakfu_server.dungeon_runtime_config import plan_from_configuration

        report = json.loads(
            (ROOT / "docs/reports/dungeons/OPEN-BOSS-CANDIDATES.json").read_text()
        )
        candidates = [
            r
            for r in report["records"]
            if r["status"] == "offline_configuration_prepared"
        ]
        self.assertGreaterEqual(len(candidates), 10)
        for row in candidates:
            with self.subTest(route=row["route"]):
                config = json.loads((ROOT / row["path"]).read_text())
                plan_from_configuration(config)
                rooms = config["compiled_plan"]["rooms"]
                self.assertEqual(len(rooms), 1)
                self.assertEqual(len(rooms[0]["monsters"]), 1)
                self.assertEqual(rooms[0]["monsters"][0]["count"], 1)
                self.assertEqual(rooms[0]["monsters"][0]["role"], "boss")
                self.assertEqual(
                    row["placement_validation"]["status"], "candidate_validated"
                )
                self.assertEqual(
                    row["sequence_validation"]["status"],
                    "offline_exploration_sequence_validated",
                )
                self.assertTrue(row["sequence_validation"]["final_exit_path"])
                self.assertEqual(config["topology"]["physical_doors"], [])
