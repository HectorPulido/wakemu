"""Structural operation catalog closure stays explicit and non-accrediting."""
import sys
import os
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
import combat_operation_catalog as catalog


class CombatOperationCatalogTests(unittest.TestCase):
    def test_morph_and_aura_keep_separate_native_dependency_domains(self):
        tables = dict(
            spells={"1": [10, 11], "6007": []},
            morph_profiles={
                "4252": dict(
                    abilities=[dict(reference=6007)], initial_state_triples=[999, 1, 1]
                )
            },
            profiles={"4252": dict(abilities=[dict(reference=6006)])},
            areas={"991": []},
            effects={
                "10": dict(effect_class=933, parameters=[4252, 0]),
                "11": dict(effect_class=338, parameters=[991, 0]),
            },
        )
        report = catalog.compile_catalog(tables, [("spell", 1)]).report()
        self.assertIn("morph:4252", report["nodes"])
        self.assertIn("spell:6007", report["nodes"])
        self.assertIn("area:991", report["nodes"])
        self.assertNotIn("summon:4252", report["nodes"])
        self.assertNotIn("state:999", report["nodes"])
        self.assertNotIn("spell:6006", report["nodes"])

    def test_compiler_import_and_empty_compile_work_without_database_configuration(
        self,
    ):
        env = dict(os.environ)
        env.pop("WAKFU_DATABASE_URL", None)
        env.pop("WAKFU_DATABASE_PASSWORD_FILE", None)
        env["PYTHONPATH"] = (
            str(ROOT / "server") + os.pathsep + str(ROOT / "server/tools")
        )
        code = (
            "import combat_operation_catalog as c; "
            "r=c.compile_catalog({'spells': {'1': []}}, [('spell', 1)]).report(); "
            "assert r['seeds'] == [{'kind': 'spell', 'reference': 1}]"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_criterion_syntax_and_runtime_predicate_axes_are_separate(self):
        tables = {
            "spells": {"908": [1]},
            "effects": {
                "1": {"effect_class": 777, "criteria": "GetLevel() > 4"},
                "2": {"effect_class": 777, "criteria": "1 &&"},
            },
        }
        supported = catalog.compile_catalog(tables, [("spell", 908)]).report()
        self.assertEqual(
            supported["nodes"]["effect:1"]["criterion_syntax"]["status"], "supported"
        )
        self.assertEqual(
            supported["nodes"]["effect:1"]["criterion_evaluation"]["status"], "unknown"
        )
        tables["spells"]["908"] = [2]
        malformed = catalog.compile_catalog(tables, [("spell", 908)]).report()
        self.assertEqual(
            malformed["nodes"]["effect:2"]["criterion_syntax"]["status"], "unsupported"
        )
        self.assertIn(
            "malformed-native-criterion",
            {issue["reason"] for issue in malformed["issues"]},
        )

    def test_retained_capability_requires_matching_native_definition_metadata(self):
        row = {
            "effect_class": 48,
            "parameters": [1, 0],
            "variant": 0,
            "minimum_level": 0,
            "maximum_level": 0,
            "native_execution_mode": 0,
            "native_timing_definition": {},
        }
        tables = {"spells": {"909": [1]}, "effects": {"1": row}}
        unknown = catalog.compile_catalog(tables, [("spell", 909)]).report()["nodes"][
            "effect:1"
        ]
        self.assertEqual(unknown["retained_execution"]["status"], "unknown")
        self.assertIn("lifecycle.retained", unknown["operation_ids"])
        metadata = {
            "effects": {
                "1": {
                    "effect_class": 48,
                    "variant": 0,
                    "minimum_level": 0,
                    "maximum_level": 0,
                    "parameters": [1, 0],
                    "definition_type": 0,
                    "subscription": False,
                }
            }
        }
        retained = catalog.compile_catalog(
            tables, [("spell", 909)], retained_metadata=metadata
        ).report()["nodes"]["effect:1"]
        self.assertEqual(retained["retained_execution"]["status"], "conditional")
        self.assertIn("lifecycle.retained", retained["operation_ids"])

        wrong = {"effects": {"1": {**metadata["effects"]["1"], "maximum_level": 2}}}
        unsupported = catalog.compile_catalog(
            tables, [("spell", 909)], retained_metadata=wrong
        ).report()["nodes"]["effect:1"]
        # Unsupported lifecycle metadata must not remove a capability that is
        # structurally required; the operation ID remains visible for review.
        self.assertEqual(unsupported["retained_execution"]["status"], "unsupported")
        self.assertIn("lifecycle.retained", unsupported["operation_ids"])
        self.assertTrue(
            any(
                issue["status"] == "unsupported"
                and issue["reason"].startswith("retained-metadata-identity-mismatch")
                for issue in catalog.compile_catalog(
                    tables, [("spell", 909)], retained_metadata=wrong
                ).report()["issues"]
            )
        )

    def test_all_affected_consumers_are_reported_for_shared_dependency(self):
        tables = {
            "spells": {"910": [1], "911": [2]},
            "effects": {
                "1": {"effect_class": 304, "parameters": [999, 0, 0, 0, 0, 0]},
                "2": {"effect_class": 304, "parameters": [999, 0, 0, 0, 0, 0]},
            },
            "states": {},
        }
        report = catalog.compile_catalog(
            tables, [("spell", 910), ("spell", 911)]
        ).report()
        issue = next(
            row
            for row in report["issues"]
            if row["reason"] == "missing-native-definition"
        )
        self.assertEqual(issue["affected_consumers"], ["spell:910", "spell:911"])

    def test_compiled_report_pins_all_five_contract_and_parser_sources(self):
        report = catalog.compile_catalog(
            {"spells": {"912": []}}, [("spell", 912)]
        ).report()
        required = {
            "server/wakfu_server/combat/combat_operation_registry.py",
            "server/wakfu_server/combat/combat_subscription_contracts.py",
            "server/wakfu_server/combat/combat_damage_contracts.py",
            "server/wakfu_server/combat/combat_local_criteria.py",
            "server/tools/combat_operation_catalog.py",
        }
        self.assertEqual(set(report["registry_sources"]), required)
        self.assertTrue(
            all(len(value) == 64 for value in report["registry_sources"].values())
        )

    def test_cell_null_contract_assessment_uses_observed_masks_and_flags(self):
        row = {
            "effect_class": 402,
            "parameters": [],
            "target_masks": [None] * 7,
            "native_effect_flags": [17],
        }
        assessment = catalog.operation_registry.assess_operation(row)
        self.assertEqual(assessment.status, "conditional")
        for invalid in (
            {**row, "target_masks": [[1], None, None, None, None, None, None]},
            {**row, "native_effect_flags": [31]},
            {**row, "parameters": [1]},
            {key: value for key, value in row.items() if key != "target_masks"},
        ):
            with self.subTest(invalid=invalid):
                status = catalog.operation_registry.assess_operation(invalid).status
                self.assertIn(status, ("unsupported", "unknown"))

    def test_malformed_catalog_rows_and_references_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Catalog tables required"):
            catalog.compile_catalog([], [("spell", 1)])
        with self.assertRaisesRegex(ValueError, "Unknown catalog seed kind"):
            catalog.compile_catalog({}, [("actor", 1)])
        with self.assertRaisesRegex(ValueError, "Positive native reference"):
            catalog.compile_catalog({"spells": {"0": []}}, [("spell", 0)])
        with self.assertRaisesRegex(ValueError, "Malformed native level roots"):
            catalog.compile_catalog(
                {"spells": {"1": {"levels": ["bad"]}}}, [("spell", 1)]
            )
        with self.assertRaisesRegex(
            ValueError, "Malformed native summon initial states"
        ):
            catalog.compile_catalog(
                {"summons": {"1": {"initial_state_triples": [7, 1]}}}, [("summon", 1)]
            )

    def test_cyclic_effect_graph_terminates_and_retains_both_edges(self):
        tables = {
            "spells": {"900": [1]},
            "effects": {
                "1": {"effect_class": 777, "children": [2], "criteria": ""},
                "2": {"effect_class": 778, "children": [1], "criteria": ""},
            },
        }
        report = catalog.compile_catalog(tables, [("spell", 900)]).report()
        self.assertEqual(set(report["nodes"]), {"spell:900", "effect:1", "effect:2"})
        self.assertEqual(
            {(edge["source"], edge["target"]) for edge in report["edges"]},
            {
                ("spell:900", "effect:1"),
                ("effect:1", "effect:2"),
                ("effect:2", "effect:1"),
            },
        )
        self.assertIn(
            "missing-shared-operation", {issue["reason"] for issue in report["issues"]}
        )

    def test_state_decurse_reports_removed_state_without_expanding_its_effects(self):
        tables = {
            "spells": {"901": [1]},
            "effects": {"1": {"effect_class": 321, "parameters": [5227, 0]}},
            "states": {"5227": [2]},
            "effects_extra": {},
        }
        report = catalog.compile_catalog(tables, [("spell", 901)]).report()
        self.assertIn(
            {
                "source": "effect:1",
                "target": "state:5227",
                "relation": "removes",
                "path": ["spell:901", "effect:1", "state:5227"],
            },
            report["edges"],
        )
        self.assertIn("state:5227", report["nodes"])
        self.assertNotIn("effect:2", report["nodes"])

    def test_dynamic_parameters_require_evaluated_level_samples(self):
        tables = {
            "spells": {"902": [1]},
            "effects": {
                "1": {"effect_class": 304, "parameters": [99, 1]},
                "2": {"effect_class": 777},
            },
            "states": {"11": [], "12": []},
        }
        report = catalog.compile_catalog(tables, [("spell", 902)]).report()
        self.assertNotIn("state:99", report["nodes"])
        self.assertIn(
            "dynamic-reference-needs-evaluated-levels",
            {issue["reason"] for issue in report["issues"]},
        )
        tables["effects"]["1"]["parameter_samples_by_level"] = {"1": [11], "2": [12]}
        report = catalog.compile_catalog(tables, [("spell", 902)]).report()
        self.assertIn("state:11", report["nodes"])
        self.assertIn("state:12", report["nodes"])

    def test_summon_307_reference_uses_signed_short_decoding(self):
        tables = {
            "summons": {"40": {"native_abilities": [], "initial_state_triples": []}},
            "effects": {"1": {"effect_class": 307, "parameters": [65540, 0]}},
        }
        # Reach family 307 as an effect root; its signed short parameter decodes to profile 4.
        tables["spells"] = {"903": [1]}
        tables["summons"]["4"] = {"native_abilities": [], "initial_state_triples": []}
        report = catalog.compile_catalog(tables, [("spell", 903)]).report()
        self.assertIn("summon:4", report["nodes"])
        self.assertIn(
            {
                "source": "effect:1",
                "target": "summon:4",
                "relation": "requires",
                "path": ["spell:903", "effect:1", "summon:4"],
            },
            report["edges"],
        )

    def test_fixed_dependencies_expand_without_effect_parameters(self):
        tables = {
            "spells": {"904": [1]},
            "effects": {"1": {"effect_class": 48}, "2": {"effect_class": 777}},
            "states": {"5227": [2]},
        }
        report = catalog.compile_catalog(tables, [("spell", 904)]).report()
        self.assertIn(
            {
                "source": "effect:1",
                "target": "state:5227",
                "relation": "conditional-positive-loss",
                "path": ["spell:904", "effect:1", "state:5227"],
            },
            report["edges"],
        )
        self.assertIn("effect:2", report["nodes"])

    def test_serialized_plan_is_deeply_immutable_from_report_callers(self):
        plan = catalog.compile_catalog(
            {"spells": {"905": [1]}, "effects": {"1": {"effect_class": 987}}},
            [("spell", 905)],
        )
        first = plan.report()
        first["nodes"]["effect:1"]["family"] = -1
        first["issues"].clear()
        second = plan.report()
        self.assertEqual(second["nodes"]["effect:1"]["family"], 987)
        self.assertIn(
            "missing-shared-operation", {issue["reason"] for issue in second["issues"]}
        )

    def test_operation_combination_and_client_axes_remain_independent(self):
        report = catalog.compile_catalog(
            {
                "spells": {"906": [1]},
                "effects": {
                    "1": {
                        "effect_class": 304,
                        "parameters": [7, 0, 0, 0, 0, 0],
                        "children": [2],
                    },
                    "2": {"effect_class": 777},
                },
                "states": {"7": []},
            },
            [("spell", 906)],
        ).report()
        modeled = report["nodes"]["effect:1"]
        self.assertEqual(modeled["operation_support"], "conditional")
        self.assertEqual(modeled["combination_verification"], "unknown")
        self.assertEqual(modeled["modeled_client_compatibility"], "unknown")
        unknown = report["nodes"]["effect:2"]
        self.assertEqual(unknown["operation_support"], "unknown")
        self.assertEqual(unknown["combination_verification"], "unknown")
        self.assertEqual(unknown["modeled_client_compatibility"], "unknown")
        self.assertEqual(report["combination_verification"], "unknown")
        self.assertEqual(report["modeled_client_compatibility"], "unknown")

    def test_class_spell_and_monster_profile_schemas_share_one_closure(self):
        tables = {
            "spells": {"907": [1]},
            "summons": {
                "80": {
                    "abilities": [{"reference": 907}],
                    "initial_state_triples": [91, 1, 0],
                }
            },
            "effects": {
                "1": {"effect_class": 304, "parameters": [92, 0]},
                "2": {"effect_class": 777},
            },
            "states": {"91": [2], "92": []},
        }
        class_report = catalog.compile_catalog(tables, [("spell", 907)]).report()
        monster_report = catalog.compile_catalog(
            {**tables, "monsters": tables["summons"]}, [("summon", 80)]
        ).report()
        self.assertEqual(class_report["schema"], catalog.SCHEMA)
        self.assertIn("state:92", class_report["nodes"])
        self.assertEqual(monster_report["schema"], catalog.SCHEMA)
        self.assertIn("spell:907", monster_report["nodes"])
        self.assertIn("state:91", monster_report["nodes"])
        self.assertIn("state:92", monster_report["nodes"])


if __name__ == "__main__":
    unittest.main()
