"""Private ranch admission must be authorized before client scene publication."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server.haven_ranch_authority import (
    portal_target,
    biome_target,
    validate_return,
)


class RanchAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(
            id=10, account_id=2, map_id=1134, instance_id=0, x=-9, y=-4, z=-1
        )
        self.bag = HavenBagSession(self.saved)
        self.actor = self.bag.move(self.bag.inside, dict(x=-8, y=5, z=4))
        self.geometry = dict(map_id=9, cells=[[-8, 5, 4], [3, 3, 0]])
        self.source = dict(id=36028, map_id=9, type="RanchEntrance", x=-9, y=5, z=4)
        self.lease_calls = 0
        self.entitled = True
        self.entitlement_calls = 0

    def lease(self):
        self.lease_calls += 1

    def entitlement(self):
        self.entitlement_calls += 1
        if not self.entitled:
            raise ValueError("Missing current Ranch entitlement")

    def request(self, body=None, actor=None, geometry=None):
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[self.source],
        ):
            return portal_target(
                actor or self.actor,
                self.bag,
                struct.pack(">qHH", 36028, 35, 0) if body is None else body,
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
                geometry=geometry or self.geometry,
            )

    def test_installed_owner_choice_and_lease_before_destination(self):
        self.assertEqual(self.request(), dict(biome_id=1, map_id=1440, x=28, y=6, z=4))
        self.assertEqual(self.lease_calls, 1)
        self.assertEqual(self.entitlement_calls, 1)

    def test_source_action_parameter_and_lengths_reject(self):
        for body in (
            b"",
            struct.pack(">qHH", 957, 35, 0),
            struct.pack(">qHH", 36028, 76, 0),
            struct.pack(">qHH", 36028, 35, 1),
            struct.pack(">qHH", 36028, 35, 0) + b"x",
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.request(body)

    def test_current_native_surface_and_range_required(self):
        for actor in (
            {**self.actor, "x": 3, "y": 3, "z": 0},
            {**self.actor, "z": 3},
            {**self.actor, "instance_id": 0},
            {**self.actor, "account_id": 9},
        ):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                self.request(actor=actor)
        with self.assertRaises(ValueError):
            self.request(geometry=dict(map_id=1440, cells=[[-8, 5, 4]]))

    def test_lease_failure_cannot_create_destination_or_session(self):
        def expired():
            raise ValueError("Expired lease")

        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[self.source],
        ):
            with self.assertRaisesRegex(ValueError, "Expired lease"):
                portal_target(
                    self.actor,
                    self.bag,
                    struct.pack(">qHH", 36028, 35, 0),
                    validate_lease=expired,
                    validate_entitlement=self.entitlement,
                    geometry=self.geometry,
                )

    def test_biome_and_return_require_live_child_scene(self):
        target = self.request()
        child = RanchSession(self.bag, self.actor, target, lease=1, now_ms=1000)
        inside = child.inside
        self.assertEqual(
            biome_target(
                inside,
                child,
                struct.pack(">i", 1),
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
            ),
            target,
        )
        validate_return(inside, child, b"\x00", validate_lease=self.lease)
        for body in (b"", b"\x01", b"\x00\x00"):
            with self.assertRaises(ValueError):
                validate_return(inside, child, body, validate_lease=self.lease)
        with self.assertRaises(ValueError):
            biome_target(
                self.actor,
                child,
                struct.pack(">i", 1),
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
            )
        child.leave(inside)
        with self.assertRaises(ValueError):
            validate_return(inside, child, b"\x00", validate_lease=self.lease)

    def test_both_entry_and_switch_recheck_entitlement_but_return_does_not(self):
        target = self.request()
        child = RanchSession(self.bag, self.actor, target, lease=1, now_ms=1000)
        self.entitled = False
        with self.assertRaisesRegex(ValueError, "Missing current Ranch entitlement"):
            self.request()
        with self.assertRaisesRegex(ValueError, "Missing current Ranch entitlement"):
            biome_target(
                child.inside,
                child,
                struct.pack(">i", 1),
                validate_lease=self.lease,
                validate_entitlement=self.entitlement,
            )
        validate_return(child.inside, child, b"\x00", validate_lease=self.lease)
        self.assertTrue(child.owns(child.inside))
