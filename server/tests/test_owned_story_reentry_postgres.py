"""Isolated paid-story restoration keeps its original instance and fee receipt."""

import json
from pathlib import Path
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import (
    dungeon_instances,
    dungeon_transport,
    generic_transports,
    owned_story_controller,
)
from wakfu_server.achievements import storage
from wakfu_server.items import quest_inventory
from wakfu_server.maps import dungeon_exit
from wakfu_server.maps.dungeon_instances import EntryRoute
from wakfu_server.maps import dungeon_progression, dungeon_runtime_config


ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps"


class OwnedStoryPaidReentryPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.camp = json.loads(
            (
                ROOT / "quest_encounter_profiles/astrub-grambo-camp.configuration.json"
            ).read_text()
        )
        self.temple = json.loads(
            (
                ROOT / "owned_story_profiles/astrub-temple-887.configuration.json"
            ).read_text()
        )

    def _install(self, db, config):
        context = config["context_policy"]
        db.execute(
            "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) "
            "VALUES(%s,%s,%s)",
            (config["route"]["key"], config["version"], Jsonb(config)),
        )
        fields = tuple(context)
        db.execute(
            "INSERT INTO dungeon_context_policy_versions("
            + ",".join(fields)
            + ") VALUES("
            + ",".join(["%s"] * len(fields))
            + ")",
            tuple(context[field] for field in fields),
        )
        db.execute(
            "INSERT INTO dungeon_context_active_policies(route_key,policy_version) VALUES(%s,%s) "
            "ON CONFLICT(route_key) DO UPDATE SET policy_version=EXCLUDED.policy_version",
            (config["route"]["key"], config["version"]),
        )
        db.execute(
            "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version) VALUES(%s,%s) "
            "ON CONFLICT(route_key) DO UPDATE SET policy_version=EXCLUDED.policy_version",
            (config["route"]["key"], config["version"]),
        )

    @staticmethod
    def _entry_route(config):
        row = config["route"]
        return EntryRoute(
            key=row["key"],
            template_id=row["template_id"],
            definition_id=row["definition_id"],
            entry_map_id=row["entry_map_id"],
            entry_object_id=row["entry_object_id"],
            destination_id=row["destination_id"],
            start_map_id=row["start_map_id"],
            criterion=row["criterion"],
            native_template_id=row.get("native_template_id"),
        )

    def _add_room_run(self, db, instance_id, config, *, status="active"):
        party_id = db.execute(
            "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()["party_id"]
        plan = dungeon_runtime_config.plan_from_configuration(config)
        dungeon_progression.initialize_run(db, instance_id, party_id, plan)
        if status == "completed":
            rooms = db.execute(
                "SELECT rooms FROM dungeon_room_runs WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()["rooms"]
            db.execute(
                "UPDATE dungeon_room_runs SET status='completed',current_room=%s WHERE instance_id=%s",
                (len(rooms), instance_id),
            )

    def _install_active_v2(self, db):
        config = dungeon_runtime_config.prepare_configuration(
            self.temple["compiled_plan"],
            self.temple["topology"],
            self.temple["route"],
            version=2,
            provenance=self.temple["provenance"],
            level_policy=self.temple["level_policy"],
        )
        self._install(db, config)
        return config

    def test_paid_native_run_restores_same_closed_instance_then_reenters_without_second_fee(
        self,
    ):
        account = self.store.register("story-reentry-test", "isolated-password")["id"]
        character = self.store.create_character(account, "Story Reentry")
        generation = self.store.begin_session(account, ttl=10000)
        character = self.store.select_character(account, generation, character["id"])
        character_id = character["id"]
        body = struct.pack(">qiBi", 23621, 4029, 0, 2)
        source = generic_transports.source(747, 23621)
        self.assertIsNotNone(source)
        self.assertEqual(
            next(
                row for row in source["destinations"] if row["destination_id"] == 4029
            )["item_reference"],
            18747,
        )
        route = self._entry_route(self.temple)

        with self.store.connection() as db:
            self._install(db, self.camp)
            self._install(db, self.temple)
            db.execute(
                "UPDATE characters SET map_id=747,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (source["x"], source["y"], source["z"], character_id),
            )
            state = storage.load_locked(db, character_id)
            state["running"] = [2166]
            state["completed"] = []
            storage.store(db, character_id, state)
            quest_inventory.grant(db, character_id, 18747, 1)

        admission = self.temple["topology"]["owned_story_controller"]["admission"]

        def story_entry_fixture(db, session, _resolved, *, store):
            if session.get("reused"):
                return
            storage.record_event(
                db,
                character_id,
                f'owned-story-entry:{session["instance_id"]}:{admission["quest_id"]}',
                dict(
                    schema="owned-quest-instance-v1",
                    quest_id=admission["quest_id"],
                    objective_id=admission["objective_id"],
                    instance_id=session["instance_id"],
                    route_key=route.key,
                ),
            )

        room_sessions = []

        def initialize_room(db, session):
            room_sessions.append(bool(session["reused"]))
            exists = db.execute(
                "SELECT 1 FROM dungeon_room_runs WHERE instance_id=%s",
                (session["instance_id"],),
            ).fetchone()
            if exists is None:
                self._add_room_run(db, session["instance_id"], self.temple)

        routes = {route.key: route}
        with patch.object(dungeon_instances, "_ROUTES", routes), patch.object(
            owned_story_controller, "initialize", side_effect=story_entry_fixture
        ):
            first = dungeon_transport._enter(
                self.store,
                account,
                generation,
                character_id,
                747,
                body,
                criterion_allowed=lambda *_: True,
                source_allowed=lambda actor, native: (
                    actor["map_id"] == 747
                    and actor["instance_id"] == 0
                    and native["id"] == 23621
                ),
                initialize_instance=initialize_room,
            )
            original_id = first["instance_id"]
            with self.store.connection() as db:
                quantity = db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=18747",
                    (character_id,),
                ).fetchone()
                self.assertIsNone(quantity)
                original_room = db.execute(
                    "SELECT rooms,current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (original_id,),
                ).fetchone()
                db.execute(
                    "UPDATE dungeon_room_runs SET status='completed',current_room=%s WHERE instance_id=%s",
                    (len(original_room["rooms"]), original_id),
                )
                state = storage.load_locked(db, character_id)
                state["running"] = []
                state["completed"] = [2166, 2170]
                storage.store(db, character_id, state)

            # Return the genuinely paid run through the normal durable leave
            # transaction; this creates the owner-bound exit witness.
            dungeon_exit._leave(
                self.store,
                account,
                generation,
                character_id,
                in_fight=lambda _: False,
                destination_for=lambda *_: dict(
                    map_id=747, x=source["x"], y=source["y"], z=source["z"]
                ),
            )

            # A completed camp encounter and its earned native objective are a
            # controlled main-story fixture; no fake combat or reward is run.
            with self.store.connection() as db:
                state = storage.load_locked(db, character_id)
                state["objectives"] = [4298]
                state["completed"] = sorted(
                    set(state["completed"]) | {2165, 2166, 2170}
                )
                storage.store(db, character_id, state)
                party_id = db.execute(
                    "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                    (character_id,),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (character_id, party_id),
                )
                camp_run = db.execute(
                    "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                    "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                    "start_map_id,context_route_key,context_policy_version) "
                    "VALUES(%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
                    (
                        party_id,
                        character_id,
                        self.camp["route"]["template_id"],
                        self.camp["route"]["definition_id"],
                        self.camp["route"]["entry_map_id"],
                        self.camp["route"]["entry_object_id"],
                        self.camp["route"]["destination_id"],
                        self.camp["route"]["start_map_id"],
                        self.camp["route"]["key"],
                        self.camp["version"],
                    ),
                ).fetchone()["instance_id"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                    "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                    (camp_run, party_id, character_id, generation),
                )
                self._add_room_run(db, camp_run, self.camp, status="completed")
                db.execute(
                    "UPDATE characters SET map_id=747,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (camp_run, source["x"], source["y"], source["z"], character_id),
                )
                temple_v2 = self._install_active_v2(db)
                self.assertEqual(temple_v2["version"], 2)

            restored = __import__(
                "wakfu_server.owned_quest_transfers", fromlist=["transfer"]
            ).transfer(
                self.store,
                account,
                generation,
                character_id,
                body,
                source_allowed=lambda actor, native: (
                    actor["map_id"] == 747 and native["id"] == 23621
                ),
                criterion_allowed=lambda *_: True,
                in_fight=lambda _: False,
                initialize_instance=initialize_room,
            )
            self.assertEqual(restored["instance_id"], original_id)
            self.assertTrue(restored["reused"])
            self.assertEqual(room_sessions, [False, True])
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT status,context_route_key,context_policy_version FROM dungeon_instances WHERE instance_id=%s",
                    (original_id,),
                ).fetchone()
                active = db.execute(
                    "SELECT policy_version FROM dungeon_runtime_active_configurations WHERE route_key=%s",
                    (self.temple["route"]["key"],),
                ).fetchone()
                room = db.execute(
                    "SELECT status,rooms,current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (original_id,),
                ).fetchone()
                events = db.execute(
                    "SELECT event_key,payload FROM character_achievement_events WHERE character_id=%s AND event_key LIKE %s ORDER BY event_key",
                    (character_id, f"owned-story-entry:{original_id}:%"),
                ).fetchall()
                self.assertEqual(row["status"], "active")
                self.assertEqual(row["context_route_key"], self.temple["route"]["key"])
                self.assertEqual(row["context_policy_version"], self.temple["version"])
                self.assertEqual(active["policy_version"], 2)
                self.assertEqual(room["rooms"], original_room["rooms"])
                self.assertEqual(room["current_room"], len(original_room["rooms"]))
                self.assertEqual(len(events), 1)
                self.assertEqual(
                    db.execute(
                        "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=18747",
                        (character_id,),
                    ).fetchone(),
                    None,
                    "reused native entry must not consume another portal fee",
                )

            # Normal exit and subsequent selection must leave no stale party.
            dungeon_exit._leave(
                self.store,
                account,
                generation,
                character_id,
                in_fight=lambda _: False,
                destination_for=lambda *_: dict(
                    map_id=747, x=source["x"], y=source["y"], z=source["z"]
                ),
            )
        alternate = self.store.create_character(account, "StoryAlternate")
        self.store.select_character(account, generation, alternate["id"])
        selected = self.store.select_character(account, generation, character_id)
        self.assertEqual(selected["instance_id"], 0)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM player_party_members WHERE character_id=%s",
                    (character_id,),
                ).fetchone()
            )
