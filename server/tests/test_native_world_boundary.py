"""Native ownership and Python socket-binding integration regressions."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from wakfu_server.world import World


def actor(identity=1, **values):
    result = dict(
        id=identity,
        account_id=identity,
        name=f"actor-{identity}",
        map_id=527,
        instance_id=0,
        x=0,
        y=0,
        z=0,
        direction=0,
    )
    result.update(values)
    return result


class NativeWorldBoundaryTests(unittest.TestCase):
    def world(self, writer=lambda *_: None):
        world = World(
            lambda row: str(row["id"]).encode(), lambda identity: b"remove", writer
        )
        self.addCleanup(world.native.close)
        return world

    def test_native_position_is_the_only_source_for_world_projections(self):
        world = self.world()
        character = actor()
        world.join("lease", object(), character)
        owner = (1, "lease", 1)
        self.assertFalse(
            any(
                key in world.native.character(owner, domain="world")
                for key in ("id", "account_id", "x", "map_id")
            )
        )
        moved = dict(character, x=7, direction=3)
        world.native.call("world.update", id=1, generation="lease", character=moved)
        self.assertEqual(world.players[1][2]["x"], 7)
        self.assertEqual(world.snapshot()[0]["direction"], 3)
        self.assertEqual(character["x"], 0)
        with self.assertRaises(TypeError):
            world.players[1] = ("lease", object(), character)

    def test_position_metadata_cannot_replace_live_world_domain_fields(self):
        world = self.world()
        character = actor(hp=70, guild_native={"id": 4})
        world.join("lease", object(), character)
        world.native.bind_character(
            (1, "lease", 1), dict(character, hp=1), domain="positions"
        )
        self.assertEqual(world.players[1][2]["hp"], 70)
        self.assertEqual(world.players[1][2]["guild_native"], {"id": 4})

    def test_scope_positions_are_nonblocking_while_another_thread_reserves_scope(self):
        world = self.world()
        world.join("lease", object(), actor())
        episode = world.scope_presence(527, 0)
        entered, release = threading.Event(), threading.Event()

        def reserve():
            with world.scope_barrier(527, 0):
                entered.set()
                self.assertTrue(release.wait(2))

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(reserve)
            self.assertTrue(entered.wait(2))
            try:
                self.assertIsNone(world.try_scope_positions(527, 0, episode))
            finally:
                release.set()
            future.result(2)
        self.assertEqual(world.try_scope_positions(527, 0, episode), ((0, 0, 0),))

    def test_conditional_socket_delivery_checks_location_after_writer_admission(self):
        sent = []
        world = self.world(lambda peer, opcode, body: sent.append((opcode, body)))
        character = actor()

        class ChangeLocation:
            def __enter__(self):
                world.refresh_location("lease", dict(character, x=1))

            def __exit__(self, *_):
                return False

        class Peer:
            pass

        peer = Peer()
        world.join("lease", peer, character)
        peer.write_lock = ChangeLocation()
        sent.clear()
        expected = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        self.assertFalse(
            world.send_to_if_location(1, "lease", expected, 123, b"old", peer=peer)
        )
        self.assertEqual(sent, [])
        self.assertEqual(world.owned_location(1)["x"], 1)

    def test_socket_delivery_does_not_own_world_metadata_or_scope_reservation(self):
        world = None
        observed = []

        def send(*_):
            self.assertFalse(world.lock._is_owned())
            with ThreadPoolExecutor(max_workers=1) as executor:
                observed.append(
                    executor.submit(
                        world.try_scope_positions, 527, 0, world.scope_presence(527, 0)
                    ).result(1)
                )

        world = self.world(send)
        world.join("lease", object(), actor())
        world.emit_location(527, 0, 123, b"update")
        self.assertEqual(observed[-1], ((0, 0, 0),))

    def test_failed_pending_bootstrap_withdraws_announced_actor(self):
        sent = []
        world = self.world(lambda peer, opcode, body: sent.append((peer, opcode, body)))
        world.join("first", "peer-1", actor(1))
        world.join("second", "peer-2", actor(2))
        sent.clear()

        def spawn(character):
            if character["id"] == 2:
                raise ValueError("bootstrap encoding failed")
            return str(character["id"]).encode()

        world.spawn = spawn
        with self.assertRaisesRegex(ValueError, "bootstrap encoding failed"):
            world.join("failed", "peer-3", actor(3))
        self.assertNotIn(3, world.players)
        first = [(opcode, body) for peer, opcode, body in sent if peer == "peer-1"]
        self.assertEqual(first, [(12608, b"3"), (12304, b"remove")])
        self.assertEqual({row["id"] for row in world.ecology_snapshot()}, {1, 2})
