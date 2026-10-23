"""Whole original ordinary level-group sources, not per-item runtime exceptions."""
from copy import deepcopy
import unittest

from wakfu_server.equipment_level_groups import qualify_plan, qualified_source, project
from wakfu_server.equipment_stats import CATALOG
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan


class EquipmentLevelGroupTests(unittest.TestCase):
    def test_four_complete_original_neo_sources_and_actor_level_matrix(self):
        for reference, ratios in (
            (32704, (100, 200)),
            (32705, (150, 300)),
            (32706, (200, 400)),
            (32707, (200, 400)),
        ):
            with self.subTest(reference=reference):
                self.assertIsNotNone(qualified_source(reference))
                source = qualified_source(reference)
                groups = [r for r in source["roots"] if r["effect_class"] == 999]
                for level in (1, 50, 245):
                    rows = project(
                        reference,
                        actor_level=level,
                        container_level=0,
                        criterion_context={"is_neo_server": True},
                    )
                    values = {r["id"]: r["values"] for r in rows}
                    for group, ratio in zip(groups, ratios):
                        child = group["child_definitions"][0]
                        self.assertEqual(
                            values[child["reference"]][0], level * ratio // 100
                        )
                    self.assertEqual(len(rows), len(CATALOG[reference]["effects"]))
                    self.assertEqual(sum(r["generic"] == 2001 for r in rows), 1)
                    self.assertEqual(
                        next(r["values"][0] for r in rows if r["generic"] == 2001), 50
                    )
                    self.assertFalse(any(r["generic"] == 999 for r in rows))
                self.assertEqual(
                    project(
                        reference,
                        actor_level=245,
                        container_level=0,
                        criterion_context={"is_neo_server": False},
                    ),
                    [],
                )

    def test_mode_authority_is_required_and_never_inferred_from_item_or_actor(self):
        for context in (None, {}, {"is_neo_server": 1}):
            with self.subTest(context=context), self.assertRaisesRegex(
                ValueError, "Neo server mode"
            ):
                project(
                    32705, actor_level=245, container_level=0, criterion_context=context
                )
        for level in (None, 0, 32768, True):
            with self.subTest(level=level), self.assertRaisesRegex(
                ValueError, "actor level"
            ):
                project(
                    32705,
                    actor_level=level,
                    container_level=0,
                    criterion_context={"is_neo_server": True},
                )

    def test_admin_subscriptions_remain_unqualified(self):
        for reference in (18612, 19531, 19532):
            with self.subTest(reference=reference):
                self.assertIsNone(qualified_source(reference))
                self.assertIsNone(
                    project(
                        reference,
                        actor_level=245,
                        container_level=0,
                        criterion_context={"is_neo_server": True},
                    )
                )

    def test_unknown_sibling_group_semantics_predicates_and_metadata_fail_complete_source(
        self,
    ):
        registry = characteristic_registry()
        for label in (
            "sibling",
            "nested-state",
            "predicate",
            "event",
            "flags",
            "delay",
            "hmi",
            "group-order",
            "growth-ratio",
            "duplicate-child",
            "selector-zero",
            "selector-ally",
            "empty-area",
            "rebind",
            "cell-mode",
            "level-minimum",
        ):
            with self.subTest(label=label):
                plan = copied_equipment_plan(32705, native_copied_equipment_catalog())
                summaries = deepcopy(CATALOG[32705]["effects"])
                group = next(r for r in plan["roots"] if r["effect_class"] == 999)
                leaf = group["child_definitions"][0]
                if label == "sibling":
                    plan["roots"][-1]["effect_class"] = 933
                    summaries[-1]["generic"] = 933
                elif label == "nested-state":
                    leaf["effect_class"] = 304
                elif label == "predicate":
                    leaf["criterion_raw"] = "IsAdmin()"
                elif label == "event":
                    leaf["metadata"]["target_masks"][5] = [1003]
                elif label == "flags":
                    leaf["metadata"]["native_effect_flags"] = [17]
                elif label == "delay":
                    leaf["metadata"]["native_execution_mode"] = 2
                elif label == "hmi":
                    leaf["metadata"]["native_hmi_actions"]["rze"] = [
                        {"type": "COSTUME"}
                    ]
                elif label == "group-order":
                    group["parameters"][0] = 1
                elif label == "growth-ratio":
                    group["parameters"][15] = 1
                elif label == "duplicate-child":
                    group["children"].append(leaf["reference"])
                    group["child_definitions"].append(deepcopy(leaf))
                elif label == "selector-zero":
                    leaf["metadata"]["native_target_selector"]["mask"] = 0
                elif label == "selector-ally":
                    leaf["metadata"]["native_target_selector"]["mask"] = 2
                elif label == "empty-area":
                    leaf["metadata"]["area_native"], leaf["metadata"]["area_class"] = (
                        "empty",
                        "anA",
                    )
                elif label == "rebind":
                    group["parameters"][10] = 1
                elif label == "cell-mode":
                    group["parameters"][4] = 0
                elif label == "level-minimum":
                    leaf["minimum_level"] = 1
                self.assertIsNotNone(qualify_plan(plan, summaries, registry))


if __name__ == "__main__":
    unittest.main()
