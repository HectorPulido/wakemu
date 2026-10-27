"""Fresh selected-owner entitlement; never reuse private-scene item snapshots."""
from contextlib import contextmanager
import struct
import unittest
from unittest.mock import patch

from wakfu_server.haven_ranch_authority import (
    require_owned_entitlement,
    validate_return,
)
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession


class RanchEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.actor = dict(
            id=10,
            account_id=2,
            map_id=9,
            instance_id=2,
            x=-8,
            y=5,
            z=4,
            account_is_admin=True,
            inventory_items=[dict(uid=99, reference=32864, quantity=1)],
        )
        self.saved = dict(
            self.actor,
            map_id=1134,
            instance_id=0,
            x=3,
            y=3,
            z=0,
            account_is_admin=False,
            inventory_items=[],
        )
        owner = self

        class Store:
            @contextmanager
            def connection(self):
                yield "owned-transaction"

            def character(self, account_id, character_id, db):
                owner.loads.append((account_id, character_id, db))
                return owner.saved

        self.store = Store()
        self.loads = []
        lease_patch = patch("wakfu_server.inventory_items._lease")
        guard_patch = patch("wakfu_server.environment_interactions._guard")
        self.lease = lease_patch.start()
        self.guard = guard_patch.start()
        self.addCleanup(lease_patch.stop)
        self.addCleanup(guard_patch.stop)

    def check(self):
        require_owned_entitlement(self.store, 2, "generation", self.actor)

    def test_stale_live_item_and_admin_flags_do_not_authorize(self):
        with self.assertRaisesRegex(ValueError, r"Bioma Esmeralda \(32864\)"):
            self.check()
        self.assertEqual(self.loads, [(2, 10, "owned-transaction")])
        self.lease.assert_called_once_with(
            self.store, "owned-transaction", 2, "generation", 10
        )
        self.guard.assert_called_once_with("owned-transaction", 10)

    def test_fresh_owned_quantity_authorizes_without_consumption_or_position_change(
        self,
    ):
        self.saved["inventory_items"] = [dict(uid=1, reference=32864, quantity=1)]
        original = dict(self.actor)
        self.check()
        self.assertEqual(self.actor, original)
        self.assertEqual(self.saved["inventory_items"][0]["quantity"], 1)

    def test_only_fresh_trusted_boolean_administrator_authorizes(self):
        self.saved["account_is_admin"] = True
        self.check()
        for invalid in (None, 1, "true"):
            self.saved["account_is_admin"] = invalid
            with self.assertRaisesRegex(ValueError, "administrator authority"):
                self.check()

    def test_other_owner_and_missing_quantity_authority_rejected(self):
        self.saved["account_id"] = 3
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.check()
        self.saved["account_id"] = 2
        self.saved.pop("inventory_items")
        with self.assertRaisesRegex(ValueError, "complete owned inventory"):
            self.check()

    def test_unrelated_item_and_malformed_owned_quantity_rejected(self):
        self.saved["inventory_items"] = [dict(uid=1, reference=32863, quantity=1)]
        with self.assertRaises(ValueError):
            self.check()
        self.saved["inventory_items"] = [dict(uid=1, reference=32864, quantity=True)]
        with self.assertRaises(ValueError):
            self.check()

    def test_lost_entitlement_does_not_prevent_native_return(self):
        outside = dict(self.actor, map_id=1134, instance_id=0)
        bag = HavenBagSession(outside)
        actor = bag.move(bag.inside, dict(x=-8, y=5, z=4))
        child = RanchSession(
            bag,
            actor,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease=1,
            now_ms=1000,
        )
        with self.assertRaises(ValueError):
            self.check()
        validate_return(child.inside, child, b"\x00", validate_lease=lambda: None)
        self.assertEqual(child.leave(child.inside)["map_id"], 9)

    def test_selected_lease_or_durable_combat_failure_precedes_snapshot(self):
        for mock in (self.lease, self.guard):
            mock.side_effect = ValueError("Authority unavailable")
            with self.assertRaisesRegex(ValueError, "Authority unavailable"):
                self.check()
            self.assertEqual(self.loads, [])
            mock.side_effect = None
