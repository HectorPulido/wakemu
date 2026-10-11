"""Integration boundaries for dungeon build profile publication and recovery."""
import ast
from pathlib import Path
import unittest


_SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _contains_call(node, name):
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == name
        for child in ast.walk(node)
    )


def _has_attribute_call(node, owner, name):
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == name
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == owner
        for child in ast.walk(node)
    )


def _opcode_branch(tree, opcode):
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        if not isinstance(node.test.left, ast.Name) or node.test.left.id != "opcode":
            continue
        if any(
            isinstance(value, ast.Constant) and value.value == opcode
            for value in node.test.comparators
        ):
            matches.append(node)
    if len(matches) != 1:
        raise AssertionError(
            f"expected one opcode {opcode} branch, found {len(matches)}"
        )
    return matches[0]


class DungeonModulationDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(_SERVER_SOURCE.read_text())

    def test_transition_hydration_passes_native_fixture_provider(self):
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "prepare_transition"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "dungeon_hydration"
        ]
        self.assertEqual(len(calls), 1)
        fixture = next(
            (
                keyword.value
                for keyword in calls[0].keywords
                if keyword.arg == "fixture_provider"
            ),
            None,
        )
        self.assertIsInstance(fixture, ast.Name)
        self.assertEqual(fixture.id, "fixture")

    def test_recovery_reloads_main_character_immediately_after_resume(self):
        selection = _opcode_branch(self.tree, 23664)
        recovery_branches = [
            node
            for node in ast.walk(selection)
            if isinstance(node, ast.If)
            and any(
                isinstance(statement, ast.Assign)
                and _has_attribute_call(
                    statement.value, "dungeon_recovery", "resume_member"
                )
                for statement in node.body
            )
        ]
        self.assertEqual(len(recovery_branches), 1)
        branch = recovery_branches[0]
        resume_index = next(
            index
            for index, statement in enumerate(branch.body)
            if _has_attribute_call(statement, "dungeon_recovery", "resume_member")
        )
        self.assertLess(resume_index + 1, len(branch.body))
        reload_statement = branch.body[resume_index + 1]
        self.assertIsInstance(reload_statement, ast.Assign)
        self.assertTrue(
            any(
                isinstance(target, ast.Name) and target.id == "character"
                for target in reload_statement.targets
            )
        )
        reload_call = reload_statement.value
        self.assertIsInstance(reload_call, ast.Call)
        self.assertIsInstance(reload_call.func, ast.Attribute)
        self.assertEqual(reload_call.func.attr, "character")
        self.assertIsInstance(reload_call.func.value, ast.Name)
        self.assertEqual(reload_call.func.value.id, "STORE")
        self.assertEqual(len(reload_call.args), 2)

    def test_reconnect_sends_build_selection_ack_between_replay_and_inventory(self):
        selection = _opcode_branch(self.tree, 23664)
        replay_index = next(
            index
            for index, statement in enumerate(selection.body)
            if any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "replay"
                and len(child.args) >= 3
                and all(
                    isinstance(child.args[position], ast.Constant)
                    and child.args[position].value == expected
                    for position, expected in ((1, 45), (2, 114))
                )
                for child in ast.walk(statement)
            )
        )
        self.assertLess(replay_index + 1, len(selection.body))
        acknowledgement = selection.body[replay_index + 1]
        self.assertIsInstance(acknowledgement, ast.Expr)
        self.assertIsInstance(acknowledgement.value, ast.Call)
        self.assertIsInstance(acknowledgement.value.func, ast.Name)
        self.assertEqual(acknowledgement.value.func.id, "send")
        self.assertTrue(
            any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "selection_message"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "builds"
                for child in ast.walk(acknowledgement.value)
            )
        )
        inventory_index = next(
            index
            for index, statement in enumerate(selection.body)
            if index > replay_index
            and _contains_call(statement, "rich_inventory_packet")
        )
        self.assertLess(replay_index + 1, inventory_index)
