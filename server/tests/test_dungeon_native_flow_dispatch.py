"""Manual native routing must guard world movement and exits before mutation."""
import ast
from pathlib import Path
import unittest


class NativeFlowDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(
            (
                Path(__file__).resolve().parents[2] / "server/local_game_server.py"
            ).read_text()
        )

    def test_native_movement_guard_precedes_position_mutation(self):
        branch = next(
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "opcode == 13331 and loaded"
        )
        code = ast.unparse(branch)
        self.assertIn("dungeon_native_flow.enabled(walking_config", code)
        self.assertIn("dungeon_native_flow.validate_movement(", code)
        self.assertLess(
            code.index("dungeon_native_flow.validate_movement("),
            code.index("position_update_started"),
        )
        self.assertIn("unlocked_room=walking_progress", code)
        self.assertIn("movement_rejected", code)

    def test_manual_exit_checks_completion_before_authorized_leave(self):
        guard = next(
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test).startswith(
                "dungeon_native_flow.enabled(dungeon_config"
            )
        )
        code = ast.unparse(guard)
        self.assertIn("physical_exit['room_order'] != 1", code)
        self.assertIn("exit_progress['status'] != 'completed'", code)
        self.assertIn("raise ValueError('Native dungeon exit is locked')", code)

    def test_native_pending_victory_keeps_existing_durable_publication_receipt(self):
        fn = next(
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "deliver_dungeon_transitions"
        )
        code = ast.unparse(fn)
        self.assertIn("physical_publication_revision", code)
        guard = next(
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.If)
            and ast.unparse(n.test).startswith(
                "dungeon_native_flow.enabled(configuration"
            )
        )
        self.assertIsInstance(guard.body[-1], ast.Return)
        self.assertNotIn("dungeon_auto_transition.advance", ast.unparse(guard))
        self.assertNotIn("dungeon_auto_exit.complete", ast.unparse(guard))
