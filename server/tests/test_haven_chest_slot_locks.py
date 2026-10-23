"""Native 12529 slot memory survives physical withdrawal and reload."""
import struct
import uuid

from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from test_inventory_shards import sample_shard_state
from wakfu_server.haven_chest import load, transfer
from wakfu_server.haven_chest_wire import bootstrap
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_shards import save as save_shards


def lock_body(compartment, locked, slots):
    encoded = compartment.encode("ascii")
    return (
        struct.pack(">B", len(encoded))
        + encoded
        + struct.pack(">Bh", int(locked), len(slots))
        + b"".join(struct.pack(">i", slot) for slot in slots)
    )


class HavenChestSlotLockPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account = self.store.register("chest-lock-owner", "local-test-password")[
            "id"
        ]
        self.char = self.store.create_character(self.account, "Chest Lock Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.container = self.char["inventory_containers"][0]["uid"]
        self.chest = load(self.store, self.account, self.generation, self.char["id"])
        self.opening = uuid.uuid4()

    def grant(self, reference, *, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    def call(self, opcode, body, *, generation=None, store=None):
        location = dict(
            self.char,
            map_id=9,
            instance_id=self.char["haven_bag"]["owner_id"],
        )
        return transfer(
            self.store if store is None else store,
            self.account,
            self.generation if generation is None else generation,
            self.char["id"],
            opcode,
            body,
            opening_token=self.opening,
            location=location,
        )

    def test_locked_slot_remembers_reference_across_full_withdraw_reopen_and_refill(
        self,
    ):
        from wakfu_server.haven_chest_layout import compartments

        slot, reference = 7, 13601
        compartment = compartments(self.chest)[0]["id"]
        rich = self.grant(reference, slot=0)
        with self.store.connection() as db:
            save_shards(db, rich["uid"], sample_shard_state())

        deposited = self.call(
            12038, deposit_body(rich["uid"], 1, slot=slot, compartment=compartment)
        )
        self.assertTrue(deposited["applied"])
        self.assertEqual(deposited["chest"]["items"][0]["slot"], slot)
        locked = self.call(12529, lock_body(compartment, True, [slot]))
        memory_uid = locked["chest"]["locks"][0]["remembered_uid"]
        self.assertNotEqual(memory_uid, rich["uid"])
        self.assertEqual(
            locked["chest"]["locks"],
            [dict(slot=slot, reference=reference, remembered_uid=memory_uid)],
        )

        withdrawn = self.call(
            12551,
            withdraw_body(
                self.char["id"],
                reference,
                1,
                self.container,
                slot=slot,
                destination=0,
                compartment=compartment,
            ),
        )
        self.assertEqual(
            withdrawn["character"]["inventory_items"][0]["uid"], rich["uid"]
        )
        self.assertEqual(withdrawn["chest"]["items"], [])
        self.assertEqual(withdrawn["chest"]["locks"][0]["remembered_uid"], memory_uid)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (rich["uid"],),
            ).fetchone()
            self.assertEqual(bytes(row["shard_state"]), sample_shard_state())

        reopened = self.reopen()
        reopened.clock = self.store.clock
        restored = load(reopened, self.account, self.generation, self.char["id"])
        self.assertEqual(restored["locks"], withdrawn["chest"]["locks"])
        opcode, packet = bootstrap(restored)
        self.assertEqual(opcode, 318)
        from wakfu_server.haven_chest_wire import _blob, _scalar

        bookmark = _scalar(1, memory_uid) + _scalar(2, reference) + _scalar(3, 0)
        bookmark_entry = _blob(
            1,
            _blob(1, bookmark) + _scalar(2, slot) + _scalar(3, 1),
        )
        self.assertIn(bookmark_entry, packet)

        other = self.grant(2504, slot=1)
        before_chest = load(self.store, self.account, self.generation, self.char["id"])
        before_inventory = self.store.character(self.account, self.char["id"])[
            "inventory_items"
        ]
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.call(
                12038, deposit_body(other["uid"], 1, slot=slot, compartment=compartment)
            )
        self.assertEqual(
            load(self.store, self.account, self.generation, self.char["id"]),
            before_chest,
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"],
            before_inventory,
        )

        refilled = self.call(
            12038, deposit_body(rich["uid"], 1, slot=slot, compartment=compartment)
        )
        physical = next(
            row for row in refilled["chest"]["items"] if row["slot"] == slot
        )
        self.assertEqual(
            (physical["item"]["uid"], physical["item"]["reference"]),
            (rich["uid"], reference),
        )
        self.assertEqual(
            physical["metadata"]["inventory_item_shards"]["shard_state"],
            sample_shard_state(),
        )
        self.assertEqual(refilled["chest"]["locks"][0]["remembered_uid"], memory_uid)

        unlocked = self.call(12529, lock_body(compartment, False, [slot]))
        self.assertEqual(unlocked["chest"]["locks"], [])
        _, unlocked_packet = bootstrap(unlocked["chest"])
        self.assertNotIn(bookmark_entry, unlocked_packet)

    def test_two_locked_cells_keep_distinct_memory_uids_while_one_item_moves_between_them(
        self,
    ):
        from wakfu_server.haven_chest_layout import compartments
        from wakfu_server.haven_chest_wire import _blob, _scalar

        reference = 13601
        first_slot, second_slot = 11, 12
        compartment = compartments(self.chest)[0]["id"]
        first = self.grant(reference, slot=0)
        second = self.grant(reference, slot=1)
        for item, slot in ((first, first_slot), (second, second_slot)):
            self.call(
                12038, deposit_body(item["uid"], 1, slot=slot, compartment=compartment)
            )
        locked = self.call(
            12529, lock_body(compartment, True, [first_slot, second_slot])
        )
        memory_by_slot = {
            row["slot"]: row["remembered_uid"] for row in locked["chest"]["locks"]
        }
        self.assertEqual(set(memory_by_slot), {first_slot, second_slot})
        self.assertEqual(len(set(memory_by_slot.values())), 2)
        self.assertNotIn(first["uid"], memory_by_slot.values())
        self.assertNotIn(second["uid"], memory_by_slot.values())

        for slot, item, destination in (
            (first_slot, first, 0),
            (second_slot, second, 1),
        ):
            self.call(
                12551,
                withdraw_body(
                    self.char["id"],
                    reference,
                    1,
                    self.container,
                    slot=slot,
                    destination=destination,
                    compartment=compartment,
                ),
            )
        empty = load(self.store, self.account, self.generation, self.char["id"])
        self.assertEqual(empty["items"], [])
        self.assertEqual(
            {row["slot"]: row["remembered_uid"] for row in empty["locks"]},
            memory_by_slot,
        )
        _, empty_packet = bootstrap(empty)
        for slot, memory_uid in memory_by_slot.items():
            marker = _scalar(1, memory_uid) + _scalar(2, reference) + _scalar(3, 0)
            entry = _blob(1, _blob(1, marker) + _scalar(2, slot) + _scalar(3, 1))
            self.assertIn(entry, empty_packet)

        # Re-deposit one physical unit into its remembered cell, then drag it
        # into the other compatible locked cell through the actual 13050 path.
        self.call(
            12038,
            deposit_body(first["uid"], 1, slot=first_slot, compartment=compartment),
        )
        relocated = (
            bytes((len(compartment),))
            + compartment.encode("ascii")
            + struct.pack(">hhhB", 1, first_slot, 1, len(compartment))
            + compartment.encode("ascii")
            + struct.pack(">i", second_slot)
        )
        moved = self.call(13050, relocated)
        self.assertTrue(moved["applied"])
        self.assertEqual(len(moved["chest"]["items"]), 1)
        self.assertEqual(
            (
                moved["chest"]["items"][0]["slot"],
                moved["chest"]["items"][0]["item"]["uid"],
            ),
            (second_slot, first["uid"]),
        )
        self.assertEqual(
            {row["slot"]: row["remembered_uid"] for row in moved["chest"]["locks"]},
            memory_by_slot,
        )
        reopened = self.reopen()
        reopened.clock = self.store.clock
        persisted = load(reopened, self.account, self.generation, self.char["id"])
        self.assertEqual(
            {row["slot"]: row["remembered_uid"] for row in persisted["locks"]},
            memory_by_slot,
        )
        self.assertEqual(len(persisted["items"]), 1)
        self.assertEqual(persisted["items"][0]["item"]["uid"], first["uid"])

    def test_bad_slot_batch_and_stale_lease_leave_locks_and_items_unchanged(self):
        from wakfu_server.haven_chest_layout import compartments

        compartment = compartments(self.chest)[0]["id"]
        item = self.grant(2504, slot=0)
        self.call(12038, deposit_body(item["uid"], 1, slot=4, compartment=compartment))
        before = load(self.store, self.account, self.generation, self.char["id"])
        malformed = lock_body(compartment, True, [4, 4])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.call(12529, malformed)
        self.assertEqual(
            load(self.store, self.account, self.generation, self.char["id"]), before
        )
        with self.assertRaises(ValueError):
            self.call(
                12529,
                lock_body(compartment, True, [4]),
                generation=f"{self.generation}-stale",
            )
        self.assertEqual(
            load(self.store, self.account, self.generation, self.char["id"]), before
        )
