import struct
import unittest
from unittest.mock import patch
from wakfu_server.haven_bag import HavenBagSession

from wakfu_server import haven_ranch as ranch


class RanchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(
            id=10,
            account_id=2,
            map_id=1134,
            instance_id=0,
            x=-9,
            y=-4,
            z=-1,
            name="Owner",
            hp=31,
            haven_bag={"owner_id": 1},
        )
        self.bag = HavenBagSession(self.saved)
        self.origin = self.bag.move(self.bag.inside, {"x": -8, "y": 5, "z": 4})
        self.target = dict(biome_id=2, map_id=1466, x=-8, y=-10, z=7)
        self.session = ranch.RanchSession(
            self.bag, self.origin, self.target, lease="lease1", now_ms=1000
        )

    def test_nested_return_preserves_exterior_and_wounds(self):
        active = self.session.move(self.session.inside, {"x": -7, "y": -10, "z": 7})
        fresh = {**self.saved, "hp": 12, "level": 51}
        active = self.session.refresh(active, fresh)
        self.assertEqual((active["map_id"], active["x"], active["hp"]), (1466, -7, 12))
        returned = self.session.leave(active)
        self.assertEqual(
            (returned["map_id"], returned["x"], returned["hp"]), (9, -8, 12)
        )
        exterior = self.bag.leave(returned)
        self.assertEqual(
            (exterior["map_id"], exterior["x"], exterior["y"], exterior["hp"]),
            (1134, -9, -4, 12),
        )
        self.assertFalse(self.session.owns(active))
        with self.assertRaises(ValueError):
            self.session.leave(active)

    def test_context_uses_account_map_empty_counts_and_authoritative_clock(self):
        self.assertEqual(
            struct.unpack(">qqBiiiq", self.session.context()),
            (2, 1466, 1, 0, 0, 0, 1000),
        )
        self.assertFalse(self.bag.owns(self.session.inside))
        self.session.validate_lease("lease1")
        with self.assertRaises(ValueError):
            self.session.validate_lease("lease2")

    def test_native_cleanup_precedes_ranch_context_and_exit_does_not_reinstall_it(self):
        with patch(
            "wakfu_server.haven_bag.map_transition", return_value=b"native-transition"
        ):
            messages = self.session.entry_messages(b"template", self.session.inside)
            self.assertEqual(
                [message for message, _ in messages],
                [13019, 13256, 13864, 13974, 12318],
            )
            repeated = self.session.entry_messages(
                b"template", self.session.inside, clear_bag_role=False
            )
            self.assertNotIn(13019, [message for message, _ in repeated])
            returned = self.session.leave(self.session.inside)
            messages = ranch.leave_messages(b"template", returned, self.bag)
            self.assertEqual(
                [message for message, _ in messages], [13256, 13307, 13974, 12318]
            )
            self.assertNotIn(13864, [message for message, _ in messages])

    def test_public_guests_keep_host_instance_and_foreign_actors_reject(self):
        visitor = HavenBagSession(
            {**self.saved, "id": 11, "account_id": 3}, owner=self.saved
        )
        child = ranch.RanchSession(
            visitor, visitor.inside, self.target, lease="x", now_ms=1000
        )
        self.assertTrue(child.inside["haven_bag_visitor"])
        self.assertEqual(child.inside["instance_id"], self.bag.bag_instance_id)
        self.assertFalse(visitor.is_owner)
        self.assertEqual(
            struct.unpack(">q", child.context()[:8])[0], self.saved["account_id"]
        )
        for key, value in (
            ("id", 99),
            ("account_id", 99),
            ("map_id", 1470),
            ("instance_id", 99),
        ):
            with self.subTest(key=key):
                self.assertFalse(self.session.owns({**self.session.inside, key: value}))
        with self.assertRaises(ValueError):
            self.session.move(self.session.inside, {"map_id": 1134})
        with self.assertRaises(ValueError):
            self.session.refresh(self.session.inside, {**self.saved, "account_id": 99})

    def test_installed_destination_requires_height_and_native_mapping(self):
        self.assertEqual(
            ranch.destination(35), dict(biome_id=1, map_id=1440, x=28, y=6, z=4)
        )
        with self.assertRaises(ValueError):
            ranch.destination(0)
        valid = {2: dict(map_id=1466, x=-8, y=-10, z=7)}
        self.assertEqual(ranch.destination(0, valid), self.target)
        for choices in (
            {2: dict(map_id=1466, x=-8, y=-10)},
            {2: dict(map_id=9, x=0, y=0, z=0)},
        ):
            with self.assertRaises(ValueError):
                ranch.destination(0, choices)
        with self.assertRaises(ValueError):
            ranch.destination(111, valid)


if __name__ == "__main__":
    unittest.main()
