"""Native component premises, not earned citizenship or merit claims."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.national_progression import (
    NationalSnapshot,
    NPC_SOURCE,
    crime_score,
    has_pvp_rank,
    normalized_score,
)
from wakfu_server.equipment_conditions import evaluate

FIXTURE = (
    Path(__file__).parent / "fixtures/native_national_component_and_equipment.json"
)


def rank_rows():
    fixture = json.loads(FIXTURE.read_text())["jvm_component"]
    return tuple(
        sorted(
            {
                (row["current_id"], row["current_threshold"])
                for row in fixture["rank_matrix"]
            }
        )
    )


def context(*, rank=0, nation=30, scores=()):
    snapshot = NationalSnapshot(
        11,
        7,
        nation,
        rank,
        tuple(scores),
        rank_rows(),
        "native-fxk-component-premise",
        "native_import",
    )
    return dict(
        actor_kind="player",
        actor_id=11,
        account_id=7,
        nation_id=nation,
        level=245,
        national_progression=snapshot.record(),
    )


def criterion(expression, source):
    return evaluate(
        expression, item={}, selected=(), owned={}, criterion_context=source
    )


class NationalEquipmentEligibilityTests(unittest.TestCase):
    def test_native_jvm_all_hundred_rank_comparisons_and_signed_score_rules(self):
        fixture = json.loads(FIXTURE.read_text())["jvm_component"]
        for row in fixture["rank_matrix"]:
            with self.subTest(row=row):
                self.assertEqual(
                    has_pvp_rank(context(rank=row["current_id"]), row["required_id"]),
                    row["has_rank"],
                )
        self.assertEqual(normalized_score(30, 30, 500), 500)
        self.assertEqual(normalized_score(30, 31, 500), 0)
        self.assertEqual(normalized_score(30, 31, -70), -70)
        self.assertEqual(crime_score(context(scores=((30, -70),))), -70)
        self.assertEqual(crime_score(context(scores=((30, -70),)), 31), 0)
        self.assertTrue(has_pvp_rank(context(rank=1), 257))
        for invalid in (-1, 10, True):
            with self.assertRaises(ValueError):
                has_pvp_rank(context(), invalid)

    def test_sixteen_original_predicates_use_actual_nation_crime_and_rank(self):
        rows = json.loads(FIXTURE.read_text())["equipment_conditions"]
        self.assertEqual(len(rows), 16)
        # Original indexed criteria, without manufacturing an item root.
        for row in rows:
            text = row["criterion"]
            if "GetCrimeScore" in text:
                self.assertTrue(
                    criterion(
                        text, context(scores=((30, -70 if "<=" in text else 500),))
                    )
                )
                self.assertFalse(criterion(text, context()))
            else:
                nation = int(text.split("==")[1].split()[0])
                self.assertTrue(criterion(text, context(rank=7, nation=nation)))
                self.assertFalse(criterion(text, context(rank=7, nation=0)))
                self.assertFalse(criterion(text, context(rank=0, nation=nation)))

    def test_missing_legacy_foreign_owner_tamper_and_short_circuit_do_not_grant(self):
        unknown = dict(
            actor_kind="player", actor_id=11, account_id=7, nation_id=30, level=245
        )
        self.assertTrue(criterion("GetNationId() == 30", unknown))
        for expression in (
            "GetCrimeScore() <= -70",
            "HasPvpRank(1)",
            "GetNationId() == 99 and HasPvpRank(1)",
        ):
            with self.assertRaises(ValueError):
                criterion(expression, unknown)
        for key, value in (("actor_id", 12), ("account_id", 8), ("nation_id", 31)):
            bad = context(rank=7)
            bad[key] = value
            with self.assertRaises(ValueError):
                criterion("HasPvpRank(1)", bad)
        bad = context()
        bad["national_progression"]["rank_id"] = 7
        with self.assertRaises(ValueError):
            criterion("HasPvpRank(1)", bad)

    def test_original_bje_ftq_refuses_crime_gear_without_owner_inheritance(self):
        owner = context(rank=7, scores=((30, -70),))
        npc = dict(
            actor_kind="native_companion_npc",
            level=245,
            native_national_component=NPC_SOURCE,
            national_progression=deepcopy(owner["national_progression"]),
        )
        self.assertFalse(criterion("GetCrimeScore() <= -70", npc))
        self.assertFalse(criterion("GetCrimeScore() > 99", npc))
        self.assertTrue(criterion("GetNationId() == 0 and HasPvpRank(0)", npc))
        self.assertFalse(criterion("HasPvpRank(1)", npc))
        del npc["native_national_component"]
        with self.assertRaises(ValueError):
            criterion("GetCrimeScore() <= -70", npc)


if __name__ == "__main__":
    unittest.main()
