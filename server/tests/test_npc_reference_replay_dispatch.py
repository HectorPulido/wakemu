"""Execute the real root replay dispatch branch without starting its services."""
import ast
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from protocol_codec import Reader

import test_npc_capture_scene as scene_tests


class NpcReferenceReplayDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "local_game_server.py").read_text())
        replay = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "replay"
        )
        dispatch = next(
            node
            for node in ast.walk(replay)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "frame['opcode'] == 23548"
        )
        cls.code = compile(
            ast.fix_missing_locations(ast.Module(body=[dispatch], type_ignores=[])),
            "<actual-native-reference-replay>",
            "exec",
        )
        wire_tree = ast.parse((root / "wakfu_server/wire.py").read_text())
        strip = next(
            node
            for node in wire_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "without_captured_players"
        )
        namespace = dict(Reader=Reader, struct=struct)
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[strip], type_ignores=[])),
                "<actual-wire-player-filter>",
                "exec",
            ),
            namespace,
        )
        cls.strip = staticmethod(namespace["without_captured_players"])
        cls.replay_ast = replay

    def run_branch(self, character, registry=(), opcode=12608):
        original = scene_tests.CapturedNpcSceneTests().packet()
        wire = SimpleNamespace(
            without_captured_players=self.strip,
            adapt=Mock(return_value=b"owned-profile"),
        )
        context = dict(
            frame={"opcode": opcode},
            original=original,
            character=character,
            registry_actor_ids=registry,
            wire=wire,
            account_id=5,
            STORE=SimpleNamespace(account_kamas=lambda _: 0),
        )
        exec(self.code, context)
        return context, wire

    def test_actual_replay_suppresses_foreign_map_and_private_captured_npcs(self):
        for character in (
            dict(map_id=1387, instance_id=0),
            dict(map_id=1134, instance_id=1),
        ):
            context, _ = self.run_branch(character)
            self.assertEqual(context["body"], b"\x00\x00")

    def test_disabled_registry_identity_cannot_resurrect_from_reference(self):
        context, _ = self.run_branch(dict(map_id=1134, instance_id=0), [-77])
        self.assertEqual(context["body"], b"\x00\x00")
        queries = [
            node.value
            for node in ast.walk(self.replay_ast)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "SELECT actor_id FROM world_dialogue_npcs" in node.value
        ]
        self.assertEqual(queries, ["SELECT actor_id FROM world_dialogue_npcs"])

    def test_character_none_keeps_existing_player_filter_without_scene_guess(self):
        context, _ = self.run_branch(None)
        self.assertEqual(context["body"][1], 1)

    def test_owned_profile_adaptation_branch_is_preserved(self):
        character = dict(id=7, map_id=1387, instance_id=0)
        context, wire = self.run_branch(character, opcode=12666)
        self.assertEqual(context["body"], b"owned-profile")
        wire.adapt.assert_called_once_with(
            12666, context["original"], 5, character, kamas=0
        )
