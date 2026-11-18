"""Isolated SQL proof for the reviewed Pizzlarva hard-score binding.

The native definition is copied from the read-only runtime catalogue into this
test's disposable schema. The test does not publish to or mutate that catalogue.
"""

from copy import deepcopy
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.achievements import mission_toolkit, storage
from wakfu_server.postgres import Database
from wakfu_server.items import quest_inventory


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT / "wakfu_server/achievements/mission_profiles/astrub-pizzlarva-score.json"
)
NATIVE_QUEST = 2149
OBJECTIVE = 4261
EVENT_TOKEN = "isolated-hard-pizzlarva-score-14412"


class PizzlarvaScorePostgresTests(PostgresCase):
    def test_native_hard_score_requires_acceptance_and_settles_rewards_atomically(self):
        import os

        runtime = Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(runtime.close)
        with runtime.connection() as source:
            release = source.execute(
                "SELECT revision,source_sha256,source_export,definition_count "
                "FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
            ).fetchone()
            native_row = source.execute(
                "SELECT data FROM native_quest_metadata_definitions "
                "WHERE revision=%s AND definition_id=%s",
                (release["revision"], NATIVE_QUEST),
            ).fetchone()
        self.assertIsNotNone(native_row)
        native = native_row["data"]["native"]
        self.assertEqual(native["d"], NATIVE_QUEST)
        self.assertEqual([row["d"] for row in native["cjJ"]], [OBJECTIVE])
        rewards = deepcopy(native["cjK"])
        self.assertEqual(
            [(row["d"], row["aeV"], row["ckl"]) for row in rewards],
            [(3694, 6, [7671]), (4660, 5, [12686, 8])],
        )
        profile = json.loads(PROFILE.read_text())
        self.assertEqual(profile["activations"], [])

        account = self.store.register("pizzlarva-score", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Pizzlarva Score")
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "UPDATE characters SET level=6,map_id=885,instance_id=0,x=0,y=0,z=0 "
                "WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases "
                "(revision,source_sha256,source_export,definition_count) "
                "VALUES(%s,%s,%s,%s)",
                (
                    release["revision"],
                    Jsonb(release["source_sha256"]),
                    release["source_export"],
                    release["definition_count"],
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions "
                "(revision,definition_id,data) VALUES(%s,%s,%s)",
                (release["revision"], NATIVE_QUEST, Jsonb(native_row["data"])),
            )
            mission_toolkit.install(db, profile, activate=True)

        character = self.store.character(account, character["id"])
        self.assertEqual((character["level"], character["map_id"]), (6, 885))

        # A trusted score fact by itself must not start a native quest. Since it
        # made no state change, the producer receipt is not consumed either.
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            before = storage.load_locked(db, character["id"])
            self.assertNotIn(NATIVE_QUEST, before["running"])
            self.assertNotIn(NATIVE_QUEST, before["completed"])
            self.assertEqual(
                mission_toolkit.settle(
                    db,
                    self.store,
                    character,
                    EVENT_TOKEN,
                    "scenario_completed",
                    14412,
                ),
                [],
            )
            untouched = storage.load_locked(db, character["id"])
            self.assertNotIn(NATIVE_QUEST, untouched["running"])
            self.assertNotIn(NATIVE_QUEST, untouched["completed"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key LIKE 'mission-toolkit:scenario_completed:14412:%%'",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )

            # Model only the independently accepted native state; no producer
            # or profile activation is being used to manufacture acceptance.
            accepted = deepcopy(untouched)
            accepted["running"] = [NATIVE_QUEST]
            accepted["active"] = [NATIVE_QUEST]
            accepted["tracking"] = [NATIVE_QUEST]
            accepted.setdefault("active_periods", {})
            accepted.setdefault("active_unknown", [])
            storage.store(db, character["id"], accepted)
            xp_before = self.store.character(account, character["id"], db)["xp"]

            try:
                with db.transaction():
                    packets = mission_toolkit.settle(
                        db,
                        self.store,
                        character,
                        EVENT_TOKEN,
                        "scenario_completed",
                        14412,
                    )
                    rolled_back = storage.load_locked(db, character["id"])
                    self.assertIn(NATIVE_QUEST, rolled_back["completed"])
                    self.assertIn(OBJECTIVE, rolled_back["objectives"])
                    self.assertTrue(packets)
                    self.assertEqual(
                        db.execute(
                            "SELECT quantity FROM character_quest_items "
                            "WHERE character_id=%s AND reference=12686",
                            (character["id"],),
                        ).fetchone()["quantity"],
                        8,
                    )
                    raise RuntimeError("rollback score settlement")
            except RuntimeError as error:
                self.assertEqual(str(error), "rollback score settlement")

            rolled_back = storage.load_locked(db, character["id"])
            self.assertIn(NATIVE_QUEST, rolled_back["running"])
            self.assertNotIn(NATIVE_QUEST, rolled_back["completed"])
            self.assertNotIn(OBJECTIVE, rolled_back["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key LIKE 'mission-toolkit:scenario_completed:14412:%%'",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=%s",
                    (character["id"], NATIVE_QUEST),
                ).fetchone()["n"],
                0,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM character_quest_items "
                    "WHERE character_id=%s AND reference=12686",
                    (character["id"],),
                ).fetchone()
            )

            packets = mission_toolkit.settle(
                db,
                self.store,
                character,
                EVENT_TOKEN,
                "scenario_completed",
                14412,
            )
            self.assertTrue(packets)
            completed = storage.load_locked(db, character["id"])
            self.assertIn(NATIVE_QUEST, completed["completed"])
            self.assertIn(OBJECTIVE, completed["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items "
                    "WHERE character_id=%s AND reference=12686",
                    (character["id"],),
                ).fetchone()["quantity"],
                8,
            )
            outbox = db.execute(
                "SELECT reward_key,payload,delivered_at "
                "FROM character_achievement_reward_outbox "
                "WHERE character_id=%s AND achievement_id=%s ORDER BY reward_key",
                (character["id"], NATIVE_QUEST),
            ).fetchall()
            self.assertEqual([row["reward_key"] for row in outbox], ["3694", "4660"])
            self.assertEqual([row["payload"] for row in outbox], rewards)
            self.assertTrue(all(row["delivered_at"] is not None for row in outbox))
            xp_after = self.store.character(account, character["id"], db)["xp"]
            self.assertGreater(xp_after, xp_before)

            # Same producer identity is inert after reconnect/reopen, including
            # both native rewards and the personal quest inventory quantity.
            self.assertEqual(
                mission_toolkit.settle(
                    db,
                    self.store,
                    character,
                    EVENT_TOKEN,
                    "scenario_completed",
                    14412,
                ),
                [],
            )

        reopened = self.reopen()
        with reopened.connection() as db:
            state = storage.load_locked(db, character["id"])
            self.assertIn(NATIVE_QUEST, state["completed"])
            self.assertIn(OBJECTIVE, state["objectives"])
            self.assertEqual(
                quest_inventory.load(db, character["id"]),
                [{"character_id": character["id"], "reference": 12686, "quantity": 8}],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key LIKE 'mission-toolkit:scenario_completed:14412:%%'",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=%s AND delivered_at IS NOT NULL",
                    (character["id"], NATIVE_QUEST),
                ).fetchone()["n"],
                2,
            )
