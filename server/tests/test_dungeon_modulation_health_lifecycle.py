"""Actual party/hero movement and canonical health share one transaction."""
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_transport, heroes, health_policy
from wakfu_server.characters.dungeon_modulation_health import reconcile
from wakfu_server.maps import dungeon_exit, dungeon_recovery


class DungeonModulationHealthLifecycleTests(PostgresCase):
    install_context_policy = Fixture.install_context_policy
    player = Fixture.player

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.main = self.player("main")
        self.account = self.main["account"]
        self.generation = self.main["generation"]
        hero = self.store.create_character(self.account, "Healthhero")
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["character"]["id"],
            hero["id"],
        )
        self.ids = [self.main["character"]["id"], hero["id"]]
        from wakfu_server.progression import level_xp

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,hp_damage=17,health_dead=false WHERE id=ANY(%s)",
                (self.ids,),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (level_xp(200), self.ids),
            )
            reconcile(self.store, db, self.ids)
        self.exterior = dict(map_id=527, instance_id=0, x=-245, y=-90, z=2)
        self.normal = self.rows()

    def rows(self):
        with self.store.connection() as db:
            return {
                row["id"]: dict(row)
                for row in db.execute(
                    "SELECT id,map_id,instance_id,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=ANY(%s)",
                    (self.ids,),
                )
            }

    def enter(self, **kwargs):
        return dungeon_transport.enter(
            self.store,
            self.account,
            self.generation,
            self.ids[0],
            527,
            struct.pack(">qiBi", 26842, 2504, 1, 2),
            criterion_allowed=lambda *_: True,
            source_allowed=lambda *_: True,
            **kwargs,
        )

    def leave(self, *, in_fight=lambda _: False):
        return dungeon_exit._leave(
            self.store,
            self.account,
            self.generation,
            self.ids[0],
            in_fight=in_fight,
            destination_for=lambda *_: self.exterior,
        )

    def test_real_entry_and_hero_exit_persist_profile_and_restore_wounds(self):
        run = self.enter()
        for identity, row in self.rows().items():
            character = self.store.character(self.account, identity)
            self.assertEqual(row["instance_id"], run["instance_id"])
            self.assertEqual(character["effective_level"], 20)
            self.assertEqual(
                (row["max_hp"], row["hp"]),
                (character["max_hp"], character["max_hp"] - 17),
            )
        self.leave()
        for identity, row in self.rows().items():
            self.assertEqual((row["instance_id"], row["hp_damage"]), (0, 17))
            self.assertEqual(
                (row["hp"], row["max_hp"]),
                (self.normal[identity]["hp"], self.normal[identity]["max_hp"]),
            )
            self.assertNotIn(
                "dungeon_modulation", self.store.character(self.account, identity)
            )

    def test_failed_entry_and_hero_combat_exit_roll_back_entire_cohort(self):
        def abort(*_):
            raise RuntimeError("after movement rollback")

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            self.enter(initialize_instance=abort)
        self.assertEqual(self.rows(), self.normal)
        self.enter()
        before = self.rows()
        with self.assertRaisesRegex(ValueError, "hero"):
            self.leave(in_fight=lambda identity: identity == self.ids[1])
        self.assertEqual(self.rows(), before)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members WHERE status='active'"
                ).fetchone()["n"],
                2,
            )

    def test_reconnect_rebinds_and_reconciles_main_and_heroes_without_healing(self):
        run = self.enter()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET max_hp=max_hp+100,hp=hp+100 WHERE id=ANY(%s)",
                (self.ids,),
            )
        generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, generation, self.ids[0])
        result = dungeon_recovery.resume_member(
            self.store, self.account, generation, self.ids[0], run["instance_id"]
        )
        self.assertEqual(set(result["character_ids"]), set(self.ids))
        for identity, row in self.rows().items():
            character = self.store.character(self.account, identity)
            self.assertEqual(
                (row["max_hp"], row["hp_damage"], row["hp"]),
                (character["max_hp"], 17, character["max_hp"] - 17),
            )
        with self.store.connection() as db:
            self.assertTrue(
                all(
                    row["session_generation"] == generation
                    for row in db.execute(
                        "SELECT session_generation FROM dungeon_instance_members WHERE instance_id=%s",
                        (run["instance_id"],),
                    )
                )
            )

    def test_stale_recovery_returns_owned_heroes_and_death_stays_dead(self):
        run = self.enter()
        dead = self.ids[1]
        with self.store.connection() as db:
            character = self.store.character(self.account, dead, db)
            health_policy.apply(db, character, 0)
            db.execute(
                "UPDATE character_regeneration SET coefficient=5 WHERE character_id=%s",
                (dead,),
            )
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                (run["instance_id"],),
            )
        configuration = {
            "topology": {
                "policy": "local_accessible_anchor_policy",
                "asset_map_id": 1086,
                "completion_destination": dict(
                    map_id=527,
                    x=-245,
                    y=-90,
                    z=2,
                    provenance={"policy": "native_entry_approved_walkable_approach"},
                ),
            }
        }
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, configuration),
        ):
            result = dungeon_recovery.resume_member(
                self.store,
                self.account,
                self.generation,
                self.ids[0],
                run["instance_id"],
            )
        self.assertTrue(result["recovered_exterior"])
        self.assertEqual(set(result["character_ids"]), set(self.ids))
        rows = self.rows()
        self.assertTrue(all(row["instance_id"] == 0 for row in rows.values()))
        self.assertEqual((rows[dead]["hp"], rows[dead]["health_dead"]), (0, True))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
                    (dead,),
                ).fetchone()["coefficient"],
                0,
            )

    def test_generic_map_transition_reconciles_return_before_health_cas(self):
        run = self.enter()
        character = self.store.character(self.account, self.ids[0])
        source = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        restored = self.store.transition_map(
            self.account, self.generation, self.ids[0], source, self.exterior
        )
        self.assertNotIn("dungeon_modulation", restored)
        row = self.rows()[self.ids[0]]
        self.assertEqual(
            (row["hp"], row["max_hp"], row["hp_damage"]),
            (self.normal[self.ids[0]]["hp"], self.normal[self.ids[0]]["max_hp"], 17),
        )
        # A subsequent real damage transition compares the persisted restored HP.
        with self.store.connection() as db:
            health_policy.apply(db, restored, restored["hp"] - 9)
        self.assertEqual(self.rows()[self.ids[0]]["hp_damage"], 26)
