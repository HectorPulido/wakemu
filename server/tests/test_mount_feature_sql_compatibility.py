"""The targeted mount feature is repeatable on the deployed374 schema."""
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import psycopg

from postgres_case import PostgresCase


class MountFeatureSQLCompatibilityTests(PostgresCase):
    def setUp(self):
        self.migrations = Path(__file__).resolve().parents[1] / "migrations"
        directory = tempfile.TemporaryDirectory(prefix="mount-schema374-")
        self.addCleanup(directory.cleanup)
        for path in self.migrations.glob("*.sql"):
            if int(path.name.split("_", 1)[0]) <= 374:
                (Path(directory.name) / path.name).symlink_to(path)
        with patch.dict(os.environ, {"WAKFU_MIGRATIONS_TEST_DIR": directory.name}):
            super().setUp()

    def test_targeted_sql_repeats_without_reset_and_rejects_conflicting_alias(self):
        from wakfu_server.mount_inventory import initialize

        sql = (self.migrations / "382_reconstructed_mount_item_aliases.sql").read_text()
        now = datetime(2033, 4, 5, tzinfo=timezone.utc)
        with self.store.connection() as db:
            history = list(
                db.execute(
                    "SELECT version,checksum FROM schema_migrations ORDER BY version"
                )
            )
            self.assertEqual([row["version"] for row in history], list(range(1, 375)))
            db.execute(sql, prepare=False)
            account = db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash) "
                "VALUES('Mount SQL','mountsql',decode(repeat('00',16),'hex'),decode('00','hex')) RETURNING id"
            ).fetchone()["id"]
            character = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,'Mount SQL','mountsql',7,false,0,0,'[]','{}',60,60) RETURNING id",
                (account,),
            ).fetchone()["id"]
            container = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,0+2193,0,20,0) RETURNING uid",
                (character,),
            ).fetchone()["uid"]
            for slot, reference in enumerate((32993, 18682)):
                uid = db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,1,%s,%s) RETURNING uid",
                    (character, reference, container, slot),
                ).fetchone()["uid"]
                initialize(db, uid, character, now)
                db.execute(
                    "UPDATE inventory_mounts SET name='Keep',xp=375,health=7 WHERE uid=%s",
                    (uid,),
                )
            before = list(db.execute("SELECT * FROM inventory_mounts ORDER BY uid"))
            db.execute(sql, prepare=False)
            self.assertEqual(
                list(db.execute("SELECT * FROM inventory_mounts ORDER BY uid")), before
            )
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT version,checksum FROM schema_migrations ORDER BY version"
                    )
                ),
                history,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM mount_models").fetchone()["n"], 40
            )
            self.assertEqual(
                db.execute(
                    "SELECT model_id FROM mount_item_models WHERE reference=32993"
                ).fetchone()["model_id"],
                116,
            )
        with self.assertRaisesRegex(
            psycopg.errors.CheckViolation, "differs from qualified policy"
        ):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE mount_item_aliases SET model_id=88 WHERE reference=32993"
                )
                db.execute(sql, prepare=False)
        with self.assertRaisesRegex(
            psycopg.errors.CheckViolation, "Incompatible mount item alias registry"
        ):
            with self.store.connection() as db:
                db.execute(
                    "ALTER TABLE mount_item_aliases DROP CONSTRAINT mount_item_aliases_model_id_fkey"
                )
                db.execute(sql, prepare=False)
        with self.store.connection() as db:
            self.assertEqual(
                list(db.execute("SELECT * FROM inventory_mounts ORDER BY uid")), before
            )
            self.assertEqual(
                db.execute(
                    "SELECT model_id FROM mount_item_aliases WHERE reference=32993"
                ).fetchone()["model_id"],
                116,
            )
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT version,checksum FROM schema_migrations ORDER BY version"
                    )
                ),
                history,
            )
