"""Actual dispatch rejection/publish boundaries preserve travel and chest authority."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from psycopg import OperationalError
from psycopg_pool import PoolTimeout

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.performance_profiler import PerformanceProfiler
from wakfu_server.travel_storage_feedback import blocked_world_rejection, rejection
import test_native_boat_dispatch as native_dispatch_fixtures


def text(packet):
    opcode, payload = packet
    if opcode != 349 or struct.unpack(">hh", payload[:4]) != (4, len(payload[4:])):
        raise AssertionError("Expected complete native information349")
    return payload[4:].decode("utf-8")


class TravelStorageFeedbackTests(unittest.TestCase):
    def test_actual_combat_gate_preserves_fight_and_reports_blocked_travel(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = deepcopy(
            next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.If)
                and ast.unparse(n.test).startswith("fight is not None and opcode in")
                and "combat_world_action_rejected" in ast.unparse(n.body)
            )
        )
        branch.orelse = []
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch],
            orelse=[],
        )
        fight, actor = object(), dict(id=41)
        sent, events = [], []
        namespace = dict(
            fight=fight,
            character=actor,
            opcode=13686,
            body=b"",
            connection=object(),
            service="world",
            send=lambda connection, service, *packet: sent.append(packet),
            record=lambda **event: events.append(event),
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        self.assertIs(namespace["fight"], fight)
        self.assertIs(namespace["character"], actor)
        self.assertEqual(len(sent), 1)
        self.assertIn("combate", text(sent[0]))
        self.assertEqual(events[0]["event"], "combat_world_action_rejected")

    def test_existing_combat_gate_explains_only_travel_and_account_chest_actions(self):
        for opcode in (13686, 12296):
            self.assertIn("combate", text(blocked_world_rejection(opcode, b"")))
        self.assertIn(
            "fuera de combate",
            text(blocked_world_rejection(12870, struct.pack(">qHH", 13261, 12, 0))),
        )
        for opcode, body in (
            (13331, b""),
            (12870, b""),
            (12870, struct.pack(">qHH", 13261, 0, 0)),
            (12870, struct.pack(">qHH", 13261, 12, 1)),
        ):
            self.assertIsNone(blocked_world_rejection(opcode, body))

    def test_span_rejections_are_actionable_and_database_details_never_escape(self):
        for action in ("transport", "chest_open"):
            for error in (
                OperationalError("password=private SELECT private_rows"),
                PoolTimeout("private_host private_key"),
                ValueError("Unexpected private SQL detail"),
            ):
                message = text(rejection(action, error))
                self.assertNotIn("private", message)
                self.assertNotIn("SELECT", message)
                self.assertIn("vuelve", message.casefold())
        self.assertIn(
            "acércate",
            text(
                rejection("transport", ValueError("Character is too far from the ZAAP"))
            ),
        )
        self.assertIn(
            "visitante",
            text(
                rejection(
                    "chest_open", ValueError("Chest requires its owner outside combat")
                )
            ),
        )

    def test_native_transport_database_failure_has_feedback_without_moving(self):
        fixture = native_dispatch_fixtures.NativeBoatDispatchTests(
            "test_nonboat_zaap_and_drago_keep_existing_resolver_and_transition"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.namespace["body"] = struct.pack(">qq", 31316, 999)
        fixture.namespace["native_transports"].resolve.return_value = {
            "source_id": 31316,
            "destination_id": 999,
            "destination": fixture.destination,
        }
        for error in (
            OperationalError("private_database"),
            PoolTimeout("private_pool"),
        ):
            fixture.namespace["send"].reset_mock()
            fixture.store.transition_map.side_effect = error
            fixture.run_dispatch()
            fixture.namespace["WORLD"].leave.assert_not_called()
            fixture.namespace["POSITIONS"].attach.assert_not_called()
            self.assertIs(fixture.namespace["character"], fixture.character)
            call = fixture.namespace["send"].call_args.args
            self.assertNotIn("private", text((call[2], call[3])))
        features = {
            row["name"]: row
            for row in fixture.namespace["PROFILER"].snapshot()["features"]
        }
        self.assertEqual(features["transport.native.commit"]["errors"], 2)
        self.assertNotIn("transport.native.publish", features)

    def chest(self, *, error=None, far=False, serializer_error=False):
        from wakfu_server import haven_chest, haven_chest_wire

        outside = dict(
            id=41,
            account_id=7,
            name="Chest Owner",
            map_id=527,
            instance_id=0,
            x=0,
            y=32,
            z=0,
        )
        bag = HavenBagSession(outside)
        actor = bag.move(bag.inside, dict(x=20 if far else 0, y=-3, z=0))
        chest = dict(
            id=str(uuid.uuid4()),
            account_id=7,
            capacity=2000,
            revision=3,
            items=[],
            locks=[],
        )
        load = Mock(return_value=chest, side_effect=error)
        sent, events = [], []
        namespace = dict(
            opcode=12870,
            body=struct.pack(">qHH", 13261, 12, 0),
            character=actor,
            bag_session=bag,
            fight=None,
            spectator_session=None,
            ranch_session=None,
            STORE=object(),
            account_id=7,
            generation="lease",
            PROFILER=PerformanceProfiler(),
            uuid=uuid,
            struct=struct,
            chest_opening=uuid.uuid4(),
            connection=object(),
            service="world",
            world_static=SimpleNamespace(
                objects=lambda _: [
                    dict(id=13261, type="AccountChest", map_id=9, x=0, y=-4, z=0)
                ]
            ),
            cancel_crafting=Mock(),
            send=lambda connection, service, *packet: sent.append(packet),
            record=lambda **event: events.append(event),
        )
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = deepcopy(
            next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.If)
                and "struct.unpack_from('>H', body, 8)[0] == 12" in ast.unparse(n.test)
            )
        )
        branch.orelse = []
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch],
            orelse=[],
        )
        serializer = (
            Mock(side_effect=ValueError("private malformed snapshot"))
            if serializer_error
            else haven_chest_wire.bootstrap
        )
        with patch.object(haven_chest, "load", load), patch.object(
            haven_chest_wire, "bootstrap", serializer
        ):
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
                    str(source),
                    "exec",
                ),
                namespace,
            )
        return namespace, load, sent, events

    def test_chest_proximity_load_and_publish_failures_leave_no_active_opening(self):
        for kwargs, span in (
            ({"far": True}, "storage.chest.open.validate"),
            ({"error": PoolTimeout("private_pool")}, "storage.chest.open.load"),
            ({"serializer_error": True}, "storage.chest.open.publish"),
        ):
            namespace, load, sent, events = self.chest(**kwargs)
            self.assertIsNone(namespace["chest_opening"])
            self.assertEqual(len(sent), 2)
            self.assertEqual(sent[0], (12088, struct.pack(">BhqI", 2, 31, 41, 0)))
            self.assertNotIn("private", text(sent[1]))
            self.assertEqual(events[-1]["event"], "account_chest_open_rejected")
            features = {
                row["name"]: row for row in namespace["PROFILER"].snapshot()["features"]
            }
            self.assertEqual(features[span]["errors"], 1)
            if kwargs.get("far"):
                load.assert_not_called()

    def test_chest_success_keeps_native_packet_order_and_profiles_actual_stages(self):
        namespace, load, sent, events = self.chest()
        load.assert_called_once()
        self.assertIsInstance(namespace["chest_opening"], uuid.UUID)
        self.assertEqual([opcode for opcode, _ in sent], [318, 12401, 12344, 12088])
        self.assertEqual(events[-1]["event"], "account_chest_opened")
        features = {
            row["name"]: row for row in namespace["PROFILER"].snapshot()["features"]
        }
        self.assertEqual(
            set(features),
            {
                "storage.chest.open.validate",
                "storage.chest.open.load",
                "storage.chest.open.publish",
            },
        )
        self.assertTrue(all(row["errors"] == 0 for row in features.values()))
