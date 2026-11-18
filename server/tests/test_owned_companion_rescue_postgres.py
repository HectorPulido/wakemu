"""Native rescue rewards a real token once, then normal bHE learns it."""

import struct
from unittest.mock import patch
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import owned_companion_rescue as module, companions
from wakfu_server.achievements import storage
from test_owned_companion_rescue import DEFINITIONS, PIN


class OwnedCompanionRescuePostgresTests(PostgresCase):
    def test_native_rescue_token_xp_once_and_normal_companion_activation(self):
        account = self.store.register("knight-rescue-test", "local-password")["id"]
        character = self.store.create_character(account, "Knight Rescue")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        selected = dict(map_id=887, optional_companion=PIN)
        # The surrounding dispatcher authenticates the real owned admission;
        # this isolated case exercises the entire durable quest/reward/item path.
        with patch.object(module, "_context", return_value=True), patch.object(
            module.mechanics, "allowed", return_value=True
        ), patch.object(module.mechanics, "authorize_action"):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                    (
                        "b" * 64,
                        Jsonb({"fixture": "native Astrub Knight definitions"}),
                        b"native fixtures",
                        2,
                    ),
                )
                for identity, definition in DEFINITIONS.items():
                    db.execute(
                        "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                        ("b" * 64, int(identity), Jsonb({"native": definition})),
                    )
                current = self.store.character(account, character["id"], db)
                state = storage.load_locked(db, character["id"])
                state["completed"] = sorted(set(state["completed"]) | {2166})
                state["running"] = sorted((set(state["running"]) | {2170}) - {2166})
                storage.store(db, character["id"], state)
                packets = module.admit(db, self.store, current, selected)
                self.assertTrue(packets)
                state = storage.load_locked(db, character["id"])
                self.assertIn(1726, state["running"])
                self.assertNotIn(1721, state["running"])
                current.update(map_id=887, instance_id=99, x=5, y=-58, z=12)
                self.assertEqual(
                    module.interact(db, self.store, current, selected, 23583, 0), []
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=18009",
                        (character["id"],),
                    ).fetchone()
                )
                state = storage.load_locked(db, character["id"])
                state["completed"] = sorted(set(state["completed"]) | {2170})
                state["running"] = [q for q in state["running"] if q != 2170]
                storage.store(db, character["id"], state)
                before_xp = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["xp"]
                xp_rate = db.execute(
                    "SELECT v.xp_rate_bp FROM combat_reward_policy_active a "
                    "JOIN combat_reward_policy_versions v USING(version) "
                    "WHERE a.singleton"
                ).fetchone()["xp_rate_bp"]
                expected_xp = 3500 * xp_rate // 10000
                packets = module.interact(db, self.store, current, selected, 23583, 0)
                self.assertTrue(packets)
                state = storage.load_locked(db, character["id"])
                self.assertIn(1726, state["completed"])
                self.assertIn(3299, state["objectives"])
                items = db.execute(
                    "SELECT uid,quantity FROM inventory_items WHERE character_id=%s AND reference=18009",
                    (character["id"],),
                ).fetchall()
                self.assertEqual([row["quantity"] for row in items], [1])
                token = items[0]["uid"]
                self.assertEqual(
                    db.execute(
                        "SELECT xp FROM character_progression WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["xp"],
                    before_xp + expected_xp,
                )
                self.assertEqual(
                    module.interact(db, self.store, current, selected, 23583, 0), []
                )
                self.assertEqual(module.admit(db, self.store, current, selected), [])
                self.assertEqual(companions.collection(db, account), ())
        body = struct.pack(">iq", 5335, token)
        learned = companions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertTrue(learned["applied"])
        replay = companions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertFalse(replay["applied"])
        with self.store.connection() as db:
            collection = companions.collection(db, account)
            self.assertEqual(len(collection), 1)
            self.assertEqual(collection[0]["breed_ref"], 2867)
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE uid=%s", (token,)
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["xp"],
                before_xp + expected_xp,
            )
            self.assertEqual(companions.controlled_count(db, [character["id"]]), 0)
