"""Sequential shared-arena policy isolation and movement regressions."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from wakfu_server import (
    dungeon_native_flow,
    dungeon_runtime,
    dungeon_shared_arena,
    dungeon_object_states,
)
from wakfu_server.dungeon_runtime_config import prepare_configuration

ROOT = Path(__file__).resolve().parents[2]


class SharedArenaTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (
                ROOT / "docs/reports/dungeons/shared-arena-v1/native_dungeon_11.json"
            ).read_text()
        )
        self.topology = self.config["topology"]

    def test_exact_same_native_cells_and_no_fake_gates_required(self):
        self.assertEqual(len(dungeon_shared_arena.validate(self.topology)), 249)
        for mutate in (
            lambda t: t["rooms"][1]["cells"].pop(),
            lambda t: t["physical_doors"].append({"source_id": 1}),
            lambda t: t.pop("shared_arena_evidence"),
        ):
            topology = copy.deepcopy(self.topology)
            mutate(topology)
            with self.assertRaises(ValueError):
                dungeon_shared_arena.validate(topology)

    def test_configuration_compiler_enforces_policy(self):
        self.topology["rooms"][1]["cells"].pop()
        with self.assertRaises(ValueError):
            prepare_configuration(
                self.config["compiled_plan"],
                self.topology,
                self.config["route"],
                version=2,
                provenance="test",
            )

    def test_position_uses_authoritative_current_encounter_not_last_matching_stage(
        self,
    ):
        p = self.topology["rooms"][0]["anchor"]
        for order in (1, 2, 3):
            self.assertEqual(
                dungeon_runtime.room_for_position(
                    self.config, 549, *p, current_room=order
                ),
                order,
            )
        with self.assertRaises(ValueError):
            dungeon_runtime.room_for_position(self.config, 549, *p)
        with self.assertRaises(ValueError):
            dungeon_runtime.room_for_position(
                self.config, 549, 999, 999, 0, current_room=1
            )

    def test_all_stages_allow_native_movement_without_future_room_collision(self):
        a, b = self.topology["exploration_geometry"]["edges"][0]
        request = dict(
            start_position=dict(zip(("x", "y", "z"), a)),
            end_position=dict(zip(("x", "y", "z"), b)),
            steps=[dict(zip(("dx", "dy", "dz"), [b[i] - a[i] for i in range(3)]))],
        )
        for order in (1, 2, 3):
            self.assertEqual(
                dungeon_native_flow.validate_movement(
                    self.topology, request, unlocked_room=order
                ),
                tuple(b),
            )
        with self.assertRaises(ValueError):
            dungeon_native_flow.validate_movement(
                self.topology, request, unlocked_room=4
            )

    def test_exit_closed_until_final_victory_while_native_cancellation_binding_retained(
        self,
    ):
        binding = self.topology["physical_exit_objects"][0]
        self.assertEqual(binding["room_order"], 1)
        self.assertFalse(
            dungeon_native_flow.exit_available(self.topology, binding, completed=False)
        )
        self.assertTrue(
            dungeon_native_flow.exit_available(self.topology, binding, completed=True)
        )
        with patch(
            "wakfu_server.generic_transports.source",
            return_value={"id": binding["source_id"], "map_id": 549},
        ), patch.object(
            dungeon_object_states, "state_packet", side_effect=lambda source, **kw: kw
        ):
            for order in (1, 2, 3):
                self.assertFalse(
                    dungeon_shared_arena.packets(
                        self.topology, map_id=549, instance_id=1, unlocked_room=order
                    )[0]["usable"]
                )
            self.assertTrue(
                dungeon_shared_arena.packets(
                    self.topology,
                    map_id=549,
                    instance_id=1,
                    unlocked_room=3,
                    completed=True,
                )[0]["usable"]
            )
            with self.assertRaises(ValueError):
                dungeon_shared_arena.packets(
                    self.topology,
                    map_id=549,
                    instance_id=1,
                    unlocked_room=2,
                    completed=True,
                )

    def test_roster_grows_without_boss_duplication_or_early_boss(self):
        rooms = self.config["compiled_plan"]["rooms"]
        self.assertEqual(
            [sum(m["count"] for m in r["monsters"]) for r in rooms], [7, 8, 8]
        )
        self.assertEqual(
            [
                sum(m["count"] for m in r["monsters"] if m["ref_id"] == 2469)
                for r in rooms
            ],
            [0, 0, 1],
        )
        scores = [
            sum(m["count"] * m["native_min_level"] for m in r["monsters"])
            for r in rooms
        ]
        self.assertEqual(scores, [700, 800, 813])


if __name__ == "__main__":
    unittest.main()
