"""Encounter exceptions must remain inventoried but never auto-selected."""
import unittest
from monster_activation_exceptions import ENCOUNTER_EXCEPTIONS, exception_reason
from prepare_monster_spell_activation import select_candidates


class MonsterActivationExceptionTests(unittest.TestCase):
    def test_all_seven_explicit_exceptions_are_withheld_at_every_level(self):
        rows = [
            dict(
                ref=reference,
                status="covered",
                spell_ids=[1],
                data_gaps=[],
                missing_families=[],
                min_level=1,
                max_level=1,
            )
            for reference in [*ENCOUNTER_EXCEPTIONS, 6]
        ]
        for maximum in (9, 100, 30000):
            self.assertEqual(
                [row["ref"] for row in select_candidates({"monsters": rows}, maximum)],
                [6],
            )
        self.assertEqual(len(ENCOUNTER_EXCEPTIONS), 7)
        self.assertIsNone(exception_reason(6))
