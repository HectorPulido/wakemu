import unittest
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
