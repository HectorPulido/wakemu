"""Real account-custody and canonical-health qualification of native32702."""
from unittest.mock import patch
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.account_quest_inventory import grant
from wakfu_server.native_world_context import battleground_worlds
from wakfu_server.neo_regeneration import (
    eligible,
    mode_from_database,
    restoration_state,
    restore_canonical,
)


class NeoRegenerationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("neo-owner", "local-password")["id"]
        self.main = self.store.create_character(self.account, "Neo Main")
        self.hero = self.store.create_character(self.account, "Neo Hero")
        self.foreign_account = self.store.register("neo-foreign", "local-password")[
            "id"
        ]
        self.foreign = self.store.create_character(self.foreign_account, "Neo Foreign")

    def wounded(self, db, character, *, dead=False):
        db.execute(
            "UPDATE characters SET hp=%s,max_hp=100,hp_damage=250,health_dead=%s WHERE id=%s",
            (0 if dead else 1, dead, character["id"]),
        )
        return dict(
            db.execute(
                "SELECT * FROM characters WHERE id=%s", (character["id"],)
            ).fetchone()
        )

    def test_exact_account_possession_mode_and_original_battlefield_gate(self):
        with self.store.connection() as db:
            self.assertFalse(mode_from_database(db))
            grant(db, self.account, 26347, 1)
            self.assertFalse(
                eligible(db, self.account, native_map_id=527, is_neo_server=True)
            )
            grant(db, self.account, 32702, 1)
            self.assertTrue(
                eligible(db, self.account, native_map_id=527, is_neo_server=True)
            )
            self.assertFalse(
                eligible(
                    db, self.foreign_account, native_map_id=527, is_neo_server=True
                )
            )
            self.assertFalse(
                eligible(db, self.account, native_map_id=527, is_neo_server=False)
            )
            for world in battleground_worlds():
                self.assertFalse(
                    eligible(db, self.account, native_map_id=world, is_neo_server=True)
                )
            with self.assertRaisesRegex(ValueError, "context"):
                eligible(db, self.account, native_map_id=527, is_neo_server=1)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"version": 1, "is_neo_server": True}),),
            )
            self.assertTrue(mode_from_database(db))
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_server_mode'",
                (Jsonb({"version": 1, "is_neo_server": "true"}),),
            )
            with self.assertRaisesRegex(ValueError, "mode"):
                mode_from_database(db)

    def test_entry_restores_main_and_same_account_hero_without_consumption(self):
        with self.store.connection() as db:
            grant(db, self.account, 32702, 1)
            for character in (self.main, self.hero):
                saved = self.wounded(db, character)
                result = restore_canonical(
                    self.store,
                    db,
                    saved,
                    native_map_id=527,
                    is_neo_server=True,
                    boundary="entry",
                )
                self.assertTrue(result["applied"])
                row = db.execute(
                    "SELECT hp,max_hp,hp_damage,health_dead FROM characters WHERE id=%s",
                    (character["id"],),
                ).fetchone()
                self.assertEqual(
                    {"hp": 100, "max_hp": 100, "hp_damage": 0, "health_dead": False},
                    row,
                )
                regen = db.execute(
                    "SELECT initial_hp,coefficient FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
                self.assertEqual({"initial_hp": 100, "coefficient": 0}, regen)
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=32702",
                    (self.account,),
                ).fetchone()["quantity"],
            )

    def test_return_after_one_hp_recovery_heals_fully_but_abort_and_dead_entry_do_not(
        self,
    ):
        from wakfu_server.health_policy import recover_finished_return, visible

        with self.store.connection() as db:
            grant(db, self.account, 32702, 1)
            saved = self.wounded(db, self.main, dead=True)
            with self.assertRaisesRegex(ValueError, "Dead characters"):
                restoration_state(
                    db, saved, native_map_id=527, is_neo_server=True, boundary="entry"
                )
            with self.assertRaisesRegex(ValueError, "boundary"):
                restoration_state(
                    db, saved, native_map_id=527, is_neo_server=True, boundary="abort"
                )
            damage, dead = recover_finished_return(100, 250, True)
            self.assertEqual((99, False), (damage, dead))
            db.execute(
                "UPDATE characters SET hp=%s,hp_damage=%s,health_dead=%s WHERE id=%s",
                (visible(100, damage, dead), damage, dead, saved["id"]),
            )
            saved = dict(
                db.execute(
                    "SELECT * FROM characters WHERE id=%s", (saved["id"],)
                ).fetchone()
            )
            result = restore_canonical(
                self.store,
                db,
                saved,
                native_map_id=527,
                is_neo_server=True,
                boundary="return",
            )
            self.assertEqual(
                (100, 0, False),
                tuple(
                    result["character"][key]
                    for key in ("hp", "hp_damage", "health_dead")
                ),
            )

    def test_foreign_stale_and_failed_application_preserve_canonical_health(self):
        with self.store.connection() as db:
            grant(db, self.account, 32702, 1)
            saved = self.wounded(db, self.main)
            forged = dict(saved, id=self.foreign["id"])
            with self.assertRaisesRegex(ValueError, "foreign"):
                restore_canonical(
                    self.store,
                    db,
                    forged,
                    native_map_id=527,
                    is_neo_server=True,
                    boundary="entry",
                )
            stale = dict(saved, hp=2, hp_damage=98)
            with self.assertRaisesRegex(ValueError, "Stale"):
                restore_canonical(
                    self.store,
                    db,
                    stale,
                    native_map_id=527,
                    is_neo_server=True,
                    boundary="entry",
                )
        from wakfu_server.health_policy import apply_damage

        def fail_after_health_write(*args, **kwargs):
            apply_damage(*args, **kwargs)
            raise ValueError("injected after canonical health write")

        with self.assertRaisesRegex(ValueError, "injected"):
            with self.store.connection() as db:
                with patch(
                    "wakfu_server.health_policy.apply_damage",
                    side_effect=fail_after_health_write,
                ):
                    restore_canonical(
                        self.store,
                        db,
                        saved,
                        native_map_id=527,
                        is_neo_server=True,
                        boundary="entry",
                    )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT hp,hp_damage,health_dead FROM characters WHERE id=%s",
                (self.main["id"],),
            ).fetchone()
            self.assertEqual({"hp": 1, "hp_damage": 250, "health_dead": False}, row)

    def test_real_admission_baseline_covers_main_hero_and_unentitled_foreign(self):
        from wakfu_server.fight_store import _health_baseline

        with self.store.connection() as db:
            grant(db, self.account, 32702, 1)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"version": 1, "is_neo_server": True}),),
            )
            for owner in (self.main, self.hero):
                self.wounded(db, owner)
                self.assertEqual(
                    (100, 100, 0, False),
                    _health_baseline(db, self.account, owner["id"]),
                )
            self.wounded(db, self.foreign)
            self.assertEqual(
                (1, 100, 250, False),
                _health_baseline(db, self.foreign_account, self.foreign["id"]),
            )

    def test_real_finished_health_return_and_replay_keep_ordinary_fences(self):
        from tests.test_combat_rewards import setup_reward_state
        from wakfu_server import health_store, health_policy
        from wakfu_server.combat_health import persist

        store, account, character, generation, fight = setup_reward_state(self.store)
        character = health_store.initialize(store, account, generation, character["id"])
        fight.actors[character["id"]].max_hp = character["max_hp"]
        fight.actors[character["id"]].hp = 0
        fight.winner = 1
        with store.connection() as db:
            grant(db, account, 32702, 1)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"version": 1, "is_neo_server": True}),),
            )
        result = persist(store, account, generation, character, fight)
        saved = result["character"]
        self.assertEqual(
            (saved["max_hp"], 0, False),
            (saved["hp"], saved["hp_damage"], saved["health_dead"]),
        )
        with store.connection() as db:
            health_policy.apply(db, saved, saved["hp"] - 3)
        replay = persist(store, account, generation, character, fight)
        self.assertFalse(replay["applied"])
        self.assertEqual(saved["max_hp"] - 3, replay["character"]["hp"])
