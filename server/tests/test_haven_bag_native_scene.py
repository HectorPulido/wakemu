"""Session and native-type regressions for bag portal publication."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_bag_native_scene import packets
from wakfu_server.haven_ranch import RanchSession, destination


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
                [
                    (13984, struct.pack(">hqh", 1, 36028, len(payload)) + payload),
                    (12344, struct.pack(">qH", 36028, len(payload)) + payload),
                ],
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

    def test_guest_enters_and_leaves_host_ranch_without_changing_owner_portal(self):
        owner = {**self.outside, "haven_bag": {"owner_id": self.outside["id"]}}
        owner_session = HavenBagSession(owner)
        owner_before = dict(owner_session.inside)
        portal_before = packets(owner_session, owner_before)
        self.assertTrue(portal_before)
        guest = {
            **self.outside,
            "id": 21,
            "account_id": 3,
            "haven_bag": {"owner_id": 21},
        }
        visitor_session = HavenBagSession(guest, owner=owner)
        visitor = visitor_session.move(
            visitor_session.inside, {"x": -8, "y": 5, "z": 4}
        )
        ranch = RanchSession(
            visitor_session, visitor, destination(35), lease="visitor", now_ms=1000
        )
        self.assertEqual(ranch.inside["instance_id"], owner["id"])
        self.assertNotEqual(ranch.inside["instance_id"], guest["id"])
        self.assertEqual(ranch.leave(ranch.inside), visitor)
        self.assertEqual(visitor_session.leave(visitor), guest)
        self.assertEqual(owner_session.inside, owner_before)
        self.assertEqual(packets(owner_session, owner_session.inside), portal_before)
        # A reconnect constructs a fresh independent owner session from storage.
        reconnected = HavenBagSession(owner)
        self.assertEqual(packets(reconnected, reconnected.inside), portal_before)

    def test_retained_portal_receives_authoritative_state_after_attachment(self):
        # A wire-level simulation of the qualified cEX/cEY distinction; this
        # does not execute the native renderer or reproduce the live report.
        state = {36028: b"stale-disabled-state"}
        publication = packets(self.session, self.inside)
        for opcode, body in publication:
            if opcode == 13984:
                # Native attachment retains an already registered object.
                self.assertEqual(state[36028], b"stale-disabled-state")
            else:
                self.assertEqual(opcode, 12344)
                identity, size = struct.unpack_from(">qH", body)
                self.assertEqual(len(body), 10 + size)
                state[identity] = body[10:]
        self.assertEqual(
            state[36028], bytes.fromhex("01020000000602000101010001010000000000")
        )
