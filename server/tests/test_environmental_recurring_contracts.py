import csv
import gzip
import json
from pathlib import Path
import unittest

from wakfu_server.objectives.environmental_recurring_contracts import (
    UnresolvedRecurringContract,
    accept_hunter,
    advance_hunter,
    compile_hunter_contract,
)


def contract(**changes):
    source = dict(
        definition_id=44,
        objectives=[
            dict(
                d=55,
                ckf=[
                    dict(
                        ckm='(GetAchievementVariable("hunterLevel006Boss1")+'
                        'GetAchievementVariable("hunterLevel021Boss2")) >= 2'
                    )
                ],
            )
        ],
        rewards=[dict(type="GIVE_PLAYER_ITEM", parameters=[7, 80], raw_flag_ckk=False)],
        anchor_ms=1000,
        period_seconds=604800,
        cooldown_seconds=0,
        repeatable=True,
        activation_criteria="",
        eligibility_criteria="GetRealLevel() >= 21",
    )
    source.update(changes)
    return compile_hunter_contract(**source)


class EnvironmentalRecurringContractsTests(unittest.TestCase):
    def test_native_expression_preserves_variable_names_and_reward_without_booster_guess(
        self,
    ):
        compiled = contract()
        self.assertEqual(compiled.boss_references, (1, 2))
        self.assertEqual(
            compiled.variable_names, ("hunterLevel006Boss1", "hunterLevel021Boss2")
        )
        self.assertEqual(
            (compiled.rewards[0].amount, compiled.rewards[0].native_flag), (80, False)
        )
        self.assertEqual(compiled.minimum_level, 21)
        with self.assertRaises(UnresolvedRecurringContract):
            contract(objectives=[dict(d=55, ckf=[])])
        with self.assertRaises(UnresolvedRecurringContract):
            contract(activation_criteria="False")
        with self.assertRaises(UnresolvedRecurringContract):
            contract(eligibility_criteria="")

    def test_distinct_paid_winning_boss_receipts_replay_and_changed_replay(self):
        compiled = contract()
        state = accept_hunter(
            compiled,
            character_id=3,
            real_level=21,
            at_ms=1001,
            acceptance_receipt_key="native-accept:44:3:1",
        )

        def win(current, fight, boss, **changes):
            values = dict(
                character_id=3,
                fight_id=fight,
                boss_reference=boss,
                completed_at_ms=2000,
                won=True,
                original_boss=True,
                final_room_completed=True,
            )
            values.update(changes)
            return advance_hunter(compiled, current, **values)

        first = win(state, 90, 1)
        self.assertIs(win(first, 90, 1), first)
        duplicate_boss = win(first, 91, 1)
        self.assertEqual(len(duplicate_boss.defeated), 1)
        self.assertIsNone(duplicate_boss.completed_at_ms)
        completed = win(duplicate_boss, 92, 2)
        self.assertEqual(completed.defeated, frozenset((1, 2)))
        self.assertEqual(completed.completed_at_ms, 2000)
        self.assertIsNone(state.completed_at_ms)
        with self.assertRaisesRegex(ValueError, "replay"):
            win(first, 90, 2)
        for changes in (
            dict(won=False),
            dict(original_boss=False),
            dict(final_room_completed=False),
        ):
            self.assertIs(win(state, 93, 1, **changes), state)

    def test_acceptance_and_native_half_open_reset_do_not_reuse_old_progress(self):
        compiled = contract()
        state = accept_hunter(
            compiled,
            character_id=3,
            real_level=21,
            at_ms=1001,
            acceptance_receipt_key="native-accept:44:3:1",
        )
        end = compiled.anchor_ms + compiled.period_ms
        for at in (1000, end):
            unchanged = advance_hunter(
                compiled,
                state,
                character_id=3,
                fight_id=90,
                boss_reference=1,
                completed_at_ms=at,
                won=True,
                original_boss=True,
                final_room_completed=True,
            )
            self.assertIs(unchanged, state)
        next_week = accept_hunter(
            compiled,
            character_id=3,
            real_level=21,
            at_ms=end,
            acceptance_receipt_key="native-accept:44:3:2",
        )
        self.assertNotEqual(next_week.acceptance.period, state.acceptance.period)
        self.assertEqual(state.defeated, frozenset())
        self.assertEqual(next_week.defeated, frozenset())
        with self.assertRaises(ValueError):
            accept_hunter(
                compiled,
                character_id=3,
                real_level=20,
                at_ms=1001,
                acceptance_receipt_key="native-accept:44:3:1",
            )
        with self.assertRaises(ValueError):
            advance_hunter(
                compiled,
                state,
                character_id=4,
                fight_id=90,
                boss_reference=1,
                completed_at_ms=2000,
                won=True,
                original_boss=True,
                final_room_completed=True,
            )

    def test_all_recovered_weekly_hunter_definitions_compile_as_one_family(self):
        base = (
            Path(__file__).resolve().parents[2]
            / "agents_docs/reports/parallel-readiness-20261021"
        )
        with (base / "recurring-source-family-classification.csv").open() as stream:
            selected = {
                r["definition_id"]
                for r in csv.DictReader(stream)
                if r["family"] == "trade_hunt_contract_candidate"
            }
        from wakfu_server.objectives.environmental_recurring_offers import (
            compile_hunter_offers,
        )

        root = Path(__file__).resolve().parents[1]
        with gzip.open(root / "protocol/npc-dialogues.json.gz", "rt") as stream:
            nodes = json.load(stream)["nodes"]
        # Exact original weekly IDs derive from the original objective family,
        # not translated names, speaker placement or guessed dialogue edges.
        with (base / "recurring-native-definitions.csv").open() as stream:
            weekly_ids = {
                int(r["definition_id"])
                for r in csv.DictReader(stream)
                if r["definition_id"] in selected
                and r["repeatable"] == "True"
                and r["calendar_period_seconds"] == "604800"
            }
        offers = compile_hunter_offers(nodes, weekly_ids)
        compiled = []
        with (base / "recurring-native-definitions.csv").open() as stream:
            for row in csv.DictReader(stream):
                if row["definition_id"] not in selected:
                    continue
                try:
                    value = compile_hunter_contract(
                        definition_id=int(row["definition_id"]),
                        objectives=json.loads(row["objectives"]),
                        rewards=json.loads(row["rewards"]),
                        anchor_ms=int(row["calendar_anchor_ms"]),
                        period_seconds=int(row["calendar_period_seconds"]),
                        cooldown_seconds=int(row["cooldown_seconds"]),
                        repeatable=row["repeatable"] == "True",
                        activation_criteria=row["activation_criteria"],
                        eligibility_criteria=row["eligibility_criteria"],
                        acceptance_criteria=offers[int(row["definition_id"])].criterion
                        if int(row["definition_id"]) in offers
                        else None,
                    )
                except UnresolvedRecurringContract:
                    continue
                compiled.append(value)
        self.assertEqual(len(compiled), 16)
        self.assertEqual(
            sorted(c.minimum_level for c in compiled), list(range(6, 232, 15))
        )
        with self.assertRaises(UnresolvedRecurringContract):
            compile_hunter_offers(
                nodes + [next(n for n in nodes if n["id"] == 3561)], weekly_ids
            )
        self.assertEqual({c.period_ms for c in compiled}, {604800000})
        self.assertEqual({c.anchor_ms for c in compiled}, {1347235200000})
        self.assertTrue(
            all(0 < c.required_distinct <= len(c.boss_references) for c in compiled)
        )
