"""Session and native-type regressions for bag portal publication."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_bag_native_scene import packets


class HavenBagNativeSceneTests(unittest.TestCase):
    def setUp(self):
        self.outside = dict(
            id=10, account_id=2, map_id=1134, instance_id=0, x=-9, y=-4, z=-1
        )
        self.session = HavenBagSession(self.outside)
        self.inside = dict(self.session.inside)

    def test_native_portal_is_published_without_unrelated_bag_objects(self):
        payload = bytes.fromhex("01020000000602000101010001010000000000")
        body = struct.pack(">hqh", 2, 36028, len(payload)) + payload
        body += struct.pack(">qh", 13261, 1) + b"x"
        definitions = [
            dict(id=36028, type="RanchEntrance"),
            dict(id=13261, type="AccountChest"),
        ]
        with patch(
            "wakfu_server.haven_bag_native_scene.world_static.objects",
            return_value=definitions,
        ), patch(
            "wakfu_server.haven_bag_native_scene.world_static.snapshots",
            return_value=[body],
        ):
            self.assertEqual(
                packets(self.session, self.inside),
                [(13984, struct.pack(">hqh", 1, 36028, len(payload)) + payload)],
            )

    def test_foreign_actor_account_or_instance_cannot_publish_portal(self):
        for field, value in (
            ("id", 11),
            ("account_id", 3),
            ("instance_id", 0),
            ("map_id", 1134),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                packets(self.session, {**self.inside, field: value})
        with self.assertRaises(ValueError):
            packets(None, self.inside)

    def test_guest_session_keeps_original_native_portal_state(self):
        guest = HavenBagSession(self.outside, owner=dict(id=20, account_id=3))
        expected = packets(self.session, self.inside)
        self.assertEqual(packets(guest, guest.inside), expected)
        self.assertEqual(guest.leave(guest.inside), self.outside)
        self.assertFalse(guest.is_owner)
