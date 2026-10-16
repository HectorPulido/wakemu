"""Execute chest transfer branches from the production local dispatcher AST."""
import ast
from copy import deepcopy
import importlib
import struct
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class HavenChestDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        cls.source = source
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "opcode in (12038, 12551, 13050) and loaded" in ast.unparse(node.test)
        )

    def run_branch(
        self, *, active=True, transfer_error=False, inventory_characters=None
    ):
        chest_wire = importlib.import_module("wakfu_server.haven_chest_wire")
        inventory_move = importlib.import_module("wakfu_server.inventory_move")
        inventory_items = importlib.import_module("wakfu_server.inventory_items")
        haven_chest = importlib.import_module("wakfu_server.haven_chest")
        actor = {
            "id": 41,
            "account_id": 7,
            "map_id": 9,
            "instance_id": 41,
            "x": 3,
            "y": 3,
            "z": 0,
            "inventory_containers": [
                dict(
                    character_id=41,
                    uid=100,
                    reference=2175,
                    kind=0,
                    capacity=30,
                    flags=0,
                ),
                dict(
                    character_id=41,
                    uid=101,
                    reference=2603,
                    kind=1,
                    capacity=4,
                    flags=0,
                ),
            ],
            "inventory_items": [],
        }
        chest = dict(
            id=str(uuid.uuid4()),
            account_id=7,
            capacity=20,
            revision=3,
            items=[],
        )
        before_custody = deepcopy((actor["inventory_items"], chest["items"]))
        sent = []
        records = []
        transfer = Mock(
            return_value=dict(
                character=actor,
                chest=chest,
                applied=True,
                inventory_characters=(actor,)
                if inventory_characters is None
                else inventory_characters,
            )
        )
        if transfer_error:
            transfer.side_effect = ValueError("Injected chest rejection")
        load = Mock(return_value=chest)
        namespace = {
            "opcode": 12038,
            "loaded": True,
            "body": b"native chest transfer",
            "chest_opening": uuid.uuid4() if active else None,
            "fight": None,
            "character": actor,
            "ranch_session": None,
            "account_id": 7,
            "generation": "session",
            "connection": object(),
            "service": "world",
            "STORE": object(),
            "active_private_session": lambda: SimpleNamespace(
                refresh=lambda current, saved: dict(saved)
            ),
            "send": lambda _connection, service, *packet: sent.append(packet),
            "record": lambda **event: records.append(event),
        }
        branch = deepcopy(self.branch)
        branch.orelse = []
        module = ast.fix_missing_locations(
            ast.Module(
                body=[
                    ast.For(
                        target=ast.Name(id="_once", ctx=ast.Store()),
                        iter=ast.Tuple(elts=[ast.Constant(value=0)], ctx=ast.Load()),
                        body=[branch],
                        orelse=[],
                    )
                ],
                type_ignores=[],
            )
        )
        with patch.object(haven_chest, "transfer", transfer), patch.object(
            haven_chest, "load", load
        ):
            exec(compile(module, str(self.source), "exec"), namespace)
        return sent, transfer, load, records, before_custody, actor, chest

    def test_success_sends_owned_full_snapshots_and_ack_without_delta(self):
        sent, transfer, load, records, _, actor, chest = self.run_branch()
        expected = [
            importlib.import_module("wakfu_server.inventory_move").synchronization(
                actor
            ),
            importlib.import_module("wakfu_server.inventory_items").equipment_inventory(
                actor
            ),
            importlib.import_module("wakfu_server.haven_chest_wire").bootstrap(chest),
            (13301, b"\x00"),
        ]
        self.assertEqual(expected, sent)
        self.assertNotIn(13929, [packet[0] for packet in sent])
        self.assertNotIn(12471, [packet[0] for packet in sent])
        transfer.assert_called_once()
        load.assert_not_called()
        self.assertEqual("account_chest_transferred", records[0]["event"])

    def test_rejection_sends_error_ack_then_owned_full_snapshots_without_delta(self):
        sent, transfer, load, records, _, actor, chest = self.run_branch(
            transfer_error=True
        )
        expected = [
            (13301, b"\x02"),
            importlib.import_module("wakfu_server.ecology_feedback").information(
                "Injected chest rejection"
            ),
            importlib.import_module("wakfu_server.inventory_move").synchronization(
                actor
            ),
            importlib.import_module("wakfu_server.inventory_items").equipment_inventory(
                actor
            ),
            importlib.import_module("wakfu_server.haven_chest_wire").bootstrap(chest),
        ]
        self.assertEqual(expected, sent)
        self.assertNotIn(13929, [packet[0] for packet in sent])
        self.assertNotIn(12471, [packet[0] for packet in sent])
        transfer.assert_called_once()
        load.assert_called_once()
        self.assertEqual("account_chest_transfer_rejected", records[0]["event"])

    def test_no_active_chest_only_rejects_and_never_touches_custody(self):
        sent, transfer, load, records, custody_before, actor, chest = self.run_branch(
            active=False
        )
        self.assertEqual(
            [
                (13301, b"\x02"),
                importlib.import_module("wakfu_server.ecology_feedback").information(
                    "No active account chest"
                ),
            ],
            sent,
        )
        self.assertEqual(custody_before, (actor["inventory_items"], chest["items"]))
        transfer.assert_not_called()
        load.assert_not_called()
        self.assertEqual("account_chest_transfer_rejected", records[0]["event"])

    def test_hero_owner_refresh_keeps_main_selected_and_publishes_hero_packets(self):
        hero = {
            "id": 42,
            "account_id": 7,
            "inventory_items": [],
            "inventory_containers": [
                dict(
                    character_id=42,
                    uid=200,
                    reference=2175,
                    kind=0,
                    capacity=30,
                    flags=0,
                ),
                dict(
                    character_id=42,
                    uid=201,
                    reference=2603,
                    kind=1,
                    capacity=4,
                    flags=0,
                ),
            ],
        }
        sent, transfer, _, records, _, main, chest = self.run_branch(
            inventory_characters=(hero,)
        )
        inventory_move = importlib.import_module("wakfu_server.inventory_move")
        inventory_items = importlib.import_module("wakfu_server.inventory_items")
        expected = [
            inventory_move.synchronization(hero),
            inventory_items.equipment_inventory(hero),
            importlib.import_module("wakfu_server.haven_chest_wire").bootstrap(chest),
            (13301, b"\x00"),
        ]
        self.assertEqual(sent, expected)
        self.assertEqual(struct.unpack_from(">q", sent[0][1])[0], hero["id"])
        self.assertEqual(struct.unpack_from(">q", sent[1][1])[0], hero["id"])
        transfer.assert_called_once()
        self.assertEqual(transfer.call_args.args[3], main["id"])
        self.assertEqual(main["id"], 41)
        self.assertEqual(records[0]["actor_id"], main["id"])


if __name__ == "__main__":
    unittest.main()
