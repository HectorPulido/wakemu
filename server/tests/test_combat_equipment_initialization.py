"""Focused copied-equipment passive and sublimation source planning tests."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_copied_equipment_plan import SOURCE
from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution
from wakfu_server.wire import proto_field


class CombatEquipmentInitializationTests(unittest.TestCase):
    @staticmethod
    def metadata():
        return {
            "target_masks": [],
            "native_target_selector": 0,
            "native_effect_flags": 0,
            "native_definition_class": 0,
            "area_class": 0,
            "area_native": 0,
            "probability_base": 0,
            "probability_per_level": 0,
        }

    @classmethod
    def effect_row(cls, reference, effect_class, *, children=(), child_definitions=()):
        return {
            "reference": reference,
            "effect_class": effect_class,
            "parameters": [],
            "parameter_count": 0,
            "variant": 0,
            "minimum_level": 0,
            "maximum_level": 0,
            "children": list(children),
            "child_definitions": list(child_definitions),
            "metadata": cls.metadata(),
            "criterion_raw": None,
            "criterion_native": None,
        }

    @classmethod
    def definition(cls, reference, level, rows):
        roots = deepcopy(rows)
        for ordinal, row in enumerate(roots):
            row["ordinal"] = ordinal
        return {
            "reference": reference,
            "container_type": 12,
            "fresh_container_level": level,
            "ordered_effects": roots,
        }

    @staticmethod
    def catalog(definitions):
        return {
            "producer": SOURCE,
            "complete": True,
            "definition_count": len(definitions),
            "definitions": {str(row["reference"]): row for row in definitions},
        }

    def setUp(self):
        child = self.effect_row(10011, 900)
        gear_roots = [
            self.effect_row(1001, 304, children=[10011], child_definitions=[child]),
            self.effect_row(1002, 302),
            self.effect_row(1003, 304),
            self.effect_row(1004, 304),
            self.effect_row(1005, 303),
        ]
        scroll_child = self.effect_row(2712311, 901)
        scroll_roots = [
            self.effect_row(
                271231,
                303,
                children=[2712311],
                child_definitions=[scroll_child],
            ),
            self.effect_row(271232, 303),
            self.effect_row(271233, 303),
        ]
        self.native_catalog = self.catalog(
            [
                self.definition(100, 80, gear_roots),
                self.definition(27123, 1, scroll_roots),
            ]
        )
        self.templates = {
            100: {
                "effects": [
                    {"id": 1001, "native_variant": 0, "native_active_effect": False},
                    {"id": 1002, "native_variant": 0, "native_active_effect": False},
                    {"id": 1003, "native_variant": 1, "native_active_effect": False},
                    {"id": 1004, "native_variant": 0, "native_active_effect": True},
                    {"id": 1005, "native_variant": 0, "native_active_effect": False},
                ]
            },
            27123: {
                "effects": [
                    {"id": 271231, "native_variant": 0, "native_active_effect": False},
                    {"id": 271232, "native_variant": 1, "native_active_effect": False},
                    {"id": 271233, "native_variant": 0, "native_active_effect": True},
                ]
            },
        }
        # The shared classifier needs the same scalar/profession ownership
        # summary fields as the actual native catalog, even for unknown roots.
        roots = {
            row["reference"]: row
            for definition in self.native_catalog["definitions"].values()
            for row in definition["ordered_effects"]
        }
        for template in self.templates.values():
            for effect in template["effects"]:
                effect.update(
                    generic=roots[effect["id"]]["effect_class"],
                    runner="fixture",
                    params=[],
                    values=[],
                    parameter_count=0,
                    stat_id=-1,
                    stat_limit=-1,
                    stat_name="",
                    has_triggers=False,
                    effect_criteria=False,
                    target_mask=0,
                )
        shard_state = proto_field(24, 27123) + proto_field(32, 27123)
        self.character = {
            "level": 100,
            "active_build_index": 0,
            "builds": {0: {"equipment": proto_field(424, 1).hex()}},
            "inventory_items": [
                {
                    "uid": 500,
                    "reference": 100,
                    "shard_state": shard_state,
                }
            ],
        }
        self.selected = [{"uid": 500, "slot": 0}]
        self.validate_sheet = patch(
            "wakfu_server.equipment.validate_sheet", return_value=self.selected
        )
        self.effective_level = patch(
            "wakfu_server.builds.effective_sheet_level", return_value=80
        )
        self.validate_sheet_mock = self.validate_sheet.start()
        self.effective_level_mock = self.effective_level.start()
        self.addCleanup(self.validate_sheet.stop)
        self.addCleanup(self.effective_level.stop)

    def make_plan(self, **kwargs):
        return plan(
            self.character,
            catalog=kwargs.pop("catalog", self.native_catalog),
            templates=kwargs.pop("templates", self.templates),
            **kwargs,
        )

    def authority(self, gear, state, reference, tag):
        return reference == 27123 and tag in (24, 32)

    def test_complete_gear_and_both_sublimation_closures_retain_parent_gear_context(
        self,
    ):
        seen = []

        def authorize(gear, state, reference, tag):
            seen.append((gear["uid"], reference, tag))
            return self.authority(gear, state, reference, tag)

        rows = self.make_plan(attachment_authority=authorize)
        self.assertEqual(seen, [(500, 27123, 24), (500, 27123, 32)])
        self.assertEqual(
            [
                (row["source_reference"], row["attachment_field"], row["roots"])
                for row in rows
            ],
            [
                (100, None, (1001, 1002, 1005)),
                (27123, 24, (271231,)),
                (27123, 32, (271231,)),
            ],
        )
        expected_parent = {
            "present": True,
            "type": 12,
            "id": 100,
            "level": 80,
            "is_spell": False,
            "native_kind": "item",
        }
        for row in rows:
            self.assertEqual(row["uid"], 500)
            self.assertEqual(row["reference"], 100)
            self.assertEqual(row["native_retained_container"], expected_parent)
        self.assertEqual(set(rows[0]["effects"]), {"1001", "10011", "1002", "1005"})
        self.assertEqual(rows[0]["effects"]["1001"]["children"], [10011])
        self.assertEqual(set(rows[1]["effects"]), {"271231", "2712311"})
        self.assertEqual(rows[1]["effects"]["271231"]["children"], [2712311])
        adjusted = self.validate_sheet_mock.call_args.args[0]
        self.assertEqual(adjusted["level"], 80)
        self.effective_level_mock.assert_called_once_with(self.character, 0)

    def test_ordinary_snapshot_ownership_and_both_authorized_slots_are_combined(self):
        rows = self.make_plan(
            ordinary_only=True,
            include_attachments=True,
            attachment_authority=self.authority,
        )
        self.assertEqual([row["attachment_field"] for row in rows], [None, 24, 32])
        self.assertTrue(all(row["unplanned_passive_effect_ids"] == () for row in rows))
        self.assertEqual(rows[1]["roots"], (271231,))
        self.assertEqual(
            rows[2]["native_retained_container"], rows[0]["native_retained_container"]
        )
        ordinary = self.make_plan(ordinary_only=True)
        self.assertEqual(rows[0], ordinary[0])
        disabled = self.make_plan(
            ordinary_only=True,
            include_attachments=True,
            attachment_authority=lambda *_args: False,
        )
        self.assertEqual(disabled, ordinary)
        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "eligibility authority"
        ):
            self.make_plan(ordinary_only=True, include_attachments=True)

    def test_missing_or_non_boolean_attachment_authority_fails_closed(self):
        with self.subTest(authority="missing"):
            with self.assertRaisesRegex(
                UnsupportedEffectExecution, "eligibility authority"
            ):
                self.make_plan()
        with self.subTest(authority="non_boolean"):
            with self.assertRaisesRegex(UnsupportedEffectExecution, "eligibility"):
                self.make_plan(attachment_authority=lambda *_args: 1)

    def test_false_attachment_authority_skips_both_scroll_roots(self):
        rows = self.make_plan(attachment_authority=lambda *_args: False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_reference"], 100)
        self.assertEqual(rows[0]["roots"], (1001, 1002, 1005))

    def test_native_passive_filter_keeps_operators_and_drops_active_or_variant_actions(
        self,
    ):
        rows = self.make_plan(attachment_authority=self.authority)
        ordinary = rows[0]
        self.assertEqual(ordinary["roots"], (1001, 1002, 1005))
        # Unknown operator roots remain planned for the later capability gate;
        # active actions and nonzero variants remain excluded from Ready.
        self.assertTrue(all(row["roots"] == (271231,) for row in rows[1:]))
        self.assertIn(1002, ordinary["roots"])
        self.assertTrue(all(1003 not in row["roots"] for row in rows))
        self.assertTrue(all(1004 not in row["roots"] for row in rows))
        self.assertIn(1005, ordinary["roots"])
        self.assertTrue(all(271232 not in row["roots"] for row in rows))
        self.assertTrue(all(271233 not in row["roots"] for row in rows))

    def test_malformed_native_effect_closure_is_rejected(self):
        broken = deepcopy(self.native_catalog)
        root = broken["definitions"]["100"]["ordered_effects"][0]
        root["child_definitions"] = []
        with self.assertRaisesRegex(ValueError, "closure|child order"):
            self.make_plan(attachment_authority=self.authority, catalog=broken)


if __name__ == "__main__":
    unittest.main()
