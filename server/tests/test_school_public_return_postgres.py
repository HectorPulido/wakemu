"""Focused SQL coverage for reviewed Huppermage public returns."""

import json
import struct
from pathlib import Path
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import quest_npc

ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ROOT / "wakfu_server/achievements/conversation_archetypes"


class SchoolPairedPublicReturnPostgresTests(PostgresCase):
    def test_native_jang_choice_uses_actual_session_and_atomic_public_transition(self):
        source_doc = json.loads(
            (ARCHETYPES / "huppermage_school_return.json").read_text()
        )
        source_speaker = source_doc["speakers"][0]
        initial = json.loads(
            (ARCHETYPES / "huppermage_school_initial_contracts.json").read_text()
        )
        target = next(
            row
            for row in initial["placements"]
            if row["row"]["actor_id"] == -2251799934952773
        )
        source = dict(source_speaker["placement"])
        source.update(
            objectives=source_speaker.get("objectives", []),
            graph=source_speaker["graph"],
            choice_paired_arrivals=source_speaker["choice_paired_arrivals"],
        )
        document = dict(
            schema="native-story-conversations-v1",
            evidence=source_doc["evidence"],
            placements=[source, target],
            bindings=[],
            turnins=[],
        )
        published = (document, {}, {})
        account = self.store.register("school-paired-return", "isolated-test-password")[
            "id"
        ]
        character = self.store.create_character(account, "School Return")
        alternative = self.store.create_character(account, "School Other")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1017,instance_id=0,x=0,y=-1,z=-77 WHERE id=%s",
                (character["id"],),
            )
            for item in (source, target):
                row = item["row"]
                db.execute(
                    "INSERT INTO world_dialogue_npcs "
                    "(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,interaction_range,enabled,provenance) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)",
                    tuple(
                        row[key]
                        for key in (
                            "actor_id",
                            "reference_id",
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                            "direction",
                            "dialogue_root",
                        )
                    )
                    + (
                        Jsonb(row["action_ids"]),
                        row["interaction_range"],
                        row["provenance"],
                    ),
                )

        from wakfu_server import npc_dialogue

        def current():
            return self.store.character(account, character["id"])

        def rows_provider():
            with self.store.connection() as db:
                row, _ = quest_npc._row(db, source["row"]["actor_id"], published)
            return [dict(row, _quest_publication=published)]

        from wakfu_server import dungeon_position_barrier
        from wakfu_server.position_buffer import Positions
        from wakfu_server.achievements import mission_toolkit

        live = {(account, generation, character["id"])}
        positions = Positions(
            self.store,
            lease_active=lambda owner, lease, identity: (owner, lease, identity)
            in live,
        )
        positions.attach(account, generation, current())
        boundaries = []
        settle = mission_toolkit.settle

        def observe_boundary(db, store, actor, *args, **kwargs):
            if kwargs.get("kind") in ("map_departure", "map_enter"):
                boundaries.append(
                    (kwargs["kind"], actor["map_id"], kwargs["reference"], id(db))
                )
            return settle(db, store, actor, *args, **kwargs)

        def choose(body):
            return dungeon_position_barrier.run_party_entry(
                self.store,
                positions,
                account,
                character["id"],
                transition=lambda owners: quest_npc.choose(
                    self.store,
                    account,
                    generation,
                    current(),
                    session,
                    body,
                    paired_position_accounts=owners,
                ),
            )

        with patch.object(
            quest_npc, "publication", return_value=published
        ), patch.object(mission_toolkit, "settle", side_effect=observe_boundary):
            session, opened = quest_npc.begin(
                self.store,
                account,
                generation,
                current(),
                source["row"]["actor_id"],
                729,
                character_provider=current,
                rows_provider=rows_provider,
            )
            self.assertTrue(opened)
            with self.assertRaises(ValueError):
                choose(struct.pack(">ii", 3359, 8309))
            self.assertEqual((current()["map_id"], current()["x"]), (1017, 0))
            # Still within the NPC's range4, but outside the original strict
            # native GetX()<4 condition. Check the late locked Store pose.
            with self.store.connection() as db:
                db.execute("UPDATE characters SET x=4 WHERE id=%s", (character["id"],))
            positions.rebind_selected(account, generation, character["id"])
            with self.assertRaises(ValueError):
                choose(struct.pack(">ii", 3364, 8309))
            self.assertEqual((current()["map_id"], current()["x"]), (1017, 4))
            self.assertEqual(boundaries, [])
            with self.store.connection() as db:
                db.execute("UPDATE characters SET x=0 WHERE id=%s", (character["id"],))
            positions.rebind_selected(account, generation, character["id"])
            before = self.store.character(account, character["id"])
            outcome = choose(struct.pack(">ii", 3364, 8309))
            with self.assertRaises(ValueError):
                choose(struct.pack(">ii", 3364, 8309))

        saved = self.store.character(account, character["id"])
        self.assertEqual(
            tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            (527, 0, 79, 46, 3),
        )
        self.assertEqual(
            outcome["transport"]["destination"],
            dict(map_id=527, instance_id=0, x=79, y=46, z=3),
        )
        self.assertEqual(saved["id"], character["id"])
        self.assertEqual(
            [
                (kind, source_map, target_map)
                for kind, source_map, target_map, _ in boundaries
            ],
            [("map_departure", 1017, 527), ("map_enter", 527, 527)],
        )
        self.assertEqual(boundaries[0][3], boundaries[1][3])
        registered = positions.entry_snapshot((account, generation, character["id"]))
        self.assertEqual(
            tuple(
                registered["current"][field]
                for field in ("map_id", "instance_id", "x", "y", "z")
            ),
            (527, 0, 79, 46, 3),
        )
        with self.store.connection() as db:
            state = db.execute(
                "SELECT state FROM character_achievement_progress WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
            self.assertNotIn(2773, state["state"]["completed"])
            self.assertNotIn(2773, state["state"]["running"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members WHERE character_id=%s AND status='active'",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
        positions.release(account, generation, character["id"])
        live.clear()
        next_generation = self.store.begin_session(account)
        self.store.select_character(account, next_generation, alternative["id"])
        with patch.object(
            quest_npc, "publication", return_value=published
        ), self.assertRaises(ValueError):
            quest_npc.choose(
                self.store,
                account,
                generation,
                saved,
                session,
                struct.pack(">ii", 3364, 8309),
                paired_position_accounts=frozenset({account}),
            )
        final_generation = self.store.begin_session(account)
        selected = self.store.select_character(
            account, final_generation, character["id"]
        )
        self.assertEqual(
            tuple(
                selected[field] for field in ("map_id", "instance_id", "x", "y", "z")
            ),
            (527, 0, 79, 46, 3),
        )


class SchoolSameAssetTerminalReturnPostgresTests(PostgresCase):
    def test_private_1018_terminal_return_closes_membership_and_reselects_public_1018(
        self,
    ):
        from hashlib import sha256
        from psycopg.types.json import Jsonb
        from wakfu_server import dungeon_instances
        from wakfu_server.maps import (
            dungeon_exit,
            owned_story_terminal_returns as returns,
        )
        from wakfu_server.position_buffer import Positions

        profile_path = (
            ROOT / "wakfu_server/maps/owned_story_profiles/huppermage-seed-1018.json"
        )
        controller = json.loads(profile_path.read_text())
        key = "qa-huppermage-seed-1018"
        from wakfu_server.maps.dungeon_runtime_config import canonical_hash

        configuration = json.loads(
            (
                ROOT
                / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.configuration.json"
            ).read_text()
        )
        configuration["version"] = 1
        configuration["route"]["key"] = key
        configuration["route"]["start_map_id"] = 1018
        configuration["compiled_plan"]["asset_map_id"] = 1018
        configuration["topology"]["asset_map_id"] = 1018
        configuration["topology"]["owned_story_controller"] = controller
        configuration["evidence_hashes"] = dict(
            configuration["evidence_hashes"],
            plan=canonical_hash(configuration["compiled_plan"]),
            topology=canonical_hash(configuration["topology"]),
            route=canonical_hash(configuration["route"]),
        )
        account = self.store.register("school-1018-return", "isolated-test-password")[
            "id"
        ]
        character = self.store.create_character(account, "School Same Asset")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) VALUES(%s,1,%s)",
                (key, Jsonb(configuration)),
            )
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,template_id,definition_id,max_level,min_level,difficulty_level,is_difficulty_available,can_increase_difficulty,is_competitive_cancelled,allowed_ids,provenance) "
                "VALUES(%s,1,1,1,0,0,1,false,false,false,'{}',%s)",
                (key, "isolated same-asset terminal return test"),
            )
            db.execute(
                "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version) VALUES(%s,1)",
                (key,),
            )
            party = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party),
            )
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id,context_route_key,context_policy_version) "
                "VALUES(%s,1,%s,1,1,1018,3916,8198,1018,%s,1) RETURNING instance_id",
                (party, character["id"], key),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                (run, party, character["id"], generation),
            )
            # The entry outbox is the durable original public pose used by the
            # normal recovery/exit path; its source and destination share map 1018.
            db.execute(
                "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,destination_map_id,destination_instance_id,destination_x,destination_y,destination_z,transition_kind) "
                "VALUES(%s,%s,1,%s,%s,1018,0,0,-27,-8,1018,%s,0,-27,-8,'enter')",
                (run, party, character["id"], generation, run),
            )
            db.execute(
                "UPDATE characters SET map_id=1018,instance_id=%s,x=0,y=-27,z=-8 WHERE id=%s",
                (run, character["id"]),
            )
            db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms) VALUES(%s,%s,%s,%s)",
                (run, party, "a" * 64, Jsonb([{}])),
            )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,status,result_revision,result) VALUES(%s,%s,1,0,'victory',1,%s)",
                (fight, run, Jsonb({"victory": True})),
            )
            receipt = {
                "kind": returns.SCHEMA,
                "instance_id": run,
                "profile_sha256": __import__(
                    "wakfu_server.owned_story_controller", fromlist=["_digest"]
                )._digest(controller),
                "victory": True,
            }
            db.execute(
                "INSERT INTO character_achievement_events(character_id,event_key,signature,payload) VALUES(%s,%s,%s,%s)",
                (
                    character["id"],
                    returns._key(run, fight),
                    sha256(b"return").hexdigest(),
                    Jsonb(receipt),
                ),
            )

        with self.store.connection() as db:
            destination = returns.pending(
                db,
                self.store,
                dict(
                    self.store.character(account, character["id"], db),
                    map_id=1018,
                    instance_id=run,
                ),
            )
        self.assertEqual(destination, dict(map_id=1018, x=0, y=-27, z=-8))
        live = {(account, generation, character["id"])}
        positions = Positions(
            self.store,
            lease_active=lambda owner, lease, identity: (owner, lease, identity)
            in live,
        )
        positions.attach(
            account, generation, self.store.character(account, character["id"])
        )
        result = dungeon_exit._leave(
            self.store,
            account,
            generation,
            character["id"],
            in_fight=lambda _identity: False,
            destination_for=lambda db, current, _run: returns.pending(
                db, self.store, current
            ),
            positions=positions,
        )
        self.assertEqual((result["map_id"], result["instance_id"]), (1018, 0))
        self.assertEqual((result["x"], result["y"], result["z"]), (0, -27, -8))
        registered = positions.entry_snapshot((account, generation, character["id"]))
        self.assertEqual(
            tuple(
                registered["current"][field]
                for field in ("map_id", "instance_id", "x", "y", "z")
            ),
            (1018, 0, 0, -27, -8),
        )
        pending = dungeon_instances.pending_transitions(
            self.store, account, generation, character["id"]
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(
            (pending[0]["source_map_id"], pending[0]["destination_map_id"]),
            (1018, 1018),
        )
        self.assertTrue(
            dungeon_instances.acknowledge_transition(
                self.store, account, generation, character["id"], pending[0]["event_id"]
            )
        )
        with self.store.connection() as db:
            member = db.execute(
                "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                (run, character["id"]),
            ).fetchone()
            self.assertEqual(member["status"], "returned")
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s", (run,)
                ).fetchone()["status"],
                "closed",
            )
            party_state = db.execute(
                "SELECT leader_id FROM player_parties WHERE id=%s", (party,)
            ).fetchone()
            self.assertIsNone(party_state["leader_id"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (party,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE instance_id=%s AND status='pending'",
                    (run,),
                ).fetchone()["n"],
                0,
            )
        next_generation = self.store.begin_session(account)
        selected = self.store.select_character(
            account, next_generation, character["id"]
        )
        self.assertEqual(
            (
                selected["map_id"],
                selected["instance_id"],
                selected["x"],
                selected["y"],
                selected["z"],
            ),
            (1018, 0, 0, -27, -8),
        )
