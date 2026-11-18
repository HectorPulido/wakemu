"""SQL lifecycle proves Ullu v2 exit, native completion and ordinary return."""

from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from hashlib import sha256
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import owned_cinematic_continuations as cinematic
from wakfu_server.achievements import storage


class OwnedCinematicV2PostgresTests(PostgresCase):
    def test_native986_stage_advances5309_once_and_returns_through_pinned_exit(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/native_quest_2689_cinematic.json"
            ).read_text()
        )
        definition = fixture["definition"]
        profile_path = cinematic.ROOT / "zinit-ullu-986.v2.json"
        pointer = {
            "path": profile_path.name,
            "sha256": sha256(profile_path.read_bytes()).hexdigest(),
        }
        account = self.store.register("ullu-v2-flow", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Ullu Voyage")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        start_time = self.store.clock()
        self.store.clock = lambda: start_time

        with self.store.connection() as db:
            party = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party),
            )
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,"
                "definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                "VALUES(%s,1,%s,987,987,987,25395,2234,987) RETURNING instance_id",
                (party, character["id"]),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,"
                "party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                (run, party, character["id"], generation),
            )
            db.execute(
                "UPDATE characters SET map_id=987,instance_id=%s,x=-10,y=-10,z=0 WHERE id=%s",
                (run, character["id"]),
            )
            revision = "c" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
                "VALUES(%s,%s,%s,1)",
                (
                    revision,
                    Jsonb({"fixture": revision}),
                    b"native 2689 cinematic fixture",
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                "VALUES(%s,2689,%s)",
                (revision, Jsonb({"native": definition})),
            )
            state = storage.load_locked(db, character["id"])
            state["completed"] = sorted(set(state["completed"]) | {2688})
            state["completion_dates"]["2688"] = int(start_time * 1000)
            state["running"] = [2689]
            state["active"] = [2689]
            state["objectives"] = [5308]
            state["tracking"] = [2689]
            storage.store(db, character["id"], state)

        from wakfu_server import dungeon_instances

        controller = {"cinematic_continuation": pointer}
        body = struct.pack(">qiBi", 25395, 2234, 0, 2)
        with patch(
            "wakfu_server.owned_story_exits.authenticate_exit",
            return_value={
                "controller": controller,
                "completed_steps": {"cave-authenticated-exit"},
            },
        ):
            with self.store.connection() as db:
                entered = cinematic.begin(
                    db,
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    source_allowed=lambda *_args: True,
                    in_fight=lambda _identity: False,
                )
        self.assertEqual(
            (entered["map_id"], entered["x"], entered["y"], entered["z"]),
            (986, -6, -8, 0),
        )
        self.assertEqual(
            entered["instance_id"], cinematic.stage_instance_id(character["id"])
        )
        transition = dungeon_instances.pending_transitions(
            self.store, account, generation, character["id"]
        )[0]
        self.assertTrue(
            dungeon_instances.acknowledge_transition(
                self.store, account, generation, character["id"], transition["event_id"]
            )
        )

        with self.store.connection() as db:
            ready = cinematic.ready(
                db, self.store, account, generation, character["id"]
            )
            self.assertEqual(ready["due_ms"], int(start_time * 1000) + 40500)
            self.assertEqual(
                ready["packets"],
                [
                    cinematic.packet(
                        cinematic.policy(controller), 16087, character["id"]
                    )
                ],
            )
            reconnect = cinematic.ready(
                db, self.store, account, generation, character["id"]
            )
            self.assertEqual(reconnect, {"packets": [], "due_ms": ready["due_ms"]})

        self.store.clock = lambda: start_time + 40.5
        with self.store.connection() as db:
            finished = cinematic.finish(
                db, self.store, account, generation, character["id"]
            )
            self.assertEqual((finished["map_id"], finished["instance_id"]), (986, 0))
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5309, progress["objectives"])
            self.assertIn(2689, progress["completed"])
            self.assertIsNone(
                cinematic.finish(db, self.store, account, generation, character["id"])
            )
            self.assertIsNone(
                cinematic.ready(db, self.store, account, generation, character["id"])
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key=%s",
                    (
                        character["id"],
                        cinematic._key(cinematic.policy(controller), "objective"),
                    ),
                ).fetchone()["n"],
                1,
            )
            outbox = db.execute(
                "SELECT * FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending'",
                (character["id"],),
            ).fetchone()
            self.assertEqual(
                (
                    outbox["source_map_id"],
                    outbox["source_instance_id"],
                    outbox["destination_map_id"],
                    outbox["destination_instance_id"],
                ),
                (986, cinematic.stage_instance_id(character["id"]), 986, 0),
            )
            membership = db.execute(
                "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                (run, character["id"]),
            ).fetchone()
            self.assertEqual(membership["status"], "returned")

        again = dungeon_instances.pending_transitions(
            self.store, account, generation, character["id"]
        )
        self.assertEqual(len(again), 1)
        self.assertTrue(
            dungeon_instances.acknowledge_transition(
                self.store, account, generation, character["id"], again[0]["event_id"]
            )
        )
