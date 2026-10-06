import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from wakfu_server.world import World
from wakfu_server import wire


class WorldTests(unittest.TestCase):
    def test_failed_delivery_reports_cause_before_shutdown(self):
        order = []

        class Peer:
            def shutdown(self, how):
                order.append(("shutdown", how))

        def fail(peer, opcode, body):
            raise BrokenPipeError(32, "closed")

        world = World(
            lambda c: b"",
            lambda c: b"",
            fail,
            delivery_failure=lambda peer, opcode, error: order.append(
                ("failure", opcode, error.errno)
            ),
        )
        world._send(Peer(), 13852, b"world movement")
        self.assertEqual(order, [("failure", 13852, 32), ("shutdown", 2)])

    def setUp(self):
        self.messages = []
        self.world = World(
            lambda c: ("spawn", c["id"], c["x"]),
            lambda c: ("remove", c),
            lambda p, op, b: self.messages.append((p, op, b)),
        )

    def character(self, id, map_id=1134, instance_id=0, x=0):
        return dict(id=id, map_id=map_id, instance_id=instance_id, x=x)

    def chat_character(self, character_id, account_id, name, map_id):
        return dict(
            id=character_id,
            account_id=account_id,
            name=name,
            map_id=map_id,
            instance_id=0,
            x=0,
            y=0,
            z=0,
        )

    def test_private_chat_is_targeted_casefolded_cross_map_and_uses_distinct_ids(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        third = self.chat_character(303, 9003, "Otro", 1134)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("recipient-generation", "recipient-peer", recipient)
        self.world.join("third-generation", "third-peer", third)
        self.messages.clear()

        delivered = self.world.private_chat(
            "sender-generation",
            sender["id"],
            sender["account_id"],
            "dEsTiNo",
            "hola ñ",
            valid_session=lambda entry: True,
        )

        self.assertTrue(delivered)
        self.assertEqual(len(self.messages), 2)
        target_delivery, sender_echo = self.messages
        self.assertEqual(target_delivery[0:2], ("recipient-peer", 720))
        self.assertEqual(sender_echo, ("sender-peer", 720, target_delivery[2]))
        self.assertNotIn("third-peer", [message[0] for message in self.messages])
        payload = target_delivery[2]
        recipient_name = "Destino".encode()
        self.assertEqual(payload[0], len(recipient_name))
        self.assertEqual(payload[1 : 1 + len(recipient_name)], recipient_name)
        recipient_id_offset = 1 + len(recipient_name)
        self.assertEqual(
            int.from_bytes(
                payload[recipient_id_offset : recipient_id_offset + 8], "big"
            ),
            recipient["id"],
        )
        self.assertIn(sender["account_id"].to_bytes(8, "big"), payload)
        self.assertNotIn(sender["id"].to_bytes(8, "big"), payload)

    def test_private_chat_reports_offline_and_self_without_echo(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        self.world.join("sender-generation", "sender-peer", sender)
        self.messages.clear()

        delivered = self.world.private_chat(
            "sender-generation",
            101,
            9001,
            "Missing",
            "hello",
            valid_session=lambda entry: True,
        )
        self.assertFalse(delivered)
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(101, "Missing"))],
        )

        self.messages.clear()
        delivered = self.world.private_chat(
            "sender-generation",
            101,
            9001,
            "sENDER",
            "hello",
            valid_session=lambda entry: True,
        )
        self.assertFalse(delivered)
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(104))],
        )

    def test_private_chat_rejects_account_identity_that_disagrees_with_sender(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        self.world.join("sender-generation", "sender-peer", sender)
        self.messages.clear()
        with self.assertRaisesRegex(ValueError, "account identity"):
            self.world.private_chat(
                "sender-generation",
                101,
                101,
                "Nobody",
                "hello",
                valid_session=lambda entry: True,
            )
        self.assertEqual(self.messages, [])

    def test_private_chat_rejects_stale_sender_and_treats_stale_target_as_offline(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        self.world.join("current-sender-generation", "sender-peer", sender)
        self.world.join("stale-recipient-generation", "old-recipient-peer", recipient)
        self.messages.clear()

        with self.assertRaisesRegex(ValueError, "stale"):
            self.world.private_chat(
                "old-sender-generation",
                101,
                9001,
                "Destino",
                "hello",
                valid_session=lambda entry: True,
            )
        self.assertEqual(self.messages, [])

        delivered = self.world.private_chat(
            "current-sender-generation",
            101,
            9001,
            "Destino",
            "hello",
            valid_session=lambda entry: entry[0] != "stale-recipient-generation",
        )
        self.assertFalse(delivered)
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(101, "Destino"))],
        )

    def test_private_chat_targets_replacement_peer_not_old_recipient_session(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("old-recipient-generation", "old-recipient-peer", recipient)
        self.world.join("new-recipient-generation", "new-recipient-peer", recipient)
        self.messages.clear()

        delivered = self.world.private_chat(
            "sender-generation",
            101,
            9001,
            "Destino",
            "hello",
            valid_session=lambda entry: True,
        )

        self.assertTrue(delivered)
        self.assertEqual(
            [message[0] for message in self.messages],
            ["new-recipient-peer", "sender-peer"],
        )
        self.assertNotIn(
            "old-recipient-peer", [message[0] for message in self.messages]
        )

    def test_private_chat_target_send_failure_returns_general_error_without_echo(self):
        class Peer:
            def __init__(self):
                self.shutdown_calls = []

            def shutdown(self, how):
                self.shutdown_calls.append(how)

        sender_peer, recipient_peer = Peer(), Peer()
        sent = []

        def deliver(peer, opcode, body):
            if peer is recipient_peer:
                raise OSError("recipient disconnected")
            sent.append((peer, opcode, body))

        world = World(lambda c: b"", lambda c: b"", deliver)
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        world.join("sender-generation", sender_peer, sender)
        world.join("recipient-generation", recipient_peer, recipient)
        sent.clear()

        delivered = world.private_chat(
            "sender-generation",
            101,
            9001,
            "Destino",
            "hello",
            valid_session=lambda entry: True,
        )

        self.assertFalse(delivered)
        self.assertEqual(recipient_peer.shutdown_calls, [2])
        self.assertEqual(sent, [(sender_peer, 349, wire.private_chat_error(140))])

    def test_private_chat_sender_echo_failure_occurs_after_recipient_delivery(self):
        class Peer:
            def __init__(self):
                self.shutdown_calls = []

            def shutdown(self, how):
                self.shutdown_calls.append(how)

        sender_peer, recipient_peer = Peer(), Peer()
        sent = []

        def deliver(peer, opcode, body):
            if peer is sender_peer:
                raise OSError("sender disconnected after recipient write")
            sent.append((peer, opcode, body))

        world = World(lambda c: b"", lambda c: b"", deliver)
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        world.join("sender-generation", sender_peer, sender)
        world.join("recipient-generation", recipient_peer, recipient)
        sent.clear()

        delivered = world.private_chat(
            "sender-generation",
            101,
            9001,
            "Destino",
            "hello",
            valid_session=lambda entry: True,
        )

        self.assertFalse(delivered)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][:2], (recipient_peer, 720))
        self.assertEqual(sender_peer.shutdown_calls, [2])

    def test_blocked_private_chat_session_check_does_not_hold_world_membership_lock(
        self,
    ):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        third = self.chat_character(303, 9003, "Otro", 900)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("recipient-generation", "recipient-peer", recipient)
        self.world.join("third-generation", "third-peer", third)
        self.messages.clear()
        checking, resume = threading.Event(), threading.Event()

        def valid_session(entry):
            if entry[2]["id"] == recipient["id"]:
                checking.set()
                if not resume.wait(timeout=5):
                    raise AssertionError("test did not release the session check")
            return True

        with ThreadPoolExecutor(max_workers=3) as workers:
            delivery = workers.submit(
                self.world.private_chat,
                "sender-generation",
                101,
                9001,
                "Destino",
                "hello",
                valid_session=valid_session,
            )
            self.assertTrue(checking.wait(timeout=2))
            snapshot = workers.submit(self.world.snapshot)
            leave = workers.submit(self.world.leave, 303, "third-generation")
            try:
                self.assertEqual(len(snapshot.result(timeout=1)), 3)
                self.assertTrue(leave.result(timeout=1))
                self.assertEqual(len(self.world.snapshot()), 2)
            finally:
                resume.set()
            self.assertTrue(delivery.result(timeout=2))

    def test_blocked_private_chat_socket_write_does_not_hold_world_membership_lock(
        self,
    ):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        third = self.chat_character(303, 9003, "Otro", 900)
        checking, resume = threading.Event(), threading.Event()
        sent = []

        def deliver(peer, opcode, body):
            if peer == "recipient-peer" and opcode == 720:
                checking.set()
                if not resume.wait(timeout=5):
                    raise AssertionError("test did not release the socket write")
            sent.append((peer, opcode, body))

        world = World(lambda c: b"", lambda c: b"", deliver)
        world.join("sender-generation", "sender-peer", sender)
        world.join("recipient-generation", "recipient-peer", recipient)
        world.join("third-generation", "third-peer", third)
        sent.clear()
        with ThreadPoolExecutor(max_workers=3) as workers:
            delivery = workers.submit(
                world.private_chat,
                "sender-generation",
                101,
                9001,
                "Destino",
                "hello",
                valid_session=lambda entry: True,
            )
            self.assertTrue(checking.wait(timeout=2))
            snapshot = workers.submit(world.snapshot)
            leave = workers.submit(world.leave, 303, "third-generation")
            try:
                self.assertEqual(len(snapshot.result(timeout=1)), 3)
                self.assertTrue(leave.result(timeout=1))
                self.assertEqual(len(world.snapshot()), 2)
            finally:
                resume.set()
            self.assertTrue(delivery.result(timeout=2))
        self.assertEqual(
            [message[0] for message in sent], ["recipient-peer", "sender-peer"]
        )

    def test_private_chat_does_not_redirect_if_target_is_replaced_during_session_check(
        self,
    ):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("old-recipient-generation", "old-recipient-peer", recipient)
        self.messages.clear()
        checking, resume = threading.Event(), threading.Event()

        def valid_session(entry):
            if entry[2]["id"] == recipient["id"]:
                checking.set()
                if not resume.wait(timeout=5):
                    raise AssertionError("test did not release the session check")
            return True

        with ThreadPoolExecutor(max_workers=2) as workers:
            delivery = workers.submit(
                self.world.private_chat,
                "sender-generation",
                101,
                9001,
                "Destino",
                "hello",
                valid_session=valid_session,
            )
            self.assertTrue(checking.wait(timeout=2))
            self.world.join("new-recipient-generation", "new-recipient-peer", recipient)
            resume.set()
            self.assertFalse(delivery.result(timeout=2))

        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(101, "Destino"))],
        )
        self.assertNotIn(
            "old-recipient-peer", [message[0] for message in self.messages]
        )
        self.assertNotIn(
            "new-recipient-peer", [message[0] for message in self.messages]
        )

    def test_mutual_visibility_move_and_departure(self):
        a, b = self.character(1), self.character(2)
        self.world.join("a", "alpha", a)
        self.world.join("b", "beta", b)
        self.assertEqual(
            self.messages,
            [("beta", 12608, ("spawn", 1, 0)), ("alpha", 12608, ("spawn", 2, 0))],
        )
        a["x"] = 5
        self.world.update("a", a, 13530, b"position")
        self.assertEqual(
            self.messages[-2:],
            [("alpha", 13530, b"position"), ("beta", 13530, b"position")],
        )
        self.assertTrue(self.world.leave(1, "a"))
        self.assertEqual(self.messages[-1], ("beta", 12304, ("remove", 1)))

    def test_remote_path_excludes_owner_and_preserves_position_for_new_joiner(self):
        a = self.character(1)
        self.world.join("a", "alpha", a)
        self.world.join("b", "beta", self.character(2))
        self.world.join("c", "other-map", self.character(3, map_id=42))
        self.messages.clear()
        a["x"] = 7
        self.world.update("a", a, 13852, b"packed path", include_sender=False)
        self.assertEqual(self.messages, [("beta", 13852, b"packed path")])
        self.world.join("d", "newcomer", self.character(4))
        self.assertIn(("newcomer", 12608, ("spawn", 1, 7)), self.messages)

    def test_map_and_instance_isolation(self):
        self.world.join("a", "alpha", self.character(1))
        self.world.join("b", "beta", self.character(2, map_id=42))
        self.world.join("c", "gamma", self.character(3, instance_id=1))
        self.assertEqual(self.messages, [])
        self.world.update("a", self.character(1, x=3), 13530, b"move")
        self.assertEqual(self.messages, [("alpha", 13530, b"move")])
        self.world.leave(1, "a")
        self.assertEqual(len(self.messages), 1)

    def test_own_bag_entry_hides_actor_and_interior_updates_are_private(self):
        outside = self.character(1, x=7)
        other = self.character(2)
        self.world.join("a", "alpha", outside)
        self.world.join("b", "beta", other)
        self.messages.clear()
        self.world.leave(1, "a")
        inside = self.character(1, map_id=9, instance_id=1, x=3)
        self.world.join("a", "alpha", inside)
        self.assertEqual(self.messages, [("beta", 12304, ("remove", 1))])
        self.world.join("c", "gamma", self.character(3, map_id=9, instance_id=3))
        self.world.update("a", {**inside, "x": 4}, 13852, b"path", include_sender=False)
        self.assertEqual(self.messages, [("beta", 12304, ("remove", 1))])
        self.world.leave(1, "a")
        self.world.join("a", "alpha", outside)
        self.assertEqual(
            self.messages[-2:],
            [("alpha", 12608, ("spawn", 2, 0)), ("beta", 12608, ("spawn", 1, 7))],
        )

    def test_late_old_session_cannot_remove_or_move_replacement(self):
        self.world.join("a", "alpha", self.character(1))
        self.world.join("b", "beta", self.character(2))
        self.world.join("new", "replacement", self.character(1, x=4))
        before = len(self.messages)
        self.assertFalse(self.world.leave(1, "a"))
        with self.assertRaises(ValueError):
            self.world.update("a", self.character(1, x=8), 13530, b"move")
        self.assertEqual(len(self.messages), before)
        self.assertEqual(self.world.players[1][2]["x"], 4)

    def test_emit_location_without_sender_and_exclude_session(self):
        self.world.join("a", "alpha", self.character(1))
        self.world.join("b", "beta", self.character(2))
        self.world.join("c", "other", self.character(3, map_id=42))
        self.world.join("d", "instance", self.character(4, instance_id=9))
        self.messages.clear()
        self.world.emit_location(1134, 0, 12304, b"npc", exclude_generation="a")
        self.assertEqual(self.messages, [("beta", 12304, b"npc")])

    def test_emit_location_failed_peer_does_not_stop_other_delivery(self):
        class Peer:
            def __init__(self, name):
                self.name = name
                self.closed = False

            def shutdown(self, how):
                self.closed = True

        bad, good = Peer("bad"), Peer("good")
        delivered = []

        def send(peer, opcode, body):
            if peer is bad:
                raise OSError("Disconnected")
            delivered.append(peer.name)

        world = World(lambda c: b"own", lambda c: b"remove", send)
        world.join("a", bad, self.character(1))
        world.join("b", good, self.character(2))
        delivered.clear()
        world.emit_location(1134, 0, 12304, b"npc")
        self.assertTrue(bad.closed)
        self.assertEqual(delivered, ["good"])


if __name__ == "__main__":
    unittest.main()
