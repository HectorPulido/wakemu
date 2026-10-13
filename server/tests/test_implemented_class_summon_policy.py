"""Implemented class summons are withheld only from ordinary wild entrypoints."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

from wakfu_server.maps.monster_minigame_policy import (
    CLASS_SUMMON_BLOCKED_REFERENCES,
    exclusion_reason,
    require_ordinary_spawn,
    requires_npc_summon_validation,
)
from monster_activation_exceptions import exclusion_status
from prepare_monster_spell_activation import select_candidates
from finalize_monster_spell_activation import finalize


class ImplementedClassSummonPolicyTests(unittest.TestCase):
    def test_known_sram_double_is_explicit_and_has_distinct_reason(self):
        self.assertEqual(CLASS_SUMMON_BLOCKED_REFERENCES, {3251})
        self.assertEqual(exclusion_reason(3251), "class_summon_implemented")
        self.assertEqual(exclusion_status(3251), "blocked_class_summon")
        with self.assertRaisesRegex(ValueError, "class summon"):
            require_ordinary_spawn(3251)

    def test_monster_producers_and_ordinary_npcs_are_not_blanket_excluded(self):
        for ref in (2437, 2535, 2825, 2078, 3939, 3945, 3949):
            self.assertIsNone(exclusion_reason(ref))
            require_ordinary_spawn(ref)

    def test_selection_preserves_monster_summoner_and_inventory(self):
        rows = [
            dict(
                ref=r,
                status="covered",
                spell_ids=[1],
                data_gaps=[],
                missing_families=[],
                min_level=1,
                max_level=1,
            )
            for r in (3251, 2535)
        ]
        self.assertEqual(
            [m["ref"] for m in select_candidates({"monsters": rows}, 9)], [2535]
        )
        self.assertEqual(len(rows), 2)

    def test_old_candidate_cannot_admit_implemented_class_summon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(
                json.dumps({"selected_references": [3251]})
            )
            with self.assertRaisesRegex(ValueError, "class_summon_implemented"):
                finalize(root, root / "absent.json", root / "output")
            self.assertFalse((root / "output").exists())

    def test_dual_npc_dependency_is_still_required_and_not_native_summon_blocked(self):
        self.assertTrue(requires_npc_summon_validation(3251))
        self.assertIsNone(exclusion_reason(3251, context="native_summon"))
        self.assertEqual(exclusion_reason(3251), "class_summon_implemented")
        with self.assertRaisesRegex(ValueError, "Unknown monster policy"):
            exclusion_reason(3251, context="guessed")

    def test_owned_native_constructor_retains_class_summon_path(self):
        source = Path(__file__).resolve().parents[1] / "wakfu_server/maps/monsters.py"
        tree = ast.parse(source.read_text())
        constructor = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "owned_instance"
        )
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in ("require_ordinary_spawn", "exclusion_reason")
                for n in ast.walk(constructor)
            )
        )


if __name__ == "__main__":
    unittest.main()
