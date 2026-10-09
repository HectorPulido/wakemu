"""The ordinary dungeon escape command precedes privileged test-console dispatch."""
import ast
from pathlib import Path
import unittest


class DungeonEscapeDispatchTests(unittest.TestCase):
    def test_escape_is_public_and_uses_owned_exit_delivery(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "server/local_game_server.py"
        self.assertTrue(path.is_file(), f"Missing server source: {path}")
        for path in (path,):
            with self.subTest(source=str(path)):
                tree = ast.parse(path.read_text())
                chat = next(
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.If)
                    and ast.unparse(node.test) == "opcode == 12366 and loaded"
                )
                escape = chat.body[1]
                self.assertIsInstance(escape, ast.If)
                self.assertEqual(
                    ast.unparse(escape.test),
                    "text.lower() in ('!exitdungeon', '!salirmazmorra')",
                )
                code = ast.unparse(escape)
                self.assertNotIn("authorize_command", code)
                self.assertNotIn("WAKFU_TEST_CONSOLE", code)
                self.assertIn("dungeon_exit.leave_automatic", code)
                self.assertIn("COMBAT_SESSIONS.lookup_character(actor_id)", code)
                self.assertIn("fight is not None or combat_session is not None", code)
                self.assertIn("deliver_dungeon_transitions(before_action=True)", code)
                self.assertIn("dungeon_exit_requested", code)
                self.assertIn("dungeon_exit_rejected", code)
                self.assertIn("674", code)
                self.assertIsInstance(escape.body[-1], ast.Continue)
