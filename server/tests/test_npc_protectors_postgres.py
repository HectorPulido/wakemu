"""Additive protector seed and authoritative scene publication contracts."""
import struct
import unittest
import psycopg
from postgres_case import PostgresCase
from wakfu_server.maps import npc_protectors, npc_world


class NpcProtectorPostgresTests(PostgresCase):
    def test_exact_seed_publishes_only_enabled_public_scene(self):
        with self.store.connection() as db:
            rows = npc_world.load_scene(db, 1385, 0)
            row = next(row for row in rows if row["reference_id"] == 5459)
            self.assertEqual(
                (row["x"], row["y"], row["z"], row["direction"]), (20, 17, 1, 3)
            )
            self.assertEqual(npc_protectors.speaker(row), (1, 424))
            self.assertEqual(
                npc_protectors.bootstrap_records(db, dict(map_id=1385, instance_id=0)),
                (npc_protectors.record(row),),
            )
            self.assertEqual(
                npc_protectors.bootstrap_records(db, dict(map_id=1385, instance_id=1)),
                (),
            )
            db.execute(
                "UPDATE world_dialogue_npcs SET enabled=false WHERE actor_id=%s",
                (row["actor_id"],),
            )
            self.assertEqual(
                npc_protectors.bootstrap_records(db, dict(map_id=1385, instance_id=0)),
                (),
            )

    def test_owned_facts_protector_dialogue_and_same_scene_revalidation(self):
        account = self.store.register("protector-facts", "test-password")["id"]
        character = self.store.create_character(account, "Protector Facts")
        from wakfu_server.maps import npc_objective_facts

        with self.store.connection() as db:
            row = next(
                row
                for row in npc_world.load_scene(db, 1385, 0)
                if row["reference_id"] == 5459
            )
        character.update(map_id=1385, instance_id=0, x=20, y=17, z=1)

        def scene():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1385, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, character["id"])

        session, packet = npc_world.begin(
            lambda: character, scene, row["actor_id"], 1244, facts_provider=facts
        )
        self.assertEqual(packet, (12969, struct.pack(">ibq", 5772, 1, 424)))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO npc_objective_facts(account_id,character_id,objective_id,completed,provenance) VALUES(%s,%s,10596,true,'test')",
                (account, character["id"]),
            )
        with self.assertRaises(ValueError):
            session.choose(5772, 13288)
        self.assertIsNone(session.node_id)

    def test_database_rejects_invalid_speaker_and_runtime_rejects_contradictory_join(
        self,
    ):
        with self.assertRaises(psycopg.IntegrityError):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE native_captured_npc_contracts SET speaker_type=2 WHERE actor_id=-1706442046308330"
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE native_captured_npc_protectors SET protector_id=425 WHERE actor_id=-1706442046308330"
            )
            with self.assertRaises(ValueError):
                npc_world.load_scene(db, 1385, 0)
