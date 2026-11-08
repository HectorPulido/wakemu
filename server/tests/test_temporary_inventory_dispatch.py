"""Loot publication must not replace the connection's selected main with a hero."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock


class TemporaryInventoryDispatchTests(unittest.TestCase):
    def test_loaded_hero_results_preserve_main_for_claim_get_all_and_recycle(self):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        for opcode in (13993, 12294, 13447):
            predicate = (
                "opcode in (13993, 12294) and loaded"
                if opcode != 13447
                else "opcode == 13447 and loaded"
            )
            branch = next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If) and ast.unparse(node.test) == predicate
            )
            action = next(node for node in branch.body if isinstance(node, ast.Try))
            start = next(
                i
                for i, node in enumerate(action.body)
                if isinstance(node, ast.Assign)
                and ast.unparse(node.targets[0]) == "saved"
            )
            statements = deepcopy(action.body[start:])
            for owner in (25, 64):
                with self.subTest(opcode=opcode, owner=owner):
                    main, saved = {"id": 25}, {"id": owner, "inventory": "updated"}
                    packets = [(12691, b"owner-specific-loot")]
                    namespace = dict(
                        opcode=opcode,
                        character=main,
                        result=dict(
                            character=saved, source=saved, packets=packets, applied=True
                        ),
                        active_private_session=Mock(return_value=None),
                        send=Mock(),
                        record=Mock(),
                        connection="peer",
                        service="world",
                    )
                    module = ast.fix_missing_locations(
                        ast.Module(body=statements, type_ignores=[])
                    )
                    exec(compile(module, str(source), "exec"), namespace)
                    self.assertIs(
                        namespace["character"], saved if owner == 25 else main
                    )
                    namespace["send"].assert_called_once_with(
                        "peer", "world", *packets[0]
                    )
                    if owner != 25:
                        namespace["active_private_session"].assert_not_called()
