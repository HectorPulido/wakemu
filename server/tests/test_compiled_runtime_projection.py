"""The mixed-module projection never hides compiler-visible edits."""
import unittest
from pathlib import Path

from tools.compiled_runtime_projection import masked_fingerprint


PATH = "wakfu_server/combat/combat_placement_policy.py"


class RuntimeProjectionTests(unittest.TestCase):
    def test_runtime_body_only_does_not_change_projection(self):
        original = "x = 1\ndef _arena(map_id):\n    return map_id\ndef freeze(value):\n    return value\ndef compile_catalog():\n    return x\n"
        modified = original.replace("return map_id", "return map_id + 42")
        self.assertIsNotNone(masked_fingerprint(PATH, original))
        self.assertEqual(
            masked_fingerprint(PATH, original), masked_fingerprint(PATH, modified)
        )
        self.assertEqual(
            masked_fingerprint(PATH, original),
            masked_fingerprint(
                PATH, original.replace("return value", "return value + 1")
            ),
        )

    def test_signature_global_and_compiler_body_remain_inputs(self):
        original = "x = 1\ndef _arena(map_id):\n    return map_id\ndef freeze(value):\n    return value\ndef compile_catalog():\n    return x\n"
        before = masked_fingerprint(PATH, original)
        for altered in (
            original.replace("map_id):", "map_id, z=0):"),
            original.replace("x = 1", "x = 2"),
            original.replace("return x", "return x + 1"),
        ):
            with self.subTest(altered=altered):
                self.assertNotEqual(before, masked_fingerprint(PATH, altered))

    def test_unknown_or_ambiguous_source_fails_closed(self):
        for source in (
            "def _arena(:\n pass",
            "@decorate\ndef _arena(x):\n return x\n",
            "def _arena(x):\n return x\ny = _arena(1)\n",
            "def _arena(x):\n return x\nclass C:\n y = _arena(1)\n",
        ):
            with self.subTest(source=source):
                self.assertIsNone(masked_fingerprint(PATH, source))
        self.assertIsNone(masked_fingerprint("unknown.py", "def _arena(x): return x"))

    def test_reviewed_modules_project_real_source(self):
        server = Path(__file__).resolve().parents[1]
        for path in (
            PATH,
            "wakfu_server/combat/combat_encounter_scene_layout.py",
            "wakfu_server/combat/combat_terrain.py",
            "wakfu_server/combat/combat_cell_group.py",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(
                    masked_fingerprint(path, (server / path).read_bytes())
                )

    def test_each_new_runtime_body_is_ignored_but_signature_and_compiler_are_not(self):
        cases = (
            ("wakfu_server/combat/combat_terrain.py", "local_arena"),
            (
                "wakfu_server/combat/combat_cell_group.py",
                "native_cell_criterion_presence",
            ),
        )
        for path, function in cases:
            source = f"VALUE = 1\ndef {function}(value):\n return value\ndef compile_catalog():\n return VALUE\n"
            with self.subTest(path=path):
                expected = masked_fingerprint(path, source)
                self.assertIsNotNone(expected)
                self.assertEqual(
                    expected,
                    masked_fingerprint(
                        path, source.replace("return value", "return value + 1")
                    ),
                )
                self.assertNotEqual(
                    expected,
                    masked_fingerprint(
                        path, source.replace("(value):", "(value, z=0):")
                    ),
                )
                self.assertNotEqual(
                    expected,
                    masked_fingerprint(
                        path, source.replace("return VALUE", "return VALUE + 1")
                    ),
                )


if __name__ == "__main__":
    unittest.main()
