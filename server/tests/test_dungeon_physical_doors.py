"""Native walking gates preserve durable victories without changing combat terrain."""
import ast
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from wakfu_server import dungeon_physical_doors as doors
from wakfu_server.dungeon_runtime_config import plan_from_configuration

ROOT = Path(__file__).resolve().parents[2]


class PhysicalDoorTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (ROOT / "docs/reports/dungeons/TOFU-RUNTIME-V3.json").read_text()
        )
        self.topology = self.config["topology"]
        self.flow = json.loads(
            (ROOT / "docs/reports/dungeons/TOFU-NATIVE-FLOW.json").read_text()
        )

    def request(self, path):
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(zip(("dx", "dy", "dz"), [b[i] - a[i] for i in range(3)]))
                for a, b in zip(path, path[1:])
            ],
        )

    def test_native_stairs_allowed_but_first_gate_locked_before_victory(self):
        path = self.flow["stages"][0]["directed_boundary_path"]
        doors.validate_movement(self.topology, self.request(path[:-1]), unlocked_room=1)
        with self.assertRaisesRegex(ValueError, "locked room gate"):
            doors.validate_movement(self.topology, self.request(path), unlocked_room=1)
        doors.validate_movement(self.topology, self.request(path), unlocked_room=2)

    def test_first_group_can_be_engaged_from_native_arrival_with_both_doors_closed(
        self,
    ):
        witness = json.loads(
            (
                ROOT / "docs/reports/dungeons/TOFU-FIRST-GROUP-REACHABILITY.json"
            ).read_text()
        )
        path = witness["path"]
        self.assertEqual(path[0], [14, -25, 0])
        self.assertEqual(witness["boss_count"], 0)
        self.assertEqual(witness["closed_doors"], [26874, 26875])
        self.assertEqual(witness["steps"], 14)
        first_cells = set(map(tuple, self.topology["rooms"][0]["cells"]))
        self.assertTrue(set(map(tuple, path)).issubset(first_cells))
        monsters = set(map(tuple, witness["monster_positions"]))
        self.assertTrue(monsters.issubset(first_cells))
        self.assertFalse(monsters.intersection(map(tuple, path)))
        target = witness["engagement_target"]
        approach = path[-1]
        self.assertEqual(abs(target[0] - approach[0]) + abs(target[1] - approach[1]), 1)
        self.assertEqual(target[2], approach[2])
        doors.validate_movement(self.topology, self.request(path), unlocked_room=1)

    def test_second_gate_requires_second_victory(self):
        request = self.request(self.flow["stages"][-1]["directed_exit_path"])
        with self.assertRaises(ValueError):
            doors.validate_movement(self.topology, request, unlocked_room=2)
        doors.validate_movement(self.topology, request, unlocked_room=3)

    def test_diagonal_gate_bypass_rejected(self):
        topology = dict(
            policy=doors.POLICY,
            rooms=[{}, {}],
            physical_doors=[dict(position=[1, 0, 0], destination_room=2)],
            exploration_geometry=dict(
                cells=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
                edges=[
                    [[0, 0, 0], [1, 0, 0]],
                    [[1, 0, 0], [1, 1, 0]],
                    [[0, 0, 0], [0, 1, 0]],
                    [[0, 1, 0], [1, 1, 0]],
                ],
            ),
        )
        with self.assertRaisesRegex(ValueError, "diagonal"):
            doors.validate_movement(
                topology, self.request([[0, 0, 0], [1, 1, 0]]), unlocked_room=1
            )
        doors.validate_movement(
            topology, self.request([[0, 0, 0], [1, 1, 0]]), unlocked_room=2
        )

    def test_three_rooms_single_boss_only_in_final_room(self):
        plan = plan_from_configuration(self.config)
        self.assertEqual(len(plan.rooms), 3)
        self.assertEqual(
            [sum(m.count for m in r.monsters if m.ref_id == 1259) for r in plan.rooms],
            [0, 0, 1],
        )
        self.assertEqual(
            [sum(m.count for m in r.monsters) for r in plan.rooms], [8, 8, 8]
        )

    def test_physical_gate_packets_use_state_not_usability(self):
        topology = dict(self.topology, physical_exit_objects=[])
        first = doors.packets(topology, map_id=1087, instance_id=42, unlocked_room=1)
        after = doors.packets(topology, map_id=1087, instance_id=42, unlocked_room=2)
        self.assertEqual(
            [struct.unpack(">q", body[:8])[0] for _, body in first], [26874, 26875]
        )
        self.assertEqual(
            [struct.unpack(">h", body[17:19])[0] for _, body in first], [1, 1]
        )
        self.assertEqual(
            [struct.unpack(">h", body[17:19])[0] for _, body in after], [0, 1]
        )
        self.assertEqual([body[19:21] for _, body in after], [b"\x00\x00", b"\x01\x00"])

    def test_tampered_frozen_configuration_rejected(self):
        self.config["compiled_plan"]["rooms"][0]["monsters"][0]["count"] = 99
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            plan_from_configuration(self.config)

    def test_session_dispatch_validates_physical_walk_before_committing_movement(self):
        source = ROOT / "server/local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13331 and loaded"
        )
        validation = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "validate_movement"
        )
        commit = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "movement_state"
        )
        correction = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "send"
            and len(node.args) >= 3
            and isinstance(node.args[2], ast.Constant)
            and node.args[2].value == 13530
        )
        self.assertLess(validation.lineno, commit.lineno)
        self.assertLess(correction.lineno, commit.lineno)
        self.assertTrue(
            any(isinstance(node, ast.Continue) for node in ast.walk(branch))
        )

    def test_invalid_frontier_rejected(self):
        for value in (0, 4, True):
            with self.assertRaises(ValueError):
                doors.blocked_cells(self.topology, value)


if __name__ == "__main__":
    unittest.main()
