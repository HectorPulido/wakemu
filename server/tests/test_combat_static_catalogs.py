import unittest
import gc
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from wakfu_server.combat_static_catalogs import ImmutableCatalog, CompiledEffects
from wakfu_server.combat_effect_runtime import (
    NativeEffectRuntimeFactory,
    NativeRuntimeContexts,
)
from unittest.mock import patch


class StaticCatalogTests(unittest.TestCase):
    def test_nested_definition_is_read_only_and_contexts_are_never_shared(self):
        original = {
            "1": {"parameters": [1, 2], "children": [], "selector": {"mask": 1}}
        }
        states = {"effects": {}}
        with patch(
            "wakfu_server.combat_native_area_metadata.merge_native_point_areas",
            side_effect=lambda value: value,
        ):
            compiled = CompiledEffects(original, states)
        contexts = lambda: NativeRuntimeContexts(*([lambda *a: None] * 15))
        first = NativeEffectRuntimeFactory(
            effects=original,
            state_catalog=states,
            characteristic_registry={},
            action_id=1,
            contexts=contexts(),
            compiled_effects=compiled,
        )
        second = NativeEffectRuntimeFactory(
            effects=original,
            state_catalog=states,
            characteristic_registry={},
            action_id=2,
            contexts=contexts(),
            compiled_effects=compiled,
        )
        self.assertIs(first.effects, second.effects)
        self.assertIsNot(first.contexts, second.contexts)
        self.assertNotEqual(first.action_id, second.action_id)
        with self.assertRaises(TypeError):
            first.effects["1"]["selector"]["mask"] = 4
        with self.assertRaises(TypeError):
            first.effects["1"]["parameters"][0] = 4
        self.assertEqual(second.effects["1"]["parameters"], (1, 2))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            NativeEffectRuntimeFactory(
                effects=dict(original),
                state_catalog=states,
                characteristic_registry={},
                action_id=1,
                contexts=contexts(),
                compiled_effects=compiled,
            )

    def test_view_deepcopy_is_safe_read_only_static_identity(self):
        from copy import deepcopy

        value = ImmutableCatalog({"nested": {"a": [1, 2]}})
        self.assertIs(deepcopy(value), value)
        self.assertEqual(value["nested"]["a"], (1, 2))

    def test_lazy_views_do_not_mutate_catalog_graph_and_are_stable(self):
        from wakfu_ai.bridge.world_bridge import fingerprint

        catalog = ImmutableCatalog({"npc": {"1740": {"fight_properties": [1, 2]}}})
        before = fingerprint(catalog)
        npc_a = catalog["npc"]
        npc_b = catalog.get("npc")
        profile_a = npc_a.get("1740")
        profile_b = npc_a["1740"]
        self.assertIs(npc_a, npc_b)
        self.assertIs(profile_a, profile_b)
        self.assertEqual(catalog._views, {})
        self.assertEqual(npc_a._views, {})
        self.assertEqual(profile_a._views, {})
        self.assertEqual(fingerprint(catalog), before)
        with self.assertRaises(TypeError):
            profile_a["fight_properties"] = ()

    def test_raw_catalog_source_mutation_remains_visible_to_full_fingerprint(self):
        from wakfu_ai.bridge.world_bridge import fingerprint

        source = {"npc": {"1740": {"fight_properties": [1, 2]}}}
        catalog = ImmutableCatalog(source)
        before = fingerprint(catalog)
        source["npc"]["1740"]["fight_properties"].append(3)
        self.assertNotEqual(fingerprint(catalog), before)

    def test_weak_view_cache_cleans_up_without_id_reuse_deletion(self):
        import importlib

        module = importlib.import_module(ImmutableCatalog.__module__)

        catalog = ImmutableCatalog({"nested": {"value": 1}})
        identity = id(catalog)
        catalog["nested"]
        self.assertIn(identity, module._VIEW_CACHE)
        stale_reference = module._VIEW_CACHE[identity][0]
        stale_cleanup = stale_reference.__callback__
        owner = weakref.ref(catalog)
        del catalog
        gc.collect()
        self.assertIsNone(owner())
        self.assertNotIn(identity, module._VIEW_CACHE)

        replacement = ImmutableCatalog({"fresh": {"value": 2}})
        replacement_identity = id(replacement)
        # Model a delayed stale cache entry at a reused object id. Lookup must
        # replace it, and the old cleanup callback must not delete that entry.
        module._VIEW_CACHE[replacement_identity] = (stale_reference, {"stale": 1})
        self.assertEqual(replacement["fresh"]["value"], 2)
        replacement_entry = module._VIEW_CACHE[replacement_identity]
        stale_cleanup(stale_reference)
        self.assertIs(module._VIEW_CACHE[replacement_identity][0], replacement_entry[0])
        self.assertIs(replacement_entry[0](), replacement)

    def test_concurrent_first_reads_share_one_immutable_view(self):
        catalog = ImmutableCatalog({"nested": {"values": [1, 2, 3]}})
        barrier = threading.Barrier(12)

        def read_view(_):
            barrier.wait()
            return catalog.get("nested")

        with ThreadPoolExecutor(max_workers=12) as pool:
            views = list(pool.map(read_view, range(12)))
        self.assertTrue(all(view is views[0] for view in views))
        self.assertEqual(views[0]["values"], (1, 2, 3))
        self.assertEqual(catalog._views, {})
