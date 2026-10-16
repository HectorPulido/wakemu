"""Execute the production 12804 rejection branch with isolated boundaries."""

import ast
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

from wakfu_server.inventory_move import EquippedTransferError


class InventoryMoveDispatchTests(unittest.TestCase):
    def test_equipped_transfer_sends_english_notice_and_keeps_selected_main(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12804 and loaded"
        )
        module = ast.fix_missing_locations(
            ast.Module(
                body=[
                    node for node in branch.body if not isinstance(node, ast.ImportFrom)
                ],
                type_ignores=[],
            )
        )

        class RemoveNestedImports(ast.NodeTransformer):
            def visit_ImportFrom(self, node):
                return None

        module = ast.fix_missing_locations(RemoveNestedImports().visit(module))
        main = {"id": 7, "inventory_items": [{"uid": 101, "quantity": 1}]}
        heroes = Mock()
        heroes.load_roster.return_value = {"heroes": [{"id": 8}]}
        hero_private_scene = Mock()
        hero_private_scene.project.return_value = {"heroes": [{"id": 8}]}
        hero_wire = Mock()
        hero_wire.refresh.return_value = (13046, b"hero-public")
        equipment_inventory = Mock(
            side_effect=[(13078, b"main-equipment"), (13078, b"hero-equipment")]
        )
        store = Mock()
        store.connection.return_value = nullcontext(Mock())
        transfer = Mock(side_effect=EquippedTransferError("equipped"))
        reload_inventory = Mock(return_value=main)
        send = Mock()
        record = Mock()
        namespace = dict(
            opcode=12804,
            loaded=True,
            EquippedTransferError=EquippedTransferError,
            transfer=transfer,
            synchronization=Mock(return_value=(13301, b"main-bags")),
            reload_inventory=reload_inventory,
            active_private_session=lambda: None,
            STORE=store,
            account_id=5,
            generation=11,
            character=main,
            body=b"request",
            connection=object(),
            service="world",
            send=send,
            record=record,
            information=lambda text: (12366, text.encode("utf-8")),
            heroes=heroes,
            hero_private_scene=hero_private_scene,
            hero_wire=hero_wire,
            equipment_inventory=equipment_inventory,
            OWNED_HERO_TEMPLATE=b"owned-template",
        )
        exec(compile(module, str(source), "exec"), namespace)

        transfer.assert_called_once_with(store, 5, 11, 7, b"request")
        reload_inventory.assert_called_once_with(store, 5, main)
        self.assertIs(namespace["character"], main)
        self.assertEqual(main["inventory_items"], [{"uid": 101, "quantity": 1}])
        sent = [call.args[2:] for call in send.call_args_list]
        self.assertIn(
            (
                12366,
                b"You cannot transfer an equipped item. Unequip it first.",
            ),
            sent,
        )
        self.assertIn((13301, b"main-bags"), sent)
        self.assertEqual(record.call_args.kwargs["event"], "inventory_move_rejected")
        self.assertEqual(record.call_args.kwargs["actor_id"], 7)


if __name__ == "__main__":
    unittest.main()
