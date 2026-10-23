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
        if len(branches) != 1:
            raise AssertionError("Expected one unified native world item branch")
        dispatch = deepcopy(branches[0])
        # This is an elif node in the larger packet loop; its orelse contains
        # every later opcode branch, including closures using outer nonlocals.
        dispatch.orelse = []
        module = ast.Module(
            body=[
                ast.For(
                    target=ast.Name(id="iteration", ctx=ast.Store()),
                    iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                    body=[dispatch],
                    orelse=[],
                )
            ],
            type_ignores=[],
        )
        cls.driver = compile(
            ast.fix_missing_locations(module), "<actual-world-13220>", "exec"
        )

    def run_request(self, body, *, simple_result=None):
        learned = Mock(
            return_value=dict(character=dict(id=7), packets=[], applied=True)
        )
        planting = Mock(side_effect=ValueError("Planting authority reached"))
        record = Mock()
        simple_use = Mock(return_value=simple_result)

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
            character=dict(id=7, map_id=22, instance_id=5, direction=3),
            position={"x": 2, "y": 3, "z": 1},
            connection=object(),
            service="world",
            send=Mock(),
            record=record,
            refresh_owned_character=lambda value: value,
            open_item_recustomization=Mock(return_value=False),
            play_inventory_emote=Mock(return_value=False),
            use_inventory_teleport=Mock(return_value=False),
            play_inventory_script=Mock(return_value=False),
            spawn_inventory_test_actor=Mock(return_value=False),
            publish_nation_character=Mock(side_effect=lambda value: value),
            publish_consumable_character=Mock(),
            owned_planting_character=planting,
            WORLD=SimpleNamespace(update=Mock()),
            COMBAT_TEST_WP=9,
            PLAYER_TEMPLATE=object(),
            POSITIONS=object(),
            wire=SimpleNamespace(
                chat=lambda *args: b"error",
                refresh_player=lambda *args: (13912, b"refreshed"),
            ),
        )
        with (
            patch(
                "wakfu_server.cosmetic_learning.learn_item",
                side_effect=validate_learning,
            ),
            patch("wakfu_server.simple_item_actions.use", simple_use),
        ):
            exec(self.driver, bindings)
        return learned, planting, record, simple_use, bindings

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
                learned, planting, record, _, _ = self.run_request(
                    self.body(native_class)
                )
                learned.assert_called_once()
                planting.assert_not_called()
                self.assertEqual(record.call_args.kwargs["event"], "item_learned")

    def test_genuine_native_seed_keeps_its_existing_planting_authority(self):
        learned, planting, record, _, _ = self.run_request(self.body("bIi"))
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
                learned, planting, record, _, _ = self.run_request(body)
                learned.assert_not_called()
                planting.assert_not_called()
                self.assertIn(
                    record.call_args.kwargs["event"],
                    {"simple_item_action_rejected", "item_learning_rejected"},
                )

    def test_simple_native_prefix_dispatches_to_the_item_action_executor(self):
        body = self.body("bHI")
        saved = dict(id=7, map_id=1, instance_id=0, direction=1, x=1, y=1, z=0)
        result = dict(character=saved, packets=[(12470, b"consume")], consumed=1)
        learned, planting, record, simple_use, bindings = self.run_request(
            body, simple_result=result
        )
        simple_use.assert_called_once()
        self.assertEqual(simple_use.call_args.args[3], 7)
        learned.assert_not_called()
        planting.assert_not_called()
        self.assertEqual(record.call_args.kwargs["event"], "simple_item_action_used")
        self.assertEqual(bindings["send"].call_args.args[2:], (12470, b"consume"))

    def test_xp_publication_uses_live_world_position_and_native_progression_body(self):
        body = self.body("bHK")
        stale = dict(id=7, map_id=3, instance_id=4, direction=1, x=1, y=2, z=0)
        result = dict(character=stale, packets=[(13912, b"stale-xp")], consumed=1)
        with patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            return_value=(13912, b"native-xp"),
        ) as progression:
            _, _, record, simple_use, bindings = self.run_request(
                body, simple_result=result
            )
        simple_use.assert_called_once()
        progression.assert_called_once()
        published = progression.call_args.args[0]
        self.assertEqual(
            tuple(
                published[key]
                for key in ("map_id", "instance_id", "direction", "x", "y", "z")
            ),
            (22, 5, 3, 2, 3, 1),
        )
        self.assertEqual(bindings["send"].call_args.args[2:], (13912, b"native-xp"))
        bindings["WORLD"].update.assert_called_once()
        bindings["publish_consumable_character"].assert_called_once_with(
            bindings["character"]
        )
        self.assertEqual(record.call_args.kwargs["event"], "simple_item_action_used")


if __name__ == "__main__":
    unittest.main()
