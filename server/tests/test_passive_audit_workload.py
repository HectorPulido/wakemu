"""Audit workload coverage, legal decks and bounded deterministic sampling."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_passive_initialization import cases
from wakfu_server.spells import validate_deck, encode_deck, available_spells


class PassiveAuditWorkloadTests(unittest.TestCase):
    def test_every_native_passive_is_independent_at_unlock_and_maximum(self):
        workload, passives = cases()
        independent = [r for r in workload if r["mode"].startswith("individual")]
        self.assertEqual(len(passives), 339)
        self.assertEqual(
            {r["spell_id"] for r in independent}, {p["id"] for p in passives}
        )
        for passive in passives:
            levels = {r["level"] for r in independent if r["spell_id"] == passive["id"]}
            self.assertEqual(levels, {max(10, passive["unlock_level"]), 200})
        for row in workload:
            active = [
                s["id"]
                for s in available_spells(row["breed"], row["level"])
                if s["kind"] == "active"
            ][:3]
            validate_deck(
                encode_deck(active, row["passive"]), row["breed"], row["level"]
            )

    def test_representative_combinations_are_distinct_owned_and_deterministic(self):
        workload, _ = cases()
        self.assertEqual(workload, cases()[0])
        samples = [r for r in workload if r["mode"].startswith("representative")]
        keys = [(r["breed"], tuple(r["passive"])) for r in samples]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(1 <= len(r["passive"]) <= 6 for r in samples))
