import ast
import unittest
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _function(tree, name):
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, got {len(matches)}")
    return matches[0]


class SpectatorTerminalDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf8")
        cls.tree = ast.parse(cls.source)
        cls.session = _function(cls.tree, "session")
        cls.idle = _function(cls.tree, "idle")

    def test_poll_preserves_terminal_identity_before_subscription_cleanup(self):
        poll_calls = [
            node
            for node in ast.walk(self.idle)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "poll"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "SPECTATORS"
        ]
        self.assertEqual(len(poll_calls), 1)
        poll_line = poll_calls[0].lineno
        close_line = next(
            node.lineno
            for node in ast.walk(self.idle)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "record"
            and any(
                keyword.arg == "event"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "combat_spectator_subscription_closed"
                for keyword in node.keywords
            )
        )
        self.assertLess(poll_line, close_line)
        self.assertIn("spectator_terminal_pending", self.source)
        self.assertIn("TerminalAck(", self.source)

    def test_terminal_ack_route_validates_lease_and_refreshes_world_without_participant_state(
        self,
    ):
        branches = [
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and ast.dump(node.test)
            == ast.dump(
                ast.parse(
                    "opcode == 12925 and loaded and spectator_terminal_pending is not None",
                    mode="eval",
                ).body
            )
        ]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        calls = [
            node.func.id
            for node in ast.walk(branch)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertIn("refresh_owned_world_after_spectating", calls)
        self.assertIn("record", calls)
        self.assertIn("pending_ack.validate", self.source)
        self.assertIn("STORE.current_session(account_id, generation)", self.source)
        participant_branch = next(
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and ast.dump(node.test)
            == ast.dump(
                ast.parse(
                    "opcode == 12925 and fight_messages is not None",
                    mode="eval",
                ).body
            )
        )
        self.assertGreater(participant_branch.lineno, branch.lineno)


if __name__ == "__main__":
    unittest.main()
