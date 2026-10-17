"""Public monster hunts stay native-backed, finite and account-idempotent."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.objectives import hunts
from wakfu_server.character_levels import MAX_CHARACTER_LEVEL


class _World:
    def __init__(self):
        self.packets = []

    def emit_location(self, map_id, instance_id, opcode, body):
        self.packets.append((map_id, instance_id, opcode, body))


def _register_group_without_wire_validation(
    groups, map_id, instance_id, group_id, members
):
    """Keep persistence exercised while isolating native packet serialization."""
    key = (map_id, instance_id, group_id)
    groups.groups[key] = {
        "members": tuple(members),
        "status": "available",
        "claim": None,
    }
    return key


class ObjectivesHuntsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("public-hunt-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Public Hunt Main")[
            "id"
        ]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.character)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=10 WHERE id=%s", (self.character,))
            # The shared native catalog contains real localized map names;
            # pin this synthetic map's label so inventory assertions stay
            # independent of migration seed data.
            db.execute(
                "UPDATE settings SET value=%s WHERE name='admin_map_names'",
                (Jsonb({"701": "Map 701", "702": "Private Map 702"}),),
            )
            self._seed_native_catalog(db)

    def test_only_online_level245_player_still_schedules_existing_native_hunt(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 245)
        now = datetime.now(timezone.utc)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=245 WHERE id=%s", (self.character,))
            online = db.execute(
                "SELECT c.level FROM sessions s JOIN characters c ON c.id=s.character_id "
                "AND c.account_id=s.account_id WHERE s.expires_at>%s AND c.deleted_at IS NULL",
                (now,),
            ).fetchall()
            self.assertEqual([row["level"] for row in online], [245])
            hunt = hunts.tick(db, now)
            self.assertIsNotNone(hunt)
            self.assertEqual(
                (hunt["monster_ref"], hunt["level"], hunt["status"]),
                (10, 10, "pending"),
            )
            # Player eligibility changes; the reviewed NPC inventory is not
            # inflated to player245 or given a broader native admission cap.
            self.assertEqual(
                db.execute(
                    "SELECT level FROM characters WHERE id=%s", (self.character,)
                ).fetchone()["level"],
                245,
            )

    @staticmethod
    def _seed_native_catalog(db):
        monsters = {
            "monsters": [
                {
                    "ref": 1,
                    "name": "Gobball",
                    "family_id": 5,
                    "min_level": 1,
                    "max_level": 20,
                    "native_abilities": [],
                },
                {
                    "ref": 10,
                    "name": "Gobball real",
                    "family_id": 5,
                    "min_level": 5,
                    "max_level": 20,
                    "native_abilities": [101],
                },
                {
                    "ref": 11,
                    "name": "Gobball utility",
                    "family_id": 5,
                    "min_level": 5,
                    "max_level": 20,
                    "native_abilities": [102],
                },
                {
                    "ref": 12,
                    "name": "Tofu real",
                    "family_id": 6,
                    "min_level": 5,
                    "max_level": 20,
                    "native_abilities": [103],
                },
            ]
        }
        plans = {
            "plans": [
                {
                    "map_id": 701,
                    "instance_id": 0,
                    "region_id": 9,
                    "members": [{"reference": 1, "x": 3, "y": 4, "z": 0}],
                },
                {
                    "map_id": 702,
                    "instance_id": 77,
                    "region_id": 9,
                    "members": [{"reference": 1, "x": 6, "y": 7, "z": 0}],
                },
            ]
        }
        enabled = {
            "10": {"min_level": 10, "max_level": 15},
            "11": {"min_level": 1, "max_level": 20},
            "12": {"min_level": 1, "max_level": 20},
        }
        documents = {
            "monsters.json": json.dumps(monsters, separators=(",", ":")).encode(),
            "initial-monster-population.json": json.dumps(
                plans, separators=(",", ":")
            ).encode(),
            "native-npc-spell-effect-trees.json": b"{}",
        }
        revision = hashlib.sha256(b"objective-hunt-test-native-catalog").hexdigest()
        source_bytes = sum(len(raw) for raw in documents.values())
        db.execute(
            "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) VALUES(%s,%s,%s,true)",
            (revision, len(documents), source_bytes),
        )
        for path, raw in documents.items():
            db.execute(
                "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,0)",
                (revision, path, raw, hashlib.sha256(raw).hexdigest(), len(raw)),
            )
        db.execute(
            "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) VALUES(%s,'native-npc-spell-effect-trees.json','activation_policy','enabled_monsters',%s)",
            (revision, Jsonb(enabled)),
        )
        db.execute(
            "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)", (revision,)
        )

    def test_native_inventory_uses_enabled_named_families_and_public_habitats_only(
        self,
    ):
        with self.store.connection() as db:
            rows = hunts.inventory(db)
        self.assertEqual(
            rows,
            [
                {
                    "monster_ref": 10,
                    "monster_name": "Gobball real",
                    "level": 10,
                    "map_id": 701,
                    "map_name": "Map 701",
                    "region_id": 9,
                    "anchor": [3, 4, 0],
                }
            ],
        )

    def test_scheduler_is_idempotent_and_replaces_only_expired_hunts(self):
        now = datetime.now(timezone.utc)
        with self.store.connection() as db:
            first = hunts.tick(db, now)
            replay = hunts.tick(db, now + timedelta(seconds=1))
            self.assertEqual((first["status"], replay["id"]), ("pending", first["id"]))
            db.execute(
                "UPDATE objectives_public_hunts SET status='alive' WHERE id=%s",
                (first["id"],),
            )
            public = hunts.snapshot(
                db, {"account_id": self.account, "character_id": self.character}
            )
            self.assertEqual(
                (public["monster_ref"], public["map_id"], public["status"]),
                (10, 701, "alive"),
            )
            second = hunts.tick(db, first["expires_at"] + timedelta(seconds=1))
            rows = db.execute(
                "SELECT id,status FROM objectives_public_hunts ORDER BY id"
            ).fetchall()
            active = db.execute(
                "SELECT count(*) n FROM objectives_public_hunts WHERE status IN('pending','alive','in_fight')"
            ).fetchone()["n"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual([row["status"] for row in rows], ["expired", "pending"])
        self.assertEqual(active, 1)

    def test_hunt_location_uses_exact_native_territory_binding(self):
        with self.store.connection() as db:
            hunt = hunts.tick(db, datetime.now(timezone.utc))
            db.execute(
                "UPDATE objectives_public_hunts SET status='alive' WHERE id=%s",
                (hunt["id"],),
            )
            definition = {
                "key": "content-v1.region.701.9",
                "title": "Territory: Gobball Village [9]",
                "description": "A native region label.",
                "kind": "achievement",
                "enabled": True,
                "objectives": [
                    {
                        "key": "entered",
                        "event": "region_entered",
                        "filters": {"map_id": 701, "region_id": 9},
                        "target": 1,
                    }
                ],
                "schedule": {"type": "once", "timezone": "America/Bogota"},
                "rewards": [],
            }
            db.execute(
                "INSERT INTO objectives_definitions(key,definition,revision) VALUES(%s,%s,1)",
                (definition["key"], Jsonb(definition)),
            )
            located = hunts.snapshot(
                db, {"account_id": self.account, "character_id": self.character}
            )
            definition["objectives"][0]["filters"]["region_id"] = 10
            db.execute(
                "UPDATE objectives_definitions SET definition=%s,revision=2 WHERE key=%s",
                (Jsonb(definition), definition["key"]),
            )
            mismatched = hunts.snapshot(
                db, {"account_id": self.account, "character_id": self.character}
            )
        self.assertEqual(located["region_name"], "Gobball Village")
        self.assertEqual(located["location"], "Map 701 · Gobball Village")
        self.assertIn("Gobball Village in Map 701", located["clue"])
        self.assertIsNone(mismatched["region_name"])
        self.assertEqual(mismatched["location"], "Map 701")
        self.assertIn("wild habitats of Map 701", mismatched["clue"])

    def test_hunt_requires_live_world_presence_and_pending_spawn_waits_for_reconnect(
        self,
    ):
        now = datetime.now(timezone.utc)
        with self.store.connection() as db:
            db.execute("DELETE FROM sessions WHERE account_id=%s", (self.account,))
            self.assertIsNone(hunts.tick(db, now))
            self.assertEqual(
                db.execute("SELECT count(*) n FROM objectives_public_hunts").fetchone()[
                    "n"
                ],
                0,
            )

        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.character)
        with self.store.connection() as db:
            hunt = hunts.tick(db, now)
        self.assertEqual(hunt["status"], "pending")

        # A web embed token or an old queued hunt cannot stand in for an active
        # selected World session; reconnecting resumes the same hunt once.
        with self.store.connection() as db:
            db.execute("DELETE FROM sessions WHERE account_id=%s", (self.account,))
        from wakfu_server.combat_group_store import PersistentGroups

        groups = PersistentGroups(self.store)
        world = _World()

        def make_monster(reference, level, identity, *, map_id, instance_id, x, y, z):
            return {
                "id": identity,
                "reference": reference,
                "level": level,
                "map_id": map_id,
                "instance_id": instance_id,
                "x": x,
                "y": y,
                "z": z,
            }

        publication_patches = (
            patch(
                "wakfu_server.objectives.hunts._spawn_position", return_value=(4, 4, 0)
            ),
            patch("wakfu_server.monster_minigame_policy.require_ordinary_spawn"),
            patch("wakfu_server.npc_actor_identity.allocate_block", return_value=44200),
            patch("wakfu_server.monsters.owned_instance", side_effect=make_monster),
            patch(
                "wakfu_server.combat.combat_groups.Groups.register",
                new=_register_group_without_wire_validation,
            ),
            patch(
                "wakfu_server.combat_monster_world.spawn_group",
                return_value=b"native-spawn",
            ),
            patch(
                "wakfu_server.combat_monster_world.remove_message",
                return_value=(12304, b"native-remove"),
            ),
        )
        for item in publication_patches:
            item.start()
            self.addCleanup(item.stop)

        self.assertEqual(hunts.publish(self.store, groups, world), [])
        with self.store.connection() as db:
            still_pending = db.execute(
                "SELECT status,group_id FROM objectives_public_hunts WHERE id=%s",
                (hunt["id"],),
            ).fetchone()
            persisted_groups = db.execute(
                "SELECT count(*) n FROM combat_groups WHERE group_id=44200"
            ).fetchone()["n"]
        self.assertEqual(
            (still_pending["status"], still_pending["group_id"]), ("pending", None)
        )
        self.assertEqual(persisted_groups, 0)
        self.assertEqual(world.packets, [])

        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.character)
        first = hunts.publish(self.store, groups, world)
        replay = hunts.publish(self.store, groups, world)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT status,group_id,published_at FROM objectives_public_hunts WHERE id=%s",
                (hunt["id"],),
            ).fetchone()
        self.assertEqual(len(first), 2)
        self.assertEqual(replay, [])
        self.assertEqual(len(world.packets), 2)
        self.assertEqual(saved["status"], "alive")
        self.assertIsNotNone(saved["group_id"])
        self.assertIsNotNone(saved["published_at"])

    def test_publish_registers_one_persistent_public_group_and_expiry_removes_it(self):
        # Use the production canonical module identity; the combat package
        # shim is distinct and lacks the maps namespace extension.
        from wakfu_server.combat_group_store import PersistentGroups

        now = datetime.now(timezone.utc)
        with self.store.connection() as db:
            hunt = hunts.tick(db, now)
        self.assertEqual(hunt["status"], "pending")
        groups = PersistentGroups(self.store)
        world = _World()

        def make_monster(reference, level, identity, *, map_id, instance_id, x, y, z):
            return {
                "id": identity,
                "reference": reference,
                "level": level,
                "map_id": map_id,
                "instance_id": instance_id,
                "x": x,
                "y": y,
                "z": z,
            }

        with patch(
            "wakfu_server.objectives.hunts._spawn_position", return_value=(4, 4, 0)
        ), patch("wakfu_server.monster_minigame_policy.require_ordinary_spawn"), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=44000
        ), patch(
            "wakfu_server.monsters.owned_instance", side_effect=make_monster
        ), patch(
            "wakfu_server.combat.combat_groups.Groups.register",
            new=_register_group_without_wire_validation,
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group",
            return_value=b"native-spawn",
        ), patch(
            "wakfu_server.combat_monster_world.remove_message",
            return_value=(12304, b"native-remove"),
        ):
            first_packets = hunts.publish(self.store, groups, world)
            second_packets = hunts.publish(self.store, groups, world)
            with self.store.connection() as db:
                saved = db.execute(
                    "SELECT status,group_id,monster_id,published_at FROM objectives_public_hunts WHERE id=%s",
                    (hunt["id"],),
                ).fetchone()
                group = db.execute(
                    "SELECT status,members FROM combat_groups WHERE map_id=701 AND instance_id=0 AND group_id=44000"
                ).fetchone()
            # Publication first removes a possibly orphaned actor with the
            # same stable id, then emits the new native spawn.
            self.assertEqual(
                first_packets,
                [
                    (701, 12304, b"native-remove"),
                    (701, 12608, b"native-spawn"),
                ],
            )
            self.assertEqual(second_packets, [])
            self.assertEqual(
                world.packets,
                [(map_id, 0, opcode, body) for map_id, opcode, body in first_packets],
            )
            self.assertEqual(
                (saved["status"], saved["group_id"], saved["monster_id"]),
                ("alive", 44000, -44000),
            )
            self.assertIsNotNone(saved["published_at"])
            self.assertEqual(group["status"], "available")
            self.assertEqual(group["members"][0]["id"], -44000)

            with self.store.connection() as db:
                db.execute(
                    "UPDATE objectives_public_hunts SET status='expired' WHERE id=%s",
                    (hunt["id"],),
                )
            removed = hunts.publish(self.store, groups, world)
            with self.store.connection() as db:
                group_status = db.execute(
                    "SELECT status FROM combat_groups WHERE map_id=701 AND instance_id=0 AND group_id=44000"
                ).fetchone()["status"]
                removed_at = db.execute(
                    "SELECT removed_at FROM objectives_public_hunts WHERE id=%s",
                    (hunt["id"],),
                ).fetchone()["removed_at"]
            self.assertEqual(removed, [(701, 12304, b"native-remove")])
            self.assertEqual(
                world.packets,
                [
                    (map_id, 0, opcode, body)
                    for map_id, opcode, body in first_packets + removed
                ],
            )
            self.assertEqual(group_status, "defeated")
            self.assertIsNotNone(removed_at)

    def test_defeated_hunt_pays_once_to_an_account_with_three_participating_heroes(
        self,
    ):
        from wakfu_server.combat import fight_store

        heroes = [
            self.store.create_character(self.account, name)["id"]
            for name in ("Public Hunt Hero A", "Public Hunt Hero B")
        ]
        fight_id = fight_store.create(
            self.store, self.account, self.generation, self.character, team=0
        )
        with self.store.connection() as db:
            for hero in heroes:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (fight_id, hero, self.account, self.generation),
                )
            fight_store.finish(
                self.store, db, self.account, self.generation, self.character, fight_id
            )
            policy = db.execute(
                "SELECT key,policy,revision FROM objectives_reward_policies WHERE key='content-v1.dungeon'"
            ).fetchone()
            hunt = db.execute(
                "INSERT INTO objectives_public_hunts(monster_ref,monster_name,level,map_id,map_name,region_id,anchor,group_id,monster_id,status,reward_snapshot,points,created_at,expires_at,fight_id) "
                "VALUES(10,'Gobball real',10,701,'Map 701',9,%s,44100,-44100,'in_fight',%s,100,%s,%s,%s) RETURNING *",
                (
                    Jsonb([3, 4, 0]),
                    Jsonb(dict(policy)),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc) + timedelta(hours=1),
                    fight_id,
                ),
            ).fetchone()

        with patch(
            "wakfu_server.objectives.reward_policies.expand",
            return_value=[{"kind": "kamas", "amount": 55}],
        ):
            with self.store.connection() as db:
                settled = hunts.settle_group(
                    db, (hunt["map_id"], 0, hunt["group_id"]), fight_id, True
                )
                replay = hunts.settle_group(
                    db, (hunt["map_id"], 0, hunt["group_id"]), fight_id, True
                )
                winners = db.execute(
                    "SELECT account_id,character_id FROM objectives_public_hunt_winners WHERE hunt_id=%s",
                    (hunt["id"],),
                ).fetchall()
                receipts = db.execute(
                    "SELECT character_id,definition_key,period_key,payload FROM objectives_rewards WHERE definition_key='public-world-hunt' ORDER BY character_id,reward_index"
                ).fetchall()
                points_rows = db.execute(
                    "SELECT account_id,source_key,points,category FROM objectives_points WHERE account_id=%s AND source_key=%s",
                    (self.account, f"public-hunt:{hunt['id']}"),
                ).fetchall()
                notices = db.execute(
                    "SELECT source_key,title,points FROM objectives_completion_notices WHERE account_id=%s AND source_key=%s",
                    (self.account, f"public-hunt:{hunt['id']}"),
                ).fetchall()
                final_status = db.execute(
                    "SELECT status FROM objectives_public_hunts WHERE id=%s",
                    (hunt["id"],),
                ).fetchone()["status"]

        self.assertEqual(settled["status"], "defeated")
        self.assertIsNone(replay)
        self.assertEqual(final_status, "defeated")
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0]["account_id"], self.account)
        self.assertIn(winners[0]["character_id"], [self.character, *heroes])
        self.assertEqual(len(receipts), 1)
        self.assertEqual(
            (
                receipts[0]["definition_key"],
                receipts[0]["period_key"],
                receipts[0]["payload"],
            ),
            (
                "public-world-hunt",
                f"hunt:{hunt['id']}",
                {"kind": "kamas", "amount": 55},
            ),
        )
        self.assertEqual(len(points_rows), 1)
        self.assertEqual(
            (
                points_rows[0]["source_key"],
                points_rows[0]["points"],
                points_rows[0]["category"],
            ),
            (f"public-hunt:{hunt['id']}", 100, "public_hunt"),
        )
        self.assertEqual(len(notices), 1)
        self.assertEqual(
            (notices[0]["source_key"], notices[0]["title"], notices[0]["points"]),
            (f"public-hunt:{hunt['id']}", "World hunt: Gobball real", 100),
        )


if __name__ == "__main__":
    unittest.main()
