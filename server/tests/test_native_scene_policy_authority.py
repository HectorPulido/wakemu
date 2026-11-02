"""Normalized policy upgrade compatibility; dedicated isolated test schema only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from postgres_case import isolated_test_url

ROOT = Path(__file__).resolve().parent
REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures/native_scene_authority"
MIGRATION = REPOSITORY / "server/migrations/348_native_scene_policy_authority.sql"
SEEDS = REPOSITORY / "server/data/installation/source/native-scene-policies"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


from wakfu_server import native_scene_policy_authority as authority
from wakfu_server import native_scene_start as scene

legacy_scene = load("_legacy133_scene_projection", FIXTURES / "legacy133_scene_room.py")


class NormalizedSceneAuthority(unittest.TestCase):
    publish_legacy_admission = True

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("WAKFU_POSTGRES_TEST_URL"):
            raise unittest.SkipTest("Explicit isolated PostgreSQL database required")
        url = isolated_test_url()
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        kwargs = (
            {}
            if password_file is None
            else dict(password=Path(password_file).read_text().strip())
        )
        cls.admin = psycopg.connect(url, autocommit=True, **kwargs)
        cls.addClassCleanup(cls.admin.close)
        # This fixture models a pre-348 database, independently of PostgresCase.
        # Run only migration348 once in this new schema; never use the full migrator.
        cls.schema = "scene_authority_" + uuid.uuid4().hex
        cls.admin.execute("CREATE SCHEMA " + cls.schema)
        cls.addClassCleanup(
            lambda: cls.admin.execute("DROP SCHEMA " + cls.schema + " CASCADE")
        )
        cls.db = psycopg.connect(
            make_conninfo(url, options="-c search_path=" + cls.schema),
            row_factory=dict_row,
            autocommit=True,
            **kwargs
        )
        cls.addClassCleanup(cls.db.close)
        cls.document = json.loads((FIXTURES / "legacy133-policy.json").read_text())
        cls.legacy = cls.document["policies"][0]
        cls.admission_document = json.loads(
            (FIXTURES / "legacy133-admission.json").read_text()
        )
        cls.admission = cls.admission_document["routes"]["native_dungeon_133"]
        cls.identity = cls.legacy["policy_id"]
        cls.profile = dict(
            schema="reconstructed_native_binary_scene_profile_v1",
            choice=5,
            native_states=[
                dict(id=5279, level=2),
                dict(id=5280, level=1),
                dict(id=5281, level=2),
            ],
        )
        with cls.db.transaction():
            cls.db.execute(
                "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL)"
            )
            cls.db.execute(
                "CREATE TABLE native_scene_start_receipts(instance_id bigint,source_id bigint,map_id integer,policy_id text,policy_sha256 text,policy jsonb,profile jsonb,payment jsonb,PRIMARY KEY(instance_id,source_id))"
            )
            cls.db.execute(
                "CREATE TABLE dungeon_runtime_configurations(route_key text,policy_version integer,configuration jsonb,PRIMARY KEY(route_key,policy_version))"
            )
            cls.db.execute(
                "INSERT INTO settings VALUES(%s,%s)",
                ("native_scene_start_contracts", Jsonb(cls.document)),
            )
            if getattr(cls, "publish_legacy_admission", True):
                cls.db.execute(
                    "INSERT INTO settings VALUES(%s,%s)",
                    (
                        "native_special_instance_admission",
                        Jsonb(cls.admission_document),
                    ),
                )
            cls.db.execute(
                "INSERT INTO native_scene_start_receipts VALUES(101,33366,1159,%s,%s,%s,%s,%s)",
                (
                    cls.identity,
                    authority.digest(cls.legacy),
                    Jsonb(cls.legacy),
                    Jsonb(cls.profile),
                    Jsonb([dict(item_ref=28028, quantity=1, fixture=True)]),
                ),
            )
            cls.receipt = cls.db.execute(
                "SELECT * FROM native_scene_start_receipts"
            ).fetchone()
            cls.db.execute(
                "INSERT INTO dungeon_runtime_configurations VALUES(%s,5,%s)",
                (
                    "native_dungeon_133",
                    Jsonb(
                        dict(
                            topology=dict(
                                native_scene_start=dict(
                                    policy_id=cls.identity, source_id=33366
                                )
                            )
                        )
                    ),
                ),
            )
            cls.db.execute((MIGRATION).read_text())

    def test_legacy_policy_admission_and_receipt_remain_exact(self):
        with self.db.transaction():
            normalized = authority.read_policy(self.db, self.identity)
            self.assertEqual(normalized, self.legacy)
            self.assertEqual(
                authority.digest(normalized),
                "693a6bef35d211ec8d7f7749952e005f860f50660b7a9c64ab3fe5320c7c51b6",
            )
            stored = self.db.execute(
                "SELECT environment_reserve_spawn_slots FROM native_scene_policies WHERE policy_id=%s",
                (self.identity,),
            ).fetchone()
            self.assertIsNone(stored["environment_reserve_spawn_slots"])
            self.assertNotIn("reserve_spawn_slots", normalized["environment"])
            room = dict(
                order=1,
                cells=copy.deepcopy(self.legacy["combat_cells"]),
                anchor=list(self.legacy["combat_anchor"]),
            )
            for started in (False, True):
                topology = dict(
                    asset_map_id=1159,
                    native_scene_start=dict(policy_id=self.identity, source_id=33366),
                    _native_scene_started=started,
                    _native_scene_profile=copy.deepcopy(self.profile)
                    if started
                    else None,
                )
                with self.subTest(started=started), patch.object(
                    legacy_scene, "binding", return_value=self.legacy, create=True
                ), patch.object(scene, "binding", return_value=normalized):
                    before = legacy_scene.scene_room(topology, copy.deepcopy(room))
                    after = scene.scene_room(topology, copy.deepcopy(room))
                    self.assertEqual(after, before)
                    self.assertNotIn("native_initial_spawn_cells", after)
                    self.assertNotIn(
                        "native_initial_spawn_cells", after.get("encounter_scene", {})
                    )

            self.assertEqual(
                authority.admission_policy(
                    self.db, "native_dungeon_133", configuration_version=5
                ),
                self.admission,
            )
            self.assertEqual(scene._receipt(self.db, 101, normalized), self.receipt)
            self.assertEqual(
                self.db.execute(
                    "SELECT value FROM settings WHERE name=%s",
                    ("native_scene_start_contracts",),
                ).fetchone()["value"],
                self.document,
            )
            published = self.db.execute(
                "SELECT value FROM settings WHERE name=%s",
                ("native_special_instance_admission",),
            ).fetchone()
            if getattr(self, "publish_legacy_admission", True):
                self.assertEqual(published["value"], self.admission_document)
            else:
                self.assertIsNone(published)

    def test_published_parent_and_children_reject_mutation(self):
        statements = [
            (
                "UPDATE native_scene_policies SET price_quantity=2 WHERE policy_id=%s",
                (self.identity,),
            ),
            (
                "DELETE FROM native_scene_policy_objects WHERE policy_id=%s",
                (self.identity,),
            ),
            (
                "INSERT INTO native_scene_profile_state_levels VALUES(%s,1,3,3)",
                (self.identity,),
            ),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(
                    psycopg.errors.RaiseException
                ), self.db.transaction():
                    self.db.execute(sql, params)
        self.assertEqual(authority.read_policy(self.db, self.identity), self.legacy)

    def test_additive_versions_resolve_only_the_pinned_scene(self):
        changed = copy.deepcopy(self.legacy)
        changed["policy_id"] += ":isolated-v2"
        admission = copy.deepcopy(self.admission)
        admission["policy_id"] += ":isolated-v2"
        admission["minimum_configuration_version"] = 6
        with self.db.transaction():
            sql = (FIXTURES / "legacy133-v2.sql").read_text()
            self.db.execute(sql)
            self.db.execute(sql)  # An identical data seed is idempotent.
            self.db.execute(
                "INSERT INTO dungeon_runtime_configurations VALUES(%s,6,%s)",
                (
                    "native_dungeon_133",
                    Jsonb(
                        dict(
                            topology=dict(
                                native_scene_start=dict(
                                    policy_id=changed["policy_id"], source_id=33366
                                )
                            )
                        )
                    ),
                ),
            )
            self.assertEqual(
                authority.admission_policy(
                    self.db, "native_dungeon_133", configuration_version=5
                ),
                self.admission,
            )
            self.assertEqual(
                authority.admission_policy(
                    self.db, "native_dungeon_133", configuration_version=6
                ),
                admission,
            )
            self.assertEqual(
                authority.read_policy(self.db, changed["policy_id"]), changed
            )
            self.assertEqual(
                scene._receipt(
                    self.db, 101, authority.read_policy(self.db, self.identity)
                ),
                self.receipt,
            )
            self.db.execute((SEEDS / "13.sql").read_text())
            trool = json.loads((FIXTURES / "trool13-policy.json").read_text())
            trool_admission = json.loads(
                (FIXTURES / "trool13-admission.json").read_text()
            )
            self.assertEqual(authority.read_policy(self.db, trool["policy_id"]), trool)
            self.assertEqual(
                authority.admission_policy(
                    self.db, "native_dungeon_13", policy_id=trool["policy_id"]
                ),
                trool_admission,
            )
            self.assertEqual(authority.read_policy(self.db, self.identity), self.legacy)
            self.assertEqual(len(authority.rules(self.db)), 3)


class AbsentLegacyAdmissionMigration(unittest.TestCase):
    """Actual B3 state: scene publication exists, outer-admission key is absent."""

    publish_legacy_admission = False

    @classmethod
    def setUpClass(cls):
        NormalizedSceneAuthority.setUpClass.__func__(cls)

    def test_absent_setting_converts_attested_source_without_publishing_json(self):
        NormalizedSceneAuthority.test_legacy_policy_admission_and_receipt_remain_exact(
            self
        )
        row = self.db.execute(
            "SELECT admission_sha256 FROM native_scene_admission_policies WHERE policy_id=%s",
            (self.identity,),
        ).fetchone()
        self.assertEqual(
            row["admission_sha256"],
            "affab21db7c0e259e68458d8919dbf3810eb6581f9caaf7548ae1abd8249bce7",
        )

    def test_present_invalid_admission_is_rejected_without_source_fallback(self):
        schema = "scene_invalid_" + uuid.uuid4().hex
        with self.assertRaisesRegex(
            psycopg.errors.RaiseException, "Legacy outer admission differs"
        ), self.db.transaction():
            self.db.execute("CREATE SCHEMA " + schema)
            self.db.execute("SET LOCAL search_path TO " + schema)
            self.db.execute(
                "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL)"
            )
            self.db.execute(
                "CREATE TABLE native_scene_start_receipts(instance_id bigint)"
            )
            changed = copy.deepcopy(self.admission_document)
            changed["routes"]["native_dungeon_133"]["maximum_members"] = 4
            self.db.execute(
                "INSERT INTO settings VALUES(%s,%s),(%s,%s)",
                (
                    "native_scene_start_contracts",
                    Jsonb(self.document),
                    "native_special_instance_admission",
                    Jsonb(changed),
                ),
            )
            self.db.execute(MIGRATION.read_text())
        self.assertEqual(authority.read_policy(self.db, self.identity), self.legacy)


if __name__ == "__main__":
    unittest.main()
