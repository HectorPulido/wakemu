"""Exercise the production 13057 purchase branch without starting the server."""
import ast
from copy import deepcopy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class StripImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return ast.copy_location(ast.Pass(), node)


class ExchangeMachineDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.source.read_text(encoding="utf-8"))
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "opcode == 13057 and loaded" in ast.unparse(node.test)
        )

    def run_branch(self, owner_id=42):
        main = {
            "id": 41,
            "account_id": 7,
            "map_id": 527,
            "instance_id": 0,
            "x": 0,
            "y": 27,
            "z": 0,
        }
        owner = {"id": owner_id, "account_id": 7}
        request = {
            "catalog_id": 265,
            "object_id": 34600,
            "offer_id": 10176,
            "quantity": 1,
            "actor_id": owner_id,
        }
        station = {"in_range": True, "object_id": 34600, "catalog_id": 265}
        result = {
            "character": owner,
            "packets": [(13929, b"quest"), (12753, b"wallet")],
            "request": request,
        }
        sent, records = [], []
        exchange_machine = SimpleNamespace(
            decode=Mock(return_value=request),
            station=Mock(return_value=station),
            purchase=Mock(return_value=result),
        )
        synchronization = Mock(return_value=(13929, b"bags"))
        equipment_inventory = Mock(return_value=(13078, b"registry"))
        refresh_owned_character = Mock(return_value=main)
        namespace = {
            "opcode": 13057,
            "loaded": True,
            "body": b"native purchase",
            "character": main,
            "account_id": 7,
            "generation": "generation",
            "connection": object(),
            "service": "world",
            "STORE": object(),
            "POSITIONS": SimpleNamespace(flush=Mock()),
            "environment_blocked": Mock(return_value=False),
            "exchange_machine": exchange_machine,
            "synchronization": synchronization,
            "equipment_inventory": equipment_inventory,
            "refresh_owned_character": refresh_owned_character,
            "send": lambda _connection, _service, *packet: sent.append(packet),
            "record": lambda **event: records.append(event),
            "DatabaseError": type("DatabaseError", (Exception,), {}),
            "PoolTimeout": type("PoolTimeout", (Exception,), {}),
        }
        branch = deepcopy(self.branch)
        branch.orelse = []
        module = ast.fix_missing_locations(
            StripImports().visit(ast.Module(body=[branch], type_ignores=[]))
        )
        exec(compile(module, str(self.source), "exec"), namespace)
        return namespace, result, main, owner, request, station, sent, records

    def test_hero_purchase_publishes_actual_owner_and_keeps_main_selected(self):
        (
            namespace,
            result,
            main,
            owner,
            request,
            station,
            sent,
            records,
        ) = self.run_branch()
        self.assertEqual(
            sent,
            [
                (13929, b"bags"),
                (13078, b"registry"),
                (13929, b"quest"),
                (12753, b"wallet"),
            ],
        )
        self.assertIs(namespace["character"], main)
        self.assertEqual(main["id"], 41)
        self.assertEqual(records[0], {"event": "exchange_machine_purchased", **request})
        self.assertNotIn(13301, [packet[0] for packet in sent])
        namespace["exchange_machine"].decode.assert_called_once_with(b"native purchase")
        namespace["POSITIONS"].flush.assert_called_once_with(
            account_id=7,
            generation="generation",
            character_id=41,
        )
        namespace["exchange_machine"].station.assert_called_once_with(main, request)
        namespace["exchange_machine"].purchase.assert_called_once_with(
            namespace["STORE"],
            7,
            "generation",
            41,
            b"native purchase",
            location=main,
            station=station,
            blocked=False,
        )
        namespace["synchronization"].assert_called_once_with(owner)
        namespace["equipment_inventory"].assert_called_once_with(owner)

    def test_main_purchase_refreshes_only_the_selected_main(self):
        namespace, result, main, _, request, _, sent, _ = self.run_branch(owner_id=41)
        namespace["refresh_owned_character"].assert_called_once_with(
            result["character"]
        )
        self.assertIs(namespace["character"], main)
        self.assertEqual([opcode for opcode, _ in sent], [13929, 13078, 13929, 12753])
        self.assertEqual(request["actor_id"], main["id"])


if __name__ == "__main__":
    unittest.main()
