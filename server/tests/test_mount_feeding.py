from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import unittest
import uuid

import psycopg
from postgres_case import PostgresCase
from wakfu_server import inventory_items, mount_feeding, mount_feeding_wire
from wakfu_server.items.inventory_items import grant
from wakfu_server.wire import proto_fields
from wakfu_server import native_catalog


class MountFeedingTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2033, 4, 5, 12, 0, tzinfo=timezone.utc)
        self.store.clock = lambda: self.now.timestamp()
        self.account = self.store.register(
            "feed_" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Feed Owner")
        # Feed interval/date tests intentionally advance the fake clock by
        # hours; keep this test lease alive for the duration of each case.
        self.generation = self.store.begin_session(self.account, ttl=1_000_000)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = self.character["inventory_containers"][0]["uid"]
        self.pet = self._grant(18682, 1, 0)
        self.food = self._grant(18378, 5, 1)
        self._make_diet_due(self.pet["uid"])

    def _grant(self, reference, quantity, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=quantity,
            container=self.container,
            slot=slot,
            allowed_references={12284, 13358, 18377, 18378, 18682, 18704},
        )

    def _configure(
        self,
        reference,
        kind,
        health_per_item=0,
        reset_hungry_clock=False,
        *,
        model_id=None,
    ):
        if model_id is None:
            with self.store.connection() as db:
                model_id = db.execute(
                    "SELECT model_id FROM inventory_mounts WHERE uid=%s",
                    (self.pet["uid"],),
                ).fetchone()["model_id"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO mount_feeding_food_policy(model_id,item_reference,effect_kind,health_per_item,reset_hungry_clock) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(model_id,item_reference) DO UPDATE SET "
                "effect_kind=excluded.effect_kind,health_per_item=excluded.health_per_item,"
                "reset_hungry_clock=excluded.reset_hungry_clock,"
                "version=mount_feeding_food_policy.version+1",
                (model_id, reference, kind, health_per_item, reset_hungry_clock),
            )

    def _make_diet_due(self, uid):
        with self.store.connection() as db:
            interval = db.execute(
                "SELECT model.meal_min_interval_seconds FROM inventory_mounts m "
                "JOIN mount_models model USING(model_id) WHERE m.uid=%s",
                (uid,),
            ).fetchone()["meal_min_interval_seconds"]
            db.execute(
                "UPDATE inventory_mounts SET last_meal_date=%s WHERE uid=%s",
                (int((self.now - timedelta(seconds=interval)).timestamp()) * 1000, uid),
            )

    def _feed(
        self, *, food=None, pet=None, quantity=1, generation=None, in_fight=False
    ):
        body = mount_feeding_wire.encode_request(
            self.food["uid"] if food is None else food,
            self.pet["uid"] if pet is None else pet,
            quantity,
        )
        return mount_feeding.feed(
            self.store,
            self.account,
            self.generation if generation is None else generation,
            self.character["id"],
            body,
            in_fight=in_fight,
        )

    def _rows(self, *, pet=None, food=None):
        pet_uid = self.pet["uid"] if pet is None else pet
        food_uid = self.food["uid"] if food is None else food
        with self.store.connection() as db:
            mount = db.execute(
                "SELECT * FROM inventory_mounts WHERE uid=%s", (pet_uid,)
            ).fetchone()
            food = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (food_uid,)
            ).fetchone()
            receipts = db.execute(
                "SELECT * FROM mount_feeding_receipts WHERE pet_uid=%s ORDER BY id",
                (pet_uid,),
            ).fetchall()
        return mount, food, receipts

    def test_seeded_food_policy_matches_every_model_native_catalog_entry(self):
        catalog = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol" / "mount-models.json"
            )
        )
        expected = set()
        for model in catalog["models"]:
            food = model["food"]
            heal_refs = {row["reference"] for row in food["healing_food_values"]}
            self.assertEqual(set(food["meal_item_refs"]), heal_refs)
            for row in food["healing_food_values"]:
                expected.add(
                    (
                        model["model_id"],
                        row["reference"],
                        "heal",
                        row["health_per_item"],
                    )
                )
            for reference in food["xp_item_refs"]:
                expected.add((model["model_id"], reference, "xp", 0))
        with self.store.connection() as db:
            actual = {
                (
                    row["model_id"],
                    row["item_reference"],
                    row["effect_kind"],
                    row["health_per_item"],
                )
                for row in db.execute(
                    "SELECT model_id,item_reference,effect_kind,health_per_item "
                    "FROM mount_feeding_food_policy"
                ).fetchall()
            }
        self.assertEqual(actual, expected)

    def test_native_xp_meal_consumes_once_and_refreshes_same_uid(self):
        result = self._feed(quantity=2)
        self.assertTrue(result["applied"])
        self.assertFalse(result["replayed"])
        self.assertEqual(result["xp_delta"], 100)
        self.assertEqual(result["health_delta"], 0)
        self.assertEqual([op for op, _ in result["packets"]], [12470, 12470, 12471])
        self.assertEqual(
            result["packets"][0], (12470, struct.pack(">qh", self.food["uid"], -2))
        )
        self.assertEqual(
            result["packets"][1], (12470, struct.pack(">qh", self.pet["uid"], -1))
        )
        refreshed = result["character"]["inventory_items"]
        pet = next(item for item in refreshed if item["uid"] == self.pet["uid"])
        food = next(item for item in refreshed if item["uid"] == self.food["uid"])
        self.assertEqual((pet["mount"]["xp"], pet["mount"]["revision"]), (100, 1))
        self.assertEqual(food["quantity"], 3)
        _, _, receipts = self._rows()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["snapshot"]["packets"][2]["opcode"], 12471)

        replay = self._feed(quantity=2)
        self.assertFalse(replay["applied"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["packets"], [])
        mount, food, receipts = self._rows()
        self.assertEqual((mount["xp"], mount["revision"]), (100, 1))
        self.assertEqual(food["quantity"], 3)
        self.assertEqual(len(receipts), 1)

        # The body has no nonce. Once the native minimum interval has elapsed,
        # the same body is treated as a new deliberate feeding operation.
        self.now += timedelta(seconds=72000)
        second = self._feed(quantity=2)
        self.assertTrue(second["applied"])
        self.assertEqual(second["xp_delta"], 100)
        mount, food, receipts = self._rows()
        self.assertEqual((mount["xp"], mount["revision"]), (200, 2))
        self.assertEqual(food["quantity"], 1)
        self.assertEqual(len(receipts), 2)

    def test_selected_character_rich_inventory_registry_contains_updated_protopet(self):
        self._configure(18378, "xp")
        result = self._feed()
        opcode, packet = inventory_items.equipment_inventory(result["character"])
        self.assertEqual(opcode, 13078)
        owner, length, flags = struct.unpack_from(">qIB", packet)
        self.assertEqual(
            (owner, flags, len(packet)), (self.character["id"], 0, 13 + length)
        )
        entries = [value for tag, value in proto_fields(packet[13:]) if tag == 10]
        pet_proto = next(
            value
            for value in entries
            if {tag >> 3: field for tag, field in proto_fields(value)}.get(1)
            == self.pet["uid"]
        )
        item_fields = {tag >> 3: value for tag, value in proto_fields(pet_proto)}
        self.assertIn(50, item_fields)
        pet_fields = {tag >> 3: value for tag, value in proto_fields(item_fields[50])}
        self.assertEqual((pet_fields[5], pet_fields[6]), (20, 50))

    def test_full_stack_replay_is_found_after_the_food_row_was_deleted(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=2 WHERE uid=%s",
                (self.food["uid"],),
            )
        result = self._feed(quantity=2)
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s",
                    (self.food["uid"],),
                ).fetchone()
            )
        replay = self._feed(quantity=2)
        self.assertTrue(replay["replayed"])
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["packets"], [])
        mount, food, receipts = self._rows()
        self.assertEqual((mount["xp"], mount["revision"]), (100, 1))
        self.assertIsNone(food)
        self.assertEqual(len(receipts), 1)

    def test_native_xp_gate_is_utc_calendar_day_not_model_interval(self):
        first = self._feed(quantity=1)
        self.assertEqual(first["xp_delta"], 50)

        # Eleven hours later is still the same native UTC date, so XP food
        # remains blocked even though the native client checks a day boundary.
        self.now += timedelta(hours=11)
        before = self._rows()
        with self.assertRaisesRegex(ValueError, "once per UTC calendar day"):
            self._feed(quantity=1)
        self.assertEqual(before, self._rows())

        # Crossing UTC midnight allows another XP meal after only 13 hours,
        # despite the model metadata's 20-hour display interval.
        self.now += timedelta(hours=2)
        second = self._feed(quantity=1)
        self.assertEqual(second["xp_delta"], 50)
        mount, food, receipts = self._rows()
        self.assertEqual((mount["xp"], mount["revision"]), (100, 2))
        self.assertEqual(food["quantity"], 3)
        self.assertEqual(len(receipts), 2)

    def test_native_xp_cap_is_clamped_and_full_mount_rejects_without_consumption(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET xp=2490 WHERE uid=%s", (self.pet["uid"],)
            )
        result = self._feed(quantity=1)
        self.assertEqual(result["xp_delta"], 10)
        self.assertEqual(
            next(
                i
                for i in result["character"]["inventory_items"]
                if i["uid"] == self.pet["uid"]
            )["mount"]["xp"],
            2500,
        )
        self.now += timedelta(seconds=72000)
        before = self._rows()
        with self.assertRaisesRegex(ValueError, "maximum XP"):
            self._feed()
        after = self._rows()
        self.assertEqual(before, after)

    def test_native_health_food_uses_yj_value_and_never_overheals(self):
        food = self._grant(18377, 3, 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=17 WHERE uid=%s", (self.pet["uid"],)
            )
        result = mount_feeding.feed(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mount_feeding_wire.encode_request(food["uid"], self.pet["uid"], 1),
            in_fight=False,
        )
        self.assertEqual((result["health_delta"], result["xp_delta"]), (3, 0))
        pet = next(
            i
            for i in result["character"]["inventory_items"]
            if i["uid"] == self.pet["uid"]
        )
        self.assertEqual(pet["mount"]["health"], 20)
        self.assertEqual(pet["mount"]["xp"], 0)
        self.assertEqual(
            result["packets"][0], (12470, struct.pack(">qh", food["uid"], -1))
        )

    def test_yh_healing_food_can_repeat_without_xp_interval_when_health_is_missing(
        self,
    ):
        food = self._grant(12284, 3, 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=0 WHERE uid=%s", (self.pet["uid"],)
            )
        first = self._feed(food=food["uid"], quantity=1)
        self.assertEqual((first["health_delta"], first["xp_delta"]), (1, 0))
        replay = self._feed(food=food["uid"], quantity=1)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["packets"], [])
        self.now += timedelta(seconds=3)
        second = self._feed(food=food["uid"], quantity=1)
        self.assertEqual((second["health_delta"], second["xp_delta"]), (1, 0))
        mount, remaining, receipts = self._rows(food=food["uid"])
        self.assertEqual((mount["health"], mount["revision"]), (2, 2))
        self.assertEqual(remaining["quantity"], 1)
        self.assertEqual(len(receipts), 2)

    def test_food_policy_does_not_fall_back_across_mount_models(self):
        pet_b = self._grant(18704, 1, 3)
        self._make_diet_due(pet_b["uid"])
        food = self._grant(18378, 2, 2)
        self._configure(18378, "xp", model_id=76)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM mount_feeding_food_policy WHERE model_id=81 AND item_reference=18378"
            )
        before = self._rows(pet=pet_b["uid"], food=food["uid"])
        with self.assertRaisesRegex(ValueError, "no native effect"):
            self._feed(food=food["uid"], pet=pet_b["uid"])
        self.assertEqual(before, self._rows(pet=pet_b["uid"], food=food["uid"]))

    def test_food_policy_is_scoped_by_model_for_same_reference(self):
        pet_b = self._grant(18704, 1, 3)
        food = self._grant(12284, 3, 2)
        self._make_diet_due(pet_b["uid"])
        self._configure(12284, "heal", 1, model_id=76)
        self._configure(12284, "xp", model_id=81)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=0 WHERE uid=%s", (self.pet["uid"],)
            )
            db.execute(
                "UPDATE inventory_mounts SET xp=0,health=20 WHERE uid=%s",
                (pet_b["uid"],),
            )

        heal = mount_feeding.feed(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mount_feeding_wire.encode_request(food["uid"], self.pet["uid"], 1),
            in_fight=False,
        )
        xp = mount_feeding.feed(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mount_feeding_wire.encode_request(food["uid"], pet_b["uid"], 1),
            in_fight=False,
        )
        self.assertEqual((heal["health_delta"], heal["xp_delta"]), (1, 0))
        self.assertEqual((xp["health_delta"], xp["xp_delta"]), (0, 50))

    def test_unknown_food_effect_fails_closed_before_any_mutation(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM mount_feeding_food_policy WHERE model_id=76 AND item_reference=18378"
            )
        before = self._rows()
        with self.assertRaisesRegex(ValueError, "no native effect"):
            self._feed()
        self.assertEqual(before, self._rows())

    def test_foreign_uids_stale_lease_and_combat_reject_atomically(self):
        other_account = self.store.register(
            "other_" + uuid.uuid4().hex[:10], "test-password"
        )["id"]
        other = self.store.create_character(other_account, "Other Owner")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        foreign_food = grant(
            self.store,
            other_account,
            other_generation,
            other["id"],
            reference=12284,
            quantity=2,
            container=other["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={12284},
        )
        before = self._rows()
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            self._feed(food=foreign_food["uid"])
        with self.assertRaisesRegex(ValueError, "combat"):
            self._feed(in_fight=True)
        stale = self.store.begin_session(self.account)
        with self.assertRaisesRegex(ValueError, "invalid|inválidos|session|Sesión"):
            self._feed(generation=self.generation)
        self.assertNotEqual(stale, self.generation)
        self.assertEqual(before, self._rows())

    def test_active_durable_fight_rejects_even_if_caller_says_not_fighting(self):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        before = self._rows()
        with self.assertRaisesRegex(ValueError, "combat"):
            self._feed(in_fight=False)
        self.assertEqual(before, self._rows())

    def test_receipt_failure_rolls_back_food_and_pet_state(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_mount_feed() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'injected feeding receipt failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_mount_feed BEFORE INSERT ON mount_feeding_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_mount_feed()"
            )
        before = self._rows()
        with self.assertRaises(psycopg.Error):
            self._feed(quantity=2)
        self.assertEqual(before, self._rows())


if __name__ == "__main__":
    unittest.main()
