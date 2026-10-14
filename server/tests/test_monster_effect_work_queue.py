"""Pure typed dependency and malformed-source regressions."""
import importlib.util
import io
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import build_monster_effect_work_queue as queue


class EffectWorkQueueTests(unittest.TestCase):
    def test_area_and_spell_identical_ids_have_distinct_namespaces(self):
        self.assertEqual(queue.dependency_namespace(315), "area")
        self.assertEqual(queue.dependency_namespace(426), "spell")
        self.assertNotEqual(
            (queue.dependency_namespace(315), "12"),
            (queue.dependency_namespace(426), "12"),
        )

    def test_truncated_source_fails_without_spinning(self):
        with self.assertRaises(ValueError):
            queue.Reader(io.StringIO("  ")).peek()

    def test_effect_criterion_signature_preserves_native_arguments(self):
        signatures = queue.predicate_signatures('HasState(2071, "caster")')
        self.assertEqual(signatures[0][0], "HasState")
        self.assertIn("2071", signatures[0][1])
        self.assertIn("caster", signatures[0][1])


if __name__ == "__main__":
    unittest.main()
