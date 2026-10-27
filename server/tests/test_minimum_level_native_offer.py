"""Actual native low-level entrance offer and durable World action boundary.

Only immutable catalog SQL is delegated to the original read-only catalog.
Application identity, policy, authored rule, queue and receipts are isolated.
Room initialization and combat are qualified by separate admission components.
"""
from copy import deepcopy
import os
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_dungeon_instances as dungeon_fixture


class MinimumLevelNativeOfferTests(PostgresCase):
    player = dungeon_fixture.DungeonInstanceTests.player

    def test_original_minimum_offer_queue_resolve_and_source_policy_controls(self):
        from wakfu_server.postgres import Database
        from wakfu_server.objectives import seasonal_entry, player_actions
        from wakfu_server.custom_tasks import player_actions as world_actions
        from wakfu_server.maps import dungeon_entry_access

        source = Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(source.close)
        player = self.player("minimum-offer")
        identity = dict(
            account_id=player["account"],
            character_id=player["character"]["id"],
            generation=player["generation"],
        )
        with source.connection() as native:
            native.execute("SET TRANSACTION READ ONLY")
            config = native.execute(
                "SELECT c.* FROM dungeon_runtime_configurations c "
                "JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version) "
                "WHERE c.route_key='native_dungeon_133'"
            ).fetchone()
            rule = native.execute(
                "SELECT * FROM objectives_definitions WHERE key='content-v1.dungeon.133'"
            ).fetchone()
            self.assertIsNotNone(config)
            self.assertIsNotNone(rule)
            route = config["configuration"]["route"]
            self.assertEqual(
                (
                    route["entry_map_id"],
                    route["entry_object_id"],
                    route["destination_id"],
                    route["criterion"],
                ),
                (1202, 29076, 3117, "GetRealLevel() >= 36"),
            )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) "
                    "VALUES(%s,%s,%s)",
                    (
                        config["route_key"],
                        config["policy_version"],
                        Jsonb(config["configuration"]),
                    ),
                )
                db.execute(
                    "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version) VALUES(%s,%s)",
                    (config["route_key"], config["policy_version"]),
                )
                db.execute(
                    "INSERT INTO objectives_definitions(key,definition,revision) VALUES(%s,%s,%s) "
                    "ON CONFLICT(key) DO NOTHING",
                    (rule["key"], Jsonb(rule["definition"]), rule["revision"]),
                )
                installed_rule = db.execute(
                    "SELECT definition FROM objectives_definitions WHERE key=%s",
                    (rule["key"],),
                ).fetchone()["definition"]
                self.assertEqual(installed_rule, rule["definition"])
                db.execute(
                    "UPDATE characters SET map_id=1202,instance_id=0,x=-22,y=-7,z=0 WHERE id=%s",
                    (identity["character_id"],),
                )

            class CatalogAndApplication:
                def __init__(self, application):
                    self.application = application

                def execute(self, sql, parameters=None):
                    if "FROM native_catalog_" in sql:
                        return native.execute(sql, parameters)
                    return self.application.execute(sql, parameters)

            with self.store.connection() as db:
                joined = CatalogAndApplication(db)
                before = deepcopy(
                    self.store.character(
                        identity["account_id"], identity["character_id"]
                    )
                )
                offers = seasonal_entry.actions(joined, identity)
                offer = next(
                    row
                    for row in offers
                    if row["key"] == "dungeon.enter.native_dungeon_133"
                )
                self.assertTrue(offer["enabled"])
                self.assertEqual(offer["target"]["criterion"], route["criterion"])
                self.assertEqual(
                    struct.unpack(">qiBi", seasonal_entry.request(offer["target"])),
                    (29076, 3117, 0, 2),
                )
                actor = dict(before, map_id=1202, instance_id=0, x=-22, y=-7, z=0)
                self.assertFalse(
                    dungeon_entry_access.minimum_offer_allowed(
                        db,
                        route["criterion"] + " and false",
                        character=actor,
                        destination_map_id=route["start_map_id"],
                    )
                )
                for key, value in (
                    ("enforce_minimum_level", True),
                    ("enforce_minimum_level", "false"),
                ):
                    with self.subTest(policy=value):
                        db.execute(
                            "UPDATE settings SET value=%s WHERE name='instance_entry_level_policy'",
                            (Jsonb(dict(version=1, **{key: value})),),
                        )
                        if type(value) is bool:
                            self.assertFalse(
                                any(
                                    x["key"] == offer["key"]
                                    for x in seasonal_entry.actions(joined, identity)
                                )
                            )
                        else:
                            with self.assertRaises(ValueError):
                                seasonal_entry.actions(joined, identity)
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='instance_entry_level_policy'",
                    (Jsonb(dict(version=1, enforce_minimum_level=False)),),
                )
                db.execute(
                    "UPDATE characters SET x=-21 WHERE id=%s",
                    (identity["character_id"],),
                )
                self.assertFalse(
                    any(
                        x["key"] == offer["key"]
                        for x in seasonal_entry.actions(joined, identity)
                    )
                )
                db.execute(
                    "UPDATE characters SET x=-22 WHERE id=%s",
                    (identity["character_id"],),
                )
                # Bound this component's action menu to the actual seasonal
                # provider, excluding unrelated PvP and paid public travel.
                with patch.object(
                    player_actions, "allowed_actions", seasonal_entry.actions
                ):
                    receipt = player_actions.enqueue(
                        joined, identity, offer["key"], "native-minimum-offer"
                    )
                    replay = player_actions.enqueue(
                        joined, identity, offer["key"], "native-minimum-offer"
                    )
                self.assertEqual(receipt["id"], replay["id"])
                action = world_actions.claim(db, identity)
                self.assertIsNotNone(action)
                world_actions.lock_running(db, action)
                self.assertEqual(
                    seasonal_entry.resolve(joined, action), offer["target"]
                )
                db.execute(
                    "UPDATE characters SET x=-21 WHERE id=%s",
                    (identity["character_id"],),
                )
                with self.assertRaises(ValueError):
                    seasonal_entry.resolve(joined, action)
                db.execute(
                    "UPDATE characters SET x=-22 WHERE id=%s",
                    (identity["character_id"],),
                )
                self.assertTrue(
                    world_actions.finish(
                        db,
                        action,
                        dict(success=True, component="resolved-native-entry-request"),
                    )
                )
                self.assertIsNone(world_actions.claim(db, identity))
            after = self.store.character(
                identity["account_id"], identity["character_id"]
            )
            self.assertEqual(
                tuple(
                    after[k]
                    for k in ("id", "level", "hp", "max_hp", "map_id", "instance_id")
                ),
                tuple(
                    before[k]
                    for k in ("id", "level", "hp", "max_hp", "map_id", "instance_id")
                ),
            )
