"""One real native productful occupation; private membership is a bounded fixture."""
from copy import deepcopy
import json
from os import environ
from pathlib import Path
import struct
from unittest.mock import patch
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import owned_story_controller, quest_resource_slots, resource_collect
from wakfu_server.achievements import mission_toolkit, storage
from wakfu_server.postgres import Database
from wakfu_server.progression import XP_BY_LEVEL
from test_quest_resource_slots_postgres import _request

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"


class OwnedStoryResourcePostgresTests(PostgresCase):
    def test_native_dig_waits_then_draws_real_inventory_and_progress_once(self):
        selected = json.loads(
            (
                ROOT / "maps/owned_story_profiles/wild-estate-brak-723.v2.json"
            ).read_text()
        )
        native_source = json.loads(
            (
                ROOT / "maps/owned_story_profiles/wild-estate-brak-723.native.v2.json"
            ).read_text()
        )
        geometry = json.loads(
            (
                ROOT / "maps/owned_story_profiles/wild-estate-brak-723.exploration.json"
            ).read_text()
        )
        toolkit = json.loads(
            (
                ROOT / "achievements/mission_profiles/wild-estate-staff-followup.json"
            ).read_text()
        )
        runtime = Database(
            environ["WAKFU_DATABASE_URL"],
            password_file=environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(runtime.close)
        with runtime.connection() as db:
            release = db.execute(
                "SELECT revision,source_sha256,source_export,definition_count FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
            ).fetchone()
            definitions = db.execute(
                "SELECT definition_id,data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=ANY(%s)",
                (release["revision"], [1623, 1677]),
            ).fetchall()
        account = self.store.register("wild-dig-native", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Native Digger")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        profile = deepcopy(native_source["resource_slots"])
        profile["owned_story"] = dict(
            controller_id=selected["id"],
            owner_id=character["id"],
            instance_id=1001,
            native_sources_sha256=selected["native_sources"]["sha256"],
        )
        target = profile["placements"][0]
        clock = [self.store.clock()]
        self.store.clock = lambda: clock[0]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    release["revision"],
                    Jsonb(release["source_sha256"]),
                    release["source_export"],
                    release["definition_count"],
                ),
            )
            for row in definitions:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (release["revision"], row["definition_id"], Jsonb(row["data"])),
                )
            db.execute(
                "UPDATE characters SET level=50,map_id=723,instance_id=1001,x=%s,y=%s,z=%s WHERE id=%s",
                (*target["approach"], character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[50], character["id"]),
            )
            mission_toolkit.install(db, toolkit, activate=True)
            state = storage.load_locked(db, character["id"])
            state["running"] = [1677]
            state["tracking"] = [1677]
            state["completed"] = [1623]
            storage.store(db, character["id"], state)
            quest_resource_slots.install(
                db,
                self.store,
                profile,
                mission_toolkit.definitions(db, toolkit),
                geometry,
            )
        body = _request(1343, *target["position"][:2])
        with patch.object(
            owned_story_controller, "_scope", return_value=(selected, set())
        ):
            prepared = resource_collect.prepare(
                self.store,
                account,
                generation,
                character["id"],
                body,
                reachable=lambda *_: True,
            )
            ticket = resource_collect.reserve(self.store, account, generation, prepared)
            self.assertEqual(ticket["duration_ms"], 2000)
            with self.assertRaises(resource_collect.HarvestNotReady):
                resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
            clock[0] += 2
            with patch(
                "wakfu_server.random_item_actions.PrivateDraw.randbelow", return_value=0
            ):
                outcome = resource_collect.complete(
                    self.store, ticket, struct.pack(">Bh", 2, 3)
                )
            self.assertTrue(outcome["applied"])
            self.assertEqual(outcome["outcome"]["native_products"], {17820: 1})
            replay = resource_collect.complete(
                self.store, ticket, struct.pack(">Bh", 2, 3)
            )
            self.assertFalse(replay["applied"])
        with self.store.connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(3105, progress["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=17820",
                    (character["id"],),
                ).fetchone()["quantity"],
                1,
            )
        self.assertIn(13879, [opcode for opcode, _ in outcome["packets"]])
        self.assertIn(
            (13832, struct.pack(">qi", character["id"], 3105)), outcome["packets"]
        )
        self.assertIn(
            (13371, struct.pack(">qiB", character["id"], 1677, 0)), outcome["packets"]
        )
        self.assertIn(
            (13371, struct.pack(">qiB", character["id"], 1677, 1)), outcome["packets"]
        )
        # The same real acquisition route continues through native bHS5160.
        # Inventory setup is a fixture; conversion and objective delivery are
        # performed only by the ordinary production item-action transaction.
        from wakfu_server.inventory_items import grant
        from wakfu_server.simple_item_actions import use

        current = self.store.character(account, character["id"])
        bag = next(row for row in current["inventory_containers"] if row["kind"] == 0)
        fragment = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=17851,
            quantity=2,
            container=bag["uid"],
            slot=0,
            allowed_references={17851},
        )
        merge = struct.pack(">iq", 5160, fragment["uid"])
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                character["id"],
                merge,
                in_fight=False,
                native_map_id=723,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (fragment["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            db.execute(
                "UPDATE inventory_items SET quantity=3 WHERE uid=%s", (fragment["uid"],)
            )
        assembled = use(
            self.store,
            account,
            generation,
            character["id"],
            merge,
            in_fight=False,
            native_map_id=723,
        )
        self.assertEqual(assembled["consumed"], 3)
        self.assertIn(13879, [opcode for opcode, _ in assembled["packets"]])
        self.assertIn(
            (13832, struct.pack(">qi", character["id"], 3106)), assembled["packets"]
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (fragment["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=17821",
                    (character["id"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertIn(3106, storage.load_locked(db, character["id"])["objectives"])
        # The timer has its own focused checks. Here exercise its unchanged
        # transaction consumer with both genuinely obtained quest components.
        from wakfu_server.application import owned_story_dispatch

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=12,y=-7,z=0 WHERE id=%s", (character["id"],)
            )
        with patch.object(
            owned_story_controller,
            "_scope",
            return_value=(
                selected,
                {"brak-past-introduction", "brak-past-inscription"},
            ),
        ):
            crafted = owned_story_dispatch.interact(
                self.store,
                account,
                generation,
                self.store.character(account, character["id"]),
                struct.pack(">qHH", 20460, 0, 0),
                loaded=True,
                blocked=False,
            )
        self.assertTrue(crafted["applied"])
        self.assertIn(
            (13832, struct.pack(">qi", character["id"], 3108)), crafted["packets"]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT reference,quantity FROM character_quest_items WHERE character_id=%s AND reference=ANY(%s) ORDER BY reference",
                    (character["id"], [17820, 17821, 17822]),
                ).fetchall(),
                [dict(reference=17822, quantity=1)],
            )
            self.assertIn(3108, storage.load_locked(db, character["id"])["objectives"])
