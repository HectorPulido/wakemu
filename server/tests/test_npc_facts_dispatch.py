"""Verify the actual production NPC callback preserves current scene authority."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class NpcFactsDispatchTests(unittest.TestCase):
    def test_production_begin_receives_owned_facts_callback(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "npc_world.begin"
        ]
        self.assertEqual(len(calls), 1)
        self.assertIn(
            ("facts_provider", "dialogue_facts"),
            [(kw.arg, ast.unparse(kw.value)) for kw in calls[0].keywords],
        )
        callback = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "dialogue_facts"
        )
        database = Mock()
        connection = Mock()
        connection.__enter__ = Mock(return_value=database)
        connection.__exit__ = Mock(return_value=False)
        load = Mock(return_value={10606: False})
        character = dict(id=8, map_id=1440, instance_id=72, x=28, y=6, z=4)
        context = dict(
            STORE=SimpleNamespace(connection=lambda: connection),
            npc_objective_facts=SimpleNamespace(load=load),
            account_id=7,
            character=character,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
                "<actual-npc-facts-callback>",
                "exec",
            ),
            context,
        )
        self.assertEqual(context["dialogue_facts"](), {10606: False})
        load.assert_called_once_with(database, 7, 8)
        self.assertEqual(
            character, dict(id=8, map_id=1440, instance_id=72, x=28, y=6, z=4)
        )
