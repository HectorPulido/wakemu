"""PostgreSQL gates for versioned dungeon configuration and atomic first spawn."""

import copy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import (
    combat_group_store,
    combat_terrain,
    dungeon_transport,
    player_parties,
)
from wakfu_server.maps import dungeon_runtime, dungeon_runtime_config


def selected_configuration():
    configured_path = os.environ.get("WAKFU_JALATO_RUNTIME_CONFIG_FIXTURE")
    path = (
        Path(configured_path)
        if configured_path
        else Path(__file__).resolve().parents[2]
        / "server/test-fixtures/dungeons/jalato-runtime-config-v1.json"
    )
    return json.loads(path.read_text(encoding="utf8"))


class DungeonRuntimeConfigurationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.config = selected_configuration()
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.config)

    def test_selected_config_install_is_immutable_and_idempotent(self):
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.config)
        with self.store.connection() as db:
            active = dungeon_runtime_config.active_configuration(db, "jalato_normal")
            setting_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_runtime_configurations "
                "WHERE route_key='jalato_normal' AND policy_version=1",
            ).fetchone()["n"]
            active_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_runtime_active_configurations "
                "WHERE route_key='jalato_normal' AND policy_version=1"
            ).fetchone()["n"]
            context_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_context_policy_versions "
                "WHERE route_key='jalato_normal' AND policy_version=1"
            ).fetchone()["n"]
        self.assertEqual(self.config, active)
        self.assertEqual((1, 1, 1), (setting_count, active_count, context_count))
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM settings "
                    "WHERE name LIKE 'dungeon_runtime_config:%' "
                    "OR name LIKE 'dungeon_runtime_active:%'"
                ).fetchone()["n"],
            )
            with self.assertRaises(Exception):
                with db.transaction():
                    db.execute(
                        "UPDATE dungeon_runtime_configurations "
                        "SET configuration=configuration || '{\"tampered\":true}'::jsonb "
                        "WHERE route_key='jalato_normal' AND policy_version=1"
                    )

    def test_conflicting_version_is_rejected_and_transaction_rolls_back(self):
        changed_plan = copy.deepcopy(self.config["compiled_plan"])
        changed_plan["rooms"][0]["monsters"][0]["count"] += 1
        conflict = dungeon_runtime_config.prepare_configuration(
            changed_plan,
            self.config["topology"],
            self.config["route"],
            version=1,
            provenance=self.config["provenance"],
        )
        with self.assertRaisesRegex(
            ValueError, "Existing configuration version is immutable"
        ):
            with self.store.connection() as db:
                dungeon_runtime_config.install_configuration(db, conflict)
        with self.store.connection() as db:
            active = dungeon_runtime_config.active_configuration(db, "jalato_normal")
        self.assertEqual(self.config, active)

        second_version = dungeon_runtime_config.prepare_configuration(
            self.config["compiled_plan"],
            self.config["topology"],
            self.config["route"],
            version=2,
            provenance="isolated PostgreSQL conflict fixture v2",
        )
        conflicting_context = dict(second_version["context_policy"])
        conflicting_context["allowed_ids"] = [999_999]
        fields = tuple(conflicting_context)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(" + ",".join(fields) + ") "
                "VALUES(" + ",".join(["%s"] * len(fields)) + ")",
                tuple(conflicting_context[field] for field in fields),
            )
        with self.assertRaisesRegex(
            ValueError, "Existing context policy version conflicts"
        ):
            with self.store.connection() as db:
                dungeon_runtime_config.install_configuration(db, second_version)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT configuration FROM dungeon_runtime_configurations "
                    "WHERE route_key='jalato_normal' AND policy_version=2",
                ).fetchone()
            )
            self.assertEqual(
                1,
                dungeon_runtime_config.active_configuration(db, "jalato_normal")[
                    "version"
                ],
            )

    def test_existing_run_stays_pinned_when_active_version_changes(self):
        members, party_id = self.party(2)
        session = self.create(members[0])
        self.assertEqual(1, session["context_policy_version"])
        second_version = dungeon_runtime_config.prepare_configuration(
            self.config["compiled_plan"],
            self.config["topology"],
            self.config["route"],
            version=2,
            provenance="isolated PostgreSQL active pointer update v2",
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, second_version)
            active = dungeon_runtime_config.active_configuration(db, "jalato_normal")
            run, pinned = dungeon_runtime.configuration_for_instance(
                db, session["instance_id"]
            )
        self.assertEqual(2, active["version"])
        self.assertEqual(1, run["context_policy_version"])
        self.assertEqual(1, pinned["version"])
        self.assertEqual(party_id, run["party_id"])

    def test_114_migrates_legacy_versions_and_pointer_without_touching_pinned_run(self):
        members, _party_id = self.party(2)
        session = self.create(members[0])
        self.assertEqual(1, session["context_policy_version"])
        version_two = dungeon_runtime_config.prepare_configuration(
            self.config["compiled_plan"],
            self.config["topology"],
            self.config["route"],
            version=2,
            provenance="pre-114 migration fixture version two",
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, version_two)
            db.execute(
                "DROP TRIGGER dungeon_runtime_configuration_immutable "
                "ON dungeon_runtime_configurations"
            )
            db.execute("DELETE FROM dungeon_runtime_active_configurations")
            db.execute("DELETE FROM dungeon_runtime_configurations")
            for config in (self.config, version_two):
                db.execute(
                    "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                    (
                        f"dungeon_runtime_config:jalato_normal:v{config['version']}",
                        json.dumps(config),
                    ),
                )
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                (
                    "dungeon_runtime_active:jalato_normal",
                    json.dumps(
                        {
                            "version": 2,
                            "key": "dungeon_runtime_config:jalato_normal:v2",
                        }
                    ),
                ),
            )
            migration = (
                Path(__file__).resolve().parents[1]
                / "migrations/114_dungeon_runtime_configuration_tables.sql"
            ).read_text(encoding="utf8")
            db.execute(migration)

        with self.store.connection() as db:
            versions = db.execute(
                "SELECT policy_version FROM dungeon_runtime_configurations "
                "WHERE route_key='jalato_normal' ORDER BY policy_version"
            ).fetchall()
            selected = db.execute(
                "SELECT policy_version FROM dungeon_runtime_active_configurations "
                "WHERE route_key='jalato_normal'"
            ).fetchone()
            legacy_count = db.execute(
                "SELECT count(*) AS n FROM settings "
                "WHERE name LIKE 'dungeon_runtime_config:%' "
                "OR name LIKE 'dungeon_runtime_active:%'"
            ).fetchone()["n"]
            run, pinned = dungeon_runtime.configuration_for_instance(
                db, session["instance_id"]
            )
            active = dungeon_runtime_config.active_configuration(db, "jalato_normal")
        self.assertEqual([1, 2], [row["policy_version"] for row in versions])
        self.assertEqual(2, selected["policy_version"])
        self.assertEqual(0, legacy_count)
        self.assertEqual(1, run["context_policy_version"])
        self.assertEqual(1, pinned["version"])
        self.assertEqual(2, active["version"])

    def test_114_malformed_legacy_rows_fail_without_deleting_source(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                ("dungeon_runtime_config:jalato_normal:v0", json.dumps(self.config)),
            )
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations/114_dungeon_runtime_configuration_tables.sql"
        ).read_text(encoding="utf8")
        with self.assertRaisesRegex(
            Exception, "Malformed legacy dungeon configuration key"
        ):
            with self.store.connection() as db:
                db.execute(migration)
        with self.store.connection() as db:
            malformed = db.execute(
                "SELECT value FROM settings "
                "WHERE name='dungeon_runtime_config:jalato_normal:v0'"
            ).fetchone()
            active = dungeon_runtime_config.active_configuration(db, "jalato_normal")
        self.assertIsNotNone(malformed)
        self.assertEqual(1, active["version"])

    def test_selected_config_initializes_first_group_inside_entry_transaction(self):
        members, _party_id = self.party(2)
        groups = combat_group_store.PersistentGroups(self.store)
        terrain = combat_terrain.map_geometry(1086)

        def initialize(db, session):
            return dungeon_runtime.initialize_instance(
                db, session, groups=groups, geometry=terrain
            )

        result = dungeon_transport.enter(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            527,
            struct.pack(">qiBi", 26842, 2504, 0, 2),
            criterion_allowed=lambda _character, _criterion: True,
            source_allowed=lambda _character, _source: True,
            initialize_instance=initialize,
        )
        instance_id = result["instance_id"]
        self.assertEqual(2, len(result["transition"]["members"]))
        with self.store.connection() as db:
            run = db.execute(
                "SELECT current_room,catalog_hash,status FROM dungeon_room_runs "
                "WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
            receipts = db.execute(
                "SELECT room_order,asset_map_id,group_id FROM dungeon_room_spawn_receipts "
                "WHERE instance_id=%s",
                (instance_id,),
            ).fetchall()
            groups_rows = db.execute(
                "SELECT map_id,instance_id,group_id,members,status FROM combat_groups "
                "WHERE instance_id=%s",
                (instance_id,),
            ).fetchall()
            entry_events = db.execute(
                "SELECT count(*) AS n FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND transition_kind='enter' AND status='pending'",
                (instance_id,),
            ).fetchone()["n"]
        self.assertEqual(
            (1, self.config["compiled_plan"]["document_sha256"], "active"),
            (run["current_room"], run["catalog_hash"], run["status"]),
        )
        self.assertEqual(1, len(receipts))
        self.assertEqual(
            (1, 1086), (receipts[0]["room_order"], receipts[0]["asset_map_id"])
        )
        self.assertEqual(1, len(groups_rows))
        self.assertEqual(
            (1086, instance_id, receipts[0]["group_id"], "available"),
            tuple(
                groups_rows[0][key]
                for key in ("map_id", "instance_id", "group_id", "status")
            ),
        )
        self.assertEqual(3, len(groups_rows[0]["members"]))
        self.assertEqual(2, entry_events)

    def test_spawn_failure_after_registration_rolls_back_entry_and_group(self):
        members, _party_id = self.party(2)
        groups = combat_group_store.PersistentGroups(self.store)
        terrain = combat_terrain.map_geometry(1086)

        def initialize_then_fail(db, session):
            dungeon_runtime.initialize_instance(
                db, session, groups=groups, geometry=terrain
            )
            raise RuntimeError("fail after initial group registration")

        with self.assertRaisesRegex(RuntimeError, "after initial group registration"):
            dungeon_transport.enter(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                527,
                struct.pack(">qiBi", 26842, 2504, 0, 2),
                criterion_allowed=lambda _character, _criterion: True,
                source_allowed=lambda _character, _source: True,
                initialize_instance=initialize_then_fail,
            )
        for member in members:
            character = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.assertEqual((527, 0), (character["map_id"], character["instance_id"]))
        with self.store.connection() as db:
            for table in (
                "dungeon_instances",
                "dungeon_room_runs",
                "dungeon_room_spawn_receipts",
                "combat_groups",
                "dungeon_transition_outbox",
            ):
                with self.subTest(table=table):
                    self.assertEqual(
                        0,
                        db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()[
                            "n"
                        ],
                    )

    def player(self):
        account = self.store.register("dr" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        suffix = "".join(
            chr(ord("a") + int(value, 16)) for value in uuid.uuid4().hex[:9]
        )
        character = self.store.create_character(account, "Drt" + suffix)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 WHERE id=%s",
                (character["id"],),
            )
        return {"account": account, "generation": generation, "character": character}

    def party(self, count):
        members = [self.player() for _ in range(count)]
        party_id = None
        for member in members[1:]:
            token = player_parties.invite(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                member["character"]["id"],
            )
            party_id = player_parties.answer(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                token,
                True,
            )
        return members, party_id

    def create(self, leader):
        from wakfu_server import dungeon_instances

        return dungeon_instances.create_or_reuse(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            "jalato_normal",
            authorize_entry=lambda _character, _route: True,
        )


class DungeonRuntimeConfigurationMigrationPostgresTests(PostgresCase):
    """Apply migration 114 over an actual isolated schema stopped at 113."""

    def setUp(self):
        migration_source = Path(__file__).resolve().parents[1] / "migrations"
        with tempfile.TemporaryDirectory(prefix="wakemu-migrations-113-") as directory:
            migration_target = Path(directory)
            for migration in migration_source.glob("*.sql"):
                if migration.name[:3].isdigit() and int(migration.name[:3]) <= 113:
                    (migration_target / migration.name).symlink_to(migration)
            prior = os.environ.get("WAKFU_MIGRATIONS_TEST_DIR")
            os.environ["WAKFU_MIGRATIONS_TEST_DIR"] = directory
            try:
                super().setUp()
            finally:
                if prior is None:
                    os.environ.pop("WAKFU_MIGRATIONS_TEST_DIR", None)
                else:
                    os.environ["WAKFU_MIGRATIONS_TEST_DIR"] = prior
        self.config = selected_configuration()
        self.migration_sql = (
            migration_source / "114_dungeon_runtime_configuration_tables.sql"
        ).read_text(encoding="utf8")

    def version(self, number):
        return dungeon_runtime_config.prepare_configuration(
            self.config["compiled_plan"],
            self.config["topology"],
            self.config["route"],
            version=number,
            provenance=f"pre-114 migration test configuration v{number}",
        )

    def test_114_copies_every_version_and_active_pointer_and_preserves_pinned_run(self):
        from wakfu_server.maps import dungeon_instances

        config_one = self.version(1)
        config_two = self.version(2)
        account = self.store.register("mig" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        suffix = "".join(
            chr(ord("a") + int(value, 16)) for value in uuid.uuid4().hex[:9]
        )
        character = self.store.create_character(account, "Mig" + suffix)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])

        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT to_regclass('dungeon_runtime_configurations') AS name"
                ).fetchone()["name"]
            )
            context_rows = [config_one["context_policy"], config_two["context_policy"]]
            for context in context_rows:
                fields = tuple(context)
                db.execute(
                    "INSERT INTO dungeon_context_policy_versions("
                    + ",".join(fields)
                    + ") "
                    "VALUES(" + ",".join(["%s"] * len(fields)) + ")",
                    tuple(context[field] for field in fields),
                )
            db.execute(
                "INSERT INTO dungeon_context_active_policies(route_key,policy_version) "
                "VALUES(%s,2)",
                (config_two["route"]["key"],),
            )
            for config in (config_one, config_two):
                db.execute(
                    "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                    (
                        f"dungeon_runtime_config:{config['route']['key']}:v{config['version']}",
                        json.dumps(config),
                    ),
                )
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                (
                    f"dungeon_runtime_active:{config_one['route']['key']}",
                    json.dumps(
                        {
                            "version": 2,
                            "key": f"dungeon_runtime_config:{config_one['route']['key']}:v2",
                        }
                    ),
                ),
            )
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party_id),
            )
            route = config_one["route"]
            instance_id = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                "start_map_id,context_route_key,context_policy_version) "
                "VALUES(%s,1,%s,%s,%s,%s,%s,%s,%s,%s,1) RETURNING instance_id",
                (
                    party_id,
                    character["id"],
                    route["template_id"],
                    route["definition_id"],
                    route["entry_map_id"],
                    route["entry_object_id"],
                    route["destination_id"],
                    route["start_map_id"],
                    route["key"],
                ),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                (instance_id, party_id, character["id"], generation),
            )
            db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms) "
                "VALUES(%s,%s,%s,%s::jsonb)",
                (
                    instance_id,
                    party_id,
                    config_one["compiled_plan"]["document_sha256"],
                    json.dumps(config_one["compiled_plan"]["rooms"]),
                ),
            )

        with self.store.connection() as db:
            db.execute(self.migration_sql)

        with self.store.connection() as db:
            versions = db.execute(
                "SELECT policy_version,configuration FROM dungeon_runtime_configurations "
                "WHERE route_key=%s ORDER BY policy_version",
                (config_one["route"]["key"],),
            ).fetchall()
            active = db.execute(
                "SELECT policy_version FROM dungeon_runtime_active_configurations "
                "WHERE route_key=%s",
                (config_one["route"]["key"],),
            ).fetchone()
            legacy_count = db.execute(
                "SELECT count(*) AS n FROM settings "
                "WHERE starts_with(name,'dungeon_runtime_config:') "
                "OR starts_with(name,'dungeon_runtime_active:')"
            ).fetchone()["n"]
            instance = db.execute(
                "SELECT context_route_key,context_policy_version,status "
                "FROM dungeon_instances WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
            run = db.execute(
                "SELECT current_room,catalog_hash,status FROM dungeon_room_runs "
                "WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
            pinned = dungeon_runtime_config.pinned_configuration(
                db, config_one["route"]["key"], instance["context_policy_version"]
            )
            selected = dungeon_runtime_config.active_configuration(
                db, config_one["route"]["key"]
            )

        self.assertEqual([1, 2], [row["policy_version"] for row in versions])
        self.assertEqual(
            [config_one, config_two], [row["configuration"] for row in versions]
        )
        self.assertEqual(2, active["policy_version"])
        self.assertEqual(0, legacy_count)
        self.assertEqual(
            (config_one["route"]["key"], 1, "active"), tuple(instance.values())
        )
        self.assertEqual(
            (1, config_one["compiled_plan"]["document_sha256"], "active"),
            tuple(run.values()),
        )
        self.assertEqual(1, pinned["version"])
        self.assertEqual(2, selected["version"])

    def test_malformed_legacy_key_rolls_back_migration_and_preserves_source(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                ("dungeon_runtime_config:bad:v0", "{}"),
            )
        with self.assertRaisesRegex(
            Exception, "Malformed legacy dungeon configuration key"
        ):
            with self.store.connection() as db:
                db.execute(self.migration_sql)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT to_regclass('dungeon_runtime_configurations') AS name"
                ).fetchone()["name"]
            )
            row = db.execute(
                "SELECT value FROM settings WHERE name='dungeon_runtime_config:bad:v0'"
            ).fetchone()
        self.assertIsNotNone(row)
