"""Multi-tab chest layout, routing, and provisioning regressions."""
import os
import struct
import unittest
from unittest.mock import patch

import test_haven_chest as fixtures
from postgres_case import PostgresCase
from wakfu_server.haven_chest_layout import compartments, provisioned_capacity, resolve
from wakfu_server.haven_chest_wire import bootstrap, contents, decode_relocate
from wakfu_server.wire import proto_fields


class HavenChestCompartmentWireTests(unittest.TestCase):
    def chest(self, capacity=2000):
        return dict(
            id=fixtures.CID,
            account_id=7,
            capacity=capacity,
            compartment_size=100,
            revision=0,
            items=[],
        )

    def test_provisioned_counts_cover_small_default_and_storage_limit(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WAKFU_HAVEN_CHEST_COMPARTMENTS", None)
            self.assertEqual(provisioned_capacity(), 2000)
        for count, expected in ((3, 300), (20, 2000), (327, 32700)):
            with self.subTest(count=count), patch.dict(
                os.environ, {"WAKFU_HAVEN_CHEST_COMPARTMENTS": str(count)}
            ):
                self.assertEqual(provisioned_capacity(), expected)
        for count in ("0", "328", "invalid"):
            with self.subTest(count=count), patch.dict(
                os.environ, {"WAKFU_HAVEN_CHEST_COMPARTMENTS": count}
            ), self.assertRaises(ValueError):
                provisioned_capacity()

    def test_bootstrap_and_contents_publish_twenty_stable_local_tabs(self):
        chest = self.chest()
        tabs = compartments(chest)
        self.assertEqual(len(tabs), 20)
        self.assertEqual([tab["offset"] for tab in tabs], list(range(0, 2000, 100)))
        self.assertEqual(tabs, compartments(chest))
        self.assertEqual(tabs[0]["id"], fixtures.CID)
        self.assertEqual(len({tab["id"] for tab in tabs}), 20)
        self.assertEqual(resolve(chest, tabs[-1]["id"]), tabs[-1])
        with self.assertRaisesRegex(ValueError, "Foreign chest compartment"):
            resolve(chest, "foreign-compartment")

        opcode, body = bootstrap(chest)
        self.assertEqual(opcode, 318)
        self.assertEqual(struct.unpack_from(">h", body)[0], 20)
        offset, indexes = 2, []
        for _ in range(20):
            (size,) = struct.unpack_from(">I", body, offset)
            offset += 4
            fields = {
                tag >> 3: value
                for tag, value in proto_fields(body[offset : offset + size])
            }
            offset += size
            indexes.append(fields[5])
            self.assertEqual(fields[7], 100)
            self.assertEqual(fields[8], 0)
        self.assertEqual(indexes, list(range(20)))
        self.assertEqual(body[offset:], b"\x01")

        opcode, delta = contents(chest)
        self.assertEqual(opcode, 13929)
        self.assertEqual(struct.unpack_from(">h", delta)[0], 20)

    def test_batch_deposit_routes_local_slot_in_selected_tab(self):
        fixture = fixtures.HavenChestPlannerTests()
        fixture.setUp()
        fixture.chest.update(capacity=2000, compartment_size=100)
        second = compartments(fixture.chest)[19]
        requests = [dict(compartment=second["id"], uid=10, slot=3, quantity=4)]
        inventory, chest = fixture.apply(requests)
        self.assertEqual(inventory[0]["item"]["quantity"], 5)
        self.assertEqual(chest["items"][0]["slot"], 1903)
        self.assertEqual(chest["items"][0]["item"]["quantity"], 4)
        before = (inventory, chest)
        with self.assertRaisesRegex(ValueError, "Foreign chest compartment"):
            fixture.apply([dict(compartment="foreign", uid=10, slot=1, quantity=1)])
        self.assertEqual((inventory, chest), before)

    def test_relocation_codec_and_planner_preserve_uid_across_tabs(self):
        chest = self.chest()
        tabs = compartments(chest)
        destination = tabs[19]["id"].encode("ascii")
        body = (
            struct.pack(">B", len(tabs[0]["id"]))
            + tabs[0]["id"].encode("ascii")
            + struct.pack(">h", 1)
            + struct.pack(">hhb", 2, 4, len(destination))
            + destination
            + struct.pack(">i", 3)
        )
        request = decode_relocate(body)
        self.assertEqual(request[0]["destination_compartment"], tabs[19]["id"])

        chest["items"] = [dict(slot=2, **fixtures.entry(uid=55, quantity=4, slot=2))]
        from wakfu_server.haven_chest import plan_relocate

        relocated = plan_relocate(
            chest,
            request,
            rules={2504: {"maximum": 99}},
            allocate=lambda: 999,
        )
        self.assertEqual(relocated["items"][0]["slot"], 1903)
        self.assertEqual(relocated["items"][0]["item"]["uid"], 55)
        self.assertEqual(relocated["items"][0]["item"]["quantity"], 4)


class HavenChestCapacityGrowthTests(PostgresCase):
    def test_existing_chest_grows_to_provisioned_tabs_once_and_never_shrinks(self):
        from wakfu_server.haven_chest import _ensure

        account_id = self.store.register("chest-growth", "local-password")["id"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_haven_chests(account_id,compartment_id,capacity,revision) "
                "VALUES(%s,%s,100,4)",
                (account_id, fixtures.CID),
            )
        with patch.dict(os.environ, {"WAKFU_HAVEN_CHEST_COMPARTMENTS": "20"}):
            with self.store.connection() as db:
                grown = _ensure(db, account_id)
            self.assertEqual((grown["capacity"], grown["revision"]), (2000, 5))
            with self.store.connection() as db:
                unchanged = _ensure(db, account_id)
            self.assertEqual((unchanged["capacity"], unchanged["revision"]), (2000, 5))
        with patch.dict(os.environ, {"WAKFU_HAVEN_CHEST_COMPARTMENTS": "3"}):
            with self.store.connection() as db:
                smaller_policy = _ensure(db, account_id)
        self.assertEqual(
            (smaller_policy["capacity"], smaller_policy["revision"]), (2000, 5)
        )
