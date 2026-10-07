import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from psycopg.types.json import Jsonb
from postgres_case import isolated_test_url


class IsolatedTestUrlTests(unittest.TestCase):
    def test_runtime_database_names_are_refused(self):
        from unittest.mock import patch

        for name in ("wakemu", "wakemu_runtime"):
            with patch.dict(
                os.environ,
                {"WAKFU_POSTGRES_TEST_URL": f"host=postgres dbname={name} user=wakemu"},
            ), self.subTest(database=name), self.assertRaisesRegex(
                RuntimeError, "runtime"
            ):
                isolated_test_url()

    def test_explicit_test_database_is_accepted(self):
        from unittest.mock import patch

        value = "host=postgres dbname=wakemu_migration_test user=wakemu"
        with patch.dict(os.environ, {"WAKFU_POSTGRES_TEST_URL": value}):
            self.assertEqual(isolated_test_url(), value)


@unittest.skipUnless(
    os.environ.get("WAKFU_POSTGRES_TEST_URL"), "Isolated PostgreSQL required"
)
class MigrationTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.postgres import Database

        self.database = Database(
            isolated_test_url(),
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(self.database.close)
        self.context = self.database.connection()
        self.db = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.schema = "migration_test_" + uuid.uuid4().hex
        self.db.execute(f"CREATE SCHEMA {self.schema}")
        self.db.execute(f"SET LOCAL search_path TO {self.schema}")
        self.addCleanup(self.db.execute, f"DROP SCHEMA {self.schema} CASCADE")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        source = Path(os.environ["WAKFU_MIGRATIONS_TEST_DIR"])
        self.migration_count = len(list(source.glob("*.sql")))
        for path in source.glob("*.sql"):
            shutil.copy(path, self.directory / path.name)

    def test_first_apply_second_noop_and_changed_checksum_rejected(self):
        from wakfu_server.postgres import migrate

        self.assertEqual(migrate(self.db, self.directory), self.migration_count)
        self.assertEqual(migrate(self.db, self.directory), 0)
        path = self.directory / "002_inventory.sql"
        path.write_text(path.read_text() + "\n-- changed\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            migrate(self.db, self.directory)
        self.assertEqual(
            self.db.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()[
                "n"
            ],
            self.migration_count,
        )

    def test_failed_migration_rolls_back_ddl_and_version(self):
        from wakfu_server.postgres import migrate
        from psycopg.errors import UndefinedTable

        migrate(self.db, self.directory)
        (self.directory / f"{self.migration_count+1:03d}_failure.sql").write_text(
            "CREATE TABLE must_not_survive(id bigint); SELECT * FROM absent_table;"
        )
        with self.assertRaises(UndefinedTable):
            migrate(self.db, self.directory)
        self.assertIsNone(
            self.db.execute("SELECT to_regclass('must_not_survive') AS t").fetchone()[
                "t"
            ]
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()[
                "n"
            ],
            self.migration_count,
        )

    def test_flora_variant_migration_keeps_special_overrides_and_prior_roll_receipt(
        self,
    ):
        from wakfu_server.postgres import migrate

        before = self.directory / "before_variant_policy"
        before.mkdir()
        after = self.directory / "after_variant_policy"
        after.mkdir()
        for path in self.directory.glob("*.sql"):
            version = int(path.name[:3])
            if version <= 32:
                shutil.copy(path, before / path.name)
            shutil.copy(path, after / path.name)

        self.assertEqual(32, migrate(self.db, before))
        # These are administrator-owned overrides for the two earlier special
        # policies. Migration 033 must leave them untouched.
        self.db.execute(
            "UPDATE resource_growth_transitions SET probability=0.37 "
            "WHERE resource_reference=60 AND from_stage=3 AND to_stage=4"
        )
        self.db.execute(
            "UPDATE resource_growth_transitions SET probability=0.61 "
            "WHERE resource_reference=139 AND from_stage=3 AND to_stage=4"
        )
        self.db.execute(
            "INSERT INTO resource_growth_decisions "
            "(resource_uid,from_stage,to_stage,probability,draw,accepted) "
            "VALUES(87654321,3,4,0.01,0.01,false)"
        )

        self.assertEqual(
            len(list(self.directory.glob("*.sql"))) - 32, migrate(self.db, after)
        )
        probabilities = {
            row["resource_reference"]: row["probability"]
            for row in self.db.execute(
                "SELECT resource_reference,probability FROM resource_growth_transitions "
                "WHERE resource_reference IN (60,139) AND from_stage=3 AND to_stage=4"
            )
        }
        self.assertEqual({60: 0.37, 139: 0.61}, probabilities)
        self.assertEqual(
            (0.01, 0.01, False),
            tuple(
                self.db.execute(
                    "SELECT probability,draw,accepted FROM resource_growth_decisions "
                    "WHERE resource_uid=87654321"
                )
                .fetchone()
                .values()
            ),
        )

    def test_planting_resource_provenance_migration_preserves_existing_receipts(self):
        from wakfu_server.postgres import migrate

        pre_provenance = self.directory / "pre_provenance"
        pre_provenance.mkdir()
        for path in self.directory.glob("*.sql"):
            if int(path.name[:3]) < 28:
                shutil.copy(path, pre_provenance / path.name)
        self.assertEqual(migrate(self.db, pre_provenance), 27)

        account = self.db.execute(
            "INSERT INTO accounts(username,username_key,salt,password_hash) VALUES(%s,%s,%s,%s) RETURNING id",
            ("ReceiptOwner", "receiptowner", bytes(16), b"test-hash"),
        ).fetchone()["id"]
        character = self.db.execute(
            "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
            "VALUES(%s,'Receipt Owner','receipt owner',8,false,0,0,'[]','{}',20,60) RETURNING id",
            (account,),
        ).fetchone()["id"]
        self.db.execute(
            "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
            "VALUES('old-success',%s,1,%s,%s,true,1)",
            (character, Jsonb({}), Jsonb({"resource_uid": 87654321, "reference": 60})),
        )
        self.db.execute(
            "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
            "VALUES('old-failure',%s,2,%s,NULL,false,0)",
            (character, Jsonb({})),
        )

        self.assertEqual(migrate(self.db, self.directory), self.migration_count - 27)
        rows = {
            row["operation_id"]: row
            for row in self.db.execute(
                "SELECT operation_id,success,resource_uid FROM planting_receipts"
            )
        }
        self.assertEqual(rows["old-success"]["resource_uid"], 87654321)
        self.assertIsNone(rows["old-failure"]["resource_uid"])

    def test_ecology_basis_point_migration_preserves_sign_visible_score_and_replay(
        self,
    ):
        from wakfu_server.postgres import migrate
        from wakfu_server import personal_ecology
        from wakfu_server.characters.ecology_progression import native_score

        before = self.directory / "before_ecology_basis_points"
        before.mkdir()
        after = self.directory / "after_ecology_basis_points"
        after.mkdir()
        for path in self.directory.glob("*.sql"):
            version = int(path.name[:3])
            if version <= 33:
                shutil.copy(path, before / path.name)
            shutil.copy(path, after / path.name)
        self.assertEqual(33, migrate(self.db, before))

        account = self.db.execute(
            "INSERT INTO accounts(username,username_key,salt,password_hash) "
            "VALUES(%s,%s,%s,%s) RETURNING id",
            ("EcologyMigration", "ecologymigration", bytes(16), b"test-hash"),
        ).fetchone()["id"]
        character = self.db.execute(
            "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
            "VALUES(%s,'Ecology Migration','ecology migration',8,false,0,0,'[]','{}',20,60) RETURNING id",
            (account,),
        ).fetchone()["id"]
        self.db.execute(
            "UPDATE characters SET ecology_value=-500,ecology_revision=4 WHERE id=%s",
            (character,),
        )
        legacy_evidence = {"kind": "harvest", "population": 4}
        self.db.execute(
            "INSERT INTO personal_ecology_receipts(character_id,operation,requested_delta,before_value,after_value,revision,evidence) "
            "VALUES(%s,'legacy-harvest',-5500,5000,-500,3,%s)",
            (character, Jsonb(legacy_evidence)),
        )
        self.db.execute(
            "INSERT INTO personal_ecology_receipts(character_id,operation,requested_delta,before_value,after_value,revision,evidence) "
            "VALUES(%s,'legacy-cross',10000,-5000,5000,1,%s)",
            (character, Jsonb({"kind": "cross-zero", "population": 5})),
        )

        self.assertEqual(
            len(list(self.directory.glob("*.sql"))) - 33, migrate(self.db, after)
        )
        migrated = self.db.execute(
            "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
            (character,),
        ).fetchone()
        receipt = self.db.execute(
            "SELECT requested_delta,before_value,after_value,revision,evidence "
            "FROM personal_ecology_receipts WHERE character_id=%s AND operation='legacy-harvest'",
            (character,),
        ).fetchone()
        self.assertEqual(-500, native_score(migrated["ecology_value"]))
        self.assertEqual(4, migrated["ecology_revision"])
        self.assertEqual(
            receipt["after_value"] - receipt["before_value"],
            receipt["requested_delta"],
        )
        self.assertEqual(-500, native_score(receipt["after_value"]))
        self.assertEqual(9900, receipt["before_value"])
        self.assertEqual(
            legacy_evidence
            | {
                "value_unit": "basis_points",
                "source_value_unit": "native_score",
                "original_native_delta": -5500,
            },
            receipt["evidence"],
        )
        cross = self.db.execute(
            "SELECT requested_delta,evidence,before_value,after_value "
            "FROM personal_ecology_receipts WHERE character_id=%s AND operation='legacy-cross'",
            (character,),
        ).fetchone()
        self.assertEqual(19800, cross["requested_delta"])
        self.assertEqual((-9900, 9900), (cross["before_value"], cross["after_value"]))
        self.assertEqual(10000, cross["evidence"]["original_native_delta"])

        # Reapplying migration is a no-op, and an old operation replays its
        # current absolute score without incrementing the character revision.
        self.assertEqual(0, migrate(self.db, after))
        replay = personal_ecology.apply(
            self.db,
            character,
            operation="new-current-operation",
            delta=-25,
            evidence={"kind": "new-operation"},
        )
        duplicate = personal_ecology.apply(
            self.db,
            character,
            operation="new-current-operation",
            delta=-25,
            evidence={"kind": "new-operation"},
        )
        self.assertFalse(replay["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(replay["packet"], duplicate["packet"])
        self.assertEqual(
            5,
            self.db.execute(
                "SELECT ecology_revision FROM characters WHERE id=%s", (character,)
            ).fetchone()["ecology_revision"],
        )

    def test_monster_pacing_migration_resets_active_age_but_preserves_stages_and_receipts(
        self,
    ):
        from wakfu_server.postgres import migrate

        before = self.directory / "before_monster_pacing"
        before.mkdir()
        after = self.directory / "after_monster_pacing"
        after.mkdir()
        for path in self.directory.glob("*.sql"):
            version = int(path.name[:3])
            if version <= 34:
                shutil.copy(path, before / path.name)
            if version <= 35:
                shutil.copy(path, after / path.name)
        self.assertEqual(34, migrate(self.db, before))

        members = [
            {
                "id": -35001,
                "ref": 2616,
                "map_id": 527,
                "instance_id": 0,
                "x": 27,
                "y": 4,
                "z": 0,
            },
            {
                "id": -35002,
                "ref": 2598,
                "map_id": 527,
                "instance_id": 0,
                "x": 27,
                "y": 5,
                "z": 0,
            },
            {
                "id": -35003,
                "ref": 1816,
                "map_id": 527,
                "instance_id": 0,
                "x": 28,
                "y": 5,
                "z": 0,
            },
        ]
        self.db.execute(
            "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,revision) "
            "VALUES(527,0,35001,%s,'available',1)",
            (Jsonb(members),),
        )
        for member in members:
            self.db.execute(
                "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) "
                "VALUES(527,0,35001,%s)",
                (member["id"],),
            )
        timer_rows = [
            (members[0]["id"], 2616, 45000, 1000, "old-run", False, 4),
            (members[1]["id"], 2598, 0, 2000, "old-run", True, 7),
            (members[2]["id"], 1816, 12000, 3000, "old-run", False, 9),
        ]
        for timer_row in timer_rows:
            self.db.execute(
                "INSERT INTO monster_maturation_timers(map_id,instance_id,monster_id,reference,"
                "remaining_ms,last_active_ms,observer_generation,due,cycle) "
                "VALUES(527,0,%s,%s,%s,%s,%s,%s,%s)",
                timer_row,
            )
        policy = Jsonb(
            {
                "interval_ms": 60000,
                "base_probability": 0.25,
                "stage_decay": 0.5,
                "boss_probability": 0.00001,
            }
        )
        for member, cycle, source, target in (
            (members[1], 6, 2616, 2598),
            (members[2], 8, 2598, 1816),
        ):
            self.db.execute(
                "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
                "group_id,from_reference,to_reference,draw,policy) "
                "VALUES(527,0,%s,%s,35001,%s,%s,0.1,%s)",
                (member["id"], cycle, source, target, policy),
            )
            self.db.execute(
                "INSERT INTO monster_maturation_outbox(map_id,instance_id,monster_id,cycle,"
                "group_id,revision,published) VALUES(527,0,%s,%s,35001,%s,true)",
                (member["id"], cycle, cycle),
            )

        applied = migrate(self.db, after)
        self.assertEqual(1, applied)
        self.assertEqual(
            900000,
            self.db.execute(
                "SELECT (value->>'interval_ms')::int AS interval FROM settings "
                "WHERE name='monster_maturation'"
            ).fetchone()["interval"],
        )
        timers = self.db.execute(
            "SELECT monster_id,reference,remaining_ms,last_active_ms,observer_generation,due,cycle "
            "FROM monster_maturation_timers ORDER BY monster_id"
        ).fetchall()
        self.assertEqual(
            [
                (members[2]["id"], 1816, 900000, None, None, False, 9),
                (members[1]["id"], 2598, 900000, None, None, False, 7),
                (members[0]["id"], 2616, 900000, None, None, False, 4),
            ],
            [tuple(row.values()) for row in timers],
        )
        receipts = self.db.execute(
            "SELECT monster_id,cycle,from_reference,to_reference FROM monster_maturation_receipts "
            "ORDER BY monster_id"
        ).fetchall()
        self.assertEqual(
            [(members[2]["id"], 8, 2598, 1816), (members[1]["id"], 6, 2616, 2598)],
            [tuple(row.values()) for row in receipts],
        )
        outbox = self.db.execute(
            "SELECT count(*) AS count FROM monster_maturation_outbox WHERE published"
        ).fetchone()["count"]
        self.assertEqual(2, outbox)

    def test_durable_reward_and_monster_identity_constraints(self):
        from wakfu_server.postgres import migrate
        from psycopg.errors import UniqueViolation

        migrate(self.db, self.directory)
        account = self.db.execute(
            "INSERT INTO accounts(username,username_key,salt,password_hash) VALUES(%s,%s,%s,%s) RETURNING id",
            ("PgOwner", "pgowner", bytes(16), b"test-hash"),
        ).fetchone()["id"]
        char = self.db.execute(
            "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) VALUES(%s,'Pg Owner','pg owner',8,false,0,0,'[]','{}',20,60) RETURNING id",
            (account,),
        ).fetchone()["id"]
        fight = self.db.execute(
            "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
        ).fetchone()["id"]
        self.db.execute(
            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
            (fight, char, account),
        )
        statement = "INSERT INTO fight_rewards(fight_id,character_id,account_id,generation,xp,kamas,start_xp,end_xp,start_level,end_level) VALUES(%s,%s,%s,%s,10,1,0,10,1,1)"
        self.db.execute(statement, (fight, char, account, "old-session"))
        with self.assertRaises(UniqueViolation):
            with self.db.transaction():
                self.db.execute(
                    statement, (fight, char, account, "replacement-session")
                )
        for group in (1, 2):
            self.db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) VALUES(1134,0,%s,'[]','available')",
                (group,),
            )
        self.db.execute("INSERT INTO combat_group_members VALUES(1134,0,1,-99)")
        with self.assertRaises(UniqueViolation):
            with self.db.transaction():
                self.db.execute("INSERT INTO combat_group_members VALUES(1134,0,2,-99)")
        self.assertEqual(
            self.db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"],
            1,
        )

    def test_player_exchange_schema_enforces_pair_and_revision_invariants(self):
        from wakfu_server.postgres import migrate
        from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

        migrate(self.db, self.directory)

        def player(label):
            account = self.db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash) "
                "VALUES(%s,%s,%s,%s) RETURNING id",
                (label, label.lower(), bytes(16), b"test-hash"),
            ).fetchone()["id"]
            character = self.db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,8,false,0,0,'[]','{}',20,60) RETURNING id",
                (account, label + " Hero", (label + " Hero").lower()),
            ).fetchone()["id"]
            return account, character

        a1, c1 = player("ExchangeOne")
        a2, c2 = player("ExchangeTwo")
        a3, c3 = player("ExchangeThree")
        exchange = self.db.execute(
            "INSERT INTO player_exchanges "
            "(inviter_id,invitee_id,inviter_account,invitee_account,"
            "inviter_generation,invitee_generation,created_at,expires_at) "
            "VALUES(%s,%s,%s,%s,'gen-one','gen-two',now(),now()+interval '60 seconds') "
            "RETURNING id",
            (c1, c2, a1, a2),
        ).fetchone()["id"]

        # Both participant foreign keys are composite: a character cannot be
        # paired with another account's identity, and an account cannot invite
        # itself through a second character.
        with self.assertRaises(ForeignKeyViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchanges "
                    "(inviter_id,invitee_id,inviter_account,invitee_account,"
                    "inviter_generation,invitee_generation,created_at,expires_at) "
                    "VALUES(%s,%s,%s,%s,'g1','g2',now(),now()+interval '1 minute')",
                    (c1, c2, a3, a2),
                )
        with self.assertRaises(CheckViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchanges "
                    "(inviter_id,invitee_id,inviter_account,invitee_account,"
                    "inviter_generation,invitee_generation,created_at,expires_at) "
                    "VALUES(%s,%s,%s,%s,'g1','g2',now(),now()+interval '1 minute')",
                    (c1, c2, a1, a1),
                )

        for character in (c1, c2):
            self.db.execute(
                "INSERT INTO player_exchange_members(exchange_id,character_id) VALUES(%s,%s)",
                (exchange, character),
            )
        self.db.execute(
            "SET CONSTRAINTS player_exchange_member_pair,player_exchange_pair_members IMMEDIATE"
        )

        # Membership must be restricted to the two identities named by the
        # exchange, not merely to any existing character. This catches a
        # third-party membership hole at the schema boundary.
        outsider_was_rejected = False
        self.db.execute("SAVEPOINT outsider_membership")
        try:
            self.db.execute(
                "INSERT INTO player_exchange_members(exchange_id,character_id) VALUES(%s,%s)",
                (exchange, c3),
            )
            self.db.execute("SET CONSTRAINTS player_exchange_member_pair IMMEDIATE")
        except ForeignKeyViolation:
            outsider_was_rejected = True
        finally:
            self.db.execute("ROLLBACK TO SAVEPOINT outsider_membership")
            self.db.execute("RELEASE SAVEPOINT outsider_membership")

        with self.assertRaises(CheckViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchange_items(exchange_id,character_id,uid,quantity) "
                    "VALUES(%s,%s,901,0)",
                    (exchange, c1),
                )
        with self.assertRaises(ForeignKeyViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchange_items(exchange_id,character_id,uid,quantity) "
                    "VALUES(%s,%s,902,1)",
                    (exchange, c3),
                )
        self.db.execute(
            "INSERT INTO player_exchange_items(exchange_id,character_id,uid,quantity) "
            "VALUES(%s,%s,903,2)",
            (exchange, c1),
        )

        # A confirmation is valid only for a nonzero published revision and
        # must be invalidated atomically when the proposal revision changes.
        with self.assertRaises(CheckViolation):
            with self.db.transaction():
                self.db.execute(
                    "UPDATE player_exchange_members SET confirmed_revision=1 "
                    "WHERE exchange_id=%s AND character_id=%s",
                    (exchange, c1),
                )
        self.db.execute(
            "UPDATE player_exchange_members SET published_revision=4,confirmed_revision=4 "
            "WHERE exchange_id=%s AND character_id=%s",
            (exchange, c1),
        )
        with self.assertRaises(CheckViolation):
            with self.db.transaction():
                self.db.execute(
                    "UPDATE player_exchange_members SET published_revision=5 "
                    "WHERE exchange_id=%s AND character_id=%s",
                    (exchange, c1),
                )

        transfers = Jsonb({"items": [], "kamas": 0})
        self.db.execute(
            "INSERT INTO player_exchange_receipts(exchange_id,revision,committed_at,transfers) "
            "VALUES(%s,4,now(),%s)",
            (exchange, transfers),
        )
        with self.assertRaises(UniqueViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchange_receipts(exchange_id,revision,committed_at,transfers) "
                    "VALUES(%s,5,now(),%s)",
                    (exchange, transfers),
                )
        with self.assertRaises(CheckViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchange_receipts(exchange_id,revision,committed_at,transfers) "
                    "VALUES(%s,5,now(),%s)",
                    (exchange, Jsonb([])),
                )

        self.db.execute(
            "INSERT INTO player_exchange_outbox "
            "(exchange_id,revision,character_id,generation,event,payload,created_at) "
            "VALUES(%s,4,%s,'gen-one','committed',%s,now())",
            (exchange, c1, Jsonb({"status": "committed"})),
        )
        with self.assertRaises(UniqueViolation):
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO player_exchange_outbox "
                    "(exchange_id,revision,character_id,generation,event,payload,created_at) "
                    "VALUES(%s,4,%s,'gen-one','committed',%s,now())",
                    (exchange, c1, Jsonb({"status": "committed"})),
                )
        self.assertEqual(
            1,
            self.db.execute(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange,),
            ).fetchone()["n"],
        )
        self.assertTrue(
            outsider_was_rejected,
            "the exchange schema accepted a member outside its inviter/invitee pair",
        )
