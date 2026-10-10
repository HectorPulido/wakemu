"""Source-level routing checks for occupation ACKs in the network dispatcher."""

import ast
import struct
import unittest
from pathlib import Path


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _session_tree():
    tree = ast.parse(SERVER_SOURCE.read_text(), filename=str(SERVER_SOURCE))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )


def _opcode_conditions(session, opcode):
    conditions = []
    for node in ast.walk(session):
        if not isinstance(node, ast.If):
            continue
        has_opcode = any(
            isinstance(candidate, ast.Compare)
            and isinstance(candidate.left, ast.Name)
            and candidate.left.id == "opcode"
            and any(
                isinstance(value, ast.Constant) and value.value == opcode
                for value in candidate.comparators
            )
            for candidate in ast.walk(node.test)
        )
        if has_opcode:
            conditions.append(node)
    return sorted(conditions, key=lambda node: node.lineno)


class CraftDispatcherRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = _session_tree()

    def test_start_branch_routes_both_verified_crafting_request_opcodes(self):
        branches = [
            node
            for node in ast.walk(self.session)
            if isinstance(node, ast.If)
            and any(
                isinstance(value, ast.Name) and value.id == "opcode"
                for value in ast.walk(node.test)
            )
            and any(
                isinstance(value, ast.Constant) and value.value == 13382
                for value in ast.walk(node.test)
            )
            and any(
                isinstance(value, ast.Constant) and value.value == 12231
                for value in ast.walk(node.test)
            )
        ]
        self.assertEqual(1, len(branches))
        branch = branches[0]
        source = ast.unparse(branch)
        self.assertIn("craft_occupation_request(body)", source)
        self.assertIn("opcode == 12231", source)
        self.assertIn("opcode in (12231, 13382)", source)
        # Malformed request parsing is handled by the same branch's ValueError
        # path, which emits the native craft result instead of falling through.
        self.assertIn("except ValueError", source)
        self.assertIn("craft_result(status, 0, 0)", source)

    def test_13429_routes_only_exact_native_kinds_and_lengths(self):
        candidates = _opcode_conditions(self.session, 13429)
        self.assertGreaterEqual(len(candidates), 3)
        env = {"opcode": 13429, "loaded": True, "COMBAT_TEST": True, "struct": struct}

        def route(body):
            env["body"] = body
            for node in candidates:
                if eval(
                    compile(ast.Expression(node.test), str(SERVER_SOURCE), "eval"), env
                ):
                    return node
            return None

        # Craft occupation kind 8 is independent of planting/harvest handlers.
        craft_complete = route(bytes.fromhex("020008"))
        craft_cancel = route(bytes.fromhex("030008"))
        self.assertIsNotNone(craft_complete)
        self.assertIs(craft_complete, craft_cancel)
        self.assertIn("craft_completion_target", ast.unparse(craft_complete))
        self.assertIn("if fight is not None:", ast.unparse(craft_complete))

        flora = route(bytes.fromhex("020003"))
        monster = route(bytes.fromhex("020006"))
        self.assertIsNotNone(flora)
        self.assertIsNotNone(monster)
        self.assertIn("resource_collect", ast.unparse(flora))
        self.assertIn("HARVESTS.complete", ast.unparse(monster))
        monster_condition = ast.unparse(monster.test)
        self.assertIn("in (2, 6)", monster_condition)
        self.assertIn("in (2, 3)", monster_condition)
        internal_dispatch = next(
            node
            for node in ast.walk(monster)
            if isinstance(node, ast.If)
            and "struct.unpack('>Bh', body)[1] == 2" in ast.unparse(node.test)
        )
        self.assertIn("PLANTINGS.complete", ast.unparse(internal_dispatch.body))
        self.assertIn("HARVESTS.complete", ast.unparse(monster))

        # Truncation, trailing bytes, and unknown kinds must not be mistaken
        # for a valid flora or monster completion and cancel their tickets.
        for malformed in (
            b"",
            bytes.fromhex("0200"),
            bytes.fromhex("02000800"),
            bytes.fromhex("020007"),
        ):
            with self.subTest(body=malformed.hex()):
                self.assertIsNone(route(malformed))

    def test_craft_completion_guard_precedes_any_completion_or_inventory_work(self):
        craft = next(
            node
            for node in _opcode_conditions(self.session, 13429)
            if "craft_completion_target" in ast.unparse(node)
        )
        text = ast.unparse(craft)
        craft_try = next(node for node in craft.body if isinstance(node, ast.Try))
        guard_node = craft_try.body[0]
        self.assertIsInstance(guard_node, ast.If)
        self.assertEqual("fight is not None", ast.unparse(guard_node.test))
        guard = text.index("if fight is not None:")
        self.assertIn("location_resolver=", text)
        self.assertIn("lambda saved: bag_session.refresh(character, saved)", text)
        self.assertIn("bag_session.owns(character)", text)
        self.assertLess(
            text.index("saved = STORE.character", text.index("else:")),
            text.index("event='craft_occupation_completed'"),
        )
        finish = text.index("complete_crafting(")
        self.assertLess(guard, finish)
        self.assertIn("except ValueError", text)
        self.assertIn("craft_occupation_rejected", text)

    def test_completion_replay_uses_public_package_aliases(self):
        craft = next(
            node
            for node in _opcode_conditions(self.session, 13429)
            if "craft_completion_target" in ast.unparse(node)
        )
        imports = {
            (node.module, alias.name)
            for node in ast.walk(craft)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertIn(("wakfu_server.inventory_move", "synchronization"), imports)
        self.assertIn(("wakfu_server.inventory_items", "equipment_inventory"), imports)


if __name__ == "__main__":
    unittest.main()
