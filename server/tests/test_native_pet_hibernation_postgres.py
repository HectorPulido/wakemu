"""Native single-use pet hibernation and exact seven-day catch-up regressions."""
from datetime import datetime, timedelta, timezone
import uuid
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.mount_feeding import feed
from wakfu_server.mount_feeding_wire import encode_request
from wakfu_server.pet_hibernation import refresh
from wakfu_server.combat_equipment_initialization import plan as combat_equipment_plan
from wakfu_server.wire import proto_field


SLEEP_MS = 7 * 24 * 60 * 60 * 1000


class NativePetHibernationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2035, 5, 6, 12, 0, tzinfo=timezone.utc)
        self.store.clock = lambda: self.now.timestamp()
        self.account = self.store.register(
            "hibernation-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Sleeping Pet Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _pet(self, reference=12128, slot=10):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    def _food(self, reference, quantity, slot=11):
        with self.store.connection() as db:
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (self.character["id"], reference, quantity, self.container, slot),
            ).fetchone()["uid"]

    def _feed(self, food_uid, pet_uid, quantity=1):
        return feed(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            encode_request(food_uid, pet_uid, quantity),
            in_fight=False,
        )

    def _pet_row(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM inventory_pets WHERE uid=%s", (uid,)
            ).fetchone()

    def _build_blobs(self, index, equipment):
        from wakfu_server.wire import proto_field

        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, index),
                (18, b"Pet sleep sheet"),
                (24, self.character["level"]),
                (56, 0),
            )
        )
        return dict(sheet=sheet, equipment=equipment, deck=b"", aptitudes=b"")

    def _quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_sleep_food_is_single_use_replay_safe_and_blocks_other_food(self):
        pet = self._pet()
        pet_uid = pet["uid"]
        now_ms = int(self.now.timestamp()) * 1000
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_pets SET xp=50,health=8,last_meal_date=%s,last_hungry_date=0 WHERE uid=%s",
                (now_ms - 30_000, pet_uid),
            )
        sleep_food = self._food(12228, 2)
        before = self._pet_row(pet_uid)
        with self.assertRaisesRegex(ValueError, "exactly one food unit"):
            self._feed(sleep_food, pet_uid, 2)
        self.assertEqual(before, self._pet_row(pet_uid))
        self.assertEqual(2, self._quantity(sleep_food))

        result = self._feed(sleep_food, pet_uid)
        self.assertTrue(result["applied"])
        self.assertFalse(result["replayed"])
        self.assertEqual((0, 0), (result["xp_delta"], result["health_delta"]))
        self.assertEqual(now_ms + SLEEP_MS, result["next_deadline_ms"])
        self.assertEqual(1, self._quantity(sleep_food))
        sleeping = self._pet_row(pet_uid)
        self.assertEqual(
            (12228, now_ms, 50, 8, before["revision"] + 1),
            (
                sleeping["sleep_item_ref"],
                sleeping["sleep_date"],
                sleeping["xp"],
                sleeping["health"],
                sleeping["revision"],
            ),
        )
        self.assertEqual(now_ms - 30_000, sleeping["last_meal_date"])
        self.assertEqual(0, sleeping["last_hungry_date"])

        retry = self._feed(sleep_food, pet_uid)
        self.assertFalse(retry["applied"])
        self.assertTrue(retry["replayed"])
        self.assertEqual(sleeping["revision"], self._pet_row(pet_uid)["revision"])
        self.assertEqual(1, self._quantity(sleep_food))

        ordinary_food = self._food(18376, 1, slot=12)
        with self.assertRaisesRegex(ValueError, "sleeping pet"):
            self._feed(ordinary_food, pet_uid)
        self.assertEqual(1, self._quantity(ordinary_food))

        unsupported_pet = self._pet(
            reference=32245, slot=13
        )  # model 260 has no native sleep-food row
        unsupported_food = self._food(12228, 1, slot=14)
        with self.assertRaisesRegex(
            ValueError, "not eligible for this native pet model"
        ):
            self._feed(unsupported_food, unsupported_pet["uid"])
        self.assertEqual(1, self._quantity(unsupported_food))

    def test_read_projection_is_read_only_and_refresh_wakes_at_exact_boundary(self):
        pet = self._pet()
        pet_uid = pet["uid"]
        started_ms = int(self.now.timestamp()) * 1000
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_pets SET last_meal_date=%s,last_hungry_date=0 WHERE uid=%s",
                (started_ms - 120_000, pet_uid),
            )
        sleep_food = self._food(12228, 1)
        started = self._feed(sleep_food, pet_uid)
        deadline = started["next_deadline_ms"]
        original = self._pet_row(pet_uid)
        self.assertTrue(
            self.store.heartbeat(self.account, self.generation, ttl=10 * 24 * 60 * 60)
        )

        self.now = datetime.fromtimestamp((deadline - 1) / 1000, timezone.utc)
        before = refresh(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertFalse(before["changed"])
        self.assertEqual(deadline, before["next_deadline_ms"])
        unchanged = self._pet_row(pet_uid)
        self.assertEqual(
            (original["sleep_date"], original["revision"], original["last_meal_date"]),
            (
                unchanged["sleep_date"],
                unchanged["revision"],
                unchanged["last_meal_date"],
            ),
        )

        self.now = datetime.fromtimestamp(deadline / 1000, timezone.utc)
        with self.store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            projected = self.store.character(self.account, self.character["id"], db)
            projected_pet = next(
                row["pet"]
                for row in projected["inventory_items"]
                if row["uid"] == pet_uid
            )
            self.assertEqual(
                (0, 0), (projected_pet["sleep_item_ref"], projected_pet["sleep_date"])
            )
            self.assertEqual(
                original["last_meal_date"] + SLEEP_MS, projected_pet["last_meal_date"]
            )
            self.assertEqual(0, projected_pet["last_hungry_date"])
            self.assertTrue(projected["pet_hibernation_projection"])
            stored = db.execute(
                "SELECT * FROM inventory_pets WHERE uid=%s", (pet_uid,)
            ).fetchone()
            self.assertEqual(
                (
                    12228,
                    original["sleep_date"],
                    original["revision"],
                    original["last_meal_date"],
                ),
                (
                    stored["sleep_item_ref"],
                    stored["sleep_date"],
                    stored["revision"],
                    stored["last_meal_date"],
                ),
            )

        woke = refresh(self.store, self.account, self.generation, self.character["id"])
        self.assertTrue(woke["changed"])
        self.assertEqual(
            (pet_uid,),
            tuple(
                row["uid"]
                for row in woke["character"]["inventory_items"]
                if row["uid"] == pet_uid
            ),
        )
        persisted = self._pet_row(pet_uid)
        self.assertEqual(
            (0, 0, original["revision"] + 1, original["last_meal_date"] + SLEEP_MS, 0),
            (
                persisted["sleep_item_ref"],
                persisted["sleep_date"],
                persisted["revision"],
                persisted["last_meal_date"],
                persisted["last_hungry_date"],
            ),
        )
        self.assertIsNone(woke["next_deadline_ms"])
        repeated = refresh(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertFalse(repeated["changed"])
        self.assertEqual(persisted["revision"], self._pet_row(pet_uid)["revision"])

    def test_equipped_pet_sleep_preserves_wounds_and_blocks_new_equip_until_wake(self):
        from wakfu_server.wire import proto_field
        from wakfu_server.health_policy import apply_damage

        pet = self._pet()
        pet_uid = pet["uid"]
        empty = self._build_blobs(0, b"")
        # Build0 is initialized below, then build1 keeps the same pet equip as a
        # saved alternate. This lets us test removal is legal while reactivation
        # of the hibernating saved sheet is rejected.
        self.store.save_build(
            self.account, self.generation, self.character["id"], 0, empty
        )
        equipment = proto_field(10, proto_field(8, pet_uid) + proto_field(16, 22))
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            1,
            self._build_blobs(1, equipment),
        )
        selected = self.store.activate_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        self.assertIn(pet_uid, [row["uid"] for row in selected["inventory_items"]])
        from wakfu_server.health_store import initialize as initialize_health

        full = initialize_health(
            self.store, self.account, self.generation, self.character["id"]
        )
        start_max = full["max_hp"]
        from wakfu_server.health import maximum

        self.assertGreater(start_max, maximum(full["breed"], full["level"]))
        damage = min(37, start_max - 1)
        with self.store.connection() as db:
            apply_damage(
                db,
                self.store.character(self.account, self.character["id"], db),
                damage,
                False,
            )
        sleep_food = self._food(12228, 1)
        self._feed(sleep_food, pet_uid)
        sleeping = self.store.character(self.account, self.character["id"])
        self.assertLess(sleeping["max_hp"], start_max)
        self.assertEqual(damage, sleeping["hp_damage"])
        self.assertEqual(sleeping["max_hp"] - damage, sleeping["hp"])
        self.assertEqual(
            pet_uid,
            next(
                row["uid"]
                for row in sleeping["inventory_items"]
                if row["uid"] == pet_uid
            ),
        )

        # Moving to a sheet without the pet is allowed; the old saved sheet is
        # retained, while new equipment and activation of that sleeping pet fail.
        self.store.activate_build(
            self.account, self.generation, self.character["id"], 0, in_fight=False
        )
        with self.assertRaisesRegex(ValueError, "sleeping native pet"):
            self.store.activate_build(
                self.account, self.generation, self.character["id"], 1, in_fight=False
            )
        with self.assertRaisesRegex(ValueError, "sleeping native pet"):
            self.store.save_build(
                self.account,
                self.generation,
                self.character["id"],
                0,
                self._build_blobs(0, equipment),
            )
        still_saved = self.store.character(self.account, self.character["id"])
        self.assertEqual(equipment.hex(), still_saved["builds"][1]["equipment"])

        deadline = self._pet_row(pet_uid)["sleep_date"] + SLEEP_MS
        self.assertTrue(
            self.store.heartbeat(self.account, self.generation, ttl=10 * 24 * 60 * 60)
        )
        self.now = datetime.fromtimestamp(deadline / 1000, timezone.utc)
        projected = self.store.character(self.account, self.character["id"])
        from wakfu_server.equipment_stats import effective_character

        before_refresh = effective_character(dict(projected, active_build_index=1))
        self.assertGreater(before_refresh["max_hp"], sleeping["max_hp"])
        self.assertEqual(before_refresh["max_hp"] - damage, before_refresh["hp"])
        self.assertEqual(damage, before_refresh["hp_damage"])
        woke = refresh(self.store, self.account, self.generation, self.character["id"])
        self.assertTrue(woke["changed"])
        self.assertEqual(damage, woke["character"]["hp_damage"])
        self.assertEqual(woke["character"]["max_hp"] - damage, woke["character"]["hp"])
        active_again = self.store.activate_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        self.assertEqual(damage, active_again["hp_damage"])
        self.assertEqual(start_max, active_again["max_hp"])
        self.assertEqual(start_max - damage, active_again["hp"])


class SleepingPetCombatSourceTests(unittest.TestCase):
    def test_sleeping_equipped_pet_is_skipped_before_passive_root_execution(self):
        # Load the statistics reducer before patching its sheet validator so
        # the mocked planner seam cannot leak into its module-level alias.
        from wakfu_server import equipment_stats  # noqa: F401

        uid = 123456
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, 0),
                (18, b"Sleep"),
                (24, 1),
                (56, 0),
            )
        )
        character = {
            "id": 1,
            "breed": 15,
            "level": 1,
            "active_build_index": 0,
            "builds": {0: {"sheet": sheet.hex(), "equipment": "aa"}},
            "inventory_items": [
                {
                    "uid": uid,
                    "reference": 12128,
                    "quantity": 1,
                    "pet": {
                        "model_id": 0,
                        "health": 20,
                        "sleep_item_ref": 12228,
                        "sleep_date": 1000,
                        "sleep_duration_ms": SLEEP_MS,
                    },
                }
            ],
        }
        with patch(
            "wakfu_server.equipment.validate_sheet",
            return_value=[{"uid": uid, "slot": 22}],
        ), patch(
            "wakfu_server.combat_equipment_initialization.copied_equipment_plan"
        ) as copied:
            result = combat_equipment_plan(
                character, catalog={}, templates={}, ordinary_only=True
            )
        self.assertEqual((), result)
        copied.assert_not_called()


if __name__ == "__main__":
    unittest.main()
