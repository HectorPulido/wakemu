import ast
import pathlib
import unittest


class SocketEnchantmentDispatchTests(unittest.TestCase):
    def test_inventory_dispatch_routes_native_requests_through_guarded_service_and_packets(
        self,
    ):
        source = pathlib.Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode in (12365, 13257, 12221, 12364, 13269) and loaded"
        )
        self.assertTrue(
            any(
                isinstance(node, ast.ImportFrom)
                and node.module == "wakfu_server.inventory_items"
                and any(alias.name == "equipment_inventory" for alias in node.names)
                for node in branch.body
            )
        )
        text = ast.dump(branch)
        self.assertIn("loaded", text)
        self.assertIn("mutate", text)
        self.assertIn("install_bonus", text)
        self.assertIn("fight", text)
        self.assertIn("packets", text)
        self.assertIn("inventory_socket_enchantment_changed", text)
        self.assertIn("inventory_socket_enchantment_rejected", text)


if __name__ == "__main__":
    unittest.main()
