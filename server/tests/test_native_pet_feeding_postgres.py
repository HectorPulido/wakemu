"""Original bHX pet-level foods through native opcode12767 ownership."""
import unittest
import uuid
from datetime import datetime, timezone

from postgres_case import PostgresCase
from wakfu_server.mount_feeding import feed
from wakfu_server.mount_feeding_wire import encode_request


class NativePetFeedingPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2035, 5, 6, 12, 0, tzinfo=timezone.utc)
        self.store.clock = lambda: self.now.timestamp()
        self.account = self.store.register(
            "native-pet-" + uuid.uuid4().hex[:12], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Native Pet Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value='false'::jsonb "
                "WHERE name='pet_feeding_daily_limit_enabled'"
            )

    def _item(self, reference, quantity=1):
        with self.store.connection() as db:
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (self.container,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (self.character["id"], reference, quantity, self.container, slot),
            ).fetchone()["uid"]

    def _pet(self, reference):
        uid = self._item(reference)
        with self.store.connection() as db:
            model = db.execute(
                "SELECT model_id,maximum_health FROM native_pet_models WHERE reference=%s",
                (reference,),
            ).fetchone()
            db.execute(
                "INSERT INTO inventory_pets(uid,model_id,health,last_meal_date,last_hungry_date) "
                "VALUES(%s,%s,%s,0,0)",
                (uid, model["model_id"], model["maximum_health"]),
            )
        return uid

    def _feed(self, pet_uid, food_uid, quantity=1, *, in_fight=False, generation=None):
        return feed(
            self.store,
            self.account,
            self.generation if generation is None else generation,
            self.character["id"],
            encode_request(food_uid, pet_uid, quantity),
            in_fight=in_fight,
        )

    def _pet_state(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT xp,revision FROM inventory_pets WHERE uid=%s", (uid,)
            ).fetchone()

    def _quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_all_three_native_food_levels_apply_and_retry_is_bounded(self):
        cases = (
            (12128, 18376, 2, 200),
            (12131, 18431, 1, 2500),
            (12127, 27578, 3, 150),
        )
        for pet_ref, food_ref, quantity, expected_xp in cases:
            with self.subTest(pet=pet_ref, food=food_ref):
                pet_uid = self._pet(pet_ref)
                food_uid = self._item(food_ref, quantity + 1)
                body = encode_request(food_uid, pet_uid, quantity)
                result = self._feed(pet_uid, food_uid, quantity)
                self.assertTrue(result["applied"])
                self.assertFalse(result["replayed"])
                self.assertEqual(expected_xp, result["xp_delta"])
                state = self._pet_state(pet_uid)
                self.assertEqual((expected_xp, 1), (state["xp"], state["revision"]))
                self.assertEqual(1, self._quantity(food_uid))
                self.assertEqual(
                    [12470, 12470, 12471, 13078],
                    [opcode for opcode, _ in result["packets"]],
                )
                replay = self._feed(pet_uid, food_uid, quantity)
                self.assertFalse(replay["applied"])
                self.assertTrue(replay["replayed"])
                self.assertEqual(expected_xp, replay["xp_delta"])
                state = self._pet_state(pet_uid)
                self.assertEqual((expected_xp, 1), (state["xp"], state["revision"]))
                self.assertEqual(1, self._quantity(food_uid))

    def test_native_model_cap_and_ineligible_food_preserve_authoritative_state(self):
        pet_uid = self._pet(12128)
        food_uid = self._item(27578, 3)
        with self.store.connection() as db:
            db.execute("UPDATE inventory_pets SET xp=2450 WHERE uid=%s", (pet_uid,))
        capped = self._feed(pet_uid, food_uid, 3)
        self.assertEqual(50, capped["xp_delta"])
        state = self._pet_state(pet_uid)
        self.assertEqual((2500, 1), (state["xp"], state["revision"]))
        self.assertIsNone(self._quantity(food_uid))

        pet_uid = self._pet(12128)
        unsupported = self._item(20274, 1)
        before = self._pet_state(pet_uid)
        with self.assertRaisesRegex(
            ValueError,
            "(?:not eligible for this native pet model|not an eligible native pet level action)",
        ):
            self._feed(pet_uid, unsupported)
        self.assertEqual(before, self._pet_state(pet_uid))
        self.assertEqual(1, self._quantity(unsupported))
        with self.assertRaisesRegex(ValueError, "during combat"):
            self._feed(pet_uid, unsupported, in_fight=True)
        self.assertEqual(1, self._quantity(unsupported))

    def test_foreign_pet_or_stale_owner_does_not_mutate_food_or_companion(self):
        pet_uid = self._pet(12128)
        food_uid = self._item(18376, 2)
        foreign = self.store.register(
            "other-pet-" + uuid.uuid4().hex[:12], "local-password"
        )["id"]
        other_character = self.store.create_character(foreign, "Foreign Pet")
        other_container = next(
            row["uid"]
            for row in other_character["inventory_containers"]
            if row["kind"] == 0
        )
        with self.store.connection() as db:
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (other_container,),
            ).fetchone()["slot"]
            foreign_pet_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,12128,1,%s,%s) RETURNING uid",
                (other_character["id"], other_container, slot),
            ).fetchone()["uid"]
            db.execute(
                "INSERT INTO inventory_pets(uid,model_id,health,last_meal_date,last_hungry_date) "
                "VALUES(%s,0,20,0,0)",
                (foreign_pet_uid,),
            )
        with self.assertRaises(ValueError):
            self._feed(foreign_pet_uid, food_uid)
        self.assertEqual(1, self._quantity(foreign_pet_uid))
        self.assertEqual(2, self._quantity(food_uid))
        with self.assertRaises(ValueError):
            self._feed(pet_uid, food_uid, generation="stale-generation")
        state = self._pet_state(pet_uid)
        self.assertEqual((0, 0), (state["xp"], state["revision"]))
        self.assertEqual(2, self._quantity(food_uid))

    def test_grant_hydration_and_whole_exchange_preserve_pet_identity_and_progress(
        self,
    ):
        from wakfu_server.inventory_items import grant, load
        from wakfu_server.exchange_transfer import apply, plan

        uid = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=12128,
            quantity=1,
            container=self.container,
            slot=20,
            allowed_references={12128},
        )["uid"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_pets SET xp=150,health=17,name='Companion One',revision=4 WHERE uid=%s",
                (uid,),
            )
            initial = next(
                item for item in load(db, self.character["id"]) if item["uid"] == uid
            )
        self.assertEqual(
            (0, 150, 17, "Companion One", 4, 12240),
            (
                initial["pet"]["model_id"],
                initial["pet"]["xp"],
                initial["pet"]["health"],
                initial["pet"]["name"],
                initial["pet"]["revision"],
                initial["pet"]["equipped_item_ref"],
            ),
        )

        recipient_account = self.store.register(
            "pet-recipient-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        recipient = self.store.create_character(recipient_account, "Pet Recipient")
        with self.store.connection() as db:
            original = [*load(db, self.character["id"]), *load(db, recipient["id"])]
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=ANY(%s)",
                    ([self.character["id"], recipient["id"]],),
                )
            ]
            final, _movements = plan(
                original,
                containers,
                [dict(uid=uid, quantity=1, character_id=self.character["id"])],
                allocate=lambda: 999_999_991,
            )
            apply(db, original, final)
            moved = next(
                item for item in load(db, recipient["id"]) if item["uid"] == uid
            )
            self.assertFalse(
                any(item["uid"] == uid for item in load(db, self.character["id"]))
            )
        self.assertEqual(
            (0, 150, 17, "Companion One", 4, 12240),
            (
                moved["pet"]["model_id"],
                moved["pet"]["xp"],
                moved["pet"]["health"],
                moved["pet"]["name"],
                moved["pet"]["revision"],
                moved["pet"]["equipped_item_ref"],
            ),
        )

        from wakfu_server.inventory_items import grant as grant_item

        with self.assertRaisesRegex(ValueError, "unstacked unit"):
            grant_item(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                reference=12128,
                quantity=2,
                container=self.container,
                slot=21,
                allowed_references={12128},
            )

    def test_equipped_hp_pet_xp_reconfigures_maximum_without_healing_wounds_or_replay(
        self,
    ):
        from wakfu_server.inventory_items import grant
        from wakfu_server.wire import proto_field
        from wakfu_server.health_store import initialize as initialize_health
        from wakfu_server.health_policy import apply_damage

        pet = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=12128,
            quantity=1,
            container=self.container,
            slot=20,
            allowed_references={12128},
        )
        equipment = proto_field(10, proto_field(8, pet["uid"]) + proto_field(16, 22))
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s AND build_index=0",
                (equipment, self.character["id"]),
            )
        full = initialize_health(
            self.store, self.account, self.generation, self.character["id"]
        )
        start_max = full["max_hp"]
        self.assertEqual(start_max, full["hp"])

        food_uid = self._item(18376, 2)
        first = self._feed(pet["uid"], food_uid)
        first_character = self.store.character(self.account, self.character["id"])
        self.assertEqual(start_max + 3, first_character["max_hp"])
        self.assertEqual(first_character["max_hp"], first_character["hp"])
        self.assertEqual(0, first_character["hp_damage"])
        self.assertEqual(
            100,
            next(
                row
                for row in first_character["inventory_items"]
                if row["uid"] == pet["uid"]
            )["pet"]["xp"],
        )
        self.assertEqual(100, first["xp_delta"])

        damage = min(37, first_character["max_hp"] - 1)
        with self.store.connection() as db:
            character = self.store.character(self.account, self.character["id"], db)
            apply_damage(db, character, damage, False)
        wounded = self.store.character(self.account, self.character["id"])
        from datetime import timedelta

        self.now += timedelta(seconds=4)
        second = self._feed(pet["uid"], food_uid)
        after = self.store.character(self.account, self.character["id"])
        self.assertEqual(first_character["max_hp"] + 3, after["max_hp"])
        self.assertEqual(damage, after["hp_damage"])
        self.assertEqual(after["max_hp"] - damage, after["hp"])
        self.assertEqual(wounded["hp_damage"], after["hp_damage"])
        with self.store.connection() as db:
            regen = db.execute(
                "SELECT initial_hp FROM character_regeneration WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()
        self.assertEqual(after["hp"], regen["initial_hp"])
        frozen = (after["hp"], after["max_hp"], after["hp_damage"], second["xp_delta"])
        replay = self._feed(pet["uid"], food_uid)
        replayed = self.store.character(self.account, self.character["id"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(
            frozen[:3], (replayed["hp"], replayed["max_hp"], replayed["hp_damage"])
        )

    def test_ordinary_native_pet_xp_food_uses_key_presence_and_daily_limit(self):
        pet_uid = self._pet(12128)
        food_uid = self._item(
            13346, 2
        )  # YI is true although the raw native flag is false.
        result = self._feed(pet_uid, food_uid)
        self.assertTrue(result["applied"])
        self.assertEqual(
            (50, 0, "xp"),
            (
                result["xp_delta"],
                result["health_delta"],
                result["receipt"]["effect_kind"],
            ),
        )
        self.assertEqual(
            (50, 1), tuple(self._pet_state(pet_uid)[key] for key in ("xp", "revision"))
        )
        self.assertEqual(1, self._quantity(food_uid))
        replay = self._feed(pet_uid, food_uid)
        self.assertTrue(replay["replayed"])
        self.assertEqual(50, self._pet_state(pet_uid)["xp"])

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value='true'::jsonb WHERE name='pet_feeding_daily_limit_enabled'"
            )
        next_food = self._item(2254, 1)
        before = self._pet_state(pet_uid)
        with self.assertRaisesRegex(ValueError, "once per UTC calendar day"):
            self._feed(pet_uid, next_food)
        self.assertEqual(before, self._pet_state(pet_uid))
        self.assertEqual(1, self._quantity(next_food))

        wrong_model_pet = self._pet(
            14335
        )  # Native model 11 excludes model-0 food 2698.
        wrong_food = self._item(2698, 1)
        with self.assertRaisesRegex(
            ValueError, "not eligible for this native pet model"
        ):
            self._feed(wrong_model_pet, wrong_food)
        self.assertEqual(1, self._quantity(wrong_food))

    def test_ordinary_pet_health_food_caps_healing_and_never_grants_xp(self):
        small_pet = self._pet(12128)
        with self.store.connection() as db:
            db.execute("UPDATE inventory_pets SET health=10 WHERE uid=%s", (small_pet,))
        small_food = self._item(12284, 2)
        small = self._feed(small_pet, small_food)
        self.assertEqual(
            (0, 1, "heal"),
            (small["xp_delta"], small["health_delta"], small["receipt"]["effect_kind"]),
        )
        with self.store.connection() as db:
            small_state = db.execute(
                "SELECT xp,health,revision FROM inventory_pets WHERE uid=%s",
                (small_pet,),
            ).fetchone()
        self.assertEqual(
            (0, 11, 1), tuple(small_state[key] for key in ("xp", "health", "revision"))
        )
        self.assertEqual(1, self._quantity(small_food))

        pet_uid = self._pet(12128)
        with self.store.connection() as db:
            db.execute("UPDATE inventory_pets SET health=10 WHERE uid=%s", (pet_uid,))
        food_uid = self._item(18377, 2)
        before = self._pet_state(pet_uid)
        with self.assertRaisesRegex(ValueError, "exceeds missing health"):
            self._feed(pet_uid, food_uid, 2)
        self.assertEqual(before, self._pet_state(pet_uid))
        self.assertEqual(2, self._quantity(food_uid))

        healed = self._feed(pet_uid, food_uid, 1)
        self.assertTrue(healed["applied"])
        self.assertEqual(
            (0, 10, "heal"),
            (
                healed["xp_delta"],
                healed["health_delta"],
                healed["receipt"]["effect_kind"],
            ),
        )
        with self.store.connection() as db:
            state = db.execute(
                "SELECT xp,health,revision FROM inventory_pets WHERE uid=%s", (pet_uid,)
            ).fetchone()
        self.assertEqual(
            (0, 20, 1), tuple(state[key] for key in ("xp", "health", "revision"))
        )
        self.assertEqual(1, self._quantity(food_uid))

        another_food = self._item(18377, 1)
        before = dict(state)
        with self.assertRaisesRegex(ValueError, "no applicable effect"):
            self._feed(pet_uid, another_food)
        with self.store.connection() as db:
            after = db.execute(
                "SELECT xp,health,revision FROM inventory_pets WHERE uid=%s", (pet_uid,)
            ).fetchone()
        self.assertEqual(before, dict(after))
        self.assertEqual(1, self._quantity(another_food))


if __name__ == "__main__":
    unittest.main()
