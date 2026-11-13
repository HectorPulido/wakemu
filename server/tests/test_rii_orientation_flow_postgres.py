"""Airyna orientation dialogue, owner encounter and hit settlement in PostgreSQL."""
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import npc_dialogue, npc_objective_facts, npc_world
from wakfu_server.achievements import rii_lesson_auto_start, rii_orientation, storage
from wakfu_server.combat.combat_group_store import PersistentGroups
from wakfu_server.combat_state import Actor, Fight


class RiiOrientationFlowPostgresTests(PostgresCase):
    def test_reopened_dialogue_spawns_admits_and_settles_orientation_hit(self):
        account = self.store.register("rii-orientation-flow", "test-password")["id"]
        character = self.store.create_character(account, "Orientation Flow")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        combat = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjK": [],
            "cjJ": [
                {"d": identity, "ckc": "", "cke": "", "ckf": []}
                for identity in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        hidden = {
            "d": 5154,
            "native_class": "aJM",
            "aqb": True,
            "isVisible": False,
            "cjK": [],
            "cjJ": [{"d": 10606, "ckc": "", "cke": "", "ckf": []}],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,2)",
                ("d" * 64, Jsonb({}), b"orientation-flow"),
            )
            for identity, native in ((5143, combat), (5154, hidden)):
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES (%s,%s,%s)",
                    ("d" * 64, identity, Jsonb({"native": native})),
                )
            row = next(
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["actor_id"] == -1706442046308339 and r["reference_id"] == 5460
            )
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (row["x"], row["y"], row["z"], character["id"]),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [5143]
            state["tracking"] = [5143]
            state["objectives"] = [10606]
            storage.store(db, character["id"], state)
            current = self.store.character(account, character["id"], db)

        groups = PersistentGroups(self.store)

        def rows():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1388, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, character["id"])

        open_body = struct.pack(
            ">ibq", 5787, npc_dialogue.NPC_SPEAKER, -1706442046308339
        )
        open_request = npc_dialogue.decode_request(npc_dialogue.OPEN_REQUEST, open_body)
        from wakfu_server import rii_airyna_dialogue

        self.assertEqual(
            (
                open_request["node_id"],
                open_request["speaker_type"],
                open_request["speaker_id"],
            ),
            (
                rii_airyna_dialogue.ROOT,
                npc_dialogue.NPC_SPEAKER,
                rii_airyna_dialogue.ACTOR,
            ),
        )
        # local_game_server maps Airyna's native re-entry speaker to the
        # accepted first-lesson action (1389), although the raw placement lists
        # the already-running action (1390).
        session, opened = rii_airyna_dialogue.begin(
            lambda: current,
            rows,
            facts,
            rii_airyna_dialogue.ACTOR,
            rii_airyna_dialogue.ACTION,
        )
        self.assertEqual(opened[0], npc_dialogue.OPEN_RESPONSE)
        request_body = struct.pack(">ii", 5787, 13322)
        request = npc_dialogue.decode_request(npc_dialogue.CHOICE_REQUEST, request_body)
        choice_packet = session.choose(**request)
        self.assertIsNotNone(choice_packet)

        lesson_scene = rii_orientation.spawn(
            self.store, groups, account, generation, current
        )
        self.assertIsNotNone(lesson_scene)
        target_request = None
        with self.store.connection() as db:
            target = rii_lesson_auto_start.target(db, groups, character["id"], 10574)
            group = next(
                g
                for g in groups.available(1388, 0)
                if any(member["id"] == target["id"] for member in g["members"])
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id",
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES (%s,%s,%s,0,%s)",
                (fight_id, character["id"], account, generation),
            )
            target_request = struct.pack(
                ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
            )
        parsed_target = struct.unpack(">qiihB", target_request)
        self.assertEqual(
            parsed_target[0:4], (target["id"], target["x"], target["y"], target["z"])
        )
        lease, monsters = groups.claim(group["key"], generation, fight_id)
        with self.store.connection() as db:
            self.assertTrue(rii_orientation.admit(db, character["id"], monsters))

        player_position = (current["x"], current["y"], current["z"])
        target_position = (target["x"], target["y"], target["z"])
        player = Actor(
            character["id"],
            0,
            player_position,
            100,
            6,
            3,
            1000,
            1,
            owner_id=character["id"],
            controlled=True,
        )
        sack = Actor(target["id"], 1, target_position, 20, 4, 2, 1, 1)
        fight = Fight(
            fight_id,
            [player, sack],
            {player_position, target_position},
            {0: {player_position}, 1: {target_position}},
        )
        with self.store.connection() as db:
            self.assertTrue(rii_orientation.bind(db, fight, character["id"], monsters))
        from wakfu_server.combat.combat_ordinary_authority import native_facing

        for direction in range(8):
            sack.direction = direction
            if native_facing(player, sack) == "BACK":
                break
        else:
            self.fail(
                "No authoritative rear-facing orientation exists for the admitted sack"
            )
        fight.ready(character["id"])
        with fight.effect_resolution():
            fight.apply_damage(character["id"], target["id"], 1)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        self.assertTrue(
            any(event.get("rii_orientation_hit") is True for event in fight.events)
        )

        member = {
            "character_id": character["id"],
            "account_id": account,
            "session_generation": generation,
            "team": 0,
            "withdrawn": False,
        }
        with self.store.connection() as db, db.transaction():
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            result = rii_orientation.settle_participants(
                db, self.store, fight, [member], monsters
            )
            self.assertTrue(result[account])
        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(10574, progress["objectives"])
            self.assertIn(10606, progress["objectives"])
            self.assertEqual(progress["tracking"], [5143])
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM character_achievement_events WHERE character_id=%s "
                    "AND event_key='rii-orientation-objective:10574'",
                    (character["id"],),
                ).fetchone()
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
