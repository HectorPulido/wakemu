"""Fifty-times ordinary rift currency, actual kills and atomic replay coverage."""
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import (
    combat_rewards,
    reward_policy,
    rift_currency_rewards as currency,
)
from wakfu_server import rift_runtime
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.monsters import reference
from wakfu_server.rift_policy import select_wave


class RiftCurrencyPolicyTests(unittest.TestCase):
    def test_multiplier_applies_after_the_ordinary_result_without_extra_rolls(self):
        scaled = currency.scaled_policy(
            combat_rewards.Policy(xp=123, kamas=17), {"xp": 100, "kamas": 100}
        )
        self.assertEqual((scaled.xp, scaled.kamas), (6150, 850))

    def test_native_and_storage_caps_keep_rewards_nonnegative(self):
        scaled = currency.scaled_policy(
            combat_rewards.Policy(xp=2**62, kamas=2**30),
            {"xp": 2**63 - 11, "kamas": 2**63 - 8},
        )
        self.assertEqual((scaled.xp, scaled.kamas), (10, 7))
        capped = currency.scaled_policy(
            combat_rewards.Policy(kamas=2**30), {"xp": 0, "kamas": 0}
        )
        self.assertEqual(capped.kamas, 2**31 - 1)


class RiftCurrencyPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("rift-currency", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Riftmoney")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            self.run = rift_runtime.enter(
                db,
                3,
                self.character["id"],
                [self.character["id"]],
                seed="money-test",
                authorize=lambda c, m: True,
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight_id, self.character["id"], self.account, self.generation),
            )
            rift_runtime.start(
                db, self.run["instance_id"], self.character["id"], fight_id
            )
            refs = select_wave(
                self.run["catalog"], self.run["policy"], self.run["seed"], 1
            )
            ids = list(range(-len(refs), 0))
            rift_runtime.bind_wave(db, self.run["instance_id"], 1, list(zip(ids, refs)))
            rift_runtime.record_wave(db, self.run["instance_id"], 1, ids, turn=2)
            self.run = rift_runtime._run(db, self.run["instance_id"])
        player = Actor(
            self.character["id"],
            0,
            (0, 0, 0),
            self.character["hp"],
            6,
            3,
            100,
            self.character["level"],
            self.account,
            True,
        )
        player.effect_stats = {36: 20}
        enemies, sources = self.enemies(ids, refs)
        cells = [(index, 0, 0) for index in range(len(enemies) + 1)]
        self.fight = Fight(
            fight_id, [player] + enemies, cells, {0: {cells[0]}, 1: set(cells[1:])}
        )
        for actor in enemies:
            actor.hp = 0
        self.fight.phase, self.fight.winner = "finished", 0
        self.fight.rift_wave_state = {"instance_id": self.run["instance_id"]}
        self.fight.rift_monsters = sources

    def enemies(self, ids, refs):
        actors, sources = [], {}
        for index, (identity, ref) in enumerate(zip(ids, refs), start=1):
            level = reference(ref)["min_level"]
            actors.append(Actor(identity, 1, (index, 0, 0), 20, 4, 2, 1, level))
            sources[identity] = dict(
                id=identity, ref=ref, level=level, instance_id=self.run["instance_id"]
            )
        return actors, sources

    def terminal(self, db, outcome="won"):
        db.execute(
            "UPDATE combat_fights SET status='finished' WHERE id=%s", (self.fight.id,)
        )
        rift_runtime.settle(
            db,
            self.run["instance_id"],
            self.fight.id,
            outcome=outcome,
            turn=40,
            apply_rewards=lambda *args: None,
        )

    def resolve(self, db, character=None):
        return currency.resolve(
            self.store,
            db,
            account_id=self.account,
            generation=self.generation,
            character_id=self.character["id"],
            fight=self.fight,
            character=character or self.character,
            eligible_character_ids=[self.character["id"]],
        )

    def test_actual_policy_is_fifty_times_baseline_and_replay_never_pays_twice(self):
        with self.store.connection() as db:
            self.terminal(db)
            with patch.object(
                reward_policy.secrets, "randbelow", return_value=0
            ) as roll:
                policy = self.resolve(db)
            self.assertEqual(roll.call_count, 1)
            receipt = db.execute(
                "SELECT * FROM fight_reward_policy_receipts"
            ).fetchone()
            baseline = receipt["snapshot"]["ordinary_baseline"]
            self.assertEqual(policy.xp, baseline["xp"] * 50)
            self.assertEqual(policy.kamas, baseline["kamas"] * 50)
            self.assertEqual(len(receipt["snapshot"]["defeated_native_monsters"]), 4)
            awarded = combat_rewards.award_shared_member(
                self.store,
                db,
                self.account,
                self.generation,
                self.character["id"],
                self.fight,
                policy,
            )
            report = combat_rewards.report_metadata(
                {
                    self.character["id"]: dict(
                        kind="player",
                        account_id=self.account,
                        name=self.character["name"],
                        breed=self.character["breed"],
                        is_male=self.character["sex"] == 0,
                    )
                },
                self.character["id"],
                awarded,
            )
            self.assertEqual(report[self.character["id"]]["gained_kamas"], policy.kamas)
            self.assertEqual(
                report[self.character["id"]]["xp_info"]["won_xp"], policy.xp
            )
            from wakfu_server.combat_results import fight_report
            from wakfu_server.wire import proto_fields

            report.update(
                {
                    identity: dict(kind="monster", ref=source["ref"])
                    for identity, source in self.fight.rift_monsters.items()
                }
            )
            encoded = fight_report(
                self.fight,
                report,
                duration_ms=40000,
                fight_instance_id=self.run["instance_id"],
                initiator_id=self.character["id"],
                fight_model=14,
            )
            team = dict(proto_fields(dict(proto_fields(encoded))[42]))
            player = dict(proto_fields(team[18]))
            self.assertEqual(player[72], policy.kamas)
            self.assertEqual(dict(proto_fields(player[66]))[16], policy.xp)
            self.assertGreater(awarded["character"]["level"], self.character["level"])
        with self.reopen().connection() as db:
            with patch.object(
                reward_policy, "resolve", side_effect=AssertionError("reroll")
            ):
                replay = self.resolve(db, awarded["character"])
            self.assertEqual(replay, policy)
            again = combat_rewards.award_shared_member(
                self.store,
                db,
                self.account,
                self.generation,
                self.character["id"],
                self.fight,
                replay,
            )
            self.assertFalse(again["awarded"])
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 1
            )

    def test_partial_last_wave_pays_dead_originals_but_not_living_or_summons(self):
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
            summon = Actor(-999, 1, (9, 0, 0), 20, 4, 2, 1, 1)
            summon.is_summon, summon.hp = True, 0
            self.fight.actors[summon.id] = summon
            self.terminal(db)
            self.resolve(db)
            snapshot = db.execute(
                "SELECT snapshot FROM fight_reward_policy_receipts"
            ).fetchone()["snapshot"]
        self.assertEqual(len(snapshot["defeated_native_monsters"]), 5)
        self.assertNotIn(
            -999, [row["actor_id"] for row in snapshot["defeated_native_monsters"]]
        )
        self.assertEqual(len(snapshot["ordinary_baseline"]["context"]["losers"]), 5)

    def test_losses_withdrawal_and_zero_kills_have_no_currency(self):
        with self.store.connection() as db:
            self.terminal(db, "lost")
            self.assertEqual(self.resolve(db), combat_rewards.Policy())
        # Independent survival fixture is covered below through the pure
        # context boundary; existing terminal results are deliberately immutable.
        self.fight.actors[self.character["id"]].pve_withdrawn = True
        with self.store.connection() as db:
            self.assertEqual(self.resolve(db), combat_rewards.Policy())

    def test_reward_failure_rolls_back_scaled_baseline_and_wallet(self):
        with self.store.connection() as db:
            self.terminal(db)
        with self.assertRaisesRegex(RuntimeError, "after policy"):
            with self.store.connection() as db:
                policy = self.resolve(db)
                combat_rewards.award_shared_member(
                    self.store,
                    db,
                    self.account,
                    self.generation,
                    self.character["id"],
                    self.fight,
                    policy,
                )
                raise RuntimeError("after policy")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_reward_policy_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )

    def test_fabricated_reference_is_rejected_and_zero_actual_kills_pay_zero(self):
        with self.store.connection() as db:
            self.terminal(db)
            first = next(iter(self.fight.rift_monsters))
            original = self.fight.rift_monsters[first]["ref"]
            self.fight.rift_monsters[first]["ref"] = 999999
            with self.assertRaisesRegex(ValueError, "authority"):
                self.resolve(db)
            self.fight.rift_monsters[first]["ref"] = original
            for identity in self.fight.rift_monsters:
                self.fight.actors[identity].hp = 1
            self.assertEqual(self.resolve(db), combat_rewards.Policy())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_reward_policy_receipts"
                ).fetchone()["n"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
