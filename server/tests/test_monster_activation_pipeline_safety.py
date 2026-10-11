"""Cross-tool safety tests for automatic NPC activation selection and receipts."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from finalize_monster_spell_activation import finalize
from prepare_monster_spell_activation import merge_npc, select_candidates
from validate_monster_spell_activation import initialization_proven


class AutomaticMonsterActivationPipelineTests(unittest.TestCase):
    INITIAL_TRIPLES = [8101, -1, 0, 8102, 3, 1]
    RESOLVED_AT_LEVEL_5 = [
        {"state_id": 8101, "level": 5, "native_rBq": True, "native_rBr": True},
        {"state_id": 8102, "level": 3, "native_rBq": False, "native_rBr": True},
    ]

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.output = self.root / "final"
        self.audit_path = self.root / "execution-validation.json"
        self.base_revision = "read-only-native-revision"

    @staticmethod
    def write_json(path, value, *, indent=None):
        path.write_text(
            json.dumps(value, separators=None if indent else (",", ":"), indent=indent)
            + "\n"
        )

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def valid_case(self, ref, level, spell_id, *, effectful=True):
        return {
            "ref": ref,
            "level": level,
            "spell_id": spell_id,
            "status": "validated",
            "successful_targets": [{"effectful": effectful}],
        }

    @classmethod
    def native_initialization_receipt(cls, ref, level):
        resolved = [
            {"state_id": 8101, "level": level, "native_rBq": True, "native_rBr": True},
            {"state_id": 8102, "level": 3, "native_rBq": False, "native_rBr": True},
        ]
        return {
            "initialized": True,
            "ref": ref,
            "descriptor_level": level,
            "raw_triples": list(cls.INITIAL_TRIPLES),
            "resolved_states": resolved,
            "applications": [
                {
                    "state_id": state["state_id"],
                    "level": state["level"],
                    "applied": True,
                }
                for state in resolved
            ],
            "placement_effects": {
                "verified": True,
                "bytes": 128,
                "effect_count": 2,
                "state_carrier_count": 2,
                "sha256": "a" * 64,
            },
        }

    def add_native_initialization_evidence(self):
        self.prepare_pipeline_artifacts()
        npc_path = self.candidate / "native-npc-spell-effect-trees.json"
        npc = json.loads(npc_path.read_text())
        npc["activation_policy"]["enabled_monsters"]["101"][
            "initial_state_triples"
        ] = list(self.INITIAL_TRIPLES)
        self.write_json(npc_path, npc)

        manifest_path = self.candidate / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["changed_documents"][npc_path.name] = self.sha(npc_path)
        self.write_json(manifest_path, manifest)

        audit = json.loads(self.audit_path.read_text())
        audit["candidate_manifest_sha256"] = self.sha(manifest_path)
        audit["changed_document_hashes"] = dict(manifest["changed_documents"])
        row = next(row for row in audit["monsters"] if row["ref"] == 101)
        row["ai_commit"]["level"] = 1
        row["ai_commit"]["native_initialization"] = self.native_initialization_receipt(
            101, 1
        )
        for case in row["cases"]:
            for target in case["successful_targets"]:
                target["native_initialization"] = self.native_initialization_receipt(
                    101, case["level"]
                )
        self.write_json(self.audit_path, audit)

    def prepare_pipeline_artifacts(self):
        coverage_rows = [
            {
                "ref": 101,
                "min_level": 1,
                "max_level": 2,
                "status": "covered",
                "spell_ids": [501],
                "data_gaps": [],
                "missing_families": [],
            },
            {
                "ref": 102,
                "min_level": 1,
                "max_level": 1,
                "status": "covered",
                "spell_ids": [502],
                "data_gaps": [],
                "missing_families": [],
            },
            {
                "ref": 999,
                "min_level": 10,
                "max_level": 20,
                "status": "covered",
                "spell_ids": [9991],
                "data_gaps": [],
                "missing_families": [],
            },
            {
                "ref": 1000,
                "min_level": 1,
                "max_level": 1,
                "status": "covered",
                "spell_ids": [10001],
                "data_gaps": ["unresolved native effect"],
                "missing_families": [],
            },
        ]
        selected = select_candidates({"monsters": coverage_rows})
        self.assertEqual([row["ref"] for row in selected], [101, 102])

        baseline_npc = {
            "spells": {"700": {"legacy": True}},
            "effects": {"old-effect": {"effect_class": 3}},
            "activation_policy": {
                "schema": "native-npc-activation-v1",
                "legacy_spell_ids": [700],
                "enabled_monsters": {
                    "900": {"min_level": 1, "max_level": 2, "spell_ids": [9001]},
                },
            },
        }
        exported = {
            "spells": {
                "501": {"levels": [{"spell_level": 1}]},
                "502": {"levels": [{"spell_level": 1}]},
            },
            "effects": {"new-effect": {"effect_class": 7}},
        }
        candidate_npc = merge_npc(baseline_npc, exported, selected)
        candidate_roots = {
            "roots": {"existing-class-root": [1, 2], "npc-root": [501, 502]}
        }
        documents = {
            "native-npc-spell-effect-trees.json": candidate_npc,
            "native-class-casting-roots.json": candidate_roots,
        }
        hashes = {}
        for name, document in documents.items():
            path = self.candidate / name
            self.write_json(path, document)
            hashes[name] = self.sha(path)

        base_documents = {
            "native-npc-spell-effect-trees.json": baseline_npc,
            "native-class-casting-roots.json": {
                "roots": {"existing-class-root": [1, 2]}
            },
        }
        base_hashes = {}
        for name, document in base_documents.items():
            path = self.candidate / ("base-" + name)
            self.write_json(path, document)
            base_hashes[name] = self.sha(path)

        inventory_rows = [
            {
                "ref": row["ref"],
                "min_level": row["min_level"],
                "max_level": row["max_level"],
                "spell_ids": row["spell_ids"],
                "activation_status": "candidate_pending_execution_validation",
                "runtime_status": "candidate_release_not_activated",
            }
            for row in selected
        ] + [
            {
                "ref": 999,
                "min_level": 10,
                "max_level": 20,
                "spell_ids": [9991],
                "activation_status": "inventory_only",
                "runtime_status": "candidate_release_not_activated",
            }
        ]
        self.write_json(
            self.candidate / "monster-status.json",
            {
                "schema": "monster-spell-activation-inventory-v1",
                "base_revision": self.base_revision,
                "activated": False,
                "monsters": inventory_rows,
            },
        )
        manifest = {
            "schema": "native-npc-activation-candidate-v1",
            "base_revision": self.base_revision,
            "activated": False,
            "selected_references": [101, 102],
            "changed_documents": hashes,
            "unchanged_documents": {
                "native-class-catalog.json": "class-preservation-hash"
            },
            "base_document_hashes": base_hashes,
        }
        self.write_json(self.candidate / "manifest.json", manifest)

        def audit_row(
            ref,
            cases,
            *,
            status="validated",
            pending_initialization=False,
            effectful=True
        ):
            return {
                "ref": ref,
                "status": status,
                "pending_initialization": pending_initialization,
                "cases": cases,
                "ai_commit": {
                    "status": "validated",
                    "packets": 1,
                    "forecast_source_unchanged": True,
                    "serializer_failure_rolled_back": True,
                },
            }

        validation = {
            "schema": "native-npc-activation-validation-v1",
            "candidate_manifest_sha256": self.sha(self.candidate / "manifest.json"),
            "changed_document_hashes": hashes,
            "base_revision": self.base_revision,
            "overlay_applied": "npc_candidate",
            "class_tests": {
                "run": 179,
                "successful": True,
                "failures": [],
                "errors": [],
                "skipped": [],
            },
            "sources_stable": True,
            "preview_sources_match_current": True,
            "runtime_code_sha256": {},
            "base_document_hashes": base_hashes,
            "monsters": [
                audit_row(101, [self.valid_case(101, level, 501) for level in (1, 2)]),
                audit_row(102, [self.valid_case(102, 1, 502, effectful=False)]),
            ],
        }
        self.write_json(self.audit_path, validation)

    def test_selector_to_finalizer_only_promotes_fully_proven_refs(self):
        self.prepare_pipeline_artifacts()
        candidate_before = {
            path.name: path.read_bytes()
            for path in self.candidate.iterdir()
            if path.is_file()
        }

        result = finalize(self.candidate, self.audit_path, self.output)

        self.assertEqual(
            result, {"validated": 1, "pending": 1, "total": 3, "activated": False}
        )
        manifest = json.loads((self.output / "manifest.json").read_text())
        inventory = json.loads((self.output / "monster-status.json").read_text())
        npc = json.loads(
            (self.output / "native-npc-spell-effect-trees.json").read_text()
        )
        self.assertEqual(manifest["selected_references"], [101])
        self.assertEqual(manifest["evaluated_references"], [101, 102])
        self.assertIs(manifest["activated"], False)
        self.assertEqual(
            set(npc["activation_policy"]["enabled_monsters"]), {"900", "101"}
        )
        self.assertEqual(npc["activation_policy"]["legacy_spell_ids"], [700])
        self.assertEqual(npc["baseline_effects"], {"old-effect": {"effect_class": 3}})
        self.assertEqual(
            json.loads((self.output / "native-class-casting-roots.json").read_text())[
                "roots"
            ]["existing-class-root"],
            [1, 2],
        )
        self.assertIs(inventory["activated"], False)
        self.assertEqual(
            candidate_before,
            {
                path.name: path.read_bytes()
                for path in self.candidate.iterdir()
                if path.is_file()
            },
        )

    def test_receipt_cannot_authorize_a_candidate_changed_after_selection(self):
        self.prepare_pipeline_artifacts()
        npc_path = self.candidate / "native-npc-spell-effect-trees.json"
        altered = json.loads(npc_path.read_text())
        altered["activation_policy"]["enabled_monsters"]["101"]["spell_ids"] = [9999]
        self.write_json(npc_path, altered)

        with self.assertRaisesRegex(ValueError, "changed after validation"):
            finalize(self.candidate, self.audit_path, self.output)
        self.assertFalse(self.output.exists())

    def test_selection_limit_is_inclusive_and_rejects_non_positive_or_boolean_values(
        self,
    ):
        rows = [
            {
                "ref": 1,
                "min_level": 1,
                "max_level": 5,
                "status": "covered",
                "spell_ids": [10],
                "data_gaps": [],
                "missing_families": [],
            },
            {
                "ref": 2,
                "min_level": 1,
                "max_level": 6,
                "status": "covered",
                "spell_ids": [20],
                "data_gaps": [],
                "missing_families": [],
            },
        ]
        self.assertEqual(
            [row["ref"] for row in select_candidates({"monsters": rows}, 5)], [1]
        )
        for invalid in (0, -1, True, 5.0):
            with self.subTest(maximum=invalid):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    select_candidates({"monsters": rows}, invalid)

    def test_native_initial_state_triples_are_copied_into_only_the_selected_policy(
        self,
    ):
        previous = {
            "spells": {"700": {"legacy": True}},
            "effects": {},
            "activation_policy": {
                "schema": "native-npc-activation-v1",
                "legacy_spell_ids": [700],
                "enabled_monsters": {
                    "900": {
                        "min_level": 1,
                        "max_level": 2,
                        "spell_ids": [9001],
                        "initial_state_triples": [91, -1, 4],
                    },
                },
            },
        }
        source_triples = [12, -1, 3, 14, 2, 7]
        selected = [
            {
                "ref": 101,
                "min_level": 1,
                "max_level": 2,
                "spell_ids": [501],
                "initial_state_triples": source_triples,
            }
        ]
        prepared = merge_npc(previous, {"spells": {}, "effects": {}}, selected)

        self.assertEqual(
            prepared["activation_policy"]["enabled_monsters"]["101"][
                "initial_state_triples"
            ],
            source_triples,
        )
        self.assertEqual(
            prepared["activation_policy"]["enabled_monsters"]["900"][
                "initial_state_triples"
            ],
            [91, -1, 4],
        )
        self.assertIsNot(
            prepared["activation_policy"]["enabled_monsters"]["101"][
                "initial_state_triples"
            ],
            source_triples,
        )
        self.assertEqual(source_triples, [12, -1, 3, 14, 2, 7])

    def test_initialization_receipt_matches_raw_triples_and_descriptor_resolution_exactly(
        self,
    ):
        exact = self.native_initialization_receipt(101, 5)
        self.assertEqual(exact["resolved_states"], self.RESOLVED_AT_LEVEL_5)
        self.assertTrue(initialization_proven(101, 5, self.INITIAL_TRIPLES, exact))
        self.assertTrue(initialization_proven(101, 5, [], None))

        invalid_receipts = []
        wrong_level = self.native_initialization_receipt(101, 4)
        invalid_receipts.append((5, wrong_level))
        wrong_raw = self.native_initialization_receipt(101, 5)
        wrong_raw["raw_triples"] = [8101, 4, 0, 8102, -1, 1]
        invalid_receipts.append((5, wrong_raw))
        unresolved_descriptor_level = self.native_initialization_receipt(101, 5)
        unresolved_descriptor_level["resolved_states"][0]["level"] = -1
        invalid_receipts.append((5, unresolved_descriptor_level))
        wrong_flag = self.native_initialization_receipt(101, 5)
        wrong_flag["resolved_states"][0]["native_rBq"] = False
        invalid_receipts.append((5, wrong_flag))
        wrong_owner = self.native_initialization_receipt(102, 5)
        invalid_receipts.append((5, wrong_owner))
        missing_application_proof = self.native_initialization_receipt(101, 5)
        missing_application_proof.pop("applications")
        invalid_receipts.append((5, missing_application_proof))
        unapplied_state = self.native_initialization_receipt(101, 5)
        unapplied_state["applications"][0]["applied"] = False
        invalid_receipts.append((5, unapplied_state))
        reordered_applications = self.native_initialization_receipt(101, 5)
        reordered_applications["applications"].reverse()
        invalid_receipts.append((5, reordered_applications))
        missing_placement = self.native_initialization_receipt(101, 5)
        missing_placement.pop("placement_effects")
        invalid_receipts.append((5, missing_placement))
        empty_placement_count = self.native_initialization_receipt(101, 5)
        empty_placement_count["placement_effects"].update(
            effect_count=0, state_carrier_count=0
        )
        invalid_receipts.append((5, empty_placement_count))
        omitted_state_carrier = self.native_initialization_receipt(101, 5)
        omitted_state_carrier["placement_effects"]["state_carrier_count"] = 0
        invalid_receipts.append((5, omitted_state_carrier))
        invalid_placement_digest = self.native_initialization_receipt(101, 5)
        invalid_placement_digest["placement_effects"]["sha256"] = "A" * 64
        invalid_receipts.append((5, invalid_placement_digest))
        unverified_placement = self.native_initialization_receipt(101, 5)
        unverified_placement["placement_effects"]["verified"] = False
        invalid_receipts.append((5, unverified_placement))
        for descriptor_level, receipt in invalid_receipts:
            with self.subTest(receipt=receipt):
                self.assertFalse(
                    initialization_proven(
                        101, descriptor_level, self.INITIAL_TRIPLES, receipt
                    )
                )

    def test_finalizer_accepts_complete_commit_and_case_initialization_receipts(self):
        self.add_native_initialization_evidence()
        result = finalize(self.candidate, self.audit_path, self.output)
        self.assertEqual(result["validated"], 1)
        final_npc = json.loads(
            (self.output / "native-npc-spell-effect-trees.json").read_text()
        )
        self.assertEqual(
            final_npc["activation_policy"]["enabled_monsters"]["101"][
                "initial_state_triples"
            ],
            self.INITIAL_TRIPLES,
        )

    def test_finalizer_requires_commit_and_each_effectful_case_initialization_receipt(
        self,
    ):
        self.add_native_initialization_evidence()
        valid_audit = json.loads(self.audit_path.read_text())
        for missing in ("commit", "case"):
            with self.subTest(missing=missing):
                audit = json.loads(json.dumps(valid_audit))
                row = next(row for row in audit["monsters"] if row["ref"] == 101)
                if missing == "commit":
                    row["ai_commit"].pop("native_initialization")
                else:
                    row["cases"][0]["successful_targets"][0].pop(
                        "native_initialization"
                    )
                self.write_json(self.audit_path, audit)
                output = self.root / ("invalid-initialization-" + missing)
                with self.assertRaisesRegex(ValueError, "No completely validated"):
                    finalize(self.candidate, self.audit_path, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
