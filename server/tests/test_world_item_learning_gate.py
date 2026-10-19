"""Exercise the actual world cqd13220 branches without a network session."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import cosmetic_learning


class WorldItemLearningGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        cls.actions = {}
        for row in _rules().values():
            cls.actions.setdefault(
                row.get("use_action_class"), row.get("use_action_id")
            )
        source = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        branches = [
            node
            for node in ast.walk(source)
            if isinstance(node, ast.If)
            and ast.unparse(node.test).startswith("opcode == 13220 and loaded")
        ]
        if len(branches) != 2:
            raise AssertionError("Expected both native world item branches")
        learning, positional = map(deepcopy, branches)
        positional.orelse = []
        learning.orelse = [positional]
        module = ast.Module(
            body=[
                ast.For(
                    target=ast.Name(id="iteration", ctx=ast.Store()),
                    iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                    body=[learning],
                    orelse=[],
                )
            ],
            type_ignores=[],
        )
        cls.driver = compile(
            ast.fix_missing_locations(module), "<actual-world-13220>", "exec"
        )

    def run_request(self, body):
        learned = Mock(
            return_value=dict(character=dict(id=7), packets=[], applied=True)
        )
        planting = Mock(side_effect=ValueError("Planting authority reached"))
        record = Mock()

        def validate_learning(*args):
            if cosmetic_learning.request_action_class(args[-1]) == "bIi":
                raise ValueError("Planting is not learning")
            return learned(*args)

        bindings = dict(
            opcode=13220,
            loaded=True,
            body=body,
            fight=None,
            STORE=object(),
            account_id=3,
            generation=9,
            character=dict(id=7),
            connection=object(),
            service="world",
            send=Mock(),
            record=record,
            refresh_owned_character=lambda value: value,
            owned_planting_character=planting,
            WORLD=object(),
            POSITIONS=object(),
            wire=SimpleNamespace(chat=lambda *args: b"error"),
        )
        with patch(
            "wakfu_server.cosmetic_learning.learn_item", side_effect=validate_learning
        ):
            exec(self.driver, bindings)
        return learned, planting, record

    def body(self, native_class):
        prefix = struct.pack(">iq", self.actions[native_class], 71)
        if native_class == "bHv":
            return prefix + struct.pack(">q", 72)
        if native_class == "bIi":
            return prefix + struct.pack(">ii", -3, 4)
        return prefix

    def test_twenty_byte_mimic_and_twelve_byte_learning_never_enter_planting(self):
        for native_class in cosmetic_learning.LEARNING_ACTION_CLASSES:
            with self.subTest(native_class=native_class):
                learned, planting, record = self.run_request(self.body(native_class))
                learned.assert_called_once()
                planting.assert_not_called()
                self.assertEqual(record.call_args.kwargs["event"], "item_learned")

    def test_genuine_native_seed_keeps_its_existing_planting_authority(self):
        learned, planting, record = self.run_request(self.body("bIi"))
        learned.assert_not_called()
        planting.assert_called_once()
        self.assertEqual(record.call_args.kwargs["event"], "planting_rejected")

    def test_malformed_or_wrong_class_requests_cannot_fall_through_to_planting(self):
        malformed = [bytes(size) for size in (0, 11, 13, 19, 21)]
        malformed += [
            self.body("bHv")[:12],
            self.body("bIt") + bytes(8),
            self.body("bIi")[:12],
            struct.pack(">iqq", self.actions["bHv"], 71, 0),
            struct.pack(">iqq", 2**30, 71, 72),
        ]
        for body in malformed:
            with self.subTest(body=body):
                learned, planting, record = self.run_request(body)
                learned.assert_not_called()
                planting.assert_not_called()
                self.assertEqual(
                    record.call_args.kwargs["event"], "item_learning_rejected"
                )


if __name__ == "__main__":
    unittest.main()
