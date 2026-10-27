"""Actual Rift preparation/routing consumes refusals before gameplay mutation."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server


class RiftStartRefusalDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        cls.tree = ast.parse(cls.source.read_text())
        cls.prepare = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "prepare_rift_start"
        )
        cls.dispatch = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.NamedExpr)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Name)
                and child.value.func.id == "prepare_rift_start"
                for child in ast.walk(node.test)
            )
        )

    def route(
        self, *, pending_peer=False, visible_peer=True, mode="recognized", body=None
    ):
        character = dict(
            id=105,
            account_id=49,
            map_id=1314,
            instance_id=288230376151711794,
            x=-2,
            y=3,
            z=0,
            hp=350,
        )
        run = dict(
            instance_id=character["instance_id"], members=[105, 106, 107, 108, 109]
        )
        rows = [
            dict(
                id=identity,
                account_id=49 if identity < 108 else 50,
                generation="a" if identity < 108 else "b",
                name="RiftPeer" if identity == 109 else f"RiftMember{identity}",
                selected_character_id=105 if identity < 108 else 109,
            )
            for identity in run["members"]
        ]
        db = Mock()
        db.execute.return_value.fetchall.return_value = rows
        sent, records, fallthrough, accepted = [], [], [], []
        plantings, harvests = Mock(), Mock()
        health, combat = dict(hp=350, regeneration="preserved"), dict(
            fight=None, phase=None
        )
        before = deepcopy((character, health, combat))

        def authorize(
            _db, _store, _account, _generation, _character, payload, **options
        ):
            if (
                not isinstance(payload, bytes)
                or len(payload) != 12
                or payload[10:] != b"\0\0"
            ):
                raise ValueError("Invalid native interactive action")
            if mode == "unrelated":
                return None
            self.assertTrue(
                options["source_allowed"](character, dict(map_id=1314, x=-2, y=2, z=0))
            )
            if mode == "private_error":
                raise ValueError("postgresql://private-token@example.invalid/internal")
            return run

        visible = {
            row["id"]: (row["generation"], None, dict(character, id=row["id"]))
            for row in rows
            if row["id"] == row["selected_character_id"]
        }
        if not visible_peer:
            visible.pop(109)
        namespace = dict(
            character=character,
            account_id=49,
            generation="a",
            connection="qa-peer",
            service="world",
            STORE=SimpleNamespace(connection=lambda: nullcontext(db)),
            WORLD=SimpleNamespace(
                lock=nullcontext(),
                players=visible,
                location=lambda actor: (actor["map_id"], actor["instance_id"]),
            ),
            send=lambda _peer, _service, opcode, payload: sent.append(
                (opcode, payload)
            ),
            record=lambda **row: records.append(row),
            opcode=12870,
            loaded=True,
            COMBAT_TEST=True,
            body=body if body is not None else struct.pack(">qHH", 33012, 0, 0),
            PLANTINGS=plantings,
            HARVESTS=harvests,
            fallthrough=fallthrough,
            accepted=accepted,
            rift_start_run=None,
        )
        # Compile the current real function and the current dispatcher prefix
        # through its first import, before any placement engine is constructed.
        prefix = []
        for statement in self.dispatch.body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                break
            prefix.append(deepcopy(statement))
        branch = ast.If(
            test=deepcopy(self.dispatch.test),
            body=prefix + ast.parse("accepted.append(rift_start_run)").body,
            orelse=ast.parse("fallthrough.append(opcode)").body,
        )
        loop = ast.For(
            target=ast.Name(id="_request", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch],
            orelse=[],
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[deepcopy(self.prepare), loop], type_ignores=[])
        )
        adapter = SimpleNamespace(authorize_start=authorize)
        transition = SimpleNamespace(
            pending=lambda account, generation, identity: {
                "instance_id": run["instance_id"]
            }
            if pending_peer and identity == 109
            else None
        )
        with patch.object(
            wakfu_server, "rift_entry_adapter", adapter, create=True
        ), patch.object(
            wakfu_server, "rift_transition_delivery", transition, create=True
        ):
            exec(compile(module, str(self.source), "exec"), namespace)
        self.assertEqual((character, health, combat), before)
        return SimpleNamespace(
            sent=sent,
            records=records,
            fallthrough=fallthrough,
            accepted=accepted,
            plantings=plantings,
            harvests=harvests,
        )

    def assert_consumed_refusal(self, result, expected):
        self.assertEqual(
            result.fallthrough,
            [],
            "recognized refusal reached generic interactive handling",
        )
        self.assertEqual(result.accepted, [])
        result.plantings.cancel.assert_not_called()
        result.harvests.cancel.assert_not_called()
        self.assertEqual(
            [row["event"] for row in result.records], ["rift_start_rejected"]
        )
        self.assertEqual(len(result.sent), 1)
        opcode, body = result.sent[0]
        self.assertEqual(opcode, 349)
        subtype, size = struct.unpack_from(">hh", body)
        self.assertEqual((subtype, size), (4, len(body) - 4))
        text = body[4:].decode()
        self.assertIn(expected, text)
        self.assertNotIn("distancia", text)
        self.assertNotIn("lejos", text)
        self.assertNotIn("Unknown interactive", text)
        return text

    def test_adjacent_altar_waiting_for_peer_is_consumed_before_gameplay_mutation(self):
        result = self.route(pending_peer=True)
        self.assert_consumed_refusal(result, "RiftPeer termine de cargar la brecha")
        self.assertEqual(
            result.records[0]["reason"],
            "Wait for every frozen rift member to load the interior",
        )

    def test_missing_world_presentation_is_consumed_with_the_actual_condition(self):
        result = self.route(visible_peer=False)
        self.assert_consumed_refusal(result, "RiftPeer termine de cargar la brecha")
        self.assertEqual(
            result.records[0]["reason"],
            "Every frozen rift member must finish loading the interior",
        )

    def test_unrelated_interactive_falls_through_and_accepted_start_keeps_normal_prefix(
        self,
    ):
        unrelated = self.route(mode="unrelated")
        self.assertEqual(unrelated.fallthrough, [12870])
        self.assertEqual(
            (unrelated.sent, unrelated.records, unrelated.accepted), ([], [], [])
        )
        unrelated.plantings.cancel.assert_not_called()
        unrelated.harvests.cancel.assert_not_called()
        accepted = self.route()
        self.assertEqual(accepted.fallthrough, [])
        self.assertEqual(len(accepted.accepted), 1)
        accepted.plantings.cancel.assert_called_once_with(105, "a")
        accepted.harvests.cancel.assert_called_once_with(105, generation="a")
        self.assertEqual((accepted.sent, accepted.records), ([], []))

    def test_malformed_payload_and_unknown_error_are_consumed_without_private_text(
        self,
    ):
        for body in (b"", struct.pack(">qHH", 33012, 0, 1)):
            with self.subTest(body=body.hex()):
                self.assert_consumed_refusal(
                    self.route(body=body), "No se pudo iniciar la brecha"
                )
        text = self.assert_consumed_refusal(
            self.route(mode="private_error"), "No se pudo iniciar la brecha"
        )
        for private in ("private-token", "example.invalid", "postgresql://"):
            self.assertNotIn(private, text)


if __name__ == "__main__":
    unittest.main()
