"""One isolated source-bound Tower ground-entry criterion regression."""
import json
import struct
from pathlib import Path
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

CONFIG = (
    Path(__file__).parent / "fixtures/tower_ground_entry/native_dungeon_133_v5.json"
)


class TowerGroundEntryPolicyTests(PostgresCase):
    def test_native_trigger_waives_only_registered_hub_story_gate(self):
        from wakfu_server import dungeon_runtime_config, dungeon_instances
        from wakfu_server import (
            quest_npc,
            quest_ground_entry,
            dungeon_criteria,
            dungeon_entry_access,
        )
        from wakfu_server.achievements import storage
        from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

        config_doc = json.loads(CONFIG.read_text())
        config = (
            config_doc["configuration"] if "configuration" in config_doc else config_doc
        )
        quest_doc = json.loads(
            Path(quest_npc.__file__)
            .with_name("native_quest_conversation_contracts.json")
            .read_text()
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, config)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"schema_version": 1, "routes": [config["route"]]}),),
            )
            quest_npc.install(db, quest_doc)
        self.assertTrue(dungeon_instances.load_runtime_routes(self.store))
        self.assertIn(29076, dungeon_instances.entry_object_ids(1202))
        self.assertEqual(
            dungeon_entry_access.policy(self.store),
            {
                "version": 1,
                "bypass_mission_prerequisites": True,
                "bypass_state_prerequisites": True,
            },
        )

        def create_actor(name):
            account = self.store.register(name, "isolated-test-password")["id"]
            created = self.store.create_character(account, name)
            generation = self.store.begin_session(account)
            actor = self.store.select_character(account, generation, created["id"])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=36,map_id=1201,instance_id=0,x=0,y=-3,z=0 WHERE id=%s",
                    (actor["id"],),
                )
            return account, generation, actor["id"]

        def snapshot(account, character_id):
            with self.store.connection() as db:
                actor = self.store.character(account, character_id, db)
                authority = storage.load_locked(db, character_id)
                rewards = storage.pending_rewards(db, character_id)
                discoveries = db.execute(
                    "SELECT kind,transport_id FROM transport_discoveries WHERE account_id=%s ORDER BY kind,transport_id",
                    (account,),
                ).fetchall()
            stable_actor = {
                key: actor.get(key)
                for key in (
                    "xp",
                    "inventory_items",
                    "quest_items",
                    "account_quest_items",
                )
            }
            return stable_actor, authority, rewards, discoveries

        def enter(account, generation, character_id, *, action=5, blocked=False):
            actor = self.store.character(account, character_id)
            self.assertEqual(
                (
                    actor["map_id"],
                    actor["instance_id"],
                    actor["x"],
                    actor["y"],
                    actor["z"],
                ),
                (1201, 0, 0, -3, 0),
            )
            return quest_ground_entry.handle(
                self.store,
                account,
                generation,
                actor,
                struct.pack(">qHH", 29090, action, 0),
                blocked=blocked,
            )

        account, generation, character_id = create_actor("tower-ground-red-green")
        before = snapshot(account, character_id)
        with self.store.connection() as db:
            authority = storage.load_locked(db, character_id)
        queries = queries_from_snapshot(
            {key: authority[key] for key in ("running", "completed", "objectives")}
        )

        # The native story fact is absent and the original strict predicate
        # remains RED on this same registered destination.
        strict_result = dungeon_criteria.evaluate(
            self.store,
            "IsAchievementComplete(3908)",
            character=self.store.character(account, character_id),
            queries=queries,
        )
        self.assertIs(strict_result, False)
        self.assertEqual(snapshot(account, character_id), before)

        # With the actual route installed and the default migration policy, the
        # same source-bound trigger uses normal teleporter resolution/transition.
        green = enter(account, generation, character_id)
        self.assertFalse(green["blocked_by_quest"])
        self.assertEqual(green["transport"]["destination"]["map_id"], 1202)
        after_actor = self.store.character(account, character_id)
        self.assertEqual(
            (
                after_actor["map_id"],
                after_actor["x"],
                after_actor["y"],
                after_actor["z"],
            ),
            (1202, 0, 0, 0),
        )
        after = snapshot(account, character_id)
        self.assertEqual(after, before)

        # A second unprogressed character confirms an unregistered destination
        # remains on the strict story gate even with the default policy enabled.
        strict_account, strict_generation, strict_character = create_actor(
            "tower-ground-unreg"
        )
        strict_before = snapshot(strict_account, strict_character)
        with self.assertRaises(ValueError):
            enter(strict_account, strict_generation, strict_character, blocked=True)
        with self.assertRaises(ValueError):
            enter(strict_account, strict_generation, strict_character, action=4)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=1 WHERE id=%s", (strict_character,))
        strict_actor = self.store.character(strict_account, strict_character)
        with self.assertRaisesRegex(ValueError, "actual walked cell"):
            quest_ground_entry.handle(
                self.store,
                strict_account,
                strict_generation,
                strict_actor,
                struct.pack(">qHH", 29090, 5, 0),
                blocked=False,
            )
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=0 WHERE id=%s", (strict_character,))
        from wakfu_server import native_catalog

        original_record = native_catalog.record

        def tampered_source(*args, **kwargs):
            record = dict(original_record(*args, **kwargs))
            record["payload_hex"] = "00"
            return record

        with patch.object(native_catalog, "record", side_effect=tampered_source):
            with self.assertRaisesRegex(ValueError, "differs from its native source"):
                enter(strict_account, strict_generation, strict_character)
        with patch.object(
            dungeon_instances, "entry_object_ids", return_value=frozenset()
        ):
            strict = enter(strict_account, strict_generation, strict_character)
        self.assertTrue(strict["blocked_by_quest"])
        self.assertEqual(snapshot(strict_account, strict_character), strict_before)

        # The policy remains fail-closed when mission/state bypasses are disabled.
        off_account, off_generation, off_character = create_actor("tower-ground-policy")
        off_before = snapshot(off_account, off_character)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_entry_access_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "bypass_mission_prerequisites": False,
                            "bypass_state_prerequisites": False,
                        }
                    ),
                ),
            )
        off = enter(off_account, off_generation, off_character)
        self.assertTrue(off["blocked_by_quest"])
        self.assertEqual(snapshot(off_account, off_character), off_before)
