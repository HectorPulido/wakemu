"""Native daily acquisition, actual settlement producers and anchored resets."""
import struct
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_guild_service_postgres as guild_fixture
from wakfu_server.guild_service import GuildService
from wakfu_server.guild_native_validators import encode_blazon
from wakfu_server.guild_primary_policy import management_policy
from wakfu_server.guild_progression import progression_policy
from wakfu_server import guild_daily_quests as daily
from wakfu_server.achievements import service, storage, wire


class GuildDailyQuestPostgresTests(PostgresCase):
    _player = guild_fixture.GuildServicePostgresTests._player
    _create = guild_fixture.GuildServicePostgresTests._create

    def setUp(self):
        super().setUp()
        self.service = GuildService(self.store)
        self.blazon = encode_blazon(
            emblem_id=1, background_id=2, background_color=3, emblem_color=4
        )
        self.policy = progression_policy(management_policy(enabled=True), enabled=True)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        self.owner = self._player("Daily Owner")
        self.guild_id = self._create(self.owner, "Native Daily Guild")["guild"]["id"]
        self.clock = self.store.now()
        self.now_patch = patch.object(
            self.store,
            "now",
            side_effect=lambda offset=0: self.clock + timedelta(seconds=offset),
        )
        self.now_patch.start()
        self.addCleanup(self.now_patch.stop)
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP+interval '10 days' WHERE account_id=%s",
                (self.owner["account"],),
            )
            db.execute(
                "UPDATE characters SET map_id=1134,x=-22,y=38,z=-8 WHERE id=%s",
                (self.owner["character"],),
            )
        self.character = self.store.character(
            self.owner["account"], self.owner["character"]
        )

    def accept(self, identity):
        return daily.activate(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            struct.pack(">i", identity),
        )

    def points(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT current_points FROM guilds WHERE id=%s", (self.guild_id,)
            ).fetchone()["current_points"]

    def fight(self, *, boss=False, count=10, level=1):
        with self.store.connection() as db:
            identity = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (identity, self.owner["character"], self.owner["account"]),
            )
            if boss:
                party = db.execute(
                    "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                    (self.owner["character"],),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (self.owner["character"], party),
                )
                instance = db.execute(
                    "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,1,%s,1,1,1134,1,1,1134) RETURNING instance_id",
                    (party, self.owner["character"]),
                ).fetchone()["instance_id"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                    (
                        instance,
                        party,
                        self.owner["character"],
                        self.owner["generation"],
                    ),
                )
                rooms = [dict(order=1, monsters=[dict(ref_id=2, role="boss")])]
                db.execute(
                    "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,status) VALUES(%s,%s,%s,%s,'completed')",
                    (instance, party, "a" * 64, Jsonb(rooms)),
                )
                db.execute(
                    "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,status,result_revision,result) VALUES(%s,%s,1,0,'victory',1,%s)",
                    (identity, instance, Jsonb(dict(completed=True))),
                )
        actors = {
            self.owner["character"]: SimpleNamespace(
                controlled=True,
                owner_id=self.owner["account"],
                team=0,
                hp=1,
                effective_level=1,
            )
        }
        roster = []
        for i in range(count):
            actors[-i - 1] = SimpleNamespace(
                controlled=False, team=1, hp=0, effective_level=level
            )
            roster.append(dict(id=-i - 1, ref=2))
        return (
            SimpleNamespace(
                id=identity,
                phase="finished",
                winner=0,
                actors=actors,
                native_summon_registrations={},
                native_companion_sources={},
            ),
            roster,
        )

    def test_actual_kill_and_boss_settlement_are_scoped_and_replay_safe(self):
        for identity in (1389, 1391):
            self.assertTrue(self.accept(identity)["applied"])
            self.assertFalse(self.accept(identity)["applied"])
        fight, roster = self.fight(count=10, level=37)
        with self.store.connection() as db:
            service.settle(db, self.store, self.character, fight, roster)
        self.assertEqual(self.points(), 0)  # 36 levels outside original ±35.
        fight, roster = self.fight(count=10)
        with self.store.connection() as db:
            first = service.settle(db, self.store, self.character, fight, roster)
            self.assertFalse(first["replay"])
            self.assertTrue(
                service.settle(db, self.store, self.character, fight, roster)["replay"]
            )
            state = storage.load_locked(db, self.character["id"])
            self.assertIn(1389, state["completed"])
            self.assertNotIn(1391, state["completed"])
        self.assertEqual(self.points(), 15)
        fight, roster = self.fight(boss=True, count=1)
        with self.store.connection() as db:
            service.settle(db, self.store, self.character, fight, roster)
            self.assertIn(
                1391, storage.load_locked(db, self.character["id"])["completed"]
            )
            self.assertEqual([], storage.pending_rewards(db, self.character["id"]))
        self.assertEqual(self.points(), 35)

    def test_actual_item_craft_completion_counts_once(self):
        from wakfu_server.craft_catalog import load_catalog
        from wakfu_server import crafting, inventory_items
        from wakfu_server.profession_store import ensure_learned
        from wakfu_server.inventory_move import STACKS

        self.accept(1390)
        ensure_learned(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.character["id"],
            [40],
        )
        for reference in (2504, 11451):
            character = self.store.character(
                self.owner["account"], self.character["id"]
            )
            inventory_items.grant(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.character["id"],
                reference=reference,
                quantity=50,
                container=character["inventory_containers"][0]["uid"],
                slot=reference % 20,
                allowed_references=set(STACKS),
            )
        station = dict(
            table_uid=31517,
            map_id=1134,
            instance_id=0,
            definition_id=72,
            profession_id=40,
            in_range=True,
        )
        catalog = load_catalog()
        started = crafting.begin(
            self.store,
            catalog,
            self.owner["account"],
            self.owner["generation"],
            self.character["id"],
            12231,
            struct.pack(">qii", 31517, 3600, 10),
            station=station,
        )
        self.clock += timedelta(seconds=30)
        result = crafting.complete(
            self.store,
            catalog,
            self.owner["account"],
            self.owner["generation"],
            self.character["id"],
            started["token"],
            started["version"],
            bytes.fromhex("020008"),
            station=station,
        )
        self.assertFalse(result["replay"])
        self.assertTrue(
            crafting.complete(
                self.store,
                catalog,
                self.owner["account"],
                self.owner["generation"],
                self.character["id"],
                started["token"],
                started["version"],
                bytes.fromhex("020008"),
                station=station,
            )["replay"]
        )
        with self.store.connection() as db:
            state = storage.load_locked(db, self.character["id"])
            self.assertEqual(state["variables"]["294"], 10)
            self.assertIn(1390, state["completed"])
        self.assertEqual(self.points(), 15)

    def test_owned_native_boundary_no_sql_cache_resets_tracking_and_clock(self):
        self.accept(1389)
        with self.store.connection() as db:
            service.track(db, self.character, 1389, True)
            dates = daily.activation_dates(db, self.character["id"])
            self.assertEqual(dates[1389], int(self.clock.timestamp() * 1000))
            state = storage.load_locked(db, self.character["id"])
            encoded = wire.section(state, activation_dates=dates)
            self.assertIn(struct.pack(">q", dates[1389]), encoded)
        boundary, packets = daily.synchronize_owned(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.character["id"],
        )
        self.assertEqual(packets, [])
        with patch.object(
            self.store, "connection", side_effect=AssertionError("No idle SQL")
        ):
            self.assertEqual(
                (boundary, []),
                daily.synchronize_owned(
                    self.store,
                    self.owner["account"],
                    self.owner["generation"],
                    self.character["id"],
                    next_boundary_ms=boundary,
                ),
            )
        self.clock += timedelta(days=1)
        next_boundary, packets = daily.synchronize_owned(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.character["id"],
            next_boundary_ms=boundary,
        )
        self.assertGreater(next_boundary, boundary)
        self.assertIn((13205, struct.pack(">qi", self.character["id"], 1389)), packets)
        with self.store.connection() as db:
            state = storage.load_locked(db, self.character["id"])
            self.assertNotIn(1389, state["running"])
            self.assertNotIn(1389, state["tracking"])
        self.assertTrue(self.accept(1389)["applied"])
        with self.assertRaises(ValueError):
            daily.activate(
                self.store,
                self.owner["account"],
                "stale",
                self.character["id"],
                struct.pack(">i", 1390),
            )
