"""Regression gates for the reviewed native one-encounter lobby arenas."""
import importlib.util
import json
from pathlib import Path
import unittest

from wakfu_server import dungeon_physical_doors
from wakfu_server.dungeon_runtime_config import plan_from_configuration

ROOT = Path(__file__).resolve().parents[2]


class ReviewedBossLobbyArenasTests(unittest.TestCase):
    def candidates(self):
        report = json.loads(
            (
                ROOT
                / "docs/reports/dungeons/REVIEWED-BOSS-LOBBY-ARENAS-20261010-V1.json"
            ).read_text()
        )
        return [
            (r, json.loads((ROOT / r["path"]).read_text())) for r in report["records"]
        ]

    def test_native_lobby_gates_open_before_any_victory(self):
        for row, config in self.candidates():
            with self.subTest(route=row["route"]):
                topology = config["topology"]
                self.assertFalse(dungeon_physical_doors.blocked_cells(topology, 1))
                packets = dungeon_physical_doors.packets(
                    dict(topology, physical_exit_objects=[]),
                    map_id=topology["asset_map_id"],
                    instance_id=1,
                    unlocked_room=1,
                )
                self.assertEqual(len(packets), 3 if row["key"] == "native:79" else 5)
                self.assertTrue(all(opcode == 12344 for opcode, body in packets))

    def test_no_invented_preliminary_encounter_or_duplicate_boss(self):
        expected = {"native:79": {2708, 2709, 2710, 2714}, "native:196": {5589}}
        for row, config in self.candidates():
            plan_from_configuration(config)
            self.assertEqual(len(config["compiled_plan"]["rooms"]), 1)
            monsters = config["compiled_plan"]["rooms"][0]["monsters"]
            self.assertEqual({m["ref_id"] for m in monsters}, expected[row["key"]])
            self.assertTrue(
                all(m["count"] == 1 and m["role"] == "boss" for m in monsters)
            )

    def test_all_bosses_spawn_beyond_lobby_and_have_engagement_witness(self):
        for row, config in self.candidates():
            lobby = set(map(tuple, config["topology"]["lobby_cells"]))
            positions = set(
                map(tuple, row["placement_validation"]["rooms"][0]["monster_positions"])
            )
            self.assertFalse(lobby & positions)
            witness = row["sequence_validation"]["rooms"][0]["engagement_witness"]
            self.assertIn(tuple(witness["target"]), positions)
            self.assertEqual(
                row["sequence_validation"]["status"],
                "offline_exploration_sequence_validated",
            )
            self.assertEqual(len(config["topology"]["physical_exit_objects"]), 1)


if __name__ == "__main__":
    unittest.main()
