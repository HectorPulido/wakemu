"""NPC startup and forecast aliases retain exactly two compiled variants."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch


class NPCRuntimeCatalogCacheTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server import combat_npc_attack as attack

        self.attack = attack
        attack.npc_runtime_catalog.cache_clear()
        self.addCleanup(attack.npc_runtime_catalog.cache_clear)
        stack = self.enterContext(ExitStack())
        from wakfu_server.combat_static_catalogs import CompiledEffects

        def effect():
            return dict(effect_class=1, parameters=[], children=[], area_class="anD")

        self.base = CompiledEffects({"base": effect()}, {"effects": {}, "states": {}})
        stack.enter_context(
            patch(
                "wakfu_server.combat_server_spell.compiled_runtime_catalog",
                return_value=self.base,
            )
        )
        stack.enter_context(
            patch.object(
                attack,
                "npc_spell_catalog",
                return_value={
                    "activation_policy": "fixture",
                    "effects": {"imported": effect()},
                    "baseline_effects": {"baseline": effect()},
                },
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.maps.dungeon_scaling_catalog.merge",
                side_effect=lambda document: document,
            )
        )
        self.extend = stack.enter_context(
            patch.object(
                self.base, "with_effect_sources", wraps=self.base.with_effect_sources
            )
        )

    def test_default_explicit_and_baseline_calls_do_not_evict_each_other(self):
        imported = self.attack.npc_runtime_catalog()
        baseline = self.attack.npc_runtime_catalog(imported=False)
        for _ in range(4):
            self.assertIs(self.attack.npc_runtime_catalog(imported=True), imported)
            self.assertIs(self.attack.npc_runtime_catalog(), imported)
            self.assertIs(self.attack.npc_runtime_catalog(imported=False), baseline)
        self.assertEqual(self.extend.call_count, 2)
        self.assertEqual(self.attack.npc_runtime_catalog.cache_info().currsize, 2)
        self.assertIn("imported", imported.source_effects)
        self.assertEqual(set(baseline.source_effects), {"base", "baseline"})
        self.assertNotIn("imported", baseline.source_effects)
        self.assertIs(imported.effects["base"], self.base.effects["base"])
        self.assertIs(baseline.effects["base"], self.base.effects["base"])

    def test_cache_clear_invalidates_both_variants(self):
        imported = self.attack.npc_runtime_catalog()
        baseline = self.attack.npc_runtime_catalog(imported=False)
        self.attack.npc_runtime_catalog.cache_clear()
        self.assertIsNot(self.attack.npc_runtime_catalog(imported=True), imported)
        self.assertIsNot(self.attack.npc_runtime_catalog(imported=False), baseline)
        self.assertEqual(self.extend.call_count, 4)
