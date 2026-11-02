"""Regressions for reviewed dungeon packet and composition boundaries."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_native_flow, dungeon_physical_doors
from wakfu_server import dungeon_main_completion, dungeon_excavation_runtime


class DungeonCompositeBoundaryTests(unittest.TestCase):
    def test_rotation_recipient_and_completion_pass_through_one_public_dispatcher(self):
        topology = dict(
            policy=dungeon_physical_doors.POLICY,
            rotation_choice=True,
            main_completion=dict(rule_key="fixture"),
        )
        with patch.object(
            dungeon_excavation_runtime, "flow_packets", return_value=((12344, b"gate"),)
        ) as rotation, patch.object(
            dungeon_main_completion, "packets", return_value=((13411, b"presentation"),)
        ) as completion:
            packets = dungeon_native_flow.packets(
                topology,
                map_id=1075,
                instance_id=901,
                unlocked_room=4,
                completed=True,
                recipient_character_id=78,
            )
        self.assertEqual(packets, ((12344, b"gate"), (13411, b"presentation")))
        rotation.assert_called_once_with(
            topology,
            map_id=1075,
            instance_id=901,
            unlocked_room=4,
            completed=True,
            recipient_character_id=78,
        )
        completion.assert_called_once_with(topology, completed=True)

    def test_movement_forwards_canonical_completion_to_physical_validator(self):
        topology = dict(policy=dungeon_physical_doors.POLICY)
        request = dict(start_position=dict(x=0, y=0, z=0), steps=[])
        with patch.object(
            dungeon_physical_doors, "validate_movement", return_value=(0, 0, 0)
        ) as physical:
            self.assertEqual(
                dungeon_native_flow.validate_movement(
                    topology, request, unlocked_room=2, completed=True
                ),
                (0, 0, 0),
            )
        self.assertIs(physical.call_args.kwargs["completed"], True)
        self.assertEqual(physical.call_args.kwargs["unlocked_room"], 2)

    def test_world_keeps_scene_binding_and_forwards_durable_walking_status(self):
        root = Path(__file__).resolve().parents[1]
        world = root / "local_game_server.py"
        if not world.exists():
            import wakfu_server

            world = (
                Path(wakfu_server.__file__).resolve().parents[1]
                / "local_game_server.py"
            )
        tree = ast.parse(world.read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        names = {node.func.id for node in calls if isinstance(node.func, ast.Name)}
        self.assertTrue(
            {"bind_scene", "scene_state_declarations", "combat_room_scene"} <= names
        )
        movement = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "dungeon_native_flow"
            and node.func.attr == "validate_movement"
        ]
        self.assertEqual(len(movement), 1)
        expression = next(
            keyword.value
            for keyword in movement[0].keywords
            if keyword.arg == "completed"
        )
        self.assertEqual(
            ast.unparse(expression), "walking_progress['status'] == 'completed'"
        )
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "walking_progress"
                for target in node.targets
            )
        ]
        self.assertEqual(len(assignments), 1)
        queries = [
            node.value
            for node in ast.walk(assignments[0].value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        self.assertTrue(
            any(
                "SELECT current_room,status FROM dungeon_room_runs" in value
                for value in queries
            )
        )

    def test_runtime_retains_all_projection_domains_and_original_scene_guard(self):
        runtime_source = Path(dungeon_native_flow.__file__).with_name(
            "dungeon_runtime.py"
        )
        tree = ast.parse(runtime_source.read_text())
        functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("combat_room_scene", functions)
        projection = ast.unparse(functions["configuration_for_instance"])
        for expression in (
            "dungeon_entry_paths.projected_for_instance",
            "dungeon_optional_continuations.project_configuration",
            "dungeon_excavation_runtime.hydrate",
        ):
            self.assertIn(expression, projection)
        initialize = ast.unparse(functions["initialize_instance"])
        self.assertIn("dungeon_excavation_tools.grant_entry", initialize)
        self.assertIn("dungeon_entry_paths.select_unfought_path", initialize)
        self.assertIn("require_component", ast.unparse(functions["combat_room_cells"]))
