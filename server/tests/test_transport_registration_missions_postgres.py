"""Native registration, discovery and quest progress share one transaction."""
import json
from pathlib import Path
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.transport_discovery import Discoveries
from wakfu_server.achievements import mission_toolkit, storage

ROOT = Path(__file__).resolve().parents[2]
BODY = struct.pack(">qHH", 27004, 24, 0)


class TransportRegistrationMissionPostgresTests(PostgresCase):
    def prepare(self):
        self.account = self.store.register("registered-mission", "isolated-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Registered Mission")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.discovery = Discoveries(self.store)
        definitions = json.loads(
            (
                ROOT / "server/tests/fixtures/native_astrub_low_level_contracts.json"
            ).read_text()
        )["definitions"]
        profile = json.loads(
            (
                ROOT
                / "server/wakfu_server/achievements/mission_profiles/astrub-low-level-followups.json"
            ).read_text()
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-162,y=60,z=0 WHERE id=%s",
                (self.character["id"],),
            )
            revision = "d" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "actual transport registration"}),
                    b"isolated fixture",
                    len(definitions),
                ),
            )
            for definition in definitions:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, definition["d"], Jsonb({"native": definition})),
                )
            mission_toolkit.install(db, profile, activate=True)
        self.character = self.store.character(self.account, self.character["id"])

    def start_return_quest(self):
        with self.store.connection() as db:
            state = storage.load_locked(db, self.character["id"])
            state.update(running=[2191], completed=[2190], objectives=[])
            storage.store(db, self.character["id"], state)

    def register(self, body=BODY):
        return self.discovery.register_character(
            self.account, self.generation, self.character, body
        )

    def test_already_known_transport_can_progress_later_active_quest_once(self):
        self.prepare()
        first = self.register()
        self.assertTrue(first["discovered"])
        self.assertEqual(first["packets"], [])
        self.start_return_quest()
        second = self.register()
        self.assertFalse(second["discovered"])
        self.assertEqual((second["kind"], second["identity"]), (2, 27004))
        self.assertIn(
            (13832, struct.pack(">qi", self.character["id"], 4281)), second["packets"]
        )
        self.assertEqual(self.register()["packets"], [])
        with self.store.connection() as db:
            state = storage.load_locked(db, self.character["id"])
            count = db.execute(
                "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key LIKE 'mission-toolkit:transport_registered:27004:%%'",
                (self.character["id"],),
            ).fetchone()["n"]
        self.assertEqual(state["objectives"], [4281])
        self.assertIn(2191, state["running"])
        self.assertNotIn(2191, state["completed"])
        self.assertEqual(count, 1)

    def test_native_known_transport_activation_progresses_without_discovery(self):
        self.prepare()
        body = struct.pack(">qHH", 27004, 0, 0)
        # Account policy may advertise every Drago as known without persisted discovery.
        self.assertEqual(
            self.discovery.activate_character(
                self.account, self.generation, self.character, body
            )["packets"],
            [],
        )
        self.start_return_quest()
        outcome = self.discovery.activate_character(
            self.account, self.generation, self.character, body
        )
        self.assertFalse(outcome["discovered"])
        self.assertIn(
            (13832, struct.pack(">qi", self.character["id"], 4281)), outcome["packets"]
        )
        self.assertNotIn(27004, self.discovery.known(self.account)[2])
        self.assertEqual(
            self.discovery.activate_character(
                self.account, self.generation, self.character, body
            )["packets"],
            [],
        )
        for invalid in (BODY, body[:-1], struct.pack(">qHH", 27004, 0, 1)):
            with self.subTest(body=invalid.hex()), self.assertRaises(ValueError):
                self.discovery.activate_character(
                    self.account, self.generation, self.character, invalid
                )
        with self.store.connection() as db:
            self.assertIn(
                4281, storage.load_locked(db, self.character["id"])["objectives"]
            )
            db.execute(
                "UPDATE characters SET x=0,y=0 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "too far"):
            self.discovery.activate_character(
                self.account, self.generation, self.character, body
            )

    def test_native_request_and_fresh_durable_position_are_required(self):
        self.prepare()
        for body in (
            struct.pack(">qHH", 27004, 0, 0),
            struct.pack(">qHH", 27004, 24, 1),
            BODY[:-1],
        ):
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                self.register(body)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=0,y=0 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "too far"):
            self.register()
        self.assertNotIn(27004, self.discovery.known(self.account)[2])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=-162,y=60 WHERE id=%s", (self.character["id"],)
            )
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.register()
        self.assertNotIn(27004, self.discovery.known(self.account)[2])

    def test_failed_mission_settlement_rolls_back_discovery_insert(self):
        self.prepare()
        self.start_return_quest()
        with patch.object(
            mission_toolkit,
            "settle",
            side_effect=RuntimeError("injected settlement failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.register()
        self.assertNotIn(27004, self.discovery.known(self.account)[2])
        with self.store.connection() as db:
            self.assertNotIn(
                4281, storage.load_locked(db, self.character["id"])["objectives"]
            )
        self.assertTrue(self.register()["discovered"])
