"""Accredit all Rift wave kills through actual durable currency authority."""
import unittest
import test_rift_currency_rewards as fixture
from postgres_case import PostgresCase
from wakfu_server.achievements import rift_facts
from wakfu_server import rift_runtime
from wakfu_server.rift_policy import select_wave


class AchievementRiftFactsPostgresTests(PostgresCase):
    def setUp(self):
        context = fixture.RiftCurrencyPostgresTests(
            methodName="test_actual_policy_is_fifty_times_baseline_and_replay_never_pays_twice"
        )
        self.addCleanup(context.doCleanups)
        context.setUp()
        for name in ("store", "account", "character", "generation", "run", "fight"):
            setattr(self, name, getattr(context, name))

    def enemies(self, ids, refs):
        return fixture.RiftCurrencyPostgresTests.enemies(self, ids, refs)

    def terminal(self, db, outcome="won"):
        return fixture.RiftCurrencyPostgresTests.terminal(self, db, outcome)

    def test_all_rosters_and_partial_last_wave_exclude_living_and_replay_identically(
        self,
    ):
        with self.store.connection() as db:
            refs = select_wave(
                self.run["catalog"], self.run["policy"], self.run["seed"], 2
            )
            ids = list(range(-100 - len(refs), -100))
            rift_runtime.bind_wave(db, self.run["instance_id"], 2, list(zip(ids, refs)))
            enemies, sources = self.enemies(ids, refs)
            enemies[0].hp = 0
            self.fight.actors.update({actor.id: actor for actor in enemies})
            self.fight.rift_monsters.update(sources)
            self.terminal(db)
            result = rift_facts.load_locked(
                db, self.fight, self.character, [self.character["id"]]
            )
            self.assertEqual(len(result), 5)
            self.assertIn(dict(id=ids[0], ref=refs[0]), result)
            self.assertFalse(set(ids[1:]) & {row["id"] for row in result})
            self.assertEqual(
                result,
                rift_facts.load_locked(
                    db, self.fight, self.character, [self.character["id"]]
                ),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_reward_policy_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_loss_gives_no_progress_and_winner_contradiction_rejected(self):
        self.fight.winner = 1
        with self.store.connection() as db:
            self.terminal(db, "lost")
            self.assertEqual(
                rift_facts.load_locked(
                    db, self.fight, self.character, [self.character["id"]]
                ),
                (),
            )
            self.fight.winner = 0
            with self.assertRaisesRegex(ValueError, "winner"):
                rift_facts.load_locked(
                    db, self.fight, self.character, [self.character["id"]]
                )


if __name__ == "__main__":
    unittest.main()
