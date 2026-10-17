import unittest

from wakfu_server.character_levels import (
    MAX_CHARACTER_LEVEL,
    supported_xp_curve,
    validate_character_level,
)
from wakfu_server.progression import character_xp, level_xp


class CharacterLevelTests(unittest.TestCase):
    def test_installed_character_curve_includes_245_and_rejects_unsupported_inputs(
        self,
    ):
        self.assertEqual(MAX_CHARACTER_LEVEL, 245)
        self.assertLess(level_xp(200), level_xp(201))
        self.assertLess(level_xp(244), level_xp(245))
        for invalid in (True, 0, -1, 246, 245.0, "245"):
            with self.subTest(level=invalid), self.assertRaises(ValueError):
                validate_character_level(invalid)

    def test_xp_consistency_checks_continue_above_the_old_cap(self):
        self.assertEqual(character_xp(dict(level=245)), level_xp(245))
        self.assertEqual(
            character_xp(dict(level=201, xp=level_xp(202) - 1)), level_xp(202) - 1
        )
        for level in (200, 201, 244):
            with self.subTest(level=level), self.assertRaises(ValueError):
                character_xp(dict(level=level, xp=level_xp(level + 1)))

    def test_invalid_or_sparse_published_curves_fail_closed(self):
        for rows in (
            {},
            {"1": 0, "3": 10},
            {"1": 0, "2": 0},
            {"1": True},
            {"01": 0},
            {"1": 1},
            {"1": 0, "2": 2**63},
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                supported_xp_curve(dict(xp_by_level=rows))

    def test_level245_uses_existing_native_aptitude_grants_without_extra_deck_slots(
        self,
    ):
        from wakfu_server.aptitudes import budgets
        from wakfu_server.spells import ACTIVE_SLOT_LEVELS, PASSIVE_SLOT_LEVELS

        self.assertEqual(budgets(245), {4: 62, 5: 62, 3: 62, 2: 62, 6: 5})
        self.assertEqual(sum(level <= 245 for level in ACTIVE_SLOT_LEVELS), 12)
        self.assertEqual(sum(level <= 245 for level in PASSIVE_SLOT_LEVELS), 6)
