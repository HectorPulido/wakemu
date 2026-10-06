import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid


@unittest.skipUnless(
    os.environ.get("WAKFU_POSTGRES_TEST_URL"), "Isolated PostgreSQL required"
)
class MigrationTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.postgres import Database

        self.database = Database(
            os.environ["WAKFU_POSTGRES_TEST_URL"],
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
            "INSERT INTO combat_fight_participants VALUES(%s,%s,%s,0)",
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
