import unittest

from scripts.prepare_world_bridge import patch_source


class PrepareWorldBridgeTests(unittest.TestCase):
    def test_preserves_other_agents_source_exactly(self):
        before = (
            "# future world header\nVALUE = 'á'\ndef session():\n    variable = 7\n"
        )
        old = "    def pass_test_monster_turn():\n        # old implementation\n        return variable\n"
        after = "\n    def next_handler():\n        return variable\n# future world footer\n"
        prepared = patch_source(before + old + after)
        self.assertTrue(prepared.startswith(before))
        self.assertTrue(prepared.endswith(after))
        self.assertNotIn("old implementation", prepared)
        self.assertEqual(prepared.count("def pass_test_monster_turn"), 1)
        self.assertEqual(patch_source(prepared), prepared)

    def test_missing_or_ambiguous_hook_rejects_preparation(self):
        for source in ("x = 1\n", "def pass_test_monster_turn(): pass\n" * 2):
            with self.subTest(source=source), self.assertRaises(ValueError):
                patch_source(source)
