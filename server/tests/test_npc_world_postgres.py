import struct
import unittest
import psycopg
from postgres_case import PostgresCase
from wakfu_server.maps.npc_world import load_scene, begin
from wakfu_server.maps import npc_objective_facts


class NpcWorldPostgresTests(PostgresCase):
    def test_owned_initial_facts_and_captured_conditional_roots(self):
        account = self.store.register("npc-facts-owner", "test-password")["id"]
        character = self.store.create_character(account, "Npc Facts")
        other = self.store.register("npc-facts-other", "test-password")["id"]
        with self.store.connection() as db:
            self.assertEqual(npc_objective_facts.load(db, account, character["id"]), {})
            with self.assertRaises(ValueError):
                npc_objective_facts.load(db, other, character["id"])
            rows = load_scene(db, 1385, 0) + load_scene(db, 1388, 0)
        self.assertEqual(
            {row["reference_id"] for row in rows}, {5459, 5460, 5461, 5467}
        )
        for row in rows:
            current = dict(
                character,
                **{key: row[key] for key in ("map_id", "instance_id", "x", "y", "z")}
            )

            def facts():
                with self.store.connection() as db:
                    return npc_objective_facts.load(db, account, character["id"])

            session, packet = begin(
                lambda: current,
                lambda: [row],
                row["actor_id"],
                row["action_ids"][0],
                facts_provider=facts,
            )
            self.assertEqual(packet[0], 12969)
            session.close()
        with self.assertRaises(psycopg.IntegrityError):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO npc_objective_facts(account_id,character_id,objective_id,completed,provenance) VALUES(%s,%s,10606,true,'foreign')",
                    (other, character["id"]),
                )

    def test_native_capture_seed_replaces_local_trials_and_revokes_session(self):
        with self.store.connection() as db:
            self.assertEqual(load_scene(db, 1134, 0), ())
            trials = db.execute(
                "SELECT enabled FROM world_dialogue_npcs WHERE native_capture_id IS NULL"
            ).fetchall()
            self.assertEqual(len(trials), 4)
            self.assertTrue(all(not row["enabled"] for row in trials))
            rows = load_scene(db, 1387, 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(load_scene(db, 1387, 1), ())
            self.assertEqual(load_scene(db, 999, 0), ())
        row = rows[0]
        self.assertEqual(
            (row["reference_id"], row["x"], row["y"], row["z"]), (5458, -12, 0, 2)
        )
        self.assertEqual(row["action_ids"], [1238])
        self.assertEqual(row["dialogue_root"], 5764)
        self.assertIn("Local initial-scene adaptation", row["provenance"])
        character = dict(
            id=100, account_id=200, map_id=1387, instance_id=0, x=-11, y=0, z=2
        )

        def snapshot():
            with self.store.connection() as db:
                return load_scene(db, 1387, 0)

        session, packet = begin(lambda: character, snapshot, row["actor_id"], 1238)
        self.assertEqual(packet, (12969, struct.pack(">ibq", 5764, 2, row["actor_id"])))
        with self.store.connection() as db:
            db.execute(
                "UPDATE world_dialogue_npcs SET enabled=false WHERE actor_id=%s",
                (row["actor_id"],),
            )
        with self.assertRaises(ValueError):
            session.choose(5764, 13344)
        self.assertIsNone(session.node_id)

    def test_capture_foreign_key_rejects_changed_original_position_or_identity(self):
        for statement in (
            "UPDATE world_dialogue_npcs SET x=-16 WHERE native_capture_id IS NOT NULL",
            "UPDATE world_dialogue_npcs SET actor_id=-7 WHERE native_capture_id IS NOT NULL",
            "UPDATE world_dialogue_npcs SET dialogue_root=6274 WHERE native_capture_id IS NOT NULL",
            "UPDATE world_dialogue_npcs SET actor_id=-7 WHERE native_capture_id IS NULL",
            "UPDATE world_dialogue_npcs SET action_ids='[515]'::jsonb WHERE native_capture_id IS NOT NULL",
            "UPDATE world_dialogue_npcs SET instance_id=1 WHERE native_capture_id IS NOT NULL",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.IntegrityError):
                    with self.store.connection() as db:
                        db.execute(statement)
