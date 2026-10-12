"""Execute the production bridge branch and separate private inventory from scene."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import haven_ranch_bridges as bridges
from wakfu_server import inventory_move, inventory_items, ecology_feedback


class RanchBridgeDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.source.read_text())
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "ranch_session" in ast.unparse(node.test)
            and "36068" in ast.unparse(node.test)
            and "36069" in ast.unparse(node.test)
        )

    def execute(self, *, guest=False, combat=False, identity=36069):
        sent, emitted, records, fallback = [], [], [], []
        actor = dict(id=41, account_id=7, map_id=1440, instance_id=17)
        saved = dict(
            actor, map_id=527, instance_id=0, x=10, y=20, inventory_items=["fresh"]
        )
        activation = Mock(
            return_value=dict(
                character=saved,
                applied=True,
                private_packets=[(12470, b"cost")],
                scene_packets=[(13080, b"bridge")],
            )
        )
        if guest:
            activation.side_effect = ValueError("Owned Ranch required")
        refreshed = Mock(
            side_effect=lambda current, fresh: dict(fresh, map_id=1440, instance_id=17)
        )
        session = SimpleNamespace(refresh=refreshed)
        ns = dict(
            loaded=True,
            ranch_session=session,
            opcode=12870,
            body=struct.pack(">qHH", identity, 0, 0),
            fight=object() if combat else None,
            spectator_session=None,
            STORE=object(),
            account_id=7,
            generation="lease",
            character=actor,
            connection=object(),
            service="world",
            struct=struct,
            send=lambda *args: sent.append(args[2:]),
            record=lambda **event: records.append(event),
            WORLD=SimpleNamespace(emit_location=lambda *args: emitted.append(args)),
            fallback=fallback,
        )
        branch = deepcopy(self.branch)
        branch.orelse = [
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="fallback", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(True)],
                    keywords=[],
                )
            )
        ]
        module = ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[]))
        with patch.object(bridges, "activate", activation), patch.object(
            inventory_move, "synchronization", return_value=(13713, b"actor")
        ), patch.object(
            inventory_items, "equipment_inventory", return_value=(13078, b"inventory")
        ), patch.object(
            ecology_feedback, "information", return_value=(674, b"denied")
        ):
            exec(compile(module, str(self.source), "exec"), ns)
        return activation, refreshed, sent, emitted, records, fallback, ns

    def test_success_keeps_actor_in_private_ranch_and_never_broadcasts_inventory(self):
        activation, refreshed, sent, emitted, records, fallback, ns = self.execute()
        activation.assert_called_once()
        refreshed.assert_called_once()
        self.assertIs(activation.call_args.kwargs["session"], ns["ranch_session"])
        self.assertEqual([packet[0] for packet in sent], [12470, 13713, 13078])
        self.assertEqual(emitted, [(1440, 17, 13080, b"bridge")])
        self.assertEqual(ns["character"]["inventory_items"], ["fresh"])
        self.assertEqual(ns["character"]["map_id"], 1440)
        self.assertFalse(fallback)

    def test_guest_rejection_and_combat_do_not_publish_private_or_bridge_state(self):
        activation, refreshed, sent, emitted, _, fallback, _ = self.execute(guest=True)
        activation.assert_called_once()
        refreshed.assert_not_called()
        self.assertEqual(sent, [(674, b"denied")])
        self.assertFalse(emitted)
        self.assertFalse(fallback)
        activation, refreshed, sent, emitted, _, fallback, _ = self.execute(combat=True)
        activation.assert_not_called()
        refreshed.assert_not_called()
        self.assertFalse(emitted)
        self.assertFalse(fallback)

    def test_unrelated_interactive_preserves_existing_dispatch(self):
        activation, refreshed, sent, emitted, _, fallback, _ = self.execute(
            identity=36088
        )
        activation.assert_not_called()
        refreshed.assert_not_called()
        self.assertFalse(sent)
        self.assertFalse(emitted)
        self.assertTrue(fallback)


class RanchBridgeMovementDispatchTests(unittest.TestCase):
    """Execute the actual approved-path guard without importing the server."""

    def execute_guard(
        self,
        *,
        blockers,
        start=(8, -8, 0),
        approved=None,
        session_present=True,
        owns=True
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        guard = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "ranch_session.owns(character)" in ast.unparse(node.test)
            and "bridge_blockers" in ast.unparse(node)
        )
        db = object()
        connection = Mock(return_value=nullcontext(db))
        session = (
            SimpleNamespace(owns=Mock(return_value=owns)) if session_present else None
        )
        points = set(approved if approved is not None else [start, (9, -9, 0)])
        ns = dict(
            ranch_session=session,
            character=dict(id=41, instance_id=17),
            STORE=SimpleNamespace(connection=connection),
            approved=points,
            movement=dict(start_position=start),
            movement_state=SimpleNamespace(key=lambda point: tuple(point)),
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[deepcopy(guard)], type_ignores=[])
        )
        with patch.object(
            bridges, "blocked_cells", return_value=set(blockers)
        ) as lookup:
            exec(compile(module, str(source), "exec"), ns)
        return connection, lookup, db

    def test_unbuilt_bridge_rejects_approved_path_entry(self):
        with self.assertRaisesRegex(ValueError, "Build the Ranch bridge"):
            self.execute_guard(blockers={(9, -9)})

    def test_built_bridge_allows_route_and_uses_canonical_private_owner(self):
        connection, lookup, db = self.execute_guard(blockers=set())
        connection.assert_called_once_with()
        lookup.assert_called_once_with(db, 17)

    def test_actor_already_on_blocked_start_can_step_out(self):
        self.execute_guard(
            blockers={(9, -9)}, start=(9, -9, 0), approved=[(9, -9, 0), (8, -9, 0)]
        )

    def test_bag_exterior_and_foreign_ranch_skip_bridge_authority(self):
        for session_present, owns in [(False, False), (True, False)]:
            with self.subTest(session_present=session_present, owns=owns):
                connection, lookup, _ = self.execute_guard(
                    blockers={(9, -9)}, session_present=session_present, owns=owns
                )
                connection.assert_not_called()
                lookup.assert_not_called()


class RanchInitialContextDispatchTests(unittest.TestCase):
    def test_actual_initial_hydration_replaces_empty_context_before_map_transition(
        self,
    ):
        from wakfu_server import haven_ranch_furniture

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "character['map_id'] == 1440"
            and "initial_ranch" in ast.unparse(node)
        )
        for map_id in (1440, 1466):
            with self.subTest(map_id=map_id):
                old = [
                    (13256, b""),
                    (13864, b"empty"),
                    (13974, b"transition"),
                    (12318, b"position"),
                ]
                ns = dict(
                    character=dict(map_id=map_id),
                    packets=list(old),
                    STORE=object(),
                    account_id=7,
                    generation="lease",
                    child=object(),
                    time=SimpleNamespace(time=lambda: 1700000000),
                )
                snapshot = Mock(
                    return_value=dict(packet=(13864, b"populated-built-slots"))
                )
                module = ast.fix_missing_locations(
                    ast.Module(body=[deepcopy(branch)], type_ignores=[])
                )
                with patch.object(haven_ranch_furniture, "snapshot", snapshot):
                    exec(compile(module, str(source), "exec"), ns)
                if map_id == 1440:
                    snapshot.assert_called_once_with(
                        ns["STORE"],
                        7,
                        "lease",
                        ns["character"],
                        session=ns["child"],
                        now_ms=1700000000000,
                    )
                    self.assertEqual(
                        ns["packets"][1], (13864, b"populated-built-slots")
                    )
                    self.assertLess(
                        [p[0] for p in ns["packets"]].index(13864),
                        [p[0] for p in ns["packets"]].index(13974),
                    )
                else:
                    snapshot.assert_not_called()
                    self.assertEqual(ns["packets"], old)
