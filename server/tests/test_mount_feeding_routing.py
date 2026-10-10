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

    def test_rejected_meal_restores_pet_metadata_before_feedback(self):
        branch = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12767 and loaded"
        )
        transaction_try = next(
            node for node in branch.body if isinstance(node, ast.Try)
        )
        handler = next(
            node
            for node in transaction_try.handlers
            if isinstance(node.type, ast.Name) and node.type.id == "ValueError"
        )
        statements = handler.body

        restore_index = next(
            index
            for index, statement in enumerate(statements)
            if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "send_batch"
        )
        restore_call = statements[restore_index].value
        restore_packets = next(
            arg for arg in restore_call.args if isinstance(arg, ast.List)
        )
        self.assertEqual(
            [ast.unparse(packet.func) for packet in restore_packets.elts],
            ["synchronization", "rich_inventory_packet"],
            "A rejected meal must refresh native inventory and ProtoPet metadata",
        )
        self.assertTrue(
            any(
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "send"
                and "information" in ast.unparse(statement.value)
                for statement in statements[restore_index + 1 :]
            ),
            "Rejection feedback should follow the inventory restoration packets",
        )

    def test_applied_meal_refreshes_world_actor_progression_and_mount_state(self):
        branch = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12767 and loaded"
        )
        transaction_try = next(
            node for node in branch.body if isinstance(node, ast.Try)
        )
        applied = next(
            node
            for statement in transaction_try.orelse
            for node in ast.walk(statement)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "result['applied']"
        )
        calls = [
            node
            for statement in transaction_try.orelse
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        ]
        publish_line = next(
            node.lineno
            for node in calls
            if ast.unparse(node.func) == "publish_mount_feeding"
        )
        actor_refresh_line = next(
            node.lineno
            for node in calls
            if ast.unparse(node.func) == "WORLD.update"
            and any(
                isinstance(child, ast.Call)
                and ast.unparse(child.func) == "wire.refresh_player"
                for child in ast.walk(node)
            )
        )
        progression_line = next(
            node.lineno
            for node in calls
            if ast.unparse(node.func) == "outside_progression"
        )
        snapshot_line = next(
            node.lineno for node in calls if ast.unparse(node.func) == "mount_snapshot"
        )
        self.assertLess(publish_line, actor_refresh_line)
        self.assertLess(actor_refresh_line, progression_line)
        self.assertLess(progression_line, snapshot_line)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and ast.unparse(node.func) == "send"
                and any(
                    isinstance(child, ast.Call)
                    and ast.unparse(child.func) == "outside_progression"
                    for child in ast.walk(node)
                )
                for statement in applied.body
                for node in ast.walk(statement)
            ),
            "Applied XP must reach the owner's progression panel",
        )
        self.assertTrue(
            any(
                isinstance(node, ast.For)
                and isinstance(node.iter, ast.Call)
                and ast.unparse(node.iter.func) == "mount_snapshot"
                and any(
                    isinstance(child, ast.Call) and ast.unparse(child.func) == "send"
                    for child in ast.walk(node)
                )
                for node in ast.walk(applied)
            ),
            "Applied feeding must refresh the native mount state",
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
