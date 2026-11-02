"""Focused clean-install export roundtrip; isolated schemas, no gameplay probes."""
import copy
import json
import gzip
import os
from pathlib import Path
import unittest
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tools import export_installation_seed as exporter
import test_native_scene_policy_authority as fixture

FIXTURES = Path(__file__).resolve().parent / "fixtures/native_scene_authority"
SEEDS = fixture.SEEDS


def configuration_tables(db):
    columns = []
    for field in exporter.CONTEXT_COLUMNS:
        kind = (
            "text"
            if field in ("route_key", "provenance")
            else "bigint[]"
            if field == "allowed_ids"
            else "boolean"
            if field.startswith(("is_", "can_"))
            else "integer"
        )
        columns.append(field + " " + kind + " NOT NULL")
    db.execute(
        "CREATE TABLE dungeon_context_policy_versions("
        + ",".join(columns)
        + ",PRIMARY KEY(route_key,policy_version))"
    )
    for table in (
        "dungeon_context_active_policies",
        "dungeon_runtime_active_configurations",
    ):
        db.execute(
            "CREATE TABLE "
            + table
            + "(route_key text PRIMARY KEY,policy_version integer NOT NULL)"
        )


class NativeSceneInstallationExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NormalizedSceneAuthority.setUpClass.__func__(cls)

    def test_readonly_export_restores_four_typed_scenes_without_legacy_settings(self):
        authority = fixture.authority
        original133 = json.loads(
            (
                FIXTURES.parent / "tower_ground_entry/native_dungeon_133_v5.json"
            ).read_text()
        )
        configurations = [original133]
        configurations += [
            json.loads(
                gzip.decompress(
                    (FIXTURES / f"configuration-{identity}.json.gz").read_bytes()
                )
            )
            for identity in (13, 134, 164)
        ]
        with self.db.transaction():
            configuration_tables(self.db)
            self.db.execute("DELETE FROM dungeon_runtime_configurations")
            self.db.execute((SEEDS / "13.sql").read_text())
            for identity in (134, 164):
                self.db.execute((SEEDS / f"{identity}.sql").read_text())
            for config in configurations:
                key = config["route"]["key"]
                version = config["version"]
                self.db.execute(
                    "INSERT INTO dungeon_runtime_configurations VALUES(%s,%s,%s)",
                    (key, version, Jsonb(config)),
                )
                fields = exporter.CONTEXT_COLUMNS
                self.db.execute(
                    "INSERT INTO dungeon_context_policy_versions("
                    + ",".join(fields)
                    + ") VALUES("
                    + ",".join(["%s"] * len(fields))
                    + ")",
                    tuple(config["context_policy"][k] for k in fields),
                )
                for table in (
                    "dungeon_context_active_policies",
                    "dungeon_runtime_active_configurations",
                ):
                    self.db.execute(
                        "INSERT INTO " + table + " VALUES(%s,%s)", (key, version)
                    )
            self.db.execute(
                "INSERT INTO settings VALUES(%s,%s)",
                (
                    "dungeon_runtime_routes",
                    Jsonb(
                        dict(
                            schema_version=1,
                            routes=[c["route"] for c in configurations],
                        )
                    ),
                ),
            )
            self.db.execute(
                "UPDATE native_scene_start_receipts SET payment=%s",
                (Jsonb([dict(marker="private-payment-marker")]),),
            )
        with self.db.transaction():
            self.db.execute("SET TRANSACTION READ ONLY")
            tables = exporter.reviewed_dungeon_rows(self.db)
        self.assertEqual(len(tables["native_scene_policies"]), 4)
        self.assertNotIn("native_scene_start_receipts", tables)
        expected_rules = {
            row["policy_id"]: authority.read_policy(self.db, row["policy_id"])
            for row in tables["native_scene_policies"]
        }
        target = "scene_clean_" + uuid.uuid4().hex
        self.admin.execute("CREATE SCHEMA " + target)
        self.addCleanup(
            lambda: self.admin.execute("DROP SCHEMA " + target + " CASCADE")
        )
        url = os.environ["WAKFU_POSTGRES_TEST_URL"]
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        kwargs = (
            {}
            if password_file is None
            else dict(password=Path(password_file).read_text().strip())
        )
        fresh = psycopg.connect(
            make_conninfo(url, options="-c search_path=" + target),
            row_factory=dict_row,
            autocommit=True,
            **kwargs,
        )
        self.addCleanup(fresh.close)
        with fresh.transaction():
            fresh.execute(
                "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL)"
            )
            fresh.execute(
                "CREATE TABLE native_scene_start_receipts(instance_id bigint,source_id bigint,map_id integer,policy_id text,policy_sha256 text,policy jsonb,profile jsonb,payment jsonb,PRIMARY KEY(instance_id,source_id))"
            )
            fresh.execute(
                "CREATE TABLE dungeon_runtime_configurations(route_key text,policy_version integer,configuration jsonb,PRIMARY KEY(route_key,policy_version))"
            )
            configuration_tables(fresh)
            fresh.execute((fixture.MIGRATION).read_text())
            self.assertEqual(
                fresh.execute(
                    "SELECT count(*) AS n FROM native_scene_policies"
                ).fetchone()["n"],
                0,
            )
        sql = exporter.reviewed_dungeon_sql(tables, schema=target).decode()
        self.assertNotIn("private-payment-marker", sql)
        self.assertNotIn(target + ".native_scene_start_receipts", sql)
        fresh.execute(sql)
        for identity, expected in expected_rules.items():
            self.assertEqual(authority.read_policy(fresh, identity), expected)
        for config in configurations:
            self.assertEqual(
                authority.admission_policy(
                    fresh,
                    config["route"]["key"],
                    configuration_version=config["version"],
                ),
                authority.admission_policy(
                    self.db,
                    config["route"]["key"],
                    configuration_version=config["version"],
                ),
            )
        self.assertEqual(
            fresh.execute(
                "SELECT count(*) AS n FROM settings WHERE name IN ('native_scene_start_contracts','native_special_instance_admission')"
            ).fetchone()["n"],
            0,
        )
        legacy = authority.read_policy(fresh, self.identity)
        self.assertEqual(legacy, self.legacy)
        self.assertNotIn("reserve_spawn_slots", legacy["environment"])
        flags = {
            r["definition_id"]: r["environment_reserve_spawn_slots"]
            for r in fresh.execute(
                "SELECT definition_id,environment_reserve_spawn_slots FROM native_scene_policies"
            ).fetchall()
        }
        self.assertEqual(flags, {13: None, 133: None, 134: True, 164: True})
        with fresh.transaction():
            fresh.execute(
                "INSERT INTO native_scene_start_receipts VALUES(101,33366,1159,%s,%s,%s,%s,%s)",
                (
                    self.identity,
                    authority.digest(legacy),
                    Jsonb(legacy),
                    Jsonb(self.profile),
                    Jsonb([dict(marker="target-private-payment")]),
                ),
            )
            fresh.execute(
                "CREATE TABLE dungeon_instances(instance_id bigint PRIMARY KEY,context_policy_version integer)"
            )
            fresh.execute("INSERT INTO dungeon_instances VALUES(101,5)")
        before = fresh.execute("SELECT * FROM native_scene_start_receipts").fetchone()
        fresh.execute(sql)  # No INSERT attempt against sealed children on replay.
        self.assertEqual(
            fresh.execute("SELECT * FROM native_scene_start_receipts").fetchone(),
            before,
        )
        self.assertEqual(
            fresh.execute(
                "SELECT context_policy_version FROM dungeon_instances"
            ).fetchone()["context_policy_version"],
            5,
        )
        self.assertEqual(
            fixture.scene._receipt(
                fresh, 101, authority.read_policy(fresh, self.identity)
            ),
            before,
        )
        conflict = copy.deepcopy(tables)
        conflict["native_scene_policy_approaches"][0]["x"] += 1
        with self.assertRaises(psycopg.errors.RaiseException):
            fresh.execute(
                exporter.reviewed_dungeon_sql(conflict, schema=target).decode()
            )
        fresh.execute("ROLLBACK")
        self.assertEqual(
            fresh.execute("SELECT * FROM native_scene_start_receipts").fetchone(),
            before,
        )
        for identity, expected in expected_rules.items():
            self.assertEqual(authority.read_policy(fresh, identity), expected)


if __name__ == "__main__":
    unittest.main()
