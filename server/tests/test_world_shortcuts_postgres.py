import struct

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant, remove
from wakfu_server.world_shortcuts import apply, owned_collection


def delta(actor, *, removals=(), assignments=()):
    body = bytearray(struct.pack(">qh", actor, len(removals)))
    for position in removals:
        body.extend(
            struct.pack(">i", position[0] << 16 | position[1] << 8 | position[2])
        )
    body.extend(struct.pack(">h", len(assignments)))
    for position, kind, long_value, reference, extra in assignments:
        key = position[0] << 16 | position[1] << 8 | position[2]
        body.extend(struct.pack(">i", key))
        body.extend(struct.pack(">bqii", kind, long_value, reference, extra))
    return bytes(body)


class WorldShortcutPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.inventory_consumables import CATALOG

        self.reference = sorted(CATALOG)[0]
        self.other_reference = sorted(CATALOG)[1]
        self.account = self.store.register("shortcut-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Shortcut Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.base_container = self.character["inventory_containers"][0]["uid"]
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=self.reference,
            quantity=2,
            container=self.base_container,
            slot=0,
            allowed_references=set(CATALOG),
        )

    def apply_delta(self, body, *, account=None, generation=None, character=None):
        return apply(
            self.store,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character is None else character,
            body,
        )

    def shortcut_rows(self, store=None):
        store = store or self.store
        with store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT character_id,bar_number,slot,shortcut_type,long_value,int_value,extra_int "
                    "FROM character_world_shortcuts WHERE character_id=%s ORDER BY bar_number,slot",
                    (self.character["id"],),
                )
            ]

    def test_owned_reference_and_uid_shortcuts_roundtrip_across_reopen(self):
        uid = self.item["uid"]
        body = delta(
            self.character["id"],
            assignments=(
                ((0, 1, 2), 1, self.reference, self.reference, -1),
                ((0, 2, 3), 2, uid, self.reference, -1),
            ),
        )
        saved = self.apply_delta(body)
        self.assertEqual(
            saved["world_shortcuts"],
            [
                {
                    "bar_number": 1,
                    "slot": 2,
                    "shortcut_type": 1,
                    "long_value": self.reference,
                    "int_value": self.reference,
                    "extra_int": -1,
                },
                {
                    "bar_number": 2,
                    "slot": 3,
                    "shortcut_type": 2,
                    "long_value": uid,
                    "int_value": self.reference,
                    "extra_int": -1,
                },
            ],
        )
        reopened = self.reopen()
        loaded = reopened.character(self.account, self.character["id"])
        self.assertEqual(loaded["world_shortcuts"], saved["world_shortcuts"])
        self.assertEqual(len(owned_collection(loaded)), 52)

    def test_invalid_second_assignment_rolls_back_removal_and_first_assignment(self):
        old = ((0, 0, 0), 1, self.reference, self.reference, -1)
        self.apply_delta(delta(self.character["id"], assignments=(old,)))
        bad_uid = self.item["uid"] + 123456
        request = delta(
            self.character["id"],
            removals=((0, 0, 0),),
            assignments=(
                ((0, 0, 1), 1, self.reference, self.reference, -1),
                ((0, 0, 2), 2, bad_uid, self.reference, -1),
            ),
        )
        before = self.shortcut_rows()
        with self.assertRaisesRegex(ValueError, "Unavailable or foreign item shortcut"):
            self.apply_delta(request)
        self.assertEqual(self.shortcut_rows(), before)

    def test_wrong_reference_foreign_uid_and_foreign_or_stale_leases_reject_atomically(
        self,
    ):
        body = delta(
            self.character["id"],
            assignments=(((0, 0, 1), 2, self.item["uid"], self.other_reference, -1),),
        )
        with self.assertRaisesRegex(ValueError, "Unavailable or foreign item shortcut"):
            self.apply_delta(body)
        self.assertEqual(self.shortcut_rows(), [])

        foreign_account = self.store.register("shortcut-foreign", "local-password")[
            "id"
        ]
        foreign_character = self.store.create_character(
            foreign_account, "Foreign Shortcut"
        )
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_character["id"]
        )
        foreign_item = grant(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_character["id"],
            reference=self.reference,
            quantity=1,
            container=foreign_character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={self.reference},
        )
        foreign_uid = delta(
            self.character["id"],
            assignments=(((0, 0, 1), 2, foreign_item["uid"], self.reference, -1),),
        )
        with self.assertRaises(ValueError):
            self.apply_delta(foreign_uid)

        before = self.shortcut_rows()
        with self.assertRaises(ValueError):
            self.apply_delta(
                body,
                account=foreign_account,
                generation=foreign_generation,
                character=self.character["id"],
            )
        stale_generation = self.generation
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.assertRaises(ValueError):
            self.apply_delta(body, generation=stale_generation)
        self.assertEqual(self.shortcut_rows(), before)

    def test_exhausted_reference_shortcut_survives_and_uid_shortcut_is_suppressed(self):
        assignments = (
            ((0, 0, 0), 1, self.reference, self.reference, -1),
            ((0, 0, 1), 2, self.item["uid"], self.reference, -1),
        )
        self.apply_delta(delta(self.character["id"], assignments=assignments))
        remove(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.item["uid"],
            self.item["quantity"],
        )
        reference_replay = delta(self.character["id"], assignments=(assignments[0],))
        self.apply_delta(reference_replay)
        before_stale_uid_replay = self.shortcut_rows()
        with self.assertRaises(ValueError):
            self.apply_delta(delta(self.character["id"], assignments=(assignments[1],)))
        self.assertEqual(self.shortcut_rows(), before_stale_uid_replay)
        saved = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(len(saved["world_shortcuts"]), 2)
        collection = owned_collection(saved)
        self.assertEqual(len(collection), 14 + 2 + 17)
        # One persisted reference assignment remains in bar 0; the now-foreign
        # UID assignment is omitted from the native collection.
        self.assertEqual(struct.unpack_from(">H", collection, 3)[0], 1)
        self.assertEqual(struct.unpack_from(">h", collection, 5)[0], 0)

    def test_replay_same_delta_preserves_inventory_and_mixed_fight_domain(self):
        body = delta(
            self.character["id"],
            assignments=(
                ((0, 0, 1), 1, self.reference, self.reference, -1),
                ((1, 0, 2), 1, self.reference, self.reference, -1),
            ),
        )
        first = self.apply_delta(body)
        inventory_before = first["inventory_items"]
        build_bytes_before = first["builds"]
        rows_before = self.shortcut_rows()
        second = self.apply_delta(body)
        self.assertEqual(second["inventory_items"], inventory_before)
        self.assertEqual(second["builds"], build_bytes_before)
        self.assertEqual(self.shortcut_rows(), rows_before)
        self.assertEqual(len(second["world_shortcuts"]), 1)
