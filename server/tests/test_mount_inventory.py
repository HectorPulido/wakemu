from datetime import datetime, timezone
import uuid
import unittest

import psycopg
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import mount_codec, mount_inventory, mount_state
from wakfu_server.inventory_items import grant


class MountInventoryTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.first_time = datetime(2033, 4, 5, 6, 7, 8, tzinfo=timezone.utc)
        self.store.clock = lambda: self.first_time.timestamp()
        self.account = self.store.register(
            "mount_" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Mount Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = self.character["inventory_containers"][0]["uid"]
        with self.store.connection() as db:
            models = db.execute(
                "SELECT * FROM mount_models ORDER BY model_id"
            ).fetchall()
        self.assertEqual(len(models), 40)
        self.assertIn(
            (
                76,
                18682,
                20,
                50,
                50,
                6,
                200,
                24,
                [12284, 13358, 18377],
                50,
                72000,
                259200,
            ),
            [tuple(row.values()) for row in models],
        )

    def _grant(self, *, reference=18682, quantity=1, character=None, slot=0):
        character = character or self.character
        return grant(
            self.store,
            self.account,
            self.generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=character["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={18682, 18704, 18705, 18706, 99999},
        )

    @staticmethod
    def _build(index, level, uid=None):
        from wakfu_server import wire

        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in (
                (8, index),
                (18, f"Mount {index}".encode()),
                (24, level),
                (56, 0),
            )
        )
        equipment = (
            wire.proto_field(10, wire.proto_field(8, uid) + wire.proto_field(16, 24))
            if uid is not None
            else b""
        )
        return {
            "sheet": sheet,
            "equipment": equipment,
            "deck": b"",
            "aptitudes": b"",
        }

    def _equipped_mount(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=35 WHERE id=%s",
                (self.character["id"],),
            )
        item = self._grant()
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            0,
            self._build(0, 35, item["uid"]),
        )
        return item, self.store.character(self.account, self.character["id"])

    def test_verified_model_initializes_owned_unit_once_and_preserves_progress(self):
        item = self._grant()
        uid = item["uid"]
        first_time = self.first_time.replace(microsecond=999999)
        later_time = datetime(2034, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
        initial = item["mount"]
        self.assertEqual(initial["model_id"], 76)
        self.assertEqual(initial["definition_id"], 76)
        self.assertEqual(initial["health"], 20)
        expected_ms = int(first_time.timestamp()) * 1000
        self.assertEqual(initial["last_meal_date"], expected_ms)
        self.assertEqual(initial["last_hungry_date"], expected_ms)

        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET name=%s,xp=%s,health=%s WHERE uid=%s",
                ("Valiente", 375, 7, uid),
            )
        with self.store.connection() as db:
            repeated = mount_inventory.initialize(
                db, uid, self.character["id"], later_time
            )
        self.assertEqual(
            (repeated["name"], repeated["xp"], repeated["health"]),
            ("Valiente", 375, 7),
        )
        self.assertEqual(repeated["last_meal_date"], expected_ms)
        self.assertEqual(repeated["last_hungry_date"], expected_ms)

    def test_state_mutation_rolls_back_when_outer_transaction_fails(self):
        item = self._grant()
        original_health = item["mount"]["health"]
        with self.assertRaisesRegex(RuntimeError, "abort grant"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_mounts SET health=health-1 WHERE uid=%s",
                    (item["uid"],),
                )
                raise RuntimeError("abort grant")
        with self.store.connection() as db:
            restored = db.execute(
                "SELECT health FROM inventory_mounts WHERE uid=%s", (item["uid"],)
            ).fetchone()
        self.assertEqual(restored["health"], original_health)

    def test_database_insert_failure_leaves_no_partial_mount_state(self):
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_mount_insert() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected mount insert failure'; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_mount_insert BEFORE INSERT ON inventory_mounts "
                "FOR EACH ROW EXECUTE FUNCTION reject_mount_insert()"
            )
        with self.assertRaises(psycopg.Error):
            self._grant()
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_mounts m JOIN inventory_items i USING(uid) "
                    "WHERE i.character_id=%s AND i.reference=18682",
                    (self.character["id"],),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE character_id=%s AND reference=18682",
                    (self.character["id"],),
                ).fetchone()
            )

    def test_foreign_stacked_nonmodel_and_autocommit_units_are_rejected(self):
        with self.store.connection() as db:
            stacked = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,18682,2,%s,0) RETURNING *",
                (self.character["id"], self.container),
            ).fetchone()
            own = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,18682,1,%s,2) RETURNING *",
                (self.character["id"], self.container),
            ).fetchone()
            sequence_before = db.execute(
                "SELECT last_value,is_called FROM inventory_uid"
            ).fetchone()
        with self.assertRaises(ValueError):
            self._grant(quantity=2, slot=3)
        with self.store.connection() as db:
            sequence_after = db.execute(
                "SELECT last_value,is_called FROM inventory_uid"
            ).fetchone()
        self.assertEqual(sequence_after, sequence_before)
        nonmodel = self._grant(reference=99999, slot=1)
        foreign_account = self.store.register(
            "foreign_mount_" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        foreign_character = self.store.create_character(
            foreign_account, "Other mount owner"
        )
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_character["id"]
        )
        foreign = grant(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_character["id"],
            reference=18682,
            quantity=1,
            container=foreign_character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={18682},
        )
        now = datetime(2033, 1, 1, tzinfo=timezone.utc)
        with self.store.connection() as db:
            for uid in (stacked["uid"], nonmodel["uid"], foreign["uid"]):
                with self.subTest(uid=uid), self.assertRaises(ValueError):
                    mount_inventory.initialize(db, uid, self.character["id"], now)
        with self.store.database.pool.connection() as db:
            db.autocommit = True
            with self.assertRaises(ValueError):
                mount_inventory.initialize(db, own["uid"], self.character["id"], now)

    def test_database_triggers_lock_mount_identity_and_bound_health(self):
        item = self._grant()
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_items SET quantity=2 WHERE uid=%s",
                    (item["uid"],),
                )
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_items SET reference=18704 WHERE uid=%s",
                    (item["uid"],),
                )
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_mounts SET health=21 WHERE uid=%s",
                    (item["uid"],),
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=7 WHERE uid=%s",
                (item["uid"],),
            )
            row = db.execute(
                "SELECT i.reference,i.quantity,m.health FROM inventory_items i "
                "JOIN inventory_mounts m USING(uid) WHERE i.uid=%s",
                (item["uid"],),
            ).fetchone()
        self.assertEqual(dict(row), {"reference": 18682, "quantity": 1, "health": 7})

    def test_hydrate_queries_only_owned_uids_and_does_not_synthesize_missing_state(
        self,
    ):
        mounted = self._grant()
        plain = self._grant(reference=99999, slot=1)
        now = datetime(2033, 1, 1, tzinfo=timezone.utc)
        with self.store.connection() as db:
            mount_inventory.initialize(db, mounted["uid"], self.character["id"], now)
        items = [mounted, plain]

        class CountingConnection:
            def __init__(self, connection):
                self.connection = connection
                self.sql = []

            def execute(self, sql, params=None):
                self.sql.append(sql)
                return self.connection.execute(sql, params)

        with self.store.connection() as db:
            counted = CountingConnection(db)
            hydrated = mount_inventory.hydrate(counted, items)
        self.assertEqual(len(counted.sql), 1)
        self.assertIn("uid=ANY(%s)", counted.sql[0])
        self.assertEqual(hydrated[0]["mount"]["definition_id"], 76)
        self.assertNotIn("mount", hydrated[1])
        self.assertEqual(hydrated[1]["uid"], plain["uid"])

    def test_inventory_load_persists_mount_protobuf_across_reopen(self):
        from wakfu_server import wire
        from wakfu_server import inventory_items
        from wakfu_server.wire import proto_fields

        item = self._grant()
        with self.store.connection() as db:
            state = mount_inventory.initialize(
                db,
                item["uid"],
                self.character["id"],
                datetime(2033, 1, 1, tzinfo=timezone.utc),
            )
            db.execute(
                "UPDATE inventory_mounts SET name=%s,xp=%s,health=%s WHERE uid=%s",
                ("Persistent", 550, 12, item["uid"]),
            )
        reopened = self.reopen()
        with reopened.connection() as db:
            loaded = inventory_items.load(db, self.character["id"])
        loaded_mount = next(row for row in loaded if row["uid"] == item["uid"])
        self.assertEqual(
            (
                loaded_mount["mount"]["name"],
                loaded_mount["mount"]["xp"],
                loaded_mount["mount"]["health"],
            ),
            ("Persistent", 550, 12),
        )
        fields = proto_fields(inventory_items.item_proto(loaded_mount))
        pet_payload = next(value for tag, value in fields if tag == 402)
        self.assertEqual(
            wire.proto_field(402, pet_payload),
            mount_codec.item_pet(loaded_mount["mount"]),
        )

    def test_active_build_selects_its_own_mount_and_refreshes_pet_section(self):
        import hashlib
        import struct
        from unittest.mock import patch

        from wakfu_server import wire

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=35 WHERE id=%s",
                (self.character["id"],),
            )
        first = self._grant(slot=0)
        second = self._grant(reference=18704, slot=1)
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            0,
            self._build(0, 35, first["uid"]),
        )
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            1,
            self._build(1, 35, second["uid"]),
        )
        code, mounted = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual((code, mounted["mount_state"]["mounted"]), (0, True))
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=12,xp=250 WHERE uid=%s",
                (second["uid"],),
            )

        template = (
            struct.pack(">BqBq", 10, wire.TEMPLATE_CHARACTER, 0, wire.TEMPLATE_ACCOUNT)
            + struct.pack(">H", 6)
            + b"Pekebu"
            + b"\x00\x00"
            + wire.INITIAL_POSITION
        )
        pet_start = 26
        layout = {
            "template_sha256": hashlib.sha256(template).hexdigest(),
            "sections": [{"name": "PET", "start": pet_start, "end": pet_start + 2}],
        }
        for index, item, expected in (
            (0, first, mount_codec.pet_section(first["mount"])),
            (
                1,
                second,
                mount_codec.pet_section(dict(second["mount"], health=12, xp=250)),
            ),
        ):
            if index:
                character = self.store.activate_build(
                    self.account,
                    self.generation,
                    self.character["id"],
                    index,
                    in_fight=False,
                )
            else:
                character = self.store.character(self.account, self.character["id"])
            if index:
                self.assertFalse(character["mount_state"]["mounted"])
                self.assertEqual(character["mount_state"]["revision"], 2)
            unit = mount_inventory.equipped(character)
            self.assertEqual(unit["uid"], item["uid"])
            self.assertEqual(mount_inventory.actor_pet(character), expected)
            with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
                opcode, body = wire.refresh_player(template, character)
            entity_size = struct.unpack_from(">h", body, 8)[0]
            self.assertEqual(opcode, 15548)
            self.assertEqual(len(body), 10 + entity_size)
            self.assertIn(expected, body[10:])

    def test_modulated_build_cannot_equip_mount_below_native_level(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=35 WHERE id=%s",
                (self.character["id"],),
            )
        item = self._grant()
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            0,
            self._build(0, 35, item["uid"]),
        )
        # A stored sheet at effective level34 cannot equip this native level35 item.
        with self.assertRaises(ValueError):
            self.store.save_build(
                self.account,
                self.generation,
                self.character["id"],
                1,
                self._build(1, 34, item["uid"]),
            )

    def test_failed_reconcile_rolls_back_build_health_and_mounted_state(self):
        item, _ = self._equipped_mount()
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            1,
            self._build(1, 34),
        )
        context = dict(
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        code, before = mount_state.toggle(
            self.store, self.account, self.generation, self.character["id"], **context
        )
        self.assertEqual((code, before["mount_state"]["mounted"]), (0, True))
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_mount_reconcile() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected mount reconcile failure'; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_mount_reconcile BEFORE UPDATE ON character_mount_state "
                "FOR EACH ROW EXECUTE FUNCTION reject_mount_reconcile()"
            )
        snapshot = (before["hp"], before["max_hp"], before["hp_damage"])
        with self.assertRaises(psycopg.Error):
            self.store.activate_build(
                self.account,
                self.generation,
                self.character["id"],
                1,
                in_fight=False,
            )
        after = self.store.character(self.account, self.character["id"])
        self.assertEqual(after["active_build_index"], 0)
        self.assertEqual((after["hp"], after["max_hp"], after["hp_damage"]), snapshot)
        self.assertTrue(after["mount_state"]["mounted"])
        self.assertEqual(after["mount_state"]["revision"], 1)

    def test_mount_toggle_persists_idempotently_and_enforces_cooldown(self):
        item, _ = self._equipped_mount()
        context = dict(
            in_fight=False, location_allowed=True, occupation_cancelable=True
        )
        self.assertEqual(
            mount_state.toggle(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                mounted=False,
                **context,
            )[0],
            0,
        )
        with self.store.connection() as db:
            self.assertEqual(mount_state.load(db, self.character["id"])["revision"], 0)
        code, mounted = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            **context,
        )
        self.assertEqual(
            (
                code,
                mounted["mount_state"]["mounted"],
                mounted["mount_state"]["revision"],
            ),
            (0, True, 1),
        )
        code, repeated = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            **context,
        )
        self.assertEqual((code, repeated["mount_state"]["revision"]), (0, 1))
        self.assertEqual(repeated["mount_state"]["last_mount_at"], self.first_time)
        # Dismount inside the mount cooldown is allowed and must preserve the
        # original mount timestamp so an immediate remount remains blocked.
        self.store.clock = lambda: self.first_time.timestamp() + 0.25
        code, dismounted = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=False,
            **context,
        )
        self.assertEqual(
            (
                code,
                dismounted["mount_state"]["mounted"],
                dismounted["mount_state"]["revision"],
            ),
            (0, False, 2),
        )
        self.assertEqual(dismounted["mount_state"]["last_mount_at"], self.first_time)
        code, too_soon = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            **context,
        )
        self.assertEqual((code, too_soon["mount_state"]["revision"]), (6, 2))
        self.store.clock = lambda: self.first_time.timestamp() + 1.1
        code, mounted_again = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            **context,
        )
        self.assertEqual(
            (
                code,
                mounted_again["mount_state"]["mounted"],
                mounted_again["mount_state"]["revision"],
            ),
            (0, True, 3),
        )

    def test_mount_toggle_native_codes_and_external_context_guards(self):
        item, _ = self._equipped_mount()
        args = (self.store, self.account, self.generation, self.character["id"])
        common = dict(
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(mount_state.toggle(*args, **dict(common, in_fight=True))[0], 3)
        self.assertEqual(
            mount_state.toggle(*args, **dict(common, location_allowed=False))[0], 4
        )
        self.assertEqual(
            mount_state.toggle(*args, **dict(common, occupation_cancelable=False))[0], 5
        )
        with self.assertRaises(ValueError):
            mount_state.toggle(*args, **dict(common, location_allowed=0))
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=0 WHERE uid=%s",
                (item["uid"],),
            )
        self.assertEqual(mount_state.toggle(*args, **common)[0], 1)

        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=20,sleep_item_ref=12284,sleep_date=%s WHERE uid=%s",
                (int(self.first_time.timestamp()) * 1000, item["uid"]),
            )
        self.assertEqual(mount_state.toggle(*args, **common)[0], 3)

        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET sleep_item_ref=0,sleep_date=0 WHERE uid=%s",
                (item["uid"],),
            )
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                (self.character["id"],),
            )
        self.assertEqual(mount_state.toggle(*args, **common)[0], 2)

    def test_mount_toggle_checks_durable_fight_session_and_fail_closed_policy(self):
        item, _ = self._equipped_mount()
        args = (self.store, self.account, self.generation, self.character["id"])
        common = dict(
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        code, unchanged = mount_state.toggle(*args, **common)
        self.assertEqual(code, 3)
        self.assertFalse(unchanged["mount_state"]["mounted"])
        with self.assertRaises(ValueError):
            mount_state.toggle(
                self.store,
                self.account,
                "stale-generation",
                self.character["id"],
                **common,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mounts_require_unlock_quest'",
                (Jsonb(True),),
            )
        with self.assertRaises(ValueError):
            mount_state.toggle(*args, **common)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mounts_require_unlock_quest'",
                (Jsonb(False),),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mount_toggle_cooldown_ms'",
                (Jsonb(True),),
            )
        with self.assertRaises(ValueError):
            mount_state.toggle(*args, **common)

    def test_mount_without_equipment_returns_native_error_and_stale_owner_cannot_mutate(
        self,
    ):
        args = (self.store, self.account, self.generation, self.character["id"])
        common = dict(
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        code, character = mount_state.toggle(*args, **common)
        self.assertEqual((code, character["mount_state"]["revision"]), (7, 0))
        foreign = self.store.register(
            "stale_mount_" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        foreign_generation = self.store.begin_session(foreign)
        with self.assertRaises(ValueError):
            mount_state.toggle(
                self.store,
                foreign,
                foreign_generation,
                self.character["id"],
                **common,
            )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM character_mount_state WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()
            )


if __name__ == "__main__":
    unittest.main()
