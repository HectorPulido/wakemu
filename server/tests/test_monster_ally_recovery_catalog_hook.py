"""Execute the real recovery block with bounded catalog identity fixtures."""
import ast
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))


class NativeAllyRecoveryCatalogHookTests(unittest.TestCase):
    def run_hook(self, document, spell_level=1):
        tree = ast.parse((TOOLS / "validate_monster_spell_activation.py").read_text())
        blocks = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "recovery_search"
            and any(
                isinstance(child, ast.Name) and child.id == "native_ally_recipe"
                for child in ast.walk(node)
            )
        ]
        self.assertEqual(len(blocks), 1)
        casting = ModuleType("wakfu_server.combat_native_spell_casting")
        casting.catalog = lambda: {"4093": {"cast_criterion_raw": ""}}
        npc = ModuleType("wakfu_server.combat_npc_attack")
        npc.npc_spell_catalog = lambda: document
        namespace = dict(
            recovery_search=True,
            scenarios=[None],
            reference=2831,
            level=1,
            spell=4093,
            spell_level=spell_level,
            capability={},
        )
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.combat_native_spell_casting": casting,
                "wakfu_server.combat_npc_attack": npc,
            },
        ):
            exec(
                compile(
                    ast.Module(body=blocks, type_ignores=[]),
                    "<actual-recovery-block>",
                    "exec",
                ),
                namespace,
            )
        return namespace["scenarios"]

    def test_exact_owned_roots_use_baseline_without_descendant_substitution(self):
        document = dict(
            spells={"4093": {"levels": [[2, 4, [107754]]]}},
            effects={},
            baseline_effects={
                "107754": {
                    "native_target_selector": {"class": "fcE", "mask": 5},
                    "children": [999],
                },
                "999": {"native_target_selector": {"class": "fcE", "mask": 8}},
            },
        )
        self.assertEqual(
            self.run_hook(document)[0]["opponent"],
            dict(reference=2831, level=1, team=1),
        )
        document["effects"]["107754"] = {
            "native_target_selector": {"class": "fcE", "mask": 8},
            "children": [999],
        }
        document["baseline_effects"]["999"]["native_target_selector"]["mask"] = 5
        self.assertEqual(self.run_hook(document), [None])

    def test_missing_owned_root_and_level_fail_closed(self):
        document = dict(spells={"4093": {"levels": [[2, 4, [107754]]]}}, effects={})
        with self.assertRaises(KeyError):
            self.run_hook(document)
        with self.assertRaisesRegex(ValueError, "spell level"):
            self.run_hook(document, 2)


if __name__ == "__main__":
    unittest.main()
