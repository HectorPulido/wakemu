"""The Incarnam outro restores native UI before publishing Rii bootstrap."""

import ast
import struct
import unittest
from source_view import WorldSourcePath as Path

from wakfu_server.achievements.incarnam_tutorial import (
    interface_recovery_packet,
    scenario_packet,
)


class IncarnamExitPresentationTests(unittest.TestCase):
    def test_native_end_tutorial_presentation_wire_bytes(self):
        self.assertEqual(
            scenario_packet(22500),
            (13411, struct.pack(">BiiB", 0, 22500, 2500, 0)),
        )

    def test_native_interface_recovery_wire_bytes(self):
        self.assertEqual(
            interface_recovery_packet(),
            (13411, struct.pack(">BiiB", 0, 16608, 2071, 0)),
        )

    def test_end_tutorial_ui_restore_precedes_public_rii_bootstrap(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server"
            / "application"
            / "session_world.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        handlers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and ast.unparse(node.test) == "scenario_callback == 22359"
        ]
        self.assertEqual(len(handlers), 1)
        handler = handlers[0]
        calls = sorted(
            (
                node.lineno,
                ast.unparse(node.func),
                tuple(ast.unparse(argument) for argument in node.args),
            )
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
        )

        def line_of(function, first_argument):
            matching = [
                line
                for line, name, args in calls
                if name == function and args and args[0] == first_argument
            ]
            self.assertEqual(len(matching), 1, (function, first_argument))
            return matching[0]

        transition_line = line_of(
            "self.state.mission_transport.transition", "self.runtime.STORE"
        )
        presentation_line = line_of(
            "self.state.incarnam_tutorial.scenario_packet", "22500"
        )
        bootstrap_line = line_of("self.publish_public_transport", "self.state.route")
        recovery_lines = [
            line
            for line, name, args in calls
            if name == "self.state.incarnam_tutorial.interface_recovery_packet"
            and not args
        ]
        self.assertEqual(len(recovery_lines), 1)
        self.assertLess(transition_line, presentation_line)
        self.assertLess(presentation_line, recovery_lines[0])
        self.assertLess(recovery_lines[0], bootstrap_line)


if __name__ == "__main__":
    unittest.main()
