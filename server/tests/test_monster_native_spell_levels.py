"""NPC spell levels follow the original bPD-to-bPO constructor sequence."""
import unittest
from unittest.mock import patch
from wakfu_server import monsters
from wakfu_server import combat_native_spell_casting


class MonsterNativeSpellLevelTests(unittest.TestCase):
    def abilities(self, parameters, maximum=3, level=5):
        record = {
            "native_abilities": [
                dict(spell_id=3799, level_parameter=p) for p in parameters
            ]
        }
        with patch.object(monsters, "reference", return_value=record), patch.object(
            monsters, "statistics", return_value={}
        ) as stats, patch.object(
            combat_native_spell_casting,
            "catalog",
            return_value={"3799": {"maximum_level": maximum}},
        ):
            result = monsters.native_abilities(2603, level)
            stats.assert_called_once_with(2603, level)
            return result

    def test_actor_relative_and_explicit_levels_clamp_at_native_maximum(self):
        self.assertEqual(
            [row["spell_level"] for row in self.abilities([-1, 2, 10])], [3, 2, 3]
        )

    def test_zero_and_other_negative_levels_are_not_invented_as_positive(self):
        self.assertEqual(
            [row["spell_level"] for row in self.abilities([0, -2])], [0, -2]
        )

    def test_actor_relative_level_below_maximum_is_preserved(self):
        self.assertEqual(
            self.abilities([-1], maximum=200, level=5),
            [dict(spell_id=3799, level_parameter=-1, spell_level=5)],
        )

    def test_unknown_or_invalid_native_maximum_fails_closed(self):
        for value in (None, True, 0, -1, 32768):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "maximum level"
            ):
                self.abilities([-1], maximum=value)

    def test_missing_native_definition_is_not_a_fallback_level(self):
        with patch.object(
            monsters,
            "reference",
            return_value={"native_abilities": [dict(spell_id=1, level_parameter=-1)]},
        ), patch.object(monsters, "statistics", return_value={}), patch.object(
            combat_native_spell_casting, "catalog", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "spell definition"):
                monsters.native_abilities(1, 5)
