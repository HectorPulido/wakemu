import unittest
from wakfu_server.world import World


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.world = World(
            lambda c: ("spawn", c["id"], c["x"]),
            lambda c: ("remove", c),
            lambda p, op, b: self.messages.append((p, op, b)),
        )

    def character(self, id, map_id=1134, instance_id=0, x=0):
        return dict(id=id, map_id=map_id, instance_id=instance_id, x=x)

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
