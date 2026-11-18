"""Isolated SQL proof for four simultaneous native pads and King reward gating."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import struct
import threading
import time
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as DungeonFixture
from wakfu_server import player_parties, simultaneous_party_pads as pads
from wakfu_server.achievements import native_dungeon_achievements as native_achievements
from wakfu_server.achievements import storage


class OrganasmPadsPostgresTests(PostgresCase):
    def _native_fixture(self):
        # Synthetic local QA roster/session fixture; the final encounter facts
        # below are explicitly a frozen-fixture proof, not a played combat.
        members = [DungeonFixture.player(self, f"organasm-{n}") for n in range(4)]
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
        profile = pads.source()
        now = time.monotonic()
        durable = []
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,"
                "template_id,definition_id,max_level,min_level,difficulty_level,"
                "is_difficulty_available,can_increase_difficulty,"
                "is_competitive_cancelled,allowed_ids,provenance) "
                "VALUES('qa-organasm',1,51,53,0,0,1,false,false,false,'{}',"
                "'isolated four-pad SQL fixture')"
            )
            revision = db.execute(
                "SELECT revision FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()["revision"]
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            instance_id = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                "start_map_id,status,ended_at,context_route_key,context_policy_version) "
                "VALUES(%s,%s,%s,51,53,1295,32889,940,448,'completed',now(),'qa-organasm',1) "
                "RETURNING instance_id",
                (party_id, revision, members[0]["character"]["id"]),
            ).fetchone()["instance_id"]
            for index, (member, pad) in enumerate(zip(members, profile["pads"])):
                character_id = member["character"]["id"]
                account_id = member["account"]
                generation = member["generation"]
                x, y, z = pad["position"]
                db.execute(
                    "UPDATE characters SET level=25,map_id=448,instance_id=%s,x=%s,y=%s,z=%s "
                    "WHERE id=%s",
                    (instance_id, x, y, z, character_id),
                )
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                    "session_generation,party_revision,role,status) VALUES(%s,%s,%s,%s,%s,%s,'active')",
                    (
                        instance_id,
                        party_id,
                        character_id,
                        generation,
                        revision,
                        "leader" if index == 0 else "member",
                    ),
                )
                durable.append(
                    dict(
                        id=character_id,
                        account_id=account_id,
                        map_id=448,
                        instance_id=instance_id,
                        x=x,
                        y=y,
                        z=z,
                        _pad_generation=generation,
                        _emote_packet=(
                            12088,
                            struct.pack(
                                ">BhqIiB", 1, 20, character_id, 5, pad["emote_id"], 0
                            ),
                        ),
                        _emote_until=now + 60,
                    )
                )
            rooms = [
                {"order": n, "monsters": [{"ref_id": 2190 + n, "count": 1}]}
                for n in range(1, 4)
            ] + [{"order": 4, "monsters": [{"ref_id": 2100, "count": 1}]}]
            db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room,status) "
                "VALUES(%s,%s,%s,%s,4,'completed')",
                (instance_id, party_id, "a" * 64, Jsonb(rooms)),
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,status,result_revision,result) "
                "VALUES(%s,%s,4,0,'victory',1,%s)",
                (fight_id, instance_id, Jsonb({"completed": True, "victory": True})),
            )
            # Minimal activated event index for the focused pad adapter test.
            db.execute(
                "INSERT INTO mission_toolkit_profiles(profile_id,version,native_revision,sha256,document) "
                "VALUES('qa-organasm-pads',1,%s,%s,%s)",
                ("b" * 64, "c" * 64, Jsonb({"fixture": "isolated producer index"})),
            )
            db.execute(
                "INSERT INTO mission_toolkit_active(profile_id,version) VALUES('qa-organasm-pads',1)"
            )
            db.execute(
                "INSERT INTO mission_toolkit_event_index(profile_id,version,kind,reference) "
                "VALUES('qa-organasm-pads',1,'party_pad_completed',%s)",
                (profile["event_reference"],),
            )
        return members, party_id, instance_id, fight_id, durable, profile

    def test_four_current_members_settle_once_and_native693_visibility_is_not_earning(
        self,
    ):
        (
            members,
            _,
            instance_id,
            fight_id,
            occupants,
            pad_profile,
        ) = self._native_fixture()

        # A stale live session cannot stand in for the frozen run membership.
        first = occupants[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET generation=%s WHERE account_id=%s",
                ("stale-" + first["_pad_generation"], first["account_id"]),
            )
            self.assertEqual(
                pads.settle_current(
                    db,
                    self.store,
                    pad_profile,
                    occupants,
                    now=time.monotonic(),
                    validate_live=lambda _participants: True,
                ),
                [],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM simultaneous_party_pad_completions WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE sessions SET generation=%s WHERE account_id=%s",
                (first["_pad_generation"], first["account_id"]),
            )

        # Concurrent callers serialize against the same real SQL roster and
        # migration-387 receipt. Settlement callbacks are stubbed only so this
        # check isolates pad completion/idempotence from unrelated quest profile
        # publication and presentation delivery.
        barrier = threading.Barrier(2)

        def settle_once():
            barrier.wait(timeout=5)
            with self.store.connection() as db:
                return pads.settle_current(
                    db,
                    self.store,
                    pad_profile,
                    occupants,
                    now=time.monotonic(),
                    validate_live=lambda _participants: True,
                )

        with patch(
            "wakfu_server.achievements.mission_toolkit.settle", return_value=[]
        ) as toolkit, patch(
            "wakfu_server.achievements.tutorial_presentation_once.claim",
            return_value=True,
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _n: settle_once(), range(2)))
        self.assertEqual(sum(bool(response) for response in responses), 1)
        self.assertEqual(sum(len(response) for response in responses), 4)
        self.assertEqual(toolkit.call_count, 4)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM simultaneous_party_pad_completions "
                    "WHERE instance_id=%s AND profile_id=%s",
                    (instance_id, pad_profile["id"]),
                ).fetchone()["n"],
                1,
            )
            # A reused member cannot fill another pad, even if its current
            # native emote and coordinates are forged to match both positions.
            reused = deepcopy(occupants)
            reused[-1]["id"] = reused[0]["id"]
            self.assertEqual(
                pads.occupied(pad_profile, reused, now=time.monotonic()), ()
            )

            # Import only exact original 693 metadata into the isolated schema.
            document = native_achievements.source()
            definition = document["definition"]
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
                "VALUES(%s,%s,%s,1)",
                (
                    document["native_metadata_revision"],
                    Jsonb({"qa": "native693 exact source"}),
                    b"isolated fixture",
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                (
                    document["native_metadata_revision"],
                    definition["d"],
                    Jsonb({"native": definition}),
                ),
            )
            char = self.store.character(
                members[0]["account"], members[0]["character"]["id"], db
            )
            # Native aHe controls visibility, not earning eligibility.
            state = storage.load_locked(db, char["id"])
            # Keep the visibility expression unchanged and do not fabricate
            # allegiance2192 merely to earn the authentic dungeon outcome.
            state.update(completed=[], completion_dates={})
            storage.store(db, char["id"], state)
            event = dict(
                fight_id=fight_id,
                completed_dungeon_id=53,
                original_breeds=[2100],
            )
            with patch(
                "wakfu_server.achievements.service.drain_rewards", return_value=[]
            ):
                self.assertEqual(
                    definition["aHe"],
                    "GetRealLevel() >= 25 and IsAchievementComplete(2192)",
                )
                db.execute("UPDATE characters SET level=24 WHERE id=%s", (char["id"],))
                char["level"] = 24
                # Missing actual dungeon/King evidence must still refuse credit.
                db.execute(
                    "UPDATE dungeon_room_runs SET status='active' WHERE instance_id=%s",
                    (instance_id,),
                )
                native_achievements.settle(db, self.store, char, event)
                self.assertNotIn(693, storage.load_locked(db, char["id"])["completed"])
                db.execute(
                    "UPDATE dungeon_room_runs SET status='completed' WHERE instance_id=%s",
                    (instance_id,),
                )
                non_king_rooms = [
                    {"order": n, "monsters": [{"ref_id": 2190 + n, "count": 1}]}
                    for n in range(1, 5)
                ]
                db.execute(
                    "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                    (Jsonb(non_king_rooms), instance_id),
                )
                native_achievements.settle(db, self.store, char, event)
                self.assertNotIn(693, storage.load_locked(db, char["id"])["completed"])
                king_rooms = non_king_rooms[:-1] + [
                    {"order": 4, "monsters": [{"ref_id": 2100, "count": 1}]}
                ]
                db.execute(
                    "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                    (Jsonb(king_rooms), instance_id),
                )
                packets = native_achievements.settle(db, self.store, char, event)
                self.assertTrue(packets)
                self.assertIn(693, storage.load_locked(db, char["id"])["completed"])
                self.assertNotIn(2192, storage.load_locked(db, char["id"])["completed"])
                rewards = db.execute(
                    "SELECT reward_key,payload FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=693 ORDER BY reward_key",
                    (char["id"],),
                ).fetchall()
                self.assertEqual(
                    [row["reward_key"] for row in rewards], ["5095", "945"]
                )
                self.assertEqual(
                    [(row["payload"]["aeV"], row["payload"]["ckl"]) for row in rewards],
                    [(5, [21004, 10]), (3, [20109])],
                )
                native_achievements.settle(db, self.store, char, event)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=693",
                        (char["id"],),
                    ).fetchone()["n"],
                    2,
                )


if __name__ == "__main__":
    unittest.main()
