"""Definition union never overrides another variant's original native row."""
import importlib.util
import os
from pathlib import Path
import unittest


class RetainedDefinitionClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(
            os.environ.get(
                "WAKFU_DEFINITION_CLOSURE_PUBLISHER",
                str(
                    Path(__file__).parents[1]
                    / "tools/publish_compiled_combat_catalog.py"
                ),
            )
        )
        spec = importlib.util.spec_from_file_location("closure_publisher_test", path)
        cls.publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.publisher)

    def test_union_resolves_foreign_definition_without_changing_entry_sources(self):
        ordinary = {"1": {"effect_class": 330, "target_masks": [None] * 7}}
        npc = {**ordinary, "293160": {"effect_class": 400, "target_masks": [None] * 7}}
        weapon = {
            **ordinary,
            "327384": {"effect_class": 1083, "target_masks": [None] * 7},
        }
        union = self.publisher.merge_resolution_definitions(
            [
                ("player", ordinary),
                ("npc_imported", npc),
                ("weapon", weapon),
            ]
        )
        self.assertIs(union["293160"], npc["293160"])
        self.assertNotIn("293160", ordinary)
        self.assertNotIn("293160", weapon)
        self.assertEqual(list(union), ["1", "293160", "327384"])

    def test_full_row_collision_including_removal_masks_rejects(self):
        base = {
            "293160": {"effect_class": 400, "target_masks": [None] * 7, "criteria": ""}
        }
        for changed in (
            {
                "effect_class": 400,
                "target_masks": [None, None, [1016], None, None, None, None],
                "criteria": "",
            },
            {"effect_class": 400, "target_masks": [None] * 7, "criteria": "False"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(
                    ValueError, "Conflicting retained definition.*293160"
                ):
                    self.publisher.merge_resolution_definitions(
                        [
                            ("npc_imported", base),
                            ("weapon", {"293160": changed}),
                        ]
                    )

    def test_exporter_timing_samples_are_not_execution_identity(self):
        original = {
            "effect_class": 400,
            "native_timing_definition": {"ryE": 1},
            "native_timing_checks": {"1": {"duration": [1, False, 1, False]}},
        }
        without_observations = {
            key: value
            for key, value in original.items()
            if key != "native_timing_checks"
        }
        union = self.publisher.merge_resolution_definitions(
            [
                ("player", {"255823": original}),
                ("npc_imported", {"255823": without_observations}),
            ]
        )
        self.assertIs(union["255823"], original)
        self.assertIn("native_timing_checks", original)
        self.assertNotIn("native_timing_checks", without_observations)
        changed = dict(without_observations, native_timing_definition={"ryE": 2})
        with self.assertRaisesRegex(
            ValueError, "Conflicting retained definition.*255823"
        ):
            self.publisher.merge_resolution_definitions(
                [
                    ("player", {"255823": original}),
                    ("npc_imported", {"255823": changed}),
                ]
            )
        changed = dict(without_observations, native_effect_flags=[4])
        with self.assertRaisesRegex(
            ValueError, "Conflicting retained definition.*255823"
        ):
            self.publisher.merge_resolution_definitions(
                [
                    ("player", {"255823": original}),
                    ("npc_imported", {"255823": changed}),
                ]
            )

    def test_nested_immutable_json_sequences_compare_by_native_values(self):
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        original = ImmutableCatalog(
            {
                "effect_class": 400,
                "native_target_selector": {"mask": 1, "offsets": [[0, 1]]},
            }
        )
        frozen = ImmutableCatalog(
            {
                "effect_class": 400,
                "native_target_selector": {"mask": 1, "offsets": ((0, 1),)},
            }
        )
        merged = self.publisher.merge_resolution_definitions(
            [
                ("player", {"35341": original}),
                ("npc_imported", {"35341": frozen}),
            ]
        )
        self.assertIs(merged["35341"], original)
        self.assertEqual(
            self.publisher.native_json(merged["35341"]),
            self.publisher.native_json(frozen),
        )
        changed = ImmutableCatalog(
            {
                "effect_class": 400,
                "native_target_selector": {"mask": 1, "offsets": ((0, 2),)},
            }
        )
        with self.assertRaisesRegex(
            ValueError, "Conflicting retained definition.*35341"
        ):
            self.publisher.merge_resolution_definitions(
                [
                    ("player", {"35341": original}),
                    ("npc_imported", {"35341": changed}),
                ]
            )

    def test_destination_keeps_existing_35341_and_rejects_ambiguous_missing_reference(
        self,
    ):
        player = {"35341": {"effect_class": 400, "parameters_by_level": [[11]] * 200}}
        imported = {
            "35341": {
                "effect_class": 400,
                "parameters_by_level": [[11]] * 245,
                "native_active_effect": True,
            },
            "293160": {"effect_class": 400, "target_masks": [None] * 7},
        }
        result = self.publisher.merge_resolution_definitions(
            [("npc_imported", imported)],
            own=player,
        )
        self.assertIs(result["35341"], player["35341"])
        self.assertIs(result["293160"], imported["293160"])
        self.assertEqual(tuple(result), ("35341", "293160"))
        reverse = self.publisher.merge_resolution_definitions(
            [("player", player)],
            own=imported,
        )
        self.assertIs(reverse["35341"], imported["35341"])
        self.assertEqual(tuple(reverse), tuple(imported))
        with self.assertRaisesRegex(
            ValueError, "Conflicting retained definition.*35341"
        ):
            self.publisher.merge_resolution_definitions(
                [("player", player), ("npc_imported", imported)],
                own={},
            )
