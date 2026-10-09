"""PostgreSQL gates for versioned dungeon configuration and atomic first spawn."""

import copy
import json
import os
from pathlib import Path
import struct
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
                "SELECT count(*) AS n FROM settings WHERE name=%s",
                ("dungeon_runtime_config:jalato_normal:v1",),
            ).fetchone()["n"]
            context_count = db.execute(
                "SELECT count(*) AS n FROM dungeon_context_policy_versions "
                "WHERE route_key='jalato_normal' AND policy_version=1"
            ).fetchone()["n"]
        self.assertEqual(self.config, active)
        self.assertEqual((1, 1), (setting_count, context_count))

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
                    "SELECT value FROM settings WHERE name=%s",
                    ("dungeon_runtime_config:jalato_normal:v2",),
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
