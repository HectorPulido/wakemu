"""Exact sealed source import preserves ownership and unsupported level zero."""
import unittest

from prepare_monster_offline_source_import import prepare_source_import


class OfflineSourceImportTests(unittest.TestCase):
    def inputs(self):
        npc = {
            "spells": {},
            "effects": {},
            "activation_policy": {"enabled_monsters": {}},
        }
        trees = {
            "spells": {"7": {"levels": [[1, 1, [8]]]}},
            "effects": {"8": {"effect_class": 4}},
        }
        states = {"states": {}, "effects": {}}
        casting = {"spells": {"7": {"levels": [[1, 1, [9]]]}}}
        roots = {"roots": {"9": {"criteria": "False"}}}
        inventory = {
            1: {
                "min_level": 1,
                "max_level": 2,
                "dependencies": {
                    "spell_ids": [7],
                    "effect_ids": [8],
                    "state_ids": [],
                    "missing_definitions": [],
                },
                "missing_casting_tables": [],
                "missing_casting_root_metadata": [],
            }
        }
        return npc, trees, states, casting, roots, inventory, [1]

    def test_exact_source_and_policy_preserved(self):
        args = self.inputs()
        result, roots, rows = prepare_source_import(*args)
        self.assertEqual(result["spells"], args[1]["spells"])
        self.assertEqual(result["activation_policy"], args[0]["activation_policy"])
        self.assertEqual(roots, args[4]["roots"])
        self.assertFalse(rows[0]["ownership_changed"])
        self.assertEqual(args[0]["spells"], {})

    def test_zero_native_level_is_explicitly_blocked(self):
        args = self.inputs()
        args[5][1]["min_level"] = 0
        result, roots, rows = prepare_source_import(*args)
        self.assertEqual(
            rows[0]["blockers"], ["unsupported_native_zero_level_activation"]
        )
        self.assertEqual(result["spells"], {})
        self.assertEqual(roots, {})

    def test_existing_mismatch_rejected(self):
        args = self.inputs()
        args[0]["effects"]["8"] = {"effect_class": 48}
        with self.assertRaisesRegex(
            ValueError, "Conflicting existing native definition"
        ):
            prepare_source_import(*args)

    def test_missing_native_casting_root_rejected(self):
        args = self.inputs()
        args[4]["roots"] = {}
        with self.assertRaisesRegex(ValueError, "Missing original casting root"):
            prepare_source_import(*args)

    def test_missing_state_definition_blocks_import(self):
        args = self.inputs()
        args[5][1]["dependencies"]["state_ids"] = [12]
        result, roots, rows = prepare_source_import(*args)
        self.assertIn("native_state_input_missing", rows[0]["blockers"])
        self.assertEqual(result["spells"], {})
