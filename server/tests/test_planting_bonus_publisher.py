"""Captured native publication lifecycle: increments, removals and actor fences."""
from contextlib import nullcontext
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server.planting_bonus_publisher import Publisher
from wakfu_server.wire import proto_fields


class Peer:
    pass


def decode(packet):
    opcode, body = packet
    if opcode != 12613:
        raise AssertionError("Expected native effect event")
    fight, action, parent, apply, effect, size = struct.unpack_from(">iiiBih", body)
    if (fight, parent, apply, effect) != (-1, -1, 0, 2000) or len(body) != 19 + size:
        raise AssertionError("Invalid native world application envelope")
    fields = dict(proto_fields(body[19:]))
    profession = dict(proto_fields(fields[66]))[152]
    amount = fields[32]
    if amount >= (1 << 63):
        amount -= 1 << 64
    if fields[24] != 72217 or fields[48] != fields[56]:
        raise AssertionError("Missing retained native definition or actor ownership")
    return fields[48], profession, amount, fields[8], action


class PlantingBonusPublisherTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.connection.return_value = nullcontext(Mock())
        self.publisher = Publisher(self.store)
        self.peer = Peer()
        self.character = {"id": 42, "account_id": 7}
        self.sent = []

    def deliver(self, packets):
        self.assertEqual((13420, struct.pack(">i", -1)), packets[-1])
        self.assertTrue(all(packet[0] == 12613 for packet in packets[:-1]))
        self.sent.extend(decode(packet) for packet in packets[:-1])

    def publish(self, bonuses, peer=None, character=None, deliver=None):
        with patch(
            "wakfu_server.planting_level_policy.account_bonuses", return_value=bonuses
        ):
            return self.publisher.publish(
                peer or self.peer, character or self.character, deliver or self.deliver
            )

    def test_capture_changes_without_stack_and_recreates_only_after_explicit_fence(
        self,
    ):
        self.publish({71: 25, 72: 50})
        self.publish({71: 25, 72: 50})
        self.publish({71: 26, 74: 3})
        self.assertEqual(
            [(42, 71, 25), (42, 72, 50), (42, 71, 1), (42, 72, -50), (42, 74, 3)],
            [row[:3] for row in self.sent],
        )
        self.publisher.reset(self.peer, 42)
        self.publish({71: 26, 74: 3})
        self.assertEqual(
            [(42, 71, 26), (42, 74, 3)], [row[:3] for row in self.sent[-2:]]
        )
        self.assertEqual(len(self.sent), len({row[3] for row in self.sent}))
        self.assertEqual(len(self.sent), len({row[4] for row in self.sent}))

    def test_hero_and_reconnection_have_independent_native_actor_baselines(self):
        self.publish({71: 25})
        self.publish({71: 25}, character={"id": 43, "account_id": 7})
        self.publish({71: 25})
        replacement = Peer()
        self.publish({71: 25}, peer=replacement)
        self.assertEqual(
            [(42, 71, 25), (43, 71, 25), (42, 71, 25)], [row[:3] for row in self.sent]
        )

    def test_failed_batch_does_not_commit_marker(self):
        with self.assertRaises(OSError):
            self.publish({71: 25}, deliver=Mock(side_effect=OSError("socket closed")))
        self.assertEqual({}, self.publisher.baselines[self.peer])

    def test_failure_of_final_native_queue_flush_does_not_commit_marker(self):
        delivered = []

        def fail_last_flush(packets):
            for packet in packets:
                if packet[0] == 13420:
                    self.assertEqual((13420, struct.pack(">i", -1)), packet)
                    raise OSError("final world queue flush write failed")
                delivered.append(decode(packet))

        with self.assertRaises(OSError):
            self.publish({71: 25, 72: 50}, deliver=fail_last_flush)
        self.assertEqual([(42, 71, 25), (42, 72, 50)], [row[:3] for row in delivered])
        self.assertEqual({}, self.publisher.baselines[self.peer])

    def test_retired_peer_is_not_retained_by_publisher(self):
        import gc
        import weakref

        peer = Peer()
        self.publish({71: 25}, peer=peer)
        reference = weakref.ref(peer)
        del peer
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(0, len(self.publisher.baselines))


class NativePlantingDispatcherTests(unittest.TestCase):
    def test_open_profile_skips_policy_and_native_profile_delivers_captured_events(
        self,
    ):
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "send_native_planting_bonus"
        )
        publisher = Mock()
        captured = []
        namespace = {
            "NATIVE_PLANTING_BONUS": False,
            "PLANTING_BONUSES": publisher,
            "send_batch": lambda peer, service, packets: captured.append(
                (peer, service, packets)
            ),
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        peer, actor = Peer(), {"id": 42, "account_id": 7}
        namespace["send_native_planting_bonus"](peer, actor)
        publisher.publish.assert_not_called()
        packet = __import__(
            "wakfu_server.planting_bonus_wire", fromlist=["delta_packet"]
        ).delta_packet(42, 71, 25, uid=100, action_id=200)
        publisher.publish.side_effect = lambda connection, character, deliver: deliver(
            [packet]
        )
        namespace["NATIVE_PLANTING_BONUS"] = True
        namespace["send_native_planting_bonus"](peer, actor)
        self.assertEqual([(peer, "world", [packet])], captured)
        self.assertEqual((42, 71, 25, 100, 200), decode(captured[0][2][0]))


class NativePlantingResetTests(unittest.TestCase):
    def test_known_initialization_and_full_refresh_clear_only_target_actor(self):
        from wakfu_server.planting_bonus_publisher import reset_actor

        entity = b"\x0a" + struct.pack(">q", 42) + bytes(20)
        initialize = struct.pack(">HqI", 1, 999, len(entity)) + entity + bytes(8)
        self.assertEqual(42, reset_actor(12666, initialize))
        self.assertEqual(42, reset_actor(13713, struct.pack(">q", 42) + entity))
        refresh = struct.pack(">qH", 42, len(entity)) + entity
        self.assertEqual(42, reset_actor(15548, refresh))
        other = b"\x0b" + entity[1:]
        self.assertEqual(
            42, reset_actor(15548, struct.pack(">qH", 42, len(other)) + other)
        )

    def test_guild_bags_account_map_and_combat_do_not_invent_recreation(self):
        from wakfu_server.planting_bonus_publisher import reset_actor

        guild = b"\x16" + bytes(48)
        self.assertIsNone(
            reset_actor(15548, struct.pack(">qH", 42, len(guild)) + guild)
        )
        self.assertIsNone(reset_actor(13713, struct.pack(">q", 42) + b"\x23\x00"))
        for opcode in (13873, 13974, 13912, 12873):
            self.assertIsNone(reset_actor(opcode, b""))

    def test_malformed_known_refresh_is_rejected(self):
        from wakfu_server.planting_bonus_publisher import reset_actor

        for opcode, body in (
            (12666, b""),
            (12666, b"\x00\x01"),
            (13713, bytes(8)),
            (15548, bytes(11)),
        ):
            with self.subTest(opcode=opcode), self.assertRaises(ValueError):
                reset_actor(opcode, body)


class NativePlantingDeliveryFenceTests(unittest.TestCase):
    def test_reset_delivery_and_marker_commit_hold_publication_lock(self):
        import threading

        store = Mock()
        store.connection.return_value = nullcontext(Mock())
        publisher, peer = Publisher(store), Peer()
        actor = {"id": 42, "account_id": 7}
        refresh = (13713, struct.pack(">q", 42) + b"\x0a" + bytes(16))
        entered, release, attempted, completed = (threading.Event() for _ in range(4))
        packets = []
        errors = []

        def write():
            entered.set()
            if not release.wait(5):
                raise AssertionError("Reset delivery did not release")

        def reset_worker():
            try:
                publisher.deliver(peer, [refresh], write)
            except BaseException as error:
                errors.append(error)

        def publish_worker():
            attempted.set()
            try:
                publisher.publish(peer, actor, packets.extend)
            except BaseException as error:
                errors.append(error)
            finally:
                completed.set()

        with patch(
            "wakfu_server.planting_level_policy.account_bonuses", return_value={71: 25}
        ):
            publisher.publish(peer, actor, packets.extend)
            packets.clear()
            resetting = threading.Thread(target=reset_worker)
            resetting.start()
            self.assertTrue(entered.wait(5))
            publishing = threading.Thread(target=publish_worker)
            publishing.start()
            self.assertTrue(attempted.wait(5))
            self.assertFalse(completed.wait(0.05))
            release.set()
            resetting.join(5)
            publishing.join(5)
        self.assertFalse(resetting.is_alive() or publishing.is_alive())
        self.assertEqual([], errors)
        self.assertEqual(
            [(42, 71, 25)],
            [decode(packet)[:3] for packet in packets if packet[0] == 12613],
        )


class NativePlantingCombatFenceTests(unittest.TestCase):
    def test_evaluated_combat_snapshots_clear_retained_world_actor_baselines(self):
        from wakfu_server.planting_bonus_publisher import reset_actors
        from wakfu_server.combat_wire import actor_state, bootstrap

        value = dict(
            fight_id=7,
            kind=0,
            bqh=42,
            myo=0,
            myp=0,
            myD=b"",
            myG=b"",
            myI=0,
            myJ=0,
            participants=[
                dict(actor_id=42, myB=0, myn=0, myC=0, myE=b"", myF=b"\x00\x00")
            ],
        )
        self.assertEqual((42,), reset_actors(12847, bootstrap(value)))
        self.assertEqual(
            (42,), reset_actors(13912, actor_state(13912, 7, 42, b"\x00\x00"))
        )
        value["compact"] = True
        self.assertEqual((), reset_actors(12847, bootstrap(value)))
        self.assertEqual((), reset_actors(12873, actor_state(12873, 7, 42, b"")))


class NativePlantingWorldRefreshTests(unittest.TestCase):
    def test_level_and_mount_owned_refreshes_republish_after_snapshot_delivery(self):
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        events = []
        packet = (15548, struct.pack(">qH", 42, 9) + b"\x0a" + struct.pack(">q", 42))
        character = {"id": 42, "account_id": 7}
        store = Mock()
        store.characters.return_value = [character]
        namespace = dict(
            result={"action": "nivel"},
            STORE=store,
            account_id=7,
            character=character,
            OWNED_HERO_TEMPLATE=b"\x0a",
            CHARACTERS=b"",
            connection=Peer(),
            service="world",
            send=lambda *args: events.append("snapshot"),
            send_native_planting_bonus=lambda *args: events.append("bonus"),
        )
        level_node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "result['action'] == 'nivel'"
        )
        with patch("wakfu_server.level_publication.refresh", return_value=[packet]):
            exec(
                compile(
                    ast.Module(body=[level_node], type_ignores=[]), str(source), "exec"
                ),
                namespace,
            )
        self.assertEqual(["snapshot", "bonus"], events)
        events.clear()
        mount = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_mount_equipment"
        )
        mount.decorator_list = []
        world = Mock()
        world.update.side_effect = lambda *args: events.append("snapshot")
        namespace.update(
            fight=None, WORLD=world, generation="lease", PLAYER_TEMPLATE=b"\x0a"
        )
        exec(
            compile(ast.Module(body=[mount], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        with patch(
            "wakfu_server.mount_publication.equipment_changes", return_value=[packet]
        ):
            namespace["publish_mount_equipment"](character, character)
            self.assertEqual(["snapshot", "bonus"], events)
            events.clear()
            namespace["fight"] = object()
            namespace["publish_mount_equipment"](character, character)
            self.assertEqual([], events)
