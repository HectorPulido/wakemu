"""Earned story links require original owned victories, not mission flags."""

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import earned_achievement_links as links, storage


class EarnedAchievementLinksPostgresTests(PostgresCase):
    def test_historical_story_recovers_pet_once_with_real_victory_receipts_and_rollback(
        self,
    ):
        account = self.store.register("earned-story", "local-password")["id"]
        character = self.store.create_character(account, "Earned Story")
        with self.store.connection() as db:
            before = storage.load_locked(db, character["id"])
            before.update(
                completed=[5568],
                objectives=[11510, 11511, 11513],
                completion_dates={"5568": 1000},
            )
            storage.store(db, character["id"], before)
            # A completed story alone must not invent the original boss kill.
            self.assertEqual(links.recover(db, self.store, character), [])
            revision = "f" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,2)",
                (
                    revision,
                    Jsonb({"fixture": "native story reward subset"}),
                    b"native reward fixture",
                ),
            )
            for identity, objective, payload in (
                (
                    5591,
                    11541,
                    [
                        dict(d=10395, aeV=5, ckk=False, ckl=[2044, 1, 4]),
                        dict(d=10394, aeV=5, ckk=False, ckl=[2990, 1, 4]),
                    ],
                ),
                (5593, 11543, [dict(d=10398, aeV=5, ckk=False, ckl=[12237, 1, 4])]),
            ):
                definition = dict(
                    d=identity,
                    native_class="aJM",
                    aqb=True,
                    cjI="",
                    cjU=0,
                    cjL=0,
                    getDuration=0,
                    cjJ=[dict(d=objective, ckc="", cke="", ckf=[])],
                    cjK=payload,
                )
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, identity, Jsonb({"native": definition})),
                )
            party = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party),
            )
            route = "legacy-map-312-18736-713"
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,template_id,definition_id,max_level,min_level,difficulty_level,is_difficulty_available,can_increase_difficulty,is_competitive_cancelled,allowed_ids,provenance) VALUES(%s,4,1000312,1000312,0,0,1,false,false,false,ARRAY[]::bigint[],'isolated owned story fixture')",
                (route,),
            )
            instance = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id,status,ended_at,context_route_key,context_policy_version) VALUES(%s,1,%s,1000312,1000312,527,18736,713,312,'completed',now(),%s,4) RETURNING instance_id",
                (party, character["id"], route),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role,status,ended_at) VALUES(%s,%s,%s,'fixture',1,'leader','returned',now())",
                (instance, party, character["id"]),
            )
            db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room,status) VALUES(%s,%s,%s,%s,3,'completed')",
                (
                    instance,
                    party,
                    "a" * 64,
                    Jsonb([{"order": 1}, {"order": 2}, {"order": 3}]),
                ),
            )
            keys = []
            for room, event in ((1, 23922), (3, 23926)):
                fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                    (fight, character["id"], account),
                )
                db.execute(
                    "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,status,result_revision,result) VALUES(%s,%s,%s,0,'victory',1,%s)",
                    (
                        fight,
                        instance,
                        room,
                        Jsonb({"victory": True, "completed": room == 3}),
                    ),
                )
                key = f"astrub-cat-story:{instance}:scene:{event}"
                payload = dict(
                    kind="owned_cat_story_scene",
                    owner=character["id"],
                    instance_id=instance,
                    event_id=event,
                    fight_id=fight,
                )
                storage.record_event(db, character["id"], key, payload)
                keys.append(key)
            foreign = dict(payload, owner=character["id"] + 1)
            storage.record_event(db, character["id"], "foreign-story-receipt", foreign)
            with self.assertRaisesRegex(ValueError, "Missing durable linked"):
                links.settle(
                    db,
                    self.store,
                    character,
                    source_quest=5568,
                    source_objective=11513,
                    event_key="foreign-story-receipt",
                )
            with self.assertRaisesRegex(RuntimeError, "rollback linked reward"):
                with db.transaction():
                    self.assertTrue(links.recover(db, self.store, character))
                    raise RuntimeError("rollback linked reward")
            self.assertNotIn(
                5593, storage.load_locked(db, character["id"])["completed"]
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            packets = links.recover(db, self.store, character)
            self.assertEqual(sum(op == 12471 for op, _ in packets), 3)
            state = storage.load_locked(db, character["id"])
            self.assertTrue({5568, 5591, 5593} <= set(state["completed"]))
            self.assertEqual(state["running"], before["running"])
            self.assertEqual(state["completion_dates"]["5568"], 1000)
            items = self.store.character(account, character["id"], db)[
                "inventory_items"
            ]
            self.assertEqual(
                sorted(item["reference"] for item in items), [2044, 2990, 12237]
            )
            pet = next(item for item in items if item["reference"] == 12237)
            self.assertEqual(
                (pet["binding_type"], pet["bound"], pet["pet"]["model_id"]),
                (4, True, 5),
            )
            self.assertEqual(links.recover(db, self.store, character), [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND delivered_at IS NOT NULL",
                    (character["id"],),
                ).fetchone()["n"],
                3,
            )
        with self.store.connection() as db:
            self.assertEqual(links.recover(db, self.store, character), [])
            self.assertEqual(
                len(
                    self.store.character(account, character["id"], db)[
                        "inventory_items"
                    ]
                ),
                3,
            )
