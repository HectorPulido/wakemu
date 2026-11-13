"""Exercise Rii arrival and a captured conversation against isolated storage."""
import struct
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import (
    mission_transport,
    native_transports,
    npc_objective_facts,
    npc_world,
)
from wakfu_server import rii_conversation_progress
from wakfu_server.achievements import storage


class RiiTransportDialoguePostgresTests(PostgresCase):
    def test_zaap_arrival_and_huly_progress_survive_reopen(self):
        account = self.store.register("rii-route-test", "test-password")["id"]
        character = self.store.create_character(account, "Rii Route")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        # The quest fixture contains only the fields used by these two actions;
        # transport objects, map transition, NPC placement and dialogue are real.
        native = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [{"d": i, "ckc": "", "cke": "", "ckf": []} for i in (10612, 10613)],
            "cjK": [],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
                "VALUES (%s,%s,%s,4)",
                ("e" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5160,%s)",
                ("e" * 64, Jsonb({"native": native})),
            )
            reminder = {
                "d": 5144,
                "native_class": "aJM",
                "aqb": True,
                "isVisible": True,
                "aHe": "GetRealLevel() < 30",
                "bwX": 5160,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [{"d": 10577, "ckc": "", "cke": "", "ckf": []}],
            }
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5144,%s)",
                ("e" * 64, Jsonb({"native": reminder})),
            )
            sanctuary = {
                "d": 5146,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjJ": [
                    {"d": i, "ckc": "", "cke": "", "ckf": []}
                    for i in (10582, 10583, 10584)
                ],
                "cjK": [],
            }
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5146,%s)",
                ("e" * 64, Jsonb({"native": sanctuary})),
            )
            introductions = {
                "d": 5154,
                "native_class": "aJM",
                "aqb": True,
                "isVisible": False,
                "cjI": "",
                "cjK": [],
                "cjJ": [
                    {"d": i, "ckc": "", "cke": "", "ckf": []}
                    for i in (10595, 10596, 10606, 10607)
                ],
            }
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5154,%s)",
                ("e" * 64, Jsonb({"native": introductions})),
            )
            source = self.store.character(account, character["id"], db)

        route = native_transports.resolve(
            source,
            struct.pack(">qq", 19249, 34644),
            known_ids={34644},
            waive_criteria=True,
        )
        # This isolated integration test does not cover dungeon health: its
        # equipment catalog requires a separate compiled publication matching
        # the currently changing source tree. All mission and map state is real.
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            arrived, packets = mission_transport.transition(
                self.store,
                account,
                generation,
                source,
                route,
                native_zaap=True,
            )
        self.assertEqual((arrived["map_id"], arrived["instance_id"]), (1385, 0))
        self.assertEqual(
            [packet[0] for packet in packets],
            [13205, 13312, 13371, 13205, 13312, 13371, 13312, 13371, 13411, 13411],
        )
        from wakfu_server import rii_scenario

        self.assertIn(rii_scenario.packet(rii_scenario.ENTRY), packets)
        self.assertIn(rii_scenario.packet(rii_scenario.INTRO), packets)
        with self.reopen().connection() as db:
            persisted = storage.load_locked(db, character["id"])
            saved = self.store.character(account, character["id"], db)
            self.assertEqual(
                (saved["map_id"], saved["x"], saved["y"], saved["z"]), (1385, 3, -22, 7)
            )
            self.assertIn(5160, persisted["running"])
            self.assertIn(5160, persisted["tracking"])
            self.assertIn(5144, persisted["running"])
            self.assertIn(5144, persisted["tracking"])
            self.assertEqual(persisted["objectives"], [])
            receipt = db.execute(
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (character["id"], "zone-entry-mission:5160"),
            ).fetchone()
            self.assertGreater(receipt["payload"]["accepted_at_ms"], 0)
            huly = next(
                row
                for row in npc_world.load_scene(db, 1385, 0)
                if row["reference_id"] == 5461
            )

        # Move the test character to Huly via the normal owned position CAS.
        location = {key: huly[key] for key in ("map_id", "instance_id", "x", "y", "z")}
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            current = self.store.transition_map(
                account, generation, character["id"], arrived, location
            )

        def scene():
            with self.store.connection() as db:
                return npc_world.load_scene(db, 1385, 0)

        def facts():
            with self.store.connection() as db:
                return npc_objective_facts.load(db, account, character["id"])

        session, _ = npc_world.begin(
            lambda: current,
            scene,
            huly["actor_id"],
            huly["action_ids"][0],
            facts_provider=facts,
        )
        for node, choice in (
            (5765, 13275),
            (5766, 13278),
            (5767, 13280),
            (5768, 13281),
            (5769, 13282),
            (5783, 13306),
        ):
            session.choose(node, choice)
        with self.reopen().connection() as db:
            tracking_before_talk = storage.load_locked(db, character["id"])["tracking"]
        outcome = rii_conversation_progress.choose(
            self.store,
            account,
            generation,
            current,
            session,
            {"node_id": 5770, "choice_id": 13283},
        )
        self.assertTrue(outcome["packets"])
        self.assertEqual(
            [
                (opcode, struct.unpack(">qiB", body)[1:])
                for opcode, body in outcome["packets"]
                if opcode == 13371
            ],
            [(13371, (5160, 0)), (13371, (5160, 1))],
        )
        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5160, progress["running"])
            self.assertIn(10612, progress["objectives"])
            self.assertEqual(progress["tracking"], tracking_before_talk)
            self.assertTrue(
                npc_objective_facts.load(db, account, character["id"])[10612]
            )

        # A real persisted level-30 update settles only this character's
        # no-reward class reminder; neither its class nor other quests change.
        from wakfu_server.achievements import rii_class_mission

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=30 WHERE id=%s AND account_id=%s",
                (character["id"], account),
            )
            levelled = self.store.character(account, character["id"], db)
            original_breed = (
                levelled["breed_id"]
                if "breed_id" in levelled
                else levelled.get("breed")
            )
            packets = rii_class_mission.reached_level(db, self.store, levelled, 30)
            self.assertEqual([packet[0] for packet in packets], [13371, 13832, 13422])
        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5144, progress["completed"])
            self.assertIn(10577, progress["objectives"])
            self.assertNotIn(5144, progress["running"])
            self.assertIn(5160, progress["running"])
            saved = self.store.character(account, character["id"], db)
            self.assertEqual(saved.get("breed_id", saved.get("breed")), original_breed)

    def test_missing_mission_definition_rolls_back_real_map_transition(self):
        account = self.store.register("rii-route-rollback", "test-password")["id"]
        character = self.store.create_character(account, "Rii Rollback")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            source = self.store.character(account, character["id"], db)
        route = native_transports.resolve(
            source,
            struct.pack(">qq", 19249, 34644),
            known_ids={34644},
            waive_criteria=True,
        )
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            with self.assertRaisesRegex(ValueError, "Missing Rii starting mission"):
                mission_transport.transition(
                    self.store, account, generation, source, route, native_zaap=True
                )
        with self.reopen().connection() as db:
            saved = self.store.character(account, character["id"], db)
            self.assertEqual(
                tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                tuple(source[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            )
            self.assertNotIn(5160, storage.load_locked(db, character["id"])["running"])


if __name__ == "__main__":
    unittest.main()
