"""Execute the actual dispatcher branch with isolated boundary functions."""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class ElementSelectionDispatchTests(unittest.TestCase):
    def run_branch(self, *, fight=None, error=None, opcode=12487, owner_id=7):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(value, ast.Constant) and value.value == opcode
                for value in ast.walk(node.test)
            )
        )
        self.assertTrue(
            any(
                isinstance(node, ast.ImportFrom)
                and node.module == "wakfu_server.inventory_items"
                and any(alias.name == "equipment_inventory" for alias in node.names)
                for node in branch.body
            ),
            "Registry publication must import its own serializer",
        )
        body = [node for node in branch.body if not isinstance(node, ast.ImportFrom)]
        helper = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "refresh_item_mutation_character"
        )
        helper.body = [
            node for node in helper.body if not isinstance(node, ast.ImportFrom)
        ]
        module = ast.fix_missing_locations(
            ast.Module(body=[helper, *body], type_ignores=[])
        )
        select = Mock(
            return_value={
                "packet": (13766, b"chosen"),
                "uid": 31,
                "character_id": owner_id,
                "applied": True,
                "status": 0,
                "cost_kamas": 0,
            },
            side_effect=error,
        )
        reload = Mock(return_value={"id": owner_id, "inventory_items": ["updated"]})
        namespace = dict(
            fight=fight,
            select_elements=select,
            identify=select,
            response=lambda result: result["packet"],
            reload_inventory=reload,
            refresh_owned_character=lambda saved: saved,
            outside_progression=Mock(return_value=(999, b"updated-statistics")),
            COMBAT_TEST_WP=6,
            synchronization=Mock(return_value=(13713, b"updated-bags")),
            equipment_inventory=Mock(return_value=(13078, b"owned-equipment")),
            STORE=Mock(character=reload),
            account_id=5,
            generation=11,
            character={"id": 7},
            body=b"request",
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            DatabaseError=type("DatabaseError", (Exception,), {}),
            PoolTimeout=type("PoolTimeout", (Exception,), {}),
            information=lambda message: (12366, message.encode()),
        )
        exec(compile(module, str(source), "exec"), namespace)
        return namespace

    def test_selection_refreshes_owned_state_and_sends_native_result(self):
        result = self.run_branch()
        result["select_elements"].assert_called_once()
        result["reload_inventory"].assert_called_once()
        self.assertEqual(result["character"]["inventory_items"], ["updated"])
        self.assertEqual(
            [call.args[-2:] for call in result["send"].call_args_list],
            [
                (999, b"updated-statistics"),
                (13713, b"updated-bags"),
                (13766, b"chosen"),
                (13078, b"owned-equipment"),
            ],
        )
        result["equipment_inventory"].assert_called_once_with(result["character"])
        result["outside_progression"].assert_called_once_with(result["character"], wp=6)
        result["reload_inventory"].assert_called_once_with(5, 7)

    def test_socket_identification_refreshes_separate_equipment_registry(self):
        result = self.run_branch(opcode=13787)
        self.assertEqual(
            [call.args[-2:] for call in result["send"].call_args_list],
            [
                (999, b"updated-statistics"),
                (13713, b"updated-bags"),
                (13766, b"chosen"),
                (13078, b"owned-equipment"),
            ],
        )

    def test_hero_mutation_refreshes_owner_without_switching_selected_main(self):
        result = self.run_branch(owner_id=8)
        result["select_elements"].assert_called_once_with(
            result["STORE"], 5, 11, 7, b"request"
        )
        result["reload_inventory"].assert_called_once_with(5, 8)
        self.assertEqual(result["character"]["id"], 7)
        self.assertEqual(result["character"].get("inventory_items"), None)
        self.assertEqual(result["send"].call_args_list[0].args[-2], 999)
        self.assertEqual(result["record"].call_args.kwargs["actor_id"], 8)

    def test_combat_rejects_before_selection_or_inventory_change(self):
        result = self.run_branch(fight=object())
        result["select_elements"].assert_not_called()
        result["reload_inventory"].assert_not_called()
        self.assertEqual(result["send"].call_args.args[-2], 12366)

    def test_invalid_choice_reports_rejection_without_success_frame(self):
        result = self.run_branch(error=ValueError("Invalid mask"))
        result["reload_inventory"].assert_not_called()
        self.assertEqual(result["send"].call_args.args[-2:], (12366, b"Invalid mask"))


if __name__ == "__main__":
    unittest.main()
