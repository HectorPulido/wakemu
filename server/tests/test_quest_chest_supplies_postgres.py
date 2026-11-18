"""Focused SQL/runtime coverage for the reviewed Frigost quest chest supply."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import struct
import os
from unittest.mock import patch
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import quest_chest_supplies as supplies
from wakfu_server.achievements import mission_toolkit, storage
from wakfu_server.items import quest_inventory
from tools import publish_quest_chest_supplies as publisher


ROOT = Path(__file__).parents[1] / "wakfu_server"


class QuestChestSuppliesPostgresTests(PostgresCase):
    def test_frigost_supply_publication_ownership_replay_and_native_finish(self):
        from wakfu_server.postgres import Database

        batch = json.loads(
            (
                ROOT / "maps/quest_chest_supply_profiles/frigost-taroudium-cores.json"
            ).read_text()
        )
        profile = json.loads(
            (
                ROOT / "achievements/mission_profiles/frigost-core-acquisitions.json"
            ).read_text()
        )

        # Copy only the pinned native quest and chest prototype from the local
        # read-only runtime catalog into this test's disposable schema.
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
            quest = source.execute(
                "SELECT data FROM native_quest_metadata_definitions "
                "WHERE revision=%s AND definition_id=1227",
                (release["revision"],),
            ).fetchone()
            prototype = source.execute(
                "SELECT * FROM native_loot_chest_prototypes WHERE p=260"
            ).fetchone()
        self.assertIsNotNone(quest)
        self.assertIsNotNone(prototype)

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases "
                "(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    release["revision"],
                    Jsonb(release["source_sha256"]),
                    release["source_export"],
                    release["definition_count"],
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                "VALUES(%s,1227,%s)",
                (release["revision"], Jsonb(quest["data"])),
            )
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM native_loot_chest_prototypes WHERE p=260"
                    ).fetchone()
                ),
                dict(prototype),
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=385"
                ).fetchone()
            )
            mission_toolkit.install(db, profile, activate=True)
            installed = publisher.install(db, batch)
            self.assertEqual(installed, {"rules": 13, "id": batch["id"]})
            self.assertEqual(publisher.install(db, batch), installed)
            with self.assertRaisesRegex(ValueError, "immutable|Published|changed"):
                edited = deepcopy(batch)
                edited["rules"][0]["authority"] += " edited"
                publisher.install(db, edited)

        rule = batch["rules"][0]
        account = self.store.register("quest-chest-owner", "isolated-test-password")[
            "id"
        ]
        generation = self.store.begin_session(account)
        character = self.store.create_character(account, "Taroudium Owner")
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["running"] = [1227]
            state["completed"] = []
            state["objectives"] = []
            state["variables"] = {}
            storage.store(db, character["id"], state)
            quest_inventory.grant(db, character["id"], 16073, 1)
            db.execute(
                "UPDATE characters SET map_id=504,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*rule["approaches"][0], character["id"]),
            )

        def current():
            return self.store.character(account, character["id"])

        def begin():
            return supplies.begin(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 22, 0),
                loaded=True,
                is_hero=False,
            )

        def finish(token):
            return supplies.finish(
                self.store,
                account,
                generation,
                current(),
                token,
                struct.pack(">bh", 2, 13),
                loaded=True,
                is_hero=False,
            )

        def state_value(packet):
            return struct.unpack_from(">h", packet[1], 17)[0]

        other_account = self.store.register(
            "quest-chest-other", "isolated-test-password"
        )["id"]
        other = self.store.create_character(other_account, "Other Owner")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=504,instance_id=0 WHERE id=%s",
                (other["id"],),
            )
        other_snapshot = supplies.snapshots(
            self.store, other_account, 504, character_id=other["id"]
        )
        owner_initial = supplies.snapshots(
            self.store, account, 504, character_id=character["id"]
        )
        self.assertEqual(len(other_snapshot), 13)
        self.assertEqual(other_snapshot, owner_initial)

        # Fail closed on each important begin precondition, restoring only the
        # QA fixture state between independent attempts.
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["running"] = []
            storage.store(db, character["id"], state)
        with self.assertRaisesRegex(ValueError, "stage is not running"):
            begin()
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
            state["running"] = [1227]
            storage.store(db, character["id"], state)
            db.execute("UPDATE characters SET x=x+20 WHERE id=%s", (character["id"],))
        with self.assertRaisesRegex(ValueError, "approach"):
            begin()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (*rule["approaches"][0], character["id"]),
            )
            db.execute(
                "DELETE FROM character_quest_items WHERE character_id=%s AND reference=16073",
                (character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "held tool"):
            begin()
        with self.store.connection() as db:
            quest_inventory.grant(db, character["id"], 16073, 1)
        with self.assertRaises(ValueError):
            supplies.begin(
                self.store,
                account,
                generation + "-stale",
                current(),
                struct.pack(">qHH", rule["object_id"], 22, 0),
                loaded=True,
                is_hero=False,
            )
        with self.assertRaises(ValueError):
            supplies.begin(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 22, 0),
                loaded=True,
                blocked=True,
                is_hero=False,
            )

        started = begin()
        self.assertTrue(started["personal_state"])
        self.assertEqual(started["location"], (504, 0))
        self.assertEqual(
            struct.unpack(">bhqqq", started["packets"][1][1]),
            (1, 13, character["id"], rule["object_id"], 1000),
        )
        self.assertEqual(
            state_value(next(p for p in started["packets"] if p[0] == 12344)), 3
        )
        self.assertEqual(
            state_value(
                supplies.snapshots(
                    self.store, account, 504, character_id=character["id"]
                )[0]
            ),
            3,
        )
        self.assertEqual(begin()["token"], started["token"])
        with self.assertRaisesRegex(ValueError, "too early"):
            finish(started["token"])
        with patch.object(
            self.store, "now", return_value=self.store.now() + timedelta(seconds=2)
        ):
            canceled = supplies.cancel(
                self.store, account, generation, current(), started["token"]
            )
        self.assertEqual(canceled["state"], "canceled")
        self.assertEqual(
            state_value(
                supplies.snapshots(
                    self.store, account, 504, character_id=character["id"]
                )[0]
            ),
            1,
        )
        self.assertEqual(
            current()["quest_items"],
            [{"character_id": character["id"], "reference": 16073, "quantity": 1}],
        )

        started = begin()
        # A same-object callback from a different private instance cannot
        # complete; returning to the ticket's durable origin permits retry.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=42 WHERE id=%s", (character["id"],)
            )
        with patch.object(
            self.store, "now", return_value=self.store.now() + timedelta(seconds=2)
        ):
            with self.assertRaisesRegex(ValueError, "moved during occupation"):
                finish(started["token"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=0 WHERE id=%s", (character["id"],)
            )
        with patch.object(
            self.store, "now", return_value=self.store.now() + timedelta(seconds=2)
        ):
            result = finish(started["token"])
        self.assertEqual(result["state"], "completed")
        self.assertTrue(any(opcode == 13879 for opcode, _ in result["packets"]))
        self.assertEqual(
            sum(
                row["quantity"]
                for row in current()["quest_items"]
                if row["reference"] == 16071
            ),
            1,
        )
        self.assertEqual(
            sum(
                row["quantity"]
                for row in current()["quest_items"]
                if row["reference"] == 16073
            ),
            1,
        )
        self.assertTrue(
            supplies.begin(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 22, 0),
                loaded=True,
                is_hero=False,
            )["replay"]
        )
        with self.store.connection() as db:
            saved = storage.load_locked(db, character["id"])
        self.assertEqual(saved["variables"].get("258"), 1)
        self.assertNotIn(2197, saved["objectives"])
        self.assertEqual(
            supplies.snapshots(
                self.store, other_account, 504, character_id=other["id"]
            ),
            other_snapshot,
        )
        self.assertNotEqual(
            supplies.snapshots(self.store, account, 504, character_id=character["id"]),
            owner_initial,
        )
        owner_finished = supplies.snapshots(
            self.store, account, 504, character_id=character["id"]
        )
        self.assertEqual(state_value(owner_finished[0]), 0)
        self.assertTrue(all(state_value(packet) == 1 for packet in owner_finished[1:]))
