"""Actual hero admission followed by disconnected account-wide health abort."""
import unittest

import test_combat_hero_takeover_postgres as fixtures
from wakfu_server import combat_health


class HeroSharedAbortPostgresTests(fixtures.HeroTakeoverPostgresTests):
    def disconnected_company(self):
        from wakfu_server.combat_shared import Registry
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        admitted = self._admit()
        fight = admitted["fight"]
        registry = Registry(
            lambda session: self.store.current_character_session(
                session.account_id, session.generation, session.character_id
            )
        )
        shared = registry.register(fight, self.session, runtime=RuntimeMessages(fight))
        self.assertEqual(registry.disconnect(self.session), [fight.id])
        self.store.end_session(self.account, self.generation)
        self.assertFalse(shared.connected)
        return shared

    def exit_rows(self):
        with self.store.connection() as db:
            return tuple(
                db.execute(
                    "SELECT character_id,generation,reason FROM fight_health_exits "
                    "WHERE fight_id=%s ORDER BY character_id",
                    (self.fight_id,),
                ).fetchall()
            )

    def character_health(self):
        identities = (self.main["id"], self.hero_a["id"], self.hero_b["id"])
        return {
            identity: {
                key: self.store.character(self.account, identity)[key]
                for key in ("hp", "max_hp", "hp_damage", "health_dead")
            }
            for identity in identities
        }

    def test_disconnected_actual_heroes_abort_and_world_heal_retry_is_idempotent(self):
        from wakfu_server import health_policy

        shared = self.disconnected_company()
        initial = self.character_health()
        with self.store.connection() as db:
            entry = db.execute(
                "SELECT entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead "
                "FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.hero_a["id"]),
            ).fetchone()
        baseline = {
            "hp": entry["entry_hp"],
            "max_hp": entry["entry_max_hp"],
            "hp_damage": entry["entry_hp_damage"],
            "health_dead": entry["entry_health_dead"],
        }
        identities = set(initial)
        # This storage-boundary fixture supplies authoritative final wounds;
        # it does not claim to qualify combat damage calculation.
        for loss, identity in enumerate(sorted(identities), 1):
            shared.fight.actors[identity].hp -= loss
        results = combat_health.persist_aborted_shared_fight(self.store, shared)
        self.assertEqual(set(results), identities)
        self.assertTrue(all(result["applied"] for result in results.values()))
        self.assert_health_rows(self.generation, identities)
        rows = self.exit_rows()
        self.assertEqual({row["reason"] for row in rows}, {"abort"})
        for loss, identity in enumerate(sorted(identities), 1):
            self.assertEqual(
                self.store.character(self.account, identity)["hp"],
                initial[identity]["hp"] - loss,
            )
        with self.store.connection() as db:
            for identity in sorted(identities):
                current = self.store.character(self.account, identity, db)
                health_policy.apply(db, current, current["hp"] + 1)
        healed = self.character_health()
        # Exercise the inner disconnected receipt check independently of
        # the shared abort's complete-account early-return branch.
        duplicate = combat_health.persist(
            self.store,
            self.account,
            self.generation,
            self.store.character(self.account, self.hero_a["id"]),
            shared.fight,
            reason="abort",
            disconnected_baseline=baseline,
            session_character_id=self.main["id"],
        )
        self.assertFalse(duplicate["applied"])
        self.assertEqual(self.character_health(), healed)
        repeated = combat_health.persist_aborted_shared_fight(self.store, shared)
        self.assertEqual(set(repeated), identities)
        self.assertTrue(all(not result["applied"] for result in repeated.values()))
        self.assertEqual(self.character_health(), healed)
        self.assertEqual(self.exit_rows(), rows)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "aborted",
            )

    def test_disconnected_hero_generation_and_replaced_session_fail_atomically(self):
        shared = self.disconnected_company()
        before_health = self.character_health()
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                ("foreign-third-generation", self.fight_id, self.hero_a["id"]),
            )
        frozen = self.members()
        with self.assertRaisesRegex(ValueError, "roster or generation changed"):
            combat_health.persist_aborted_shared_fight(self.store, shared)
        self.assertEqual(self.members(), frozen)
        self.assertEqual(self.character_health(), before_health)
        self.assertFalse(self.exit_rows())
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (self.generation, self.fight_id, self.hero_a["id"]),
            )
        new_generation = self.replace_session()
        with self.assertRaisesRegex(ValueError, "generation was replaced"):
            combat_health.persist_aborted_shared_fight(self.store, shared)
        self.assertEqual(self.character_health(), before_health)
        self.assertFalse(self.exit_rows())
        self.assertTrue(
            self.store.current_character_session(
                self.account, new_generation, self.main["id"]
            )
        )
        self.assertEqual(set(self.members().values()), {self.generation})
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "placement",
            )


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(
        HeroSharedAbortPostgresTests(name)
        for name in (
            "test_disconnected_actual_heroes_abort_and_world_heal_retry_is_idempotent",
            "test_disconnected_hero_generation_and_replaced_session_fail_atomically",
        )
    )
