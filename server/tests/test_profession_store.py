import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import uuid

from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase, isolated_test_url
from wakfu_server.profession_store import (
    account_packet,
    award,
    ensure_learned,
    ensure_all_learned,
    learned,
    level,
)
from wakfu_server.profession_wire import MAX_XP, snapshot
from wakfu_server.profession_rewards import base_xp
from wakfu_server.monster_collect import resolve_target
from wakfu_server.combat_groups import Groups
from wakfu_server.monsters import owned_instance


class ProfessionTests(PostgresCase):
    def actor(self, store=None, username="profession-owner", name="Profession First"):
        store = self.store if store is None else store
        account = store.register(username, "local-password")["id"]
        character = store.create_character(account, name)
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        return account, character, generation

    def test_default_unlock_covers_native_jobs_and_preserves_existing_progress(self):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        account, character, generation = self.actor()
        native_ids = set(
            native_catalog.load(DATA_ROOT / "profession-actions.json")["profession_ids"]
        )
        result = ensure_all_learned(self.store, account, generation, character["id"])
        self.assertEqual(result["levels"], dict.fromkeys(native_ids, 0))
        self.assertEqual(
            {
                struct.unpack(">i", body)[0]
                for opcode, body in result["packets"]
                if opcode == 12675
            },
            native_ids,
        )
        self.assertEqual(result["packets"][-1][0], 13873)
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=30000,counters=ARRAY[1,2,3,4],actions=ARRAY[1632] "
                "WHERE account_id=%s AND profession_id=73",
                (account,),
            )
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s AND profession_id=74",
                (account,),
            )
            db.execute(
                "UPDATE account_craft_state SET configuration=%s,additional=%s WHERE account_id=%s",
                (bytes.fromhex("0801"), bytes.fromhex("18012001"), account),
            )
        repaired = ensure_all_learned(self.store, account, generation, character["id"])
        self.assertEqual(set(repaired["levels"]), native_ids)
        self.assertEqual(repaired["levels"][73], 20)
        self.assertEqual(repaired["levels"][74], 0)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT xp,counters,actions FROM account_professions "
                "WHERE account_id=%s AND profession_id=73",
                (account,),
            ).fetchone()
            self.assertEqual(
                dict(row),
                {"xp": 30000, "counters": [1, 2, 3, 4], "actions": [1632]},
            )
            self.assertEqual(account_packet(db, account), repaired["packets"][-1])
        self.assertEqual(
            ensure_all_learned(self.store, account, generation, character["id"]),
            repaired,
        )
        with self.assertRaises(ValueError):
            ensure_all_learned(self.store, account, "stale", character["id"])

    def test_action_reward_policy_validates_exact_fields_types_ranges_and_recipe_slots(
        self,
    ):
        valid = {
            "version": 1,
            "planting_xp": 10,
            "harvest_xp": 50,
            "recipe_slot_xp": 100,
        }
        with self.store.connection() as db:
            for policy in (
                {**valid, "version": True},
                {**valid, "planting_xp": True},
                {**valid, "harvest_xp": -1},
                {**valid, "recipe_slot_xp": 3_000_001},
                {k: v for k, v in valid.items() if k != "harvest_xp"},
                {**valid, "unknown": 1},
            ):
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='profession_action_rewards'",
                    (Jsonb(policy),),
                )
                with self.subTest(policy=policy), self.assertRaisesRegex(
                    ValueError, "action reward policy"
                ):
                    base_xp(db, "planting")

            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_action_rewards'",
                (Jsonb(valid),),
            )
            self.assertEqual(base_xp(db, "planting"), 10)
            self.assertEqual(base_xp(db, "harvest"), 50)
            self.assertEqual(base_xp(db, "recipe", recipe_slots=1), 100)
            self.assertEqual(base_xp(db, "recipe", recipe_slots=16), 1600)
            for slots in (0, 17, True):
                with self.subTest(recipe_slots=slots), self.assertRaises(ValueError):
                    base_xp(db, "recipe", recipe_slots=slots)
            with self.assertRaises(ValueError):
                base_xp(db, "unknown")

    def test_territorial_profession_percent_applies_before_account_multiplier(self):
        account, character, generation = self.actor(
            username="profession-territory", name="Territory XP"
        )
        ensure_learned(self.store, account, generation, character["id"], [72])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_xp'",
                (Jsonb({"multiplier_basis_points": 20000}),),
            )
            credited = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=10,
                operation="territory-xp-order",
                territory_percent=30,
            )
        self.assertEqual(credited["xp"], 26)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT applied_xp FROM profession_xp_receipts "
                "WHERE account_id=%s AND operation=%s",
                (account, "territory-xp-order"),
            ).fetchone()
        self.assertEqual(receipt["applied_xp"], 26)

    def test_fresh_unlearned_and_account_level_shared_between_characters(self):
        account, one, generation = self.actor()
        two = self.store.create_character(account, "Profession Second")
        self.assertEqual(level(self.store, account, generation, one["id"], 74), 0)
        self.assertFalse(learned(self.store, account, generation, one["id"], 74))
        ensure_learned(self.store, account, generation, one["id"], [74])
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=74",
                (75 * 20 * 20, account),
            )
        self.assertEqual(level(self.store, account, generation, one["id"], 74), 20)
        with self.assertRaises(ValueError):
            level(self.store, account, generation, two["id"], 74)
        self.store.select_character(account, generation, two["id"])
        self.assertTrue(learned(self.store, account, generation, two["id"], 74))
        self.assertEqual(level(self.store, account, generation, two["id"], 74), 20)

        stale = generation
        replacement = self.store.begin_session(account)
        self.store.select_character(account, replacement, two["id"])
        with self.assertRaises(ValueError):
            level(self.store, account, stale, two["id"], 74)

        foreign, foreign_char, foreign_generation = self.actor(
            username="profession-foreign", name="Profession Foreign"
        )
        self.assertEqual(
            level(self.store, foreign, foreign_generation, foreign_char["id"], 74), 0
        )
        self.assertFalse(
            learned(self.store, foreign, foreign_generation, foreign_char["id"], 74)
        )

    def test_learning_preserves_xp_snapshot_and_account_settings_on_reopen(self):
        account, one, generation = self.actor(
            username="profession-learner", name="Learn First"
        )
        two = self.store.create_character(account, "Learn Second")
        learned_result = ensure_learned(
            self.store, account, generation, one["id"], [72, 74]
        )
        self.assertEqual(learned_result["levels"], {72: 0, 74: 0})
        self.assertEqual(
            [packet[0] for packet in learned_result["packets"]], [12675, 12675, 13873]
        )
        self.assertTrue(learned(self.store, account, generation, one["id"], 74))

        configuration = bytes.fromhex("0801")
        additional = bytes.fromhex("18012001")
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=150 WHERE account_id=%s AND profession_id=74",
                (account,),
            )
            db.execute(
                "UPDATE account_craft_state SET configuration=%s,additional=%s WHERE account_id=%s",
                (configuration, additional, account),
            )
        preserved = ensure_learned(self.store, account, generation, one["id"], [74])
        self.assertEqual(preserved["levels"][74], 1)
        self.assertEqual(
            preserved["packets"][-1],
            snapshot(
                {
                    72: {"xp": 0, "counters": [0, 0, 0, 0], "actions": []},
                    74: {"xp": 150, "counters": [0, 0, 0, 0], "actions": []},
                },
                configuration=configuration,
                additional=additional,
            ),
        )

        reopened = self.reopen()
        self.assertEqual(level(reopened, account, generation, one["id"], 74), 1)
        self.store.select_character(account, generation, two["id"])
        self.assertEqual(level(self.store, account, generation, two["id"], 74), 1)
        with reopened.connection() as db:
            opcode, body = account_packet(db, account)
        self.assertEqual(opcode, 13873)
        self.assertEqual(
            body,
            snapshot(
                {
                    72: {"xp": 0, "counters": [0, 0, 0, 0], "actions": []},
                    74: {"xp": 150, "counters": [0, 0, 0, 0], "actions": []},
                },
                configuration=configuration,
                additional=additional,
            )[1],
        )
        with self.assertRaises(ValueError):
            ensure_learned(self.store, account, generation, one["id"], [999999])
        with self.assertRaises(ValueError):
            ensure_learned(self.store, account, "stale", two["id"], [74])

    def test_award_replay_applies_no_second_delta(self):
        account, character, generation = self.actor(
            username="profession-award", name="Award Owner"
        )
        ensure_learned(self.store, account, generation, character["id"], [72])
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=150 WHERE account_id=%s AND profession_id=72",
                (account,),
            )
        with self.store.connection() as db:
            first = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=100,
                operation="craft-once",
            )
        self.assertTrue(first["applied"])
        self.assertEqual(first["xp"], 100)
        self.assertEqual(struct.unpack(">iq", first["packets"][0][1]), (72, 100))
        with self.store.connection() as db:
            replay = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=900,
                operation="craft-once",
            )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["packets"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (account,),
                ).fetchone()["xp"],
                250,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM profession_xp_receipts WHERE account_id=%s",
                    (account,),
                ).fetchone()["count"],
                1,
            )

    def test_award_and_action_side_effect_roll_back_atomically(self):
        account, character, generation = self.actor(
            username="profession-rollback", name="Rollback Owner"
        )
        ensure_learned(self.store, account, generation, character["id"], [72])
        before_hp = character["hp"]
        with self.assertRaisesRegex(RuntimeError, "abort simulated action"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET hp=hp-1 WHERE id=%s", (character["id"],)
                )
                award(
                    self.store,
                    db,
                    account,
                    generation,
                    character["id"],
                    72,
                    base_xp=50,
                    operation="rollback-action",
                )
                raise RuntimeError("abort simulated action")
        saved = self.store.character(account, character["id"])
        self.assertEqual(saved["hp"], before_hp)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (account,),
                ).fetchone()["xp"],
                0,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM profession_xp_receipts WHERE account_id=%s AND operation=%s",
                    (account, "rollback-action"),
                ).fetchone()
            )
        with self.store.connection() as db:
            committed = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=50,
                operation="rollback-action",
            )
        self.assertTrue(committed["applied"])
        self.assertEqual(committed["xp"], 50)

    def test_stale_award_cap_and_multiplier_boolean_rejection(self):
        account, character, generation = self.actor(
            username="profession-cap", name="Cap Owner"
        )
        ensure_learned(self.store, account, generation, character["id"], [72])
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=72",
                (MAX_XP - 20, account),
            )
        with self.store.connection() as db:
            capped = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=100,
                operation="cap-last-delta",
            )
        self.assertEqual(capped["xp"], 20)
        with self.store.connection() as db:
            at_cap = award(
                self.store,
                db,
                account,
                generation,
                character["id"],
                72,
                base_xp=100,
                operation="already-at-cap",
            )
        self.assertEqual(at_cap["xp"], 0)
        self.assertEqual(at_cap["packets"], [])

        replacement = self.store.begin_session(account)
        self.store.select_character(account, replacement, character["id"])
        with self.assertRaises(ValueError):
            with self.store.connection() as db:
                award(
                    self.store,
                    db,
                    account,
                    generation,
                    character["id"],
                    72,
                    base_xp=1,
                    operation="stale-session",
                )

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='profession_xp'",
                (Jsonb({"multiplier_basis_points": True}),),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            with self.store.connection() as db:
                award(
                    self.store,
                    db,
                    account,
                    replacement,
                    character["id"],
                    72,
                    base_xp=1,
                    operation="bad-multiplier",
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                    (account,),
                ).fetchone()["xp"],
                MAX_XP,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM profession_xp_receipts WHERE account_id=%s AND operation=%s",
                    (account, "bad-multiplier"),
                ).fetchone()
            )

    def test_registry_resolves_actual_instance_and_rejects_claimed_group(self):
        groups = Groups()
        npc = owned_instance(
            5525, 1, -200, map_id=1134, instance_id=7, x=-7, y=-7, z=-1
        )
        groups.register(1134, 7, 200, [npc])
        character = dict(map_id=1134, instance_id=7)
        self.assertEqual(resolve_target(groups, character, -200)["instance_id"], 7)
        with self.assertRaises(ValueError):
            resolve_target(groups, dict(map_id=1134, instance_id=0), -200)
        groups.claim((1134, 7, 200), "own-generation", 123)
        with self.assertRaises(ValueError):
            resolve_target(groups, character, -200)

    def test_migration_keeps_max_legacy_level_instead_of_summing_characters(self):
        from wakfu_server.storage.postgres import Database, migrate
        from wakfu_server.storage.store import Store

        base_url = isolated_test_url()
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        admin = Database(base_url, password_file=password_file)
        schema = "profession_migration_" + uuid.uuid4().hex
        try:
            with admin.connection() as db:
                db.execute(f"CREATE SCHEMA {schema}")
            scoped_url = make_conninfo(base_url, options=f"-c search_path={schema}")
            old_store = Store(scoped_url, password_file=password_file)
            try:
                migration_source = Path(__file__).resolve().parents[1] / "migrations"
                with tempfile.TemporaryDirectory() as temp_dir:
                    prefix_dir = Path(temp_dir)
                    for migration in sorted(migration_source.glob("*.sql")):
                        if int(migration.name[:3]) <= 12:
                            shutil.copyfile(migration, prefix_dir / migration.name)
                    with old_store.connection() as db:
                        migrate(db, prefix_dir)
                    first_account = old_store.register(
                        "legacy-profession", "local-password"
                    )["id"]

                    # Construct the pre-013 fixture through its historical schema;
                    # current Store creation requires later deletion columns.
                    def legacy_character(account_id, name):
                        with old_store.connection() as db:
                            return db.execute(
                                "INSERT INTO characters(account_id,name,name_key,breed,sex,"
                                "face,hair,colors,appearance,hp,max_hp) "
                                "VALUES(%s,%s,%s,8,false,0,0,'[]','{}',60,60) RETURNING id",
                                (account_id, name, name.casefold()),
                            ).fetchone()

                    first = legacy_character(first_account, "Legacy First")
                    second = legacy_character(first_account, "Legacy Second")
                    other_account = old_store.register(
                        "legacy-other", "local-password"
                    )["id"]
                    other = legacy_character(other_account, "Legacy Other")
                    with old_store.connection() as db:
                        db.execute(
                            "INSERT INTO character_professions VALUES(%s,74,12),(%s,74,20),(%s,74,4)",
                            (first["id"], second["id"], other["id"]),
                        )
                        migrate(db, migration_source)
                        rows = {
                            row["account_id"]: row["xp"]
                            for row in db.execute(
                                "SELECT account_id,xp FROM account_professions WHERE profession_id=74"
                            )
                        }
                    self.assertEqual(
                        rows, {first_account: 75 * 20 * 20, other_account: 75 * 4 * 4}
                    )
                    self.assertNotEqual(rows[first_account], 75 * (12 + 20) ** 2)
            finally:
                old_store.close()
        finally:
            with admin.connection() as db:
                db.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            admin.close()


if __name__ == "__main__":
    unittest.main()
