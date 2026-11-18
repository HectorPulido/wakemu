"""A committed native interactive completion activates its reviewed follow-up."""

import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from tools.install_quest_interactions import install as install_interactions
from wakfu_server.achievements import interactive_missions, mission_toolkit, storage


ROOT = Path(__file__).resolve().parents[1]
NATIVE_FIXTURE = ROOT / "tests/fixtures/native_astrub_low_level_contracts.json"
FOLLOWUP_PROFILE = (
    ROOT / "wakfu_server/achievements/mission_profiles/astrub-forest-followups.json"
)
INTERACTION_MANIFEST = (
    ROOT / "wakfu_server/achievements/quest_interactions/astrub-reserve.json"
)


class InteractiveMissionFollowupPostgresTests(PostgresCase):
    def test_native_objective_completion_activates_followup_and_replay_does_not_duplicate_bread(
        self,
    ):
        account = self.store.register("wikan-followup", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Wikan Follow")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])

        native_bytes = NATIVE_FIXTURE.read_bytes()
        native_document = json.loads(native_bytes)
        definitions = {
            row["d"]: row
            for row in native_document["definitions"]
            if row["d"] in {2158, 2159, 2190, 2191}
        }
        revision = hashlib.sha256(
            (str(account) + ":astrub-followup-interaction").encode()
        ).hexdigest()
        manifest = json.loads(INTERACTION_MANIFEST.read_text())
        body = struct.pack(">qHH", 23650, 0, 0)

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases "
                "(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture_sha256": hashlib.sha256(native_bytes).hexdigest()}),
                    native_bytes,
                    len(definitions),
                ),
            )
            for identity, definition in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES(%s,%s,%s)",
                    (revision, identity, Jsonb({"native": definition})),
                )
            self.assertEqual(1, install_interactions(db, manifest, revision))
            mission_toolkit.install(
                db, json.loads(FOLLOWUP_PROFILE.read_text()), activate=True
            )
            db.execute(
                "UPDATE characters SET map_id=888,instance_id=0,x=4,y=-2,z=0 WHERE id=%s",
                (character["id"],),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [2158]
            state["completed"] = []
            state["objectives"] = [4274]
            state["tracking"] = [2158]
            storage.store(db, character["id"], state)

        location = self.store.character(account, character["id"])
        interaction = {
            "type": "GenericActivableInteractiveElement",
            "x": 4,
            "y": -3,
            "z": 0,
        }
        with patch("wakfu_server.world_static.interaction", return_value=interaction):
            result = interactive_missions.interact(
                self.store,
                account,
                generation,
                location,
                body,
                loaded=True,
                blocked=False,
            )
            self.assertTrue(result["applied"])
            self.assertEqual(result["completed"], [2158])
            packet_opcodes = [
                packet[0]
                for packet in result["packets"]
                if isinstance(packet, tuple) and len(packet) == 2
            ]
            self.assertIn(13832, packet_opcodes)
            self.assertIn(13422, packet_opcodes)

            with self.store.connection() as db:
                state = storage.load_locked(db, character["id"])
                self.assertIn(2158, state["completed"])
                self.assertIn(2159, state["running"])
                self.assertEqual(
                    db.execute(
                        "SELECT quantity FROM character_quest_items "
                        "WHERE character_id=%s AND reference=12686",
                        (character["id"],),
                    ).fetchone()["quantity"],
                    20,
                )
                owner = self.store.character(account, character["id"], db)

            replay = interactive_missions.interact(
                self.store,
                account,
                generation,
                owner,
                body,
                loaded=True,
                blocked=False,
            )
            self.assertFalse(replay["applied"])
            self.assertEqual(replay["packets"], [])

        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items "
                    "WHERE character_id=%s AND reference=12686",
                    (character["id"],),
                ).fetchone()["quantity"],
                20,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key='quest-interactive:2158:4275'",
                    (character["id"],),
                ).fetchone()["count"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
