import ast
from pathlib import Path
import unittest


class MountFeedingRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).parents[1] / "local_game_server.py"
        cls.tree = ast.parse(source.read_text())

    def test_loaded_12767_routes_domain_errors_separately_from_publication(self):
        branches = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12767 and loaded"
        ]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "prepare_mount_feeding"
                for node in ast.walk(branch)
            )
        )

        tries = [node for node in branch.body if isinstance(node, ast.Try)]
        self.assertEqual(len(tries), 1)
        transaction_try = tries[0]
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "prepare_mount_feeding"
                for statement in transaction_try.body
                for node in ast.walk(statement)
            )
        )
        self.assertTrue(
            any(
                isinstance(handler.type, ast.Tuple)
                and {ast.unparse(item) for item in handler.type.elts}
                == {"DatabaseError", "PoolTimeout"}
                for handler in transaction_try.handlers
            )
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "publish_mount_feeding"
                for statement in transaction_try.orelse
                for node in ast.walk(statement)
            ),
            "Committed packet publication must be outside the ValueError handlers",
        )
        self.assertTrue(
            any(
                isinstance(handler.type, ast.Name) and handler.type.id == "ValueError"
                for handler in transaction_try.handlers
            )
        )

    def test_branch_precedes_mount_toggle_and_requires_loaded_character(self):
        source = Path(__file__).parents[1] / "local_game_server.py"
        text = source.read_text()
        self.assertLess(
            text.index("elif opcode == 12767 and loaded:"),
            text.index("elif opcode in (12634, 13928) and loaded:"),
        )

    def test_character_selection_restores_rich_registry_after_world_bootstrap(self):
        for opcode in (23664, 22296):
            with self.subTest(opcode=opcode):
                branch = next(
                    node
                    for node in ast.walk(self.tree)
                    if isinstance(node, ast.If)
                    and ast.unparse(node.test) == f"opcode == {opcode}"
                )
                calls = sorted(
                    (
                        node.lineno,
                        node.func.id,
                    )
                    for statement in branch.body
                    for node in ast.walk(statement)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id
                    in {"replay", "rich_inventory_packet", "initialize_pool"}
                )
                lines = {name: line for line, name in calls}
                self.assertTrue(
                    {"replay", "rich_inventory_packet", "initialize_pool"}
                    <= lines.keys()
                )
                self.assertLess(lines["replay"], lines["rich_inventory_packet"])
                self.assertLess(
                    lines["rich_inventory_packet"], lines["initialize_pool"]
                )


if __name__ == "__main__":
    unittest.main()
