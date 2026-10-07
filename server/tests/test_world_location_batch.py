import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from wakfu_server.world import World


class LocationBatchTests(unittest.TestCase):
    def character(self, identity, *, map_id=4, instance_id=5):
        return dict(
            id=identity,
            name=str(identity),
            account_id=identity,
            map_id=map_id,
            instance_id=instance_id,
        )

    def world(self, writer, *, failure=None):
        return World(
            lambda character: b"",
            lambda identity: b"",
            lambda *args: None,
            deliver_batch=writer,
            delivery_failure=failure,
        )

    def attach(self, world, identity, generation, peer, **location):
        # Join bootstrap delivery is outside the batch under test.
        world.join(generation, peer, self.character(identity, **location))

    def test_ordered_batch_one_writer_per_location_peer_with_exact_exclusions(self):
        writes = []
        world = self.world(lambda peer, packets: writes.append((peer, tuple(packets))))
        for identity, generation, peer, location in (
            (1, "a", "participant", {}),
            (2, "a", "same-generation", {}),
            (3, "b", "observer", {}),
            (4, "c", "public", {}),
            (5, "d", "other-instance", {"instance_id": 6}),
            (6, "e", "other-map", {"map_id": 7}),
        ):
            self.attach(world, identity, generation, peer, **location)
        packets = ((12608, b"roster"), (13753, b"marker"))
        self.assertEqual(
            2,
            world.emit_location_batch(
                4, 5, iter(packets), exclude_sessions=((1, "a"), (3, "b"))
            ),
        )
        self.assertEqual(writes, [("same-generation", packets), ("public", packets)])
        writes.clear()
        self.assertEqual(
            2, world.emit_location_batch(4, 5, packets, exclude_generation="a")
        )
        self.assertEqual(writes, [("observer", packets), ("public", packets)])

    def test_failure_reports_batch_opcode_and_shuts_down_only_failed_peer(self):
        calls = []

        class Peer:
            def __init__(self, name):
                self.name = name

            def shutdown(self, how):
                calls.append(("shutdown", self.name, how))

        def write(peer, packets):
            calls.append(("write", peer.name, tuple(packets)))
            if peer.name == "broken":
                raise BrokenPipeError(32, "closed")

        world = self.world(
            write,
            failure=lambda peer, opcode, error: calls.append(
                ("failure", peer.name, opcode, error.errno)
            ),
        )
        self.attach(world, 1, "a", Peer("broken"))
        self.attach(world, 2, "b", Peer("good"))
        packets = ((12608, b"roster"), (13753, b"marker"))
        self.assertEqual(1, world.emit_location_batch(4, 5, packets))
        self.assertEqual(
            calls,
            [
                ("write", "broken", packets),
                ("failure", "broken", 12608, 32),
                ("shutdown", "broken", 2),
                ("write", "good", packets),
            ],
        )

    def test_snapshot_captures_old_peer_without_holding_membership_lock(self):
        entered, release = threading.Event(), threading.Event()
        writes = []

        def write(peer, packets):
            writes.append(peer)
            if peer == "first":
                entered.set()
                self.assertTrue(release.wait(2))

        world = self.world(write)
        self.attach(world, 1, "a", "first")
        self.attach(world, 2, "old", "old-peer")
        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(
                world.emit_location_batch, 4, 5, ((12608, b"x"), (13753, b"y"))
            )
            self.assertTrue(entered.wait(2))
            replacement = executor.submit(self.attach, world, 2, "new", "new-peer")
            try:
                replacement.result(0.5)
            finally:
                release.set()
            self.assertEqual(2, future.result(2))
        self.assertEqual(writes, ["first", "old-peer"])
        self.assertEqual(world.players[2][0], "new")

    def test_empty_batch_has_no_writes(self):
        writes = []
        world = self.world(lambda peer, packets: writes.append((peer, packets)))
        self.attach(world, 1, "a", "peer")
        self.assertEqual(0, world.emit_location_batch(4, 5, ()))
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
