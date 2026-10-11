"""Native stele packet, rotation and cumulative selection contracts."""
import json
from pathlib import Path
import re
import struct
import unittest

from wakfu_server import dungeon_stele
from wakfu_server.wire import proto_fields


class DungeonSteleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sql = (
            Path(__file__).resolve().parents[1]
            / "migrations/133_native_dungeon_steles.sql"
        ).read_text()
        cls.configurations = [
            json.loads(s.replace("''", "'"))
            for s in re.findall(
                r"INSERT INTO dungeon_stele_definitions VALUES \(\d+,'(.*?)'::jsonb\);",
                sql,
            )
        ]

    def test_installed_placements_use_complete_fixed_rotation_definitions(self):
        self.assertEqual(len(self.configurations), 35)
        for config in self.configurations:
            self.assertEqual(len(config["source_sha256"]), 64)
            for tier in config["tiers"]:
                self.assertLessEqual(
                    len(tier["dynamic_rewards"]), tier["dynamic_rewards_count"]
                )
            self.assertTrue(
                all(
                    d["state_id"] > 0 and d["weight"] > 0
                    for d in config["difficulties"]
                )
            )

    def test_rejected_browse_cancels_only_native_stele_occupation(self):
        self.assertEqual(
            dungeon_stele.cancel_packet(99), (12088, struct.pack(">BhqI", 3, 34, 99, 0))
        )
        for invalid in (True, 0, -1):
            with self.assertRaises(ValueError):
                dungeon_stele.cancel_packet(invalid)

    def test_native_request_has_definition_then_difficulties_then_rewards(self):
        body = struct.pack(">qhii hii", 6, 2, 12, 11, 2, 60, 61)
        self.assertEqual(dungeon_stele.request(body), (6, [11, 12], [60, 61]))
        for malformed in (
            body[:-1],
            body + b"\0",
            struct.pack(">qh", 6, -1),
            struct.pack(">qhii h", 6, 2, 11, 11, 0),
        ):
            with self.assertRaises(ValueError):
                dungeon_stele.request(malformed)

    def test_locked_or_unrotated_rewards_cannot_be_selected(self):
        config = self.configurations[0]
        tier = config["tiers"][0]
        reward = tier["dynamic_rewards"][0]["id"]
        with self.assertRaises(ValueError):
            dungeon_stele.plan(config, [], [reward])
        with self.assertRaises(ValueError):
            dungeon_stele.plan(config, [config["difficulties"][0]["id"]], [2**30])
        with self.assertRaises(ValueError):
            dungeon_stele.plan(config, [2**30], [])

    def test_every_tier_publishes_only_current_selected_dynamic_items(self):
        for config in self.configurations:
            difficulties = [r["id"] for r in config["difficulties"]]
            rewards = sorted(
                {r["id"] for t in config["tiers"] for r in t["dynamic_rewards"]}
            )
            chosen = dungeon_stele.plan(config, difficulties, rewards)
            self.assertEqual(
                chosen["item_references"],
                sorted({r["item_reference"] for r in chosen["rewards"]}),
            )
            opcode, body = dungeon_stele.information(config, chosen)
            self.assertEqual(opcode, 13326)
            fields = list(proto_fields(body))
            self.assertEqual(fields[0], (8, config["id"]))
            self.assertEqual([v for t, v in fields if t == 24], sorted(difficulties))
            self.assertEqual(fields[-1], (32, 1))
            self.assertEqual(
                len([1 for t, _ in fields if t == 18]), len(config["tiers"])
            )

    def test_free_option_threshold_uses_native_tier_weight(self):
        config = self.configurations[0]
        chosen = dungeon_stele.plan(
            config, [r["id"] for r in config["difficulties"]], []
        )
        self.assertEqual(chosen["paid_options"], 0)
        self.assertTrue(chosen["rewards"])
        self.assertEqual(
            chosen["state_ids"],
            [
                r["state_id"]
                for r in sorted(config["difficulties"], key=lambda r: r["id"])
            ],
        )


if __name__ == "__main__":
    unittest.main()
