"""Farmergency resets every aptitude allocation without disturbing owned builds."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import restat_item_actions as actions
from wakfu_server.wire import proto_field, proto_fields
from wakfu_server.inventory_items import grant
from wakfu_server import builds, health_policy


class RestatItemWireTests(unittest.TestCase):
    def test_exact_request_and_level_preserving_allocation_removal(self):
        body = struct.pack(">iq", 8399, 123)
        self.assertEqual(actions.action_class(body), "bHx")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 904, 123)))
        with self.assertRaises(ValueError):
            actions.action_class(body + b"\0")
        for level in (20, (1 << 64) - 1):
            blob = proto_field(24, level) + proto_field(
                34, proto_field(8, 1) + proto_field(16, 2)
            )
            self.assertEqual(
                list(proto_fields(actions.cleared_sheet(blob))), [(24, level)]
            )


class RestatItemPostgresTests(PostgresCase):
    def fixture(self, other=False):
        self.store.clock = lambda: 1000
        account = self.store.register(
            "restat-other" if other else "restat-owner", "local-password"
        )["id"]
        character = self.store.create_character(
            account, "Other Restat" if other else "Restat Owner"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=40 WHERE id=%s", (character["id"],))
        character = self.store.character(account, character["id"])
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        item = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=20691,
            quantity=2,
            container=bag["uid"],
            slot=0,
            allowed_references={20691},
        )
        return account, generation, character, item

    def saved_pages(self, account, generation, character):
        for index, level in ((0, (1 << 64) - 1), (1, 20)):
            metadata = b"".join(
                proto_field(tag, value)
                for tag, value in (
                    (8, index),
                    (18, b"Current" if index == 0 else b"Low level"),
                    (24, level),
                    (56, 1),
                    (64, int(index == 0)),
                )
            )
            blobs = dict(
                sheet=metadata,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=proto_field(24, level)
                + proto_field(34, proto_field(8, 1) + proto_field(16, 2)),
            )
            self.store.save_build(account, generation, character["id"], index, blobs)

    def test_all_pages_reset_levels_gear_decks_identity_and_wounds_persist(self):
        account, generation, character, item = self.fixture()
        self.saved_pages(account, generation, character)
        before = self.store.character(account, character["id"])
        with self.store.connection() as db:
            health_policy.apply_damage(db, before, 17, False)
        before = self.store.character(account, character["id"])
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", 8399, item["uid"]),
            in_fight=False,
        )
        after = result["character"]
        self.assertEqual(result["reset_build_indices"], [0, 1])
        self.assertEqual([packet[0] for packet in result["packets"]], [12470, 12103])
        for key in (
            "id",
            "account_id",
            "level",
            "xp",
            "breed",
            "active_build_index",
            "hp_damage",
            "health_dead",
        ):
            if key in before:
                self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["hp_damage"], 17)
        self.assertEqual(after["hp"], max(1, after["max_hp"] - 17))
        for index, previous in before["builds"].items():
            current = after["builds"][index]
            for key in ("sheet", "equipment", "deck"):
                self.assertEqual(current[key], previous[key])
            self.assertEqual(
                current["aptitudes"],
                actions.cleared_sheet(bytes.fromhex(previous["aptitudes"])).hex(),
            )
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(restored["builds"], after["builds"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in restored["inventory_items"]
                if row["uid"] == item["uid"]
            ),
            1,
        )

    def test_foreign_stale_combat_and_invalid_page_roll_back_source_and_pages(self):
        account, generation, character, item = self.fixture()
        self.saved_pages(account, generation, character)
        other, other_generation, other_character, _ = self.fixture(other=True)
        body = struct.pack(">iq", 8399, item["uid"])
        for owner, lease, actor, fight in (
            (other, other_generation, other_character["id"], False),
            (account, "stale", character["id"], False),
            (account, generation, character["id"], True),
        ):
            with self.assertRaises(ValueError):
                actions.use(self.store, owner, lease, actor, body, in_fight=fight)
        with self.store.connection() as db:
            # The invalid later page must also roll back the earlier page's
            # successful allocation removal inside the same transaction.
            db.execute(
                "UPDATE character_builds SET aptitudes=%s WHERE character_id=%s AND build_index=1",
                (proto_field(40, 123), character["id"]),
            )
            before = list(
                db.execute(
                    "SELECT * FROM character_builds WHERE character_id=%s ORDER BY build_index",
                    (character["id"],),
                )
            )
        with self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            after = list(
                db.execute(
                    "SELECT * FROM character_builds WHERE character_id=%s ORDER BY build_index",
                    (character["id"],),
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                2,
            )
        self.assertEqual(after, before)
