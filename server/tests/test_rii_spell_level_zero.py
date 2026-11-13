import json
import unittest
from pathlib import Path
from unittest.mock import patch
from wakfu_server.combat_native_spell_casting import native_casting_table
from wakfu_server.combat_critical import spell_critical_available


class RiiSpellLevelZeroTests(unittest.TestCase):
    def test_tutorial_zero_level_critical_branches_match_native_client(self):
        for reference in range(7963, 7976):
            with self.subTest(reference=reference):
                self.assertFalse(spell_critical_available(reference, 0))

    def test_other_spells_and_levels_keep_existing_critical_policy(self):
        with patch(
            "wakfu_server.combat_critical._spell_availability",
            return_value={"42": {"critical_levels": [1]}},
        ):
            self.assertTrue(spell_critical_available(42, 1))
            with self.assertRaisesRegex(
                ValueError, "audited native spell critical level"
            ):
                spell_critical_available(42, 0)

    def test_native_zero_casting_tables_cover_each_tutorial_spell(self):
        data = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server"
                / "achievements"
                / "rii_spell_level_zero.json"
            ).read_text()
        )
        self.assertEqual(set(data["spells"]), {str(n) for n in range(7963, 7976)})
        self.assertEqual(set(data["casting"]), set(data["spells"]))
        for reference in range(7963, 7976):
            record, index = native_casting_table(
                reference, 0, zero_casting=data["casting"]
            )
            self.assertEqual(index, 0)
            self.assertEqual(record["levels"][0], data["spells"][str(reference)])
        self.assertEqual(data["effects"]["361213"]["parameters"], [25, 0])


if __name__ == "__main__":
    unittest.main()
