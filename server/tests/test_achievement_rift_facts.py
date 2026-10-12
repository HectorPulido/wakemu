"""All-wave Rift achievement accreditation without reward or client mutation."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.pq import TransactionStatus
from wakfu_server.achievements.rift_facts import load_locked


class RiftFactsTests(unittest.TestCase):
    def setUp(self):
        self.character = {"id": 1, "account_id": 2}
        self.run = dict(
            instance_id=7,
            fight_id=9,
            status="won",
            members=[1],
            completed_waves=1,
            defeated_monsters=2,
            policy={"turn_budget": 40},
        )
        self.receipt = dict(
            outcome="won",
            result=dict(outcome="won", turn=40, completed_waves=1, defeated_monsters=2),
        )
        self.rosters = [
            dict(actor_ids=[-2, -1], species_refs=[101, 102]),
            dict(actor_ids=[-4, -3], species_refs=[103, 104]),
        ]

        def actor(identity, hp, controlled=False):
            return SimpleNamespace(
                id=identity,
                hp=hp,
                team=0 if controlled else 1,
                controlled=controlled,
                effective_level=10,
                pve_withdrawn=False,
            )

        self.fight = SimpleNamespace(
            id=9,
            phase="finished",
            winner=0,
            rift_wave_state={"instance_id": 7},
            actors={
                1: actor(1, 10, True),
                -1: actor(-1, 0),
                -2: actor(-2, 0),
                -3: actor(-3, 10),
                -4: actor(-4, 0),
                -99: actor(-99, 0),
            },
        )
        self.fight.actors[-99].is_summon = True
        self.fight.rift_monsters = {
            identity: dict(id=identity, ref=ref, level=10, instance_id=7)
            for roster in self.rosters
            for identity, ref in zip(roster["actor_ids"], roster["species_refs"])
        }
        self.db = SimpleNamespace(
            info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS),
            execute=self.execute,
        )

    def execute(self, query, params):
        if "rift_settlement_receipts" in query:
            return SimpleNamespace(fetchone=lambda: self.receipt)
        if "rift_wave_rosters" in query:
            return SimpleNamespace(fetchall=lambda: self.rosters)
        raise AssertionError("Unexpected facts mutation/query: " + query)

    def facts(self, eligible=(1,)):
        # Original reward_context performs all authority checks. Only its final
        # monetary context construction is stubbed; no XP policy is needed here.
        with patch("wakfu_server.rift_runtime._run", return_value=self.run), patch(
            "wakfu_server.rift_currency_rewards.combat_reward_context.build_context",
            return_value=object(),
        ):
            return load_locked(self.db, self.fight, self.character, eligible)

    def test_all_completed_and_partial_final_kills_exclude_live_and_summoned(self):
        self.assertEqual(
            self.facts(),
            ({"id": -4, "ref": 103}, {"id": -2, "ref": 101}, {"id": -1, "ref": 102}),
        )
        self.assertEqual(self.facts(), self.facts())  # Stable replay facts, no award.

    def test_sources_rosters_and_actor_identity_must_agree(self):
        for mutation in (
            "reference",
            "missing",
            "extra",
            "duplicate",
            "summon",
            "level",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation == "reference":
                    self.fight.rift_monsters[-4]["ref"] = 999
                elif mutation == "missing":
                    del self.fight.rift_monsters[-4]
                elif mutation == "extra":
                    self.fight.rift_monsters[-99] = dict(
                        id=-99, ref=999, level=10, instance_id=7
                    )
                elif mutation == "duplicate":
                    self.rosters[1]["actor_ids"][0] = -1
                elif mutation == "summon":
                    self.fight.actors[-4].is_summon = True
                elif mutation == "level":
                    self.fight.actors[-4].effective_level = 11
                with self.assertRaises(ValueError):
                    self.facts()

    def test_terminal_receipt_survival_and_transaction_are_required(self):
        for mutation in (
            "missing",
            "early",
            "counter",
            "status",
            "fight",
            "transaction",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation == "missing":
                    self.receipt = None
                elif mutation == "early":
                    self.receipt["result"]["turn"] = 39
                elif mutation == "counter":
                    self.receipt["result"]["defeated_monsters"] = 99
                elif mutation == "status":
                    self.run["status"] = "running"
                elif mutation == "fight":
                    self.run["fight_id"] = 10
                elif mutation == "transaction":
                    self.db.info.transaction_status = TransactionStatus.IDLE
                with self.assertRaises(ValueError):
                    self.facts()

    def test_frozen_eligibility_excludes_withdrawn_and_foreign_members(self):
        for eligible in ((1, 1), (2,), ()):
            with self.subTest(eligible=eligible), self.assertRaises(ValueError):
                self.facts(eligible)
        self.fight.actors[1].pve_withdrawn = True
        with self.assertRaises(ValueError):
            self.facts()

    def test_defeat_and_closed_runs_never_create_winning_kill_facts(self):
        for outcome in ("lost", "closed"):
            self.run["status"] = outcome
            self.receipt.update(outcome=outcome, result={"outcome": outcome})
            self.fight.winner = 1
            self.assertEqual(self.facts(), ())
        self.fight.winner = 0
        with self.assertRaises(ValueError):
            self.facts()
