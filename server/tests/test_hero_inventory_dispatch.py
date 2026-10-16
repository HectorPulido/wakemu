"""UID-only dispatcher actions publish to the hero without selecting that hero."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class StripImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return ast.copy_location(ast.Pass(), node)


class HeroInventoryDispatchTests(unittest.TestCase):
    def run_branch(self, opcode):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        nodes = ast.walk(ast.parse(source.read_text()))
        needle = f"opcode == {opcode}"
        node = next(
            n
            for n in nodes
            if isinstance(n, ast.If)
            and (
                needle in ast.unparse(n.test)
                if opcode not in (12365, 13269)
                else "opcode in (12365, 13257, 12221, 12364, 13269)"
                in ast.unparse(n.test)
            )
            and (opcode != 13220 or "len(body) == 12" in ast.unparse(n.test))
        )
        node = deepcopy(node)
        node.orelse = []
        code = ast.fix_missing_locations(
            StripImports().visit(ast.Module(body=[node], type_ignores=[]))
        )
        main, hero = dict(id=7), dict(id=8)
        result = dict(
            character=hero,
            character_id=8,
            uid=55,
            operation="reroll",
            applied=True,
            replayed=False,
            xp_delta=1,
            health_delta=0,
            packets=[(12470, b"item")],
            equipment_packet=(13078, b"registry"),
        )
        sent = []
        owner_refresh = Mock(return_value=hero)
        response = Mock(return_value=[(13713, b"hero-bags")])
        bonus_response = Mock(return_value=[(13713, b"hero-bonus")])
        namespace = dict(
            opcode=opcode,
            loaded=True,
            body=b"x" * 12,
            character=main,
            STORE=object(),
            account_id=1,
            generation="generation",
            fight=None,
            connection=object(),
            service="world",
            OWNED_HERO_TEMPLATE=b"template",
            PLAYER_TEMPLATE=b"main-template",
            WORLD=SimpleNamespace(update=Mock()),
            DatabaseError=type("DatabaseError", (Exception,), {}),
            PoolTimeout=type("PoolTimeout", (Exception,), {}),
            prepare_mount_feeding=Mock(return_value=result),
            publish_mount_feeding=lambda value, publish: publish(value["packets"]),
            send_batch=lambda connection, service, packets: sent.extend(packets),
            refresh=Mock(return_value=(13046, b"hero")),
            refresh_owned_character=Mock(return_value=main),
            outside_progression=Mock(return_value=(13912, b"hero-health")),
            mount_snapshot=Mock(return_value=()),
            mutate=Mock(return_value=result),
            install_bonus=Mock(return_value=result),
            refresh_item_mutation_character=owner_refresh,
            packets=response,
            bonus_installation_packets=bonus_response,
            destroy=Mock(return_value=result),
            learn_item=Mock(return_value=result),
            equipment_inventory=Mock(return_value=(13078, b"registry")),
            send=lambda connection, service, opcode, body: sent.append((opcode, body)),
            record=Mock(),
        )
        exec(compile(code, str(source), "exec"), namespace)
        self.assertIs(namespace["character"], main)
        self.assertTrue(sent)
        self.assertEqual(namespace["record"].call_args.kwargs["actor_id"], 8)
        namespace["refresh_owned_character"].assert_not_called()
        return namespace, result, hero

    def test_socket_and_bonus_results_use_the_real_owner(self):
        for opcode, helper in (
            (12365, "packets"),
            (13269, "bonus_installation_packets"),
        ):
            with self.subTest(opcode=opcode):
                namespace, result, _ = self.run_branch(opcode)
                namespace["refresh_item_mutation_character"].assert_called_once_with(8)
                namespace[helper].assert_called_once_with(8, result)

    def test_destroy_and_account_learning_keep_the_selected_main(self):
        namespace, _, hero = self.run_branch(12490)
        namespace["equipment_inventory"].assert_called_once_with(hero)
        self.run_branch(13220)

    def test_hero_feeding_refreshes_owned_registry_without_world_session_handoff(self):
        namespace, _, hero = self.run_branch(12767)
        namespace["WORLD"].update.assert_not_called()
        namespace["refresh"].assert_called_once_with(b"template", hero)
        namespace["outside_progression"].assert_called_once_with(hero)
        namespace["mount_snapshot"].assert_called_once_with(hero)


if __name__ == "__main__":
    unittest.main()
