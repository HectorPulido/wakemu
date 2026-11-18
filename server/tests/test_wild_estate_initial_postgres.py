"""Real SQL verifies Wild Estate departure settlement shares travel rollback."""

import json
from pathlib import Path
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server import mission_transport
from wakfu_server.achievements import mission_character_events, mission_toolkit, storage


ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads(
    (
        ROOT / "wakfu_server/achievements/mission_profiles/wild-estate-initial.json"
    ).read_text()
)
NATIVE = json.loads(
    (Path(__file__).parent / "fixtures/native_wild_estate_initial.json").read_text()
)


class WildEstateDeparturePostgresTests(PostgresCase):
    def test_departure_completion_rolls_back_with_failed_move_and_commits_on_travel(
        self,
    ):
        account = self.store.register("wild-estate-departure", "isolated-password")[
            "id"
        ]
        character = self.store.create_character(account, "Wild Estate")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=50,map_id=527,instance_id=0,x=0,y=32,z=0 WHERE id=%s",
                (character["id"],),
            )
            revision = "c" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "wild-estate-native"}),
                    b"isolated fixture",
                    len(NATIVE["definitions"]),
                ),
            )
            for definition in NATIVE["definitions"]:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, definition["d"], Jsonb({"native": definition})),
                )
            mission_toolkit.install(db, PROFILE, activate=True)

        character = self.store.character(account, character["id"])
        ready_packets = mission_character_events.ready(
            self.store, account, generation, character
        )
        self.assertIn(13205, [opcode for opcode, _body in ready_packets])
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            before = self.store.character(account, character["id"], db)
            before_state = storage.load_locked(db, character["id"])
            self.assertIn(1686, before_state["running"])

        route = {
            "destination": {"map_id": 711, "instance_id": 0, "x": 3, "y": 22, "z": -74}
        }
        with patch.object(
            self.store,
            "transition_map_in_transaction",
            side_effect=ValueError("forced CAS failure"),
        ):
            with self.assertRaisesRegex(ValueError, "forced CAS failure"):
                mission_transport.transition(
                    self.store, account, generation, before, route, native_zaap=False
                )
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            after_rollback = self.store.character(account, character["id"], db)
            rolled_back = storage.load_locked(db, character["id"])
            self.assertEqual(after_rollback["map_id"], 527)
            self.assertEqual(rolled_back["objectives"], before_state["objectives"])
            self.assertNotIn(1686, rolled_back["completed"])
            self.assertEqual(after_rollback["xp"], before["xp"])

        arrived, _packets = mission_transport.transition(
            self.store, account, generation, before, route, native_zaap=False
        )
        self.assertEqual((arrived["map_id"], arrived["instance_id"]), (711, 0))
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            final_state = storage.load_locked(db, character["id"])
            self.assertIn(1686, final_state["completed"])
            self.assertIn(3170, final_state["objectives"])
            self.assertIn(1616, final_state["running"])
            self.assertGreater(
                self.store.character(account, character["id"], db)["xp"], before["xp"]
            )
