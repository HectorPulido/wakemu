import unittest
from concurrent.futures import ThreadPoolExecutor
import struct
import threading
from wakfu_server.world import World
from wakfu_server import wire


class WorldTests(unittest.TestCase):
    def test_ranch_scene_refresh_is_scoped_coalesced_and_excludes_origin_lease(self):
        class Peer:
            pass

        world = World(lambda c: b"", lambda c: b"", lambda *_: None)
        origin, same_scope, other_instance, other_map = (Peer(), Peer(), Peer(), Peer())
        world.join("origin", origin, self.character(1, map_id=1440, instance_id=2))
        world.join("same", same_scope, self.character(2, map_id=1440, instance_id=2))
        world.join(
            "instance", other_instance, self.character(3, map_id=1440, instance_id=3)
        )
        world.join("map", other_map, self.character(4, map_id=1441, instance_id=2))

        self.assertEqual(
            1,
            world.request_ranch_scene_refresh(1440, 2, exclude_generation="origin"),
        )
        first = same_scope.ranch_scene_refresh
        self.assertEqual(first[:4], (2, "same", 1440, 2))
        self.assertFalse(hasattr(origin, "ranch_scene_refresh"))
        self.assertFalse(hasattr(other_instance, "ranch_scene_refresh"))
        self.assertFalse(hasattr(other_map, "ranch_scene_refresh"))

        self.assertEqual(2, world.request_ranch_scene_refresh(1440, 2))
        self.assertEqual((1, "origin", 1440, 2), origin.ranch_scene_refresh[:4])
        second = same_scope.ranch_scene_refresh
        self.assertEqual(second[:4], first[:4])
        self.assertGreater(second[4], first[4])

    def test_ranch_scene_refresh_does_not_redirect_stale_connection_work(self):
        class Peer:
            pass

        world = World(lambda c: b"", lambda c: b"", lambda *_: None)
        old_peer, current_peer = Peer(), Peer()
        character = self.character(9, map_id=1440, instance_id=4)
        world.join("old-lease", old_peer, character)
        self.assertEqual(1, world.request_ranch_scene_refresh(1440, 4))
        stale_request = old_peer.ranch_scene_refresh

        self.assertTrue(world.leave(9, "old-lease"))
        world.join("new-lease", current_peer, character)
        self.assertEqual(1, world.request_ranch_scene_refresh(1440, 4))

        self.assertEqual(stale_request, old_peer.ranch_scene_refresh)
        self.assertEqual("new-lease", current_peer.ranch_scene_refresh[1])
        self.assertGreater(current_peer.ranch_scene_refresh[4], stale_request[4])

    def test_actor_refresh_batches_reset_before_state_replay_to_same_observers(self):
        batches = []

        class Peer:
            def __init__(self, name):
                self.name = name

        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c["id"]),
            lambda *_: None,
            deliver_batch=lambda peer, packets: batches.append(
                (peer.name, tuple(packets))
            ),
            refresh_state_packets=lambda character: (
                (12613, ("food-state", character["id"])),
            ),
        )
        owner = self.character(101, map_id=1134, instance_id=7)
        observer = self.character(102, map_id=1134, instance_id=7)
        other_instance = self.character(103, map_id=1134, instance_id=8)
        world.join("owner", Peer("owner"), owner)
        world.join("observer", Peer("observer"), observer)
        world.join("other-instance", Peer("other"), other_instance)
        batches.clear()

        # A native format-10 reconstruction clears the actor's current effects.
        reset_body = struct.pack(">qH", owner["id"], 1) + b"\x0a"
        world.update("owner", owner, 15548, reset_body, include_sender=False)

        expected = ((15548, reset_body), (12613, ("food-state", 101)))
        self.assertEqual(batches, [("observer", expected)])

    def test_send_batch_uses_one_batch_writer_for_captured_peer(self):
        sent = []

        class Peer:
            def shutdown(self, how):
                self.fail("batch delivery should not shut down the peer")

        peer = Peer()
        world = World(
            lambda c: b"",
            lambda c: b"",
            lambda *_: self.fail("single-packet writer should not be used"),
            deliver_batch=lambda target, packets: sent.append((target, tuple(packets))),
        )
        world.join("lease", peer, self.character(81, map_id=4, instance_id=5))

        self.assertTrue(
            world.send_batch_to(81, "lease", ((13482, b"ready"), (12755, b"report")))
        )
        self.assertEqual(sent, [(peer, ((13482, b"ready"), (12755, b"report")))])
        self.assertFalse(world.send_batch_to(81, "old-lease", ((1, b"stale"),)))

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

    def test_information_all_reaches_snapshot_across_locations_and_skips_failed_peer(
        self,
    ):
        attempts = []
        failures = []

        class Peer:
            def __init__(self, name):
                self.name = name

            def shutdown(self, how):
                attempts.append(("shutdown", self.name, how))

        def deliver(peer, opcode, body):
            attempts.append((peer.name, opcode, body))
            if peer.name == "broken":
                raise BrokenPipeError(32, "gone")

        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            deliver,
            delivery_failure=lambda peer, opcode, error: failures.append(
                (peer.name, opcode, error.errno)
            ),
        )
        world.join("g1", Peer("map-a"), self.character(1, map_id=1, instance_id=0))
        world.join("g2", Peer("broken"), self.character(2, map_id=2, instance_id=8))
        world.join("g3", Peer("map-b"), self.character(3, map_id=1, instance_id=9))
        attempts.clear()

        delivered = world.information_all("Guardado global completado")

        self.assertEqual(2, delivered)
        sent = [event for event in attempts if len(event) == 3 and event[1] == 349]
        self.assertEqual({"map-a", "broken", "map-b"}, {event[0] for event in sent})
        self.assertEqual({("broken", 349, 32)}, set(failures))
        self.assertIn(("shutdown", "broken", 2), attempts)

    def test_information_all_does_not_hold_world_lock_during_socket_write(self):
        entered = threading.Event()
        release = threading.Event()

        class Peer:
            def shutdown(self, how):
                pass

        def deliver(_peer, opcode, _body):
            if opcode == 349:
                entered.set()
                self.assertTrue(release.wait(2))

        world = World(lambda c: b"", lambda c: b"", deliver)
        world.join("generation", Peer(), self.character(81, map_id=4, instance_id=5))
        with ThreadPoolExecutor(max_workers=2) as pool:
            sending = pool.submit(world.information_all, "Guardado iniciado")
            self.assertTrue(entered.wait(2))
            snapshot = pool.submit(world.snapshot)
            try:
                self.assertEqual([81], [row["id"] for row in snapshot.result(0.5)])
            finally:
                release.set()
            self.assertEqual(1, sending.result(2))

    def test_join_orders_state_snapshots_after_spawn_for_matching_instance_only(self):
        events = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: events.append(("send", peer, opcode, body)),
            state_packets=lambda character: ((12634, ("ride", character["id"])),),
        )
        first = self.character(1, map_id=1134, instance_id=7)
        second_instance = self.character(2, map_id=1134, instance_id=8)
        newcomer = self.character(3, map_id=1134, instance_id=7)
        world.join("g1", "peer1", first)
        world.join("g2", "peer2", second_instance)
        events.clear()

        world.join("g3", "peer3", newcomer)

        self.assertEqual(
            events,
            [
                ("send", "peer3", 12608, ("spawn", 1)),
                ("send", "peer3", 12634, ("ride", 1)),
                ("send", "peer1", 12608, ("spawn", 3)),
                ("send", "peer1", 12634, ("ride", 3)),
                ("send", "peer3", 12634, ("ride", 3)),
            ],
        )

    def test_join_reconnect_replays_own_state_after_registration(self):
        observations = []
        world = None

        def state_packets(character):
            observations.append((character["id"] in world.players, character["id"]))
            return ((12634, ("ride", character["id"])),)

        messages = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: messages.append((peer, opcode, body)),
            state_packets=state_packets,
        )
        actor = self.character(11, map_id=1134, instance_id=2)
        world.join("old-generation", "old-peer", actor)
        observations.clear()
        messages.clear()

        world.join("new-generation", "new-peer", actor)

        self.assertEqual(observations, [(True, 11)])
        self.assertEqual(messages, [("new-peer", 12634, ("ride", 11))])

    def test_resynchronize_restores_visible_snapshot_only_to_current_peer(self):
        messages = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: messages.append((peer, opcode, body)),
            state_packets=lambda c: ((12634, ("ride", c["id"])),),
        )
        owner = self.character(1, map_id=1134, instance_id=7)
        other = self.character(2, map_id=1134, instance_id=7)
        foreign_instance = self.character(3, map_id=1134, instance_id=8)
        world.join("owner-generation", "owner-peer", owner)
        world.join("other-generation", "other-peer", other)
        world.join("foreign-generation", "foreign-peer", foreign_instance)
        messages.clear()

        self.assertTrue(world.resynchronize("owner-generation", "owner-peer", owner))

        self.assertEqual(
            messages,
            [
                ("owner-peer", 12608, ("spawn", 2)),
                ("owner-peer", 12634, ("ride", 2)),
                ("owner-peer", 12634, ("ride", 1)),
            ],
        )

    def test_resynchronize_rejects_stale_session_without_delivery(self):
        messages = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: messages.append((peer, opcode, body)),
        )
        actor = self.character(1)
        world.join("new-generation", "new-peer", actor)
        messages.clear()

        self.assertRaisesRegex(
            ValueError,
            "stale",
            world.resynchronize,
            "old-generation",
            "old-peer",
            actor,
        )
        self.assertEqual(messages, [])

    def test_join_does_not_publish_mount_state_for_dismounted_actor(self):
        messages = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: messages.append((peer, opcode, body)),
            state_packets=lambda character: (),
        )
        world.join("g1", "peer1", self.character(1))
        self.assertEqual(messages, [])

    def test_publish_ecology_uses_current_session_and_location_and_rejects_old_revision(
        self,
    ):
        messages = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c),
            lambda peer, opcode, body: messages.append((peer, opcode, body)),
        )
        owner = dict(
            self.character(40, map_id=1200, instance_id=9),
            ecology_value=0,
            ecology_revision=0,
        )
        observer = self.character(41, map_id=1200, instance_id=9)
        unrelated = self.character(42, map_id=1134, instance_id=0)
        world.join("old", "old-owner", owner)
        world.join("observer-session", "observer", observer)
        world.join("other-session", "other", unrelated)
        messages.clear()

        committed = dict(
            owner, map_id=1134, instance_id=0, ecology_value=25, ecology_revision=1
        )
        self.assertTrue(world.publish_ecology(committed))
        self.assertEqual(
            {(peer, opcode) for peer, opcode, _ in messages},
            {("old-owner", 13574), ("observer", 13574)},
        )
        self.assertEqual(len({body for _, _, body in messages}), 1)
        updated = {c["id"]: c for c in world.snapshot()}[40]
        self.assertEqual(
            (1200, 9, 25, 1),
            (
                updated["map_id"],
                updated["instance_id"],
                updated["ecology_value"],
                updated["ecology_revision"],
            ),
        )

        messages.clear()
        stale = dict(committed, ecology_value=-25, ecology_revision=0)
        self.assertFalse(world.publish_ecology(stale))
        self.assertEqual(messages, [])
        still_current = {c["id"]: c for c in world.snapshot()}[40]
        self.assertEqual(
            (25, 1), (still_current["ecology_value"], still_current["ecology_revision"])
        )

    def test_publish_ecology_offline_owner_is_not_broadcast(self):
        committed = dict(self.character(50), ecology_value=25, ecology_revision=1)
        self.assertFalse(self.world.publish_ecology(committed))
        self.assertEqual(self.messages, [])

    def test_private_information_reaches_only_current_online_character_peer(self):
        from wakfu_server.ecology_feedback import information

        owner = self.character(51, map_id=1134, instance_id=4)
        observer = self.character(52, map_id=1134, instance_id=4)
        self.world.join("owner-gen", "owner-peer", owner)
        self.world.join("observer-gen", "observer-peer", observer)
        self.messages.clear()

        self.assertTrue(self.world.information(51, "Ecosistema: afinidad neutral."))
        self.assertEqual(
            [("owner-peer", *information("Ecosistema: afinidad neutral."))],
            self.messages,
        )
        self.messages.clear()
        self.assertFalse(self.world.information(999, "No debe enviarse"))
        self.assertEqual([], self.messages)

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

    def test_private_chat_social_block_denies_before_any_fanout(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("recipient-generation", "recipient-peer", recipient)
        self.messages.clear()
        checks = []

        def blocked(sender_account, recipient_account):
            checks.append((sender_account, recipient_account))
            return 103

        delivered = self.world.private_chat(
            "sender-generation",
            sender["id"],
            sender["account_id"],
            "Destino",
            "hello",
            valid_session=lambda entry: True,
            block_reason=blocked,
        )

        self.assertFalse(delivered)
        self.assertEqual(checks, [(sender["account_id"], recipient["account_id"])])
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(103, "Destino"))],
        )

    def test_private_chat_social_policy_runs_outside_world_lock(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        third = self.chat_character(303, 9003, "Otro", 900)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("recipient-generation", "recipient-peer", recipient)
        self.world.join("third-generation", "third-peer", third)
        self.messages.clear()
        checking, resume = threading.Event(), threading.Event()

        def block_reason(_sender_account, _recipient_account):
            checking.set()
            if not resume.wait(timeout=5):
                raise AssertionError("test did not release social policy lookup")
            return 102

        with ThreadPoolExecutor(max_workers=3) as workers:
            delivery = workers.submit(
                self.world.private_chat,
                "sender-generation",
                sender["id"],
                sender["account_id"],
                "Destino",
                "hello",
                valid_session=lambda entry: True,
                block_reason=block_reason,
            )
            self.assertTrue(checking.wait(timeout=2))
            snapshot = workers.submit(self.world.snapshot)
            leave = workers.submit(self.world.leave, third["id"], "third-generation")
            try:
                self.assertEqual(len(snapshot.result(timeout=1)), 3)
                self.assertTrue(leave.result(timeout=1))
            finally:
                resume.set()
            self.assertFalse(delivery.result(timeout=2))
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(102, "Destino"))],
        )

    def test_social_policy_is_not_consulted_for_stale_recipient_lease(self):
        sender = self.chat_character(101, 9001, "Sender", 1134)
        recipient = self.chat_character(202, 9002, "Destino", 42)
        self.world.join("sender-generation", "sender-peer", sender)
        self.world.join("recipient-generation", "recipient-peer", recipient)
        self.messages.clear()
        checks = []

        delivered = self.world.private_chat(
            "sender-generation",
            sender["id"],
            sender["account_id"],
            "Destino",
            "hello",
            valid_session=lambda entry: entry[0] == "sender-generation",
            block_reason=lambda *accounts: checks.append(accounts) or 103,
        )

        self.assertFalse(delivered)
        self.assertEqual(checks, [])
        self.assertEqual(
            self.messages,
            [("sender-peer", 349, wire.private_chat_error(101, "Destino"))],
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

    def test_emit_location_excludes_exact_participant_sessions(self):
        self.world.join("same-generation", "participant", self.character(1))
        self.world.join("other-generation", "nearby", self.character(2))
        self.world.join("same-generation", "other-character", self.character(3))
        self.messages.clear()

        self.world.emit_location(
            1134,
            0,
            13753,
            b"marker",
            exclude_sessions={(1, "same-generation")},
        )

        self.assertEqual(
            self.messages,
            [
                ("nearby", 13753, b"marker"),
                ("other-character", 13753, b"marker"),
            ],
        )

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
