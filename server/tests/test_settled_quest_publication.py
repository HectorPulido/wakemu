"""Durable quest rewards refresh the live character before notifications."""

import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from wakfu_server.application.session_objectives import ObjectivesSessionMixin
from wakfu_server.application.session_private_scenes import PrivateScenesMixin
from wakfu_server.application.session import Session
from wakfu_server.application.dispatch_result import DispatchResult


class PrivateContext:
    def owns(self, character):
        return character["map_id"] == 9 and character["instance_id"] == 42

    def refresh(self, character, saved):
        return {
            **character,
            **saved,
            **{key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")},
            "haven_bag": character["haven_bag"],
            "haven_bag_visitor": character["haven_bag_visitor"],
        }


class SessionHarness(ObjectivesSessionMixin, PrivateScenesMixin):
    pass


class SettledQuestPublicationTests(unittest.TestCase):
    def setUp(self):
        self.session = SessionHarness()
        self.character = {
            "id": 77,
            "account_id": 8,
            "hp": 153,
            "max_hp": 160,
            "level": 11,
            "map_id": 9,
            "instance_id": 42,
            "direction": 3,
            "x": 12,
            "y": -4,
            "z": 1,
            "haven_bag": {"instance_id": 42},
            "haven_bag_visitor": True,
            "inventory": [],
        }
        self.private_context = PrivateContext()
        self.packets = [(12345, b"quest reward")]
        self.events = []
        store = Mock()
        store.character.return_value = {
            "id": 77,
            "account_id": 8,
            "hp": 163,
            "max_hp": 170,
            "level": 12,
            "inventory": [{"item_id": 31007, "quantity": 3}],
        }

        def merge(account, generation, updated):
            self.events.append(("merge", deepcopy(updated)))

        def send_batch(connection, service, packets):
            self.events.append(("send", deepcopy(self.session.state.character)))

        self.session.runtime = SimpleNamespace(
            STORE=store,
            POSITIONS=SimpleNamespace(merge=merge),
            send_batch=send_batch,
        )
        self.session.state = SimpleNamespace(
            character=self.character,
            account_id=8,
            generation="lease-2",
            position={"x": 12, "y": -4, "z": 1},
            ranch_session=None,
            bag_session=self.private_context,
            connection=object(),
            service="world",
        )

    def test_settled_reward_refreshes_durable_state_before_send_and_keeps_private_scene(
        self,
    ):
        self.session.publish_settled_quest_packets(self.packets)
        saved = self.session.state.character
        self.assertEqual((saved["hp"], saved["max_hp"], saved["level"]), (163, 170, 12))
        self.assertEqual(saved["inventory"], [{"item_id": 31007, "quantity": 3}])
        self.assertEqual(
            (saved["map_id"], saved["instance_id"], saved["x"], saved["y"], saved["z"]),
            (9, 42, 12, -4, 1),
        )
        self.assertEqual(saved["haven_bag"], {"instance_id": 42})
        self.assertTrue(saved["haven_bag_visitor"])
        self.assertIs(self.session.state.bag_session, self.private_context)
        self.assertIsNone(self.session.state.ranch_session)
        self.assertEqual([event[0] for event in self.events], ["merge", "send"])
        self.assertEqual(self.events[-1][1], saved)
        self.session.runtime.STORE.character.assert_called_once_with(8, 77)

    def test_empty_packets_skip_durable_reads_but_preserve_send_batch_contract(self):
        self.session.publish_settled_quest_packets([])
        self.session.runtime.STORE.character.assert_not_called()
        self.assertEqual(self.events, [("send", self.character)])

    def test_all_three_rii_dialogue_routes_call_generic_settled_publisher(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server"
            / "application"
            / "session_objectives.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ObjectivesSessionMixin"
        )
        dialogue = next(
            node
            for node in handler.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "handle_world_dialogue"
        )
        calls = [
            node
            for node in ast.walk(dialogue)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "self.publish_settled_quest_packets"
        ]
        self.assertEqual(len(calls), 6)
        self.assertEqual(
            [ast.unparse(call.args[0]) for call in calls],
            [
                "suspect_packets",
                "ruel_packets",
                "self.state.outcome['packets']",
                "self.state.outcome['packets']",
                "self.state.outcome['packets']",
                "self.state.outcome['packets']",
            ],
        )

    def test_actual_portal_handler_commits_scene_and_registry_before_packets(self):
        session = object.__new__(Session)
        character = {
            "id": 77,
            "account_id": 8,
            "map_id": 1385,
            "instance_id": 0,
            "x": 2,
            "y": -11,
            "z": 1,
        }
        pending = SimpleNamespace()
        result_character = {**character, "x": 3, "y": -18, "z": 4}
        packets = [(12345, b"scene")]
        positions = SimpleNamespace(
            account_barrier=lambda *_: nullcontext(),
            flush=lambda **_: None,
            attach=Mock(),
        )
        runtime = SimpleNamespace(
            POSITIONS=positions,
            flush_positions=Mock(),
            STORE=object(),
            Movement=lambda position: ("movement", position),
            WORLD=SimpleNamespace(update=Mock()),
            send_batch=Mock(),
            record=Mock(),
        )
        session.runtime = runtime
        session.environment_blocked = Mock(return_value=False)
        approved_positions = frozenset({(2, -11, 1), (3, -15, 1)})
        session.state = SimpleNamespace(
            account_id=8,
            generation="lease",
            character=character,
            body=struct.pack(">qHH", 34719, 5, 0),
            connection=pending,
            service="world",
            position={"x": 2, "y": -11, "z": 1},
            movement_state=SimpleNamespace(approved=approved_positions),
        )
        with patch(
            "wakfu_server.rii_zaap_scene.begin",
            return_value={
                "started": True,
                "character": result_character,
                "packets": packets,
            },
        ) as begin:
            session.handle_rii_zaap_scene()
        begin.assert_called_once_with(
            runtime.STORE,
            8,
            "lease",
            character,
            session.state.body,
            approved_positions=tuple(approved_positions),
        )
        positions.attach.assert_called_once_with(8, "lease", result_character)
        runtime.WORLD.update.assert_called_once_with(
            "lease", result_character, *packets[0], include_sender=False
        )
        runtime.send_batch.assert_called_once_with(pending, "world", packets)
        self.assertEqual(pending.pending_rii_zaap_scene, 77)
        self.assertEqual(session.state.position, {"x": 3, "y": -18, "z": 4})

    def test_actual_dispatch_routes_captured_portal_activation_to_scene_handler(self):
        session = object.__new__(Session)
        session.state = SimpleNamespace(
            opcode=12870,
            loaded=True,
            service="world",
            generation="lease",
            artifact_action_request=False,
            body=struct.pack(">qHH", 34719, 5, 0),
            character={"id": 77, "map_id": 1385, "instance_id": 0},
            ranch_session=None,
        )
        session.runtime = SimpleNamespace(COMBAT_TEST=False)
        session.handle_rii_zaap_scene = Mock(return_value=DispatchResult.CONTINUE)
        self.assertIs(session.dispatch_request(), DispatchResult.CONTINUE)
        session.handle_rii_zaap_scene.assert_called_once_with()

    def test_blocked_portal_handler_is_a_noop(self):
        session = object.__new__(Session)
        connection = SimpleNamespace(pending_rii_zaap_scene=77)
        session.state = SimpleNamespace(
            account_id=8,
            generation="lease",
            character={"id": 77, "map_id": 1385, "instance_id": 0},
            body=struct.pack(">qHH", 34719, 5, 0),
            connection=connection,
            service="world",
        )
        session.environment_blocked = Mock(return_value=True)
        session.runtime = SimpleNamespace(record=Mock())
        with patch("wakfu_server.rii_zaap_scene.begin") as begin:
            session.handle_rii_zaap_scene()
        begin.assert_not_called()
        self.assertEqual(connection.pending_rii_zaap_scene, 77)
        self.assertEqual(session.state.character["map_id"], 1385)

    def test_actual_22534_callback_checks_owner_clears_pending_and_publishes_route(
        self,
    ):
        session = object.__new__(Session)
        connection = SimpleNamespace(pending_rii_zaap_scene=77)
        character = {"id": 77, "map_id": 1385, "instance_id": 0}
        route = {
            "destination": {"map_id": 527, "instance_id": 0, "x": 1, "y": 2, "z": 3}
        }
        saved = {"id": 77}
        packets = [(12470, b"reward")]
        called = []

        def publish(route_arg, saved_arg, **kwargs):
            called.append((route_arg, saved_arg, kwargs))
            kwargs["before_bootstrap"]()

        session.publish_public_transport = Mock(side_effect=publish)
        session.publish_settled_quest_packets = Mock()
        session.runtime = SimpleNamespace(
            POSITIONS=SimpleNamespace(account_barrier=lambda *_: nullcontext()),
            flush_positions=Mock(),
            STORE=object(),
            record=Mock(),
        )
        session.state = SimpleNamespace(
            body=struct.pack(">i", 22534),
            account_id=8,
            generation="lease",
            character=character,
            connection=connection,
            fight=None,
            combat_session=None,
        )
        with patch(
            "wakfu_server.rii_zaap_scene.finish",
            return_value=(saved, packets, route),
        ) as finish:
            session.handle_world_loaded()
        finish.assert_called_once()
        self.assertEqual(finish.call_args.kwargs["pending_character_id"], 77)
        self.assertIsNone(connection.pending_rii_zaap_scene)
        session.publish_public_transport.assert_called_once()
        self.assertEqual(called[0][:2], (route, saved))
        session.publish_settled_quest_packets.assert_called_once_with(packets)

    def test_actual_22534_callback_rejects_foreign_pending_owner(self):
        session = object.__new__(Session)
        session.publish_public_transport = Mock()
        session.runtime = SimpleNamespace(
            POSITIONS=SimpleNamespace(account_barrier=lambda *_: nullcontext()),
            flush_positions=Mock(),
            STORE=object(),
            record=Mock(),
        )
        session.state = SimpleNamespace(
            body=struct.pack(">i", 22534),
            account_id=8,
            generation="lease",
            character={"id": 77, "map_id": 1385, "instance_id": 0},
            connection=SimpleNamespace(pending_rii_zaap_scene=88),
            fight=None,
            combat_session=None,
        )
        with patch(
            "wakfu_server.rii_zaap_scene.finish",
            side_effect=ValueError("foreign owner"),
        ) as finish:
            session.handle_world_loaded()
        finish.assert_called_once()
        session.publish_public_transport.assert_not_called()
        self.assertEqual(session.state.connection.pending_rii_zaap_scene, 88)


if __name__ == "__main__":
    unittest.main()
