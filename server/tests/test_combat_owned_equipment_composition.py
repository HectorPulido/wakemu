"""Owned static deltas avoid full catalog traversal without relaxing conflicts."""
from collections.abc import Mapping
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat.combat_static_catalogs import CompiledEffects


def definition(**changes):
    value = dict(
        effect_class=400,
        parameters=[1, 0],
        children=[],
        variant=0,
        minimum_level=0,
        maximum_level=200,
        criteria="",
        target_masks=[None] * 7,
        native_target_selector={"class": "fcE", "mask": 1},
        native_effect_flags=[],
        native_localization_enabled=False,
        area_class="anD",
        area_native="point",
    )
    value.update(changes)
    return value


class CountingMapping(Mapping):
    def __init__(self, values):
        self.values_by_key = values
        self.iterations = 0
        self.lookups = 0

    def __iter__(self):
        self.iterations += 1
        return iter(self.values_by_key)

    def __getitem__(self, key):
        self.lookups += 1
        return self.values_by_key[key]

    def __len__(self):
        return len(self.values_by_key)

    def reset(self):
        self.iterations = self.lookups = 0


class OwnedEquipmentCompositionTests(unittest.TestCase):
    def setUp(self):
        self.metadata = patch(
            "wakfu_server.combat.combat_native_area_metadata.native_point_area_metadata",
            return_value={},
        )
        self.metadata.start()
        self.addCleanup(self.metadata.stop)

    def test_empty_or_already_present_sources_reuse_qualified_base(self):
        original = definition()
        compiled = CompiledEffects({"1": original}, {"effects": {}})
        self.assertIs(compiled_with_sources(compiled, iter(())), compiled)
        self.assertIs(
            compiled_with_sources(compiled, [{"effects": {"1": deepcopy(original)}}]),
            compiled,
        )

    def test_small_delta_never_scans_existing_spell_or_state_catalog(self):
        spells = CountingMapping({str(i): definition() for i in range(2000)})
        states = CountingMapping({str(3000 + i): definition() for i in range(2000)})
        compiled = CompiledEffects(spells, {"effects": states})
        spells.reset()
        states.reset()
        extended = compiled_with_sources(
            compiled, [{"effects": {"9000": definition()}}]
        )
        self.assertEqual((spells.iterations, states.iterations), (0, 0))
        self.assertLessEqual(spells.lookups, 4)
        self.assertLessEqual(states.lookups, 2)
        self.assertEqual(len(extended.effects), 4001)
        self.assertIs(extended.effects["1"], compiled.effects["1"])
        self.assertEqual(set(extended.effects), set(compiled.effects) | {"9000"})
        with self.assertRaises(TypeError):
            extended.effects["9000"]["parameters"][0] = 99
        with self.assertRaises(TypeError):
            extended.effects["9000"] = definition()
        self.assertNotIn("9000", compiled.effects)
        self.assertIs(deepcopy(extended.effects), extended.effects)

    def test_all_execution_identity_conflicts_still_reject(self):
        changes = dict(
            effect_class=401,
            parameters=[2, 0],
            children=[7],
            variant=1,
            minimum_level=1,
            maximum_level=199,
            criteria="False",
            target_masks=[[1], None, None, None, None, None, None],
            native_target_selector={"class": "fcE", "mask": 2},
            native_effect_flags=[17],
            native_localization_enabled=True,
        )
        for field, changed in changes.items():
            with self.subTest(field=field):
                compiled = CompiledEffects({"1": definition()}, {"effects": {}})
                with self.assertRaisesRegex(ValueError, "Conflicting native"):
                    compiled_with_sources(
                        compiled, [{"effects": {"1": definition(**{field: changed})}}]
                    )
                compiled = CompiledEffects({}, {"effects": {"1": definition()}})
                with self.assertRaisesRegex(ValueError, "Conflicting native"):
                    compiled_with_sources(
                        compiled, [{"effects": {"1": definition(**{field: changed})}}]
                    )

    def test_source_order_and_state_only_overlap_preserve_previous_merge_precedence(
        self,
    ):
        compiled = CompiledEffects(
            {"1": definition(label="base")},
            {"effects": {"2": definition(label="state")}},
        )
        extended = compiled_with_sources(
            compiled,
            [
                {
                    "effects": {
                        "1": definition(label="ignored"),
                        "2": definition(label="attachment"),
                        "3": definition(label="first"),
                    }
                },
                {"effects": {"3": definition(label="second")}},
            ],
        )
        self.assertEqual(extended.effects["1"]["label"], "base")
        self.assertEqual(extended.effects["2"]["label"], "attachment")
        self.assertEqual(extended.effects["3"]["label"], "first")
        self.assertEqual(list(extended.effects), ["1", "2", "3"])
        with self.assertRaisesRegex(ValueError, "Conflicting native"):
            compiled_with_sources(
                compiled,
                [
                    {"effects": {"3": definition()}},
                    {"effects": {"3": definition(effect_class=401)}},
                ],
            )

    def test_repeated_mutable_source_is_revalidated_not_cached_by_identity(self):
        compiled = CompiledEffects({"1": definition()}, {"effects": {}})
        source = {"effects": {"1": definition()}}
        self.assertIs(compiled_with_sources(compiled, [source]), compiled)
        source["effects"]["1"]["parameters"][0] = 3
        with self.assertRaisesRegex(ValueError, "Conflicting native"):
            compiled_with_sources(compiled, [source])

    def test_delta_point_area_metadata_is_checked_and_compiled(self):
        compiled = CompiledEffects({}, {"effects": {}})
        points = definition(area_class="anE", area_native="native-points")
        with self.assertRaisesRegex(ValueError, "Missing native point area"):
            compiled_with_sources(compiled, [{"effects": {"2": points}}])
        metadata = {"2": dict(points, native_area_points=[[0, 0], [1, 0]])}
        with patch(
            "wakfu_server.combat.combat_native_area_metadata.native_point_area_metadata",
            return_value=metadata,
        ):
            extended = compiled_with_sources(compiled, [{"effects": {"2": points}}])
            self.assertEqual(
                extended.effects["2"]["native_area_points"], ((0, 0), (1, 0))
            )
            bad = dict(points, native_area_points=[[4, 0]])
            with self.assertRaisesRegex(
                ValueError, "Conflicting native point area offsets"
            ):
                compiled_with_sources(compiled, [{"effects": {"2": bad}}])

    def test_delta_iteration_order_matches_full_merge_with_state_only_definitions(self):
        from wakfu_server.combat.combat_effect_runtime import _merge_effects

        for sources in (
            [{"effects": {"3": definition()}}],
            [{"effects": {"3": definition(), "2": definition(label="source")}}],
            [{"effects": {"2": definition(label="source"), "3": definition()}}],
        ):
            with self.subTest(source_order=list(sources[0]["effects"])):
                compiled = CompiledEffects(
                    {"1": definition()},
                    {"effects": {"4": definition(), "2": definition(label="state")}},
                )
                merged = dict(compiled.source_effects)
                for source in sources:
                    merged = _merge_effects(merged, {"effects": source["effects"]})
                expected = CompiledEffects(merged, compiled.source_states)
                extended = compiled_with_sources(compiled, sources)
                self.assertEqual(list(extended.effects), list(expected.effects))
                self.assertEqual(
                    list(extended.source_effects), list(expected.source_effects)
                )
                for reference in expected.effects:
                    self.assertEqual(
                        extended.effects[reference], expected.effects[reference]
                    )
