"""Isolated PostgreSQL account-wide hero generation fences and health exits."""
import struct
import unittest
from unittest.mock import patch

import test_combat_heroes_postgres as fixtures
from wakfu_server import fight_store, combat_health


class HeroTakeoverPostgresTests(fixtures.CombatHeroesPostgresTests):
    def setUp(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_heroes import player_actor

        # The older admission test imports the nested package spelling.
        # Build this new fixture with the production public module identity,
        # including its typed StateLedger, before any actor is initialized.
        with patch.object(fixtures, "Actor", Actor), patch.object(
            fixtures, "Fight", Fight
        ), patch.object(fixtures, "Session", Session), patch.object(
            fixtures, "player_actor", player_actor
        ):
            super().setUp()

    def _admit(self, fight=None, session=None):
        from wakfu_server.combat_heroes import admit_owned_heroes

        with self.store.connection() as db:
            return admit_owned_heroes(
                db, self.store, session or self.session, fight or self.fight
            )

    def members(self):
        with self.store.connection() as db:
            return {
                row["character_id"]: row["session_generation"]
                for row in db.execute(
                    "SELECT character_id,session_generation FROM combat_fight_participants "
                    "WHERE fight_id=%s ORDER BY character_id",
                    (self.fight_id,),
                ).fetchall()
            }

    def replace_session(self):
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.main["id"])
        return generation

    def takeover(self, generation):
        return fight_store.takeover_participant(
            self.store,
            self.account,
            generation,
            self.main["id"],
            self.fight_id,
            previous_generation=self.generation,
        )

    def assert_health_rows(self, generation, identities):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,generation FROM fight_health_exits WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchall()
        self.assertEqual({row["character_id"] for row in rows}, set(identities))
        self.assertEqual({row["generation"] for row in rows}, {generation})

    def test_actual_hero_admission_takeover_abandon_and_native_return(self):
        from wakfu_server import combat_abandon
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        admitted = self._admit()
        fight = admitted["fight"]
        identities = {self.main["id"], self.hero_a["id"], self.hero_b["id"]}
        self.assertEqual(set(self.members()), identities)
        replacement = self.replace_session()
        self.assertTrue(self.takeover(replacement))
        self.assertEqual(set(self.members().values()), {replacement})
        runtime = RuntimeMessages(fight)
        main = self.store.character(self.account, self.main["id"])
        result = combat_abandon.prepare(
            self.store, self.account, replacement, main, runtime, b""
        )
        self.assertTrue(result["applied"])
        self.assert_health_rows(replacement, identities)
        returned = combat_abandon.return_to_world(
            self.store,
            self.account,
            replacement,
            result["character"],
            runtime,
            struct.pack(">iB", self.fight_id, 0),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        with self.store.connection() as db:
            status = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
            ).fetchone()["status"]
        self.assertEqual(status, "aborted")
        self.assertEqual(set(self.members().values()), {replacement})

    def test_idempotent_main_new_repairs_old_heroes_without_touching_peer(self):
        self._admit()
        peer_account = self.store.register("takeover-peer", "peer-password")["id"]
        peer = self.store.create_character(peer_account, "Takeover Peer")
        peer_generation = self.store.begin_session(peer_account)
        self.store.select_character(peer_account, peer_generation, peer["id"])
        with self.store.connection() as db:
            fight_store.join_participant(
                self.store,
                db,
                peer_account,
                peer_generation,
                peer["id"],
                self.fight_id,
                target_character_id=self.main["id"],
                team=0,
            )
        replacement = self.replace_session()
        # Reproduce the historic partial main-only update, then repair it.
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (replacement, self.fight_id, self.main["id"]),
            )
        self.assertTrue(self.takeover(replacement))
        self.assertFalse(self.takeover(replacement))
        expected = {
            self.main["id"]: replacement,
            self.hero_a["id"]: replacement,
            self.hero_b["id"]: replacement,
            peer["id"]: peer_generation,
        }
        self.assertEqual(self.members(), expected)
        with self.assertRaises(ValueError):
            fight_store.takeover_participant(
                self.store,
                peer_account,
                peer_generation,
                self.main["id"],
                self.fight_id,
                previous_generation=self.generation,
            )
        self.assertEqual(self.members(), expected)

    def test_mixed_third_generation_rejects_without_partial_updates(self):
        self._admit()
        replacement = self.replace_session()
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                ("third-foreign-generation", self.fight_id, self.hero_b["id"]),
            )
        before = self.members()
        with self.assertRaisesRegex(ValueError, "Stale durable account"):
            self.takeover(replacement)
        self.assertEqual(self.members(), before)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                0,
            )

    def test_terminal_return_recovery_rebinds_and_persists_all_heroes(self):
        admitted = self._admit()
        fight = admitted["fight"]
        # Storage-focused terminal fixture; this does not qualify combat damage.
        fight.phase = "finished"
        fight.winner = 0
        with self.store.connection() as db:
            fight_store.finish(
                self.store,
                db,
                self.account,
                self.generation,
                self.main["id"],
                self.fight_id,
            )
            fight_store._write_terminal_checkpoint(
                db, self.store, self.account, self.generation, fight
            )
        replacement = self.replace_session()
        main = self.store.character(self.account, self.main["id"])
        result = fight_store.recover_finished_return(
            self.store,
            self.account,
            replacement,
            self.main["id"],
            fight,
            main,
            previous_generation=self.generation,
        )
        identities = {self.main["id"], self.hero_a["id"], self.hero_b["id"]}
        self.assertEqual(set(self.members().values()), {replacement})
        self.assert_health_rows(replacement, identities)
        self.assertTrue(result["applied"])
        repeated = fight_store.recover_finished_return(
            self.store,
            self.account,
            replacement,
            self.main["id"],
            fight,
            result["character"],
            previous_generation=self.generation,
        )
        self.assertFalse(repeated["applied"])
        self.assert_health_rows(replacement, identities)


def load_tests(loader, _tests, _pattern):
    # Reuse admission setup only, without repeating inherited unrelated tests.
    return unittest.TestSuite(
        HeroTakeoverPostgresTests(name)
        for name in (
            "test_actual_hero_admission_takeover_abandon_and_native_return",
            "test_idempotent_main_new_repairs_old_heroes_without_touching_peer",
            "test_mixed_third_generation_rejects_without_partial_updates",
            "test_terminal_return_recovery_rebinds_and_persists_all_heroes",
        )
    )
