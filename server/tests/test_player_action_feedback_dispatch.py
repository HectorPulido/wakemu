"""Real rejection handlers explain failures while preserving native recovery."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from psycopg import OperationalError
from wakfu_server.ecology_feedback import information
from wakfu_server.player_action_feedback import failure_message
from wakfu_server.rift_entry_feedback import RiftEntryError


class PlayerActionFeedbackDispatchTests(unittest.TestCase):
    def test_actual_rejection_handlers_keep_recovery_and_sanitize_player_text(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        contexts = {
            "transport_rejected": ("Party changed during dungeon entry", "grupo", 1),
            "rift_entry_rejected": ("Invalid rift character session", "selección", 1),
            "resource_harvest_rejected": ("Base inventory full", "espacio", 2),
            "inventory_recycling_rejected": (
                "Desequip item from every build before recycling",
                "equipado",
                1,
            ),
            "exchange_request_rejected": (
                "Desequip the exchange item from every build first",
                "equipado",
                1,
            ),
            "haven_bag_furniture_edit_rejected": (
                "Unsupported itemizable action",
                "mobiliario",
                1,
            ),
        }
        for event, (reason, expected_word, expected_handlers) in contexts.items():
            handlers = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ExceptHandler)
                and any(
                    isinstance(child, ast.keyword)
                    and child.arg == "event"
                    and isinstance(child.value, ast.Constant)
                    and child.value.value == event
                    for statement in node.body
                    for child in ast.walk(statement)
                )
            ]
            self.assertEqual(len(handlers), expected_handlers, event)
            for index, handler in enumerate(handlers):
                with self.subTest(event=event, handler=index):
                    errors = [ValueError(reason)]
                    if event == "rift_entry_rejected":
                        errors.append(
                            ValueError("Only the current party leader may enter a rift")
                        )
                        errors.append(
                            RiftEntryError(
                                "proximity",
                                "Rift member ELLECHERO is too far",
                                member={"id": 46, "name": "ELLECHERO"},
                            )
                        )
                    if event in (
                        "inventory_recycling_rejected",
                        "exchange_request_rejected",
                    ):
                        errors.append(
                            OperationalError(
                                "postgresql://qa:private-password@example.invalid/private?token=private-token"
                            )
                        )
                    for error in errors:
                        sent, records = [], []
                        actor = {"id": 7, "map_id": 527, "instance_id": 0}
                        original = deepcopy(actor)
                        cancel = Mock()
                        namespace = dict(
                            error=error,
                            character=actor,
                            connection="peer",
                            service="world",
                            account_id=2,
                            generation="current",
                            information=information,
                            opcode=13406,
                            record=lambda **row: records.append(row),
                            send=lambda _peer, _service, opcode, body: sent.append(
                                (opcode, body)
                            ),
                            cancel_flora=cancel,
                            is_dungeon_run=lambda instance: False,
                            fixture=lambda opcode: b"original-transport-template",
                            wire=SimpleNamespace(
                                adapt=lambda *args: b"original-transport-recovery"
                            ),
                        )
                        loop = ast.For(
                            target=ast.Name(id="_attempt", ctx=ast.Store()),
                            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                            body=deepcopy(handler.body),
                            orelse=[],
                        )
                        module = ast.fix_missing_locations(
                            ast.Module(body=[loop], type_ignores=[])
                        )
                        exec(compile(module, str(source), "exec"), namespace)
                        self.assertEqual(actor, original)
                        self.assertEqual(records[0]["event"], event)
                        self.assertEqual(
                            records[0]["reason"],
                            type(error).__name__
                            if event
                            in (
                                "inventory_recycling_rejected",
                                "exchange_request_rejected",
                            )
                            else str(error),
                        )
                        self.assertEqual(sent[0][0], 349)
                        subtype, size = struct.unpack(">hh", sent[0][1][:4])
                        text = sent[0][1][4:].decode("utf-8")
                        self.assertEqual((subtype, size), (4, len(sent[0][1][4:])))
                        self.assertTrue(text.startswith("No se"))
                        if isinstance(error, OperationalError):
                            for private in (
                                "private-password",
                                "private-token",
                                "postgresql://",
                                "example.invalid",
                            ):
                                self.assertNotIn(private, text)
                        else:
                            expected = (
                                "líder" if "leader" in str(error) else expected_word
                            )
                            if isinstance(error, RiftEntryError):
                                expected = "ellechero"
                            self.assertIn(expected, text.casefold())
                            self.assertNotIn(str(error), text)
                        if event == "transport_rejected":
                            self.assertEqual(
                                sent[1:], [(13974, b"original-transport-recovery")]
                            )
                        else:
                            self.assertEqual(len(sent), 1)
                        self.assertEqual(
                            cancel.call_count, int(event == "resource_harvest_rejected")
                        )
        for action in (
            "build_save",
            "inventory_move",
            "exchange",
            "hero_selection",
            "hero_switch",
            "transport",
            "rift_entry",
            "harvest",
            "recycling",
            "furniture",
        ):
            with self.subTest(unknown_failure_action=action):
                text = failure_message(
                    action,
                    RuntimeError("private-password private-token internal-stack"),
                )
                self.assertTrue(text.startswith("No se pudo"))
                self.assertNotIn("private-", text)
                self.assertNotIn("internal-stack", text)
                self.assertGreater(len(text.split(". ")), 1)

    def test_equipment_exchange_reasons_do_not_confuse_missing_units_with_reservations(
        self,
    ):
        for action, reason, expected in (
            (
                "exchange",
                "Native item binding or criterion prohibits exchange",
                "vínculo",
            ),
            ("exchange", "Exchange recipient inventory is full", "espacio"),
            (
                "exchange",
                "Exchange item is unavailable or foreign",
                "ya no está disponible",
            ),
            (
                "inventory_move",
                "Offered item cannot change inventory owner",
                "reservado",
            ),
            (
                "inventory_move",
                "Partial item UID was not reserved by this session",
                "reserva para dividir",
            ),
        ):
            with self.subTest(action=action, reason=reason):
                text = failure_message(action, ValueError(reason))
                self.assertIn(expected, text)
                self.assertNotIn(reason, text)
                if "unavailable" in reason:
                    self.assertNotIn("reservado", text)
