"""Real owned transactions distinguish two units of the same mount template."""
from datetime import datetime, timedelta, timezone
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import (
    inventory_items,
    inventory_actions,
    mount_feeding,
    mount_feeding_wire,
    wire,
    builds,
)


class MountSameReferenceIsolationTests(PostgresCase):
    def test_feed_one_unit_protect_inactive_build_and_destroy_only_other_unit(self):
        now = datetime(2033, 4, 5, 12, 0, tzinfo=timezone.utc)
        self.store.clock = lambda: now.timestamp()
        account = self.store.register("same-mount-owner", "local-password")["id"]
        character = self.store.create_character(account, "Same Mount Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        container = character["inventory_containers"][0]["uid"]

        def grant(reference, quantity, slot):
            return inventory_items.grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=reference,
                quantity=quantity,
                container=container,
                slot=slot,
                allowed_references={18682, 18378},
            )

        a, b, food = grant(18682, 1, 0), grant(18682, 1, 1), grant(18378, 5, 2)
        self.assertNotEqual(a["uid"], b["uid"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=50 WHERE id=%s", (character["id"],))
            interval = db.execute(
                "SELECT meal_min_interval_seconds FROM mount_models WHERE model_id=76"
            ).fetchone()["meal_min_interval_seconds"]
            db.execute(
                "UPDATE inventory_mounts SET last_meal_date=%s WHERE uid=%s",
                (int((now - timedelta(seconds=interval)).timestamp()) * 1000, a["uid"]),
            )

        def build(index, uid=None):
            sheet = b"".join(
                wire.proto_field(tag, value)
                for tag, value in (
                    (8, index),
                    (18, f"Mount {index}".encode()),
                    (24, 50),
                    (56, 0),
                )
            )
            equipment = (
                wire.proto_field(
                    10, wire.proto_field(8, uid) + wire.proto_field(16, 24)
                )
                if uid
                else builds.EMPTY_EQUIPMENT
            )
            return dict(sheet=sheet, equipment=equipment, deck=b"", aptitudes=b"")

        self.store.save_build(account, generation, character["id"], 0, build(0))
        self.store.save_build(
            account, generation, character["id"], 1, build(1, b["uid"])
        )
        self.store.activate_build(
            account, generation, character["id"], 0, in_fight=False
        )
        result = mount_feeding.feed(
            self.store,
            account,
            generation,
            character["id"],
            mount_feeding_wire.encode_request(food["uid"], a["uid"], 2),
            in_fight=False,
        )

        def items(store):
            return {
                item["uid"]: item
                for item in store.character(account, character["id"])["inventory_items"]
            }

        after_feed = items(self.store)
        self.assertEqual(
            (100, 0, 3),
            (
                after_feed[a["uid"]]["mount"]["xp"],
                after_feed[b["uid"]]["mount"]["xp"],
                after_feed[food["uid"]]["quantity"],
            ),
        )
        self.assertEqual(result["xp_delta"], 100)
        with self.assertRaisesRegex(ValueError, "Desequip"):
            inventory_actions.destroy(
                self.store,
                account,
                generation,
                character["id"],
                struct.pack(">q", b["uid"]),
            )
        self.assertEqual(after_feed, items(self.store))
        self.store.save_build(account, generation, character["id"], 1, build(1))
        deleted = inventory_actions.destroy(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">q", b["uid"]),
        )
        self.assertEqual(
            deleted["packets"], [(12470, struct.pack(">qh", b["uid"], -1))]
        )
        persisted = items(self.reopen())
        self.assertEqual(set(persisted), {a["uid"], food["uid"]})
        self.assertEqual(
            (100, 1, 3),
            (
                persisted[a["uid"]]["mount"]["xp"],
                persisted[a["uid"]]["mount"]["revision"],
                persisted[food["uid"]]["quantity"],
            ),
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_mounts WHERE uid=%s", (b["uid"],)
                ).fetchone()
            )
            receipts = db.execute(
                "SELECT pet_uid FROM mount_feeding_receipts WHERE character_id=%s",
                (character["id"],),
            ).fetchall()
        self.assertEqual([a["uid"]], [row["pet_uid"] for row in receipts])


if __name__ == "__main__":
    unittest.main()
