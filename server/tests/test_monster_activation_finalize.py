"""Finalization gates for NPC spell execution candidates."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import finalize_monster_spell_activation as finalizer


class MonsterActivationFinalizeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.validation = self.root / "validation.json"
        self.output = self.root / "final"
        self.monsters = [
            {
                "ref": 1,
                "min_level": 1,
                "max_level": 2,
                "spell_ids": [101, 102],
                "activation_status": "candidate_pending_execution_validation",
                "runtime_status": "candidate_release_not_activated",
                "note": "selected",
            },
            {
                "ref": 2,
                "min_level": 1,
                "max_level": 1,
                "spell_ids": [201],
                "activation_status": "candidate_pending_execution_validation",
                "runtime_status": "candidate_release_not_activated",
                "note": "selected",
            },
            {
                "ref": 99,
                "min_level": 10,
                "max_level": 20,
                "spell_ids": [999],
                "activation_status": "inventory_only",
                "runtime_status": "candidate_release_not_activated",
                "note": "high-level inventory row",
            },
        ]
        self.npc = {
            "spells": {"777": {"legacy": True}},
            "effects": {"new-effect": {"effect_class": 7}},
            "baseline_effects": {"old-effect": {"effect_class": 3, "parameters": [1]}},
            "activation_policy": {
                "schema": "native-npc-activation-v1",
                "legacy_spell_ids": [777],
                "enabled_monsters": {
                    "1": {"min_level": 1, "max_level": 2, "spell_ids": [101, 102]},
                    "2": {"min_level": 1, "max_level": 1, "spell_ids": [201]},
                },
            },
        }
        self.base_npc = {
            "effects": {"old-effect": {"effect_class": 3, "parameters": [1]}},
            "activation_policy": {
                "legacy_spell_ids": [777],
                "enabled_monsters": {
                    "900": {"min_level": 1, "max_level": 3, "spell_ids": [9001]}
                },
            },
        }
        self.base_roots = {"roots": {"class-root": [10]}}
        self.write_candidate()
        self.audit = self.make_audit()
        self.write_audit()

    @staticmethod
    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    def write_candidate(self):
        self.changed_names = [
            "native-npc-spell-effect-trees.json",
            "native-class-casting-roots.json",
        ]
        documents = {
            self.changed_names[0]: self.npc,
            self.changed_names[1]: {"roots": {"new": [1]}},
        }
        hashes = {}
        for name, document in documents.items():
            raw = json.dumps(document, separators=(",", ":")).encode()
            (self.candidate / name).write_bytes(raw)
            hashes[name] = self.sha(raw)
        base_npc_path = self.candidate / ("base-" + self.changed_names[0])
        base_roots_path = self.candidate / ("base-" + self.changed_names[1])
        base_npc_path.write_text(json.dumps(self.base_npc))
        base_roots_path.write_text(json.dumps(self.base_roots))
        (self.candidate / "monster-status.json").write_text(
            json.dumps(
                {
                    "schema": "monster-spell-activation-inventory-v1",
                    "base_revision": "base-1",
                    "activated": False,
                    "summary": {
                        "candidate_pending_execution_validation": 2,
                        "inventory_only": 1,
                    },
                    "monsters": self.monsters,
                }
            )
        )
        self.manifest = {
            "schema": "native-npc-activation-candidate-v1",
            "base_revision": "base-1",
            "activated": False,
            "selected_references": [1, 2],
            "changed_documents": hashes,
            "unchanged_documents": {"spell-effect-trees.json": "class-hash"},
            "base_document_hashes": {
                self.changed_names[0]: finalizer.digest(base_npc_path),
                self.changed_names[1]: finalizer.digest(base_roots_path),
            },
        }
        self.write_manifest()

    def write_manifest(self):
        (self.candidate / "manifest.json").write_text(json.dumps(self.manifest))

    def validated_row(self, ref, levels_and_spells):
        return {
            "ref": ref,
            "status": "validated",
            "pending_initialization": False,
            "ai_commit": {
                "status": "validated",
                "packets": 1,
                "forecast_source_unchanged": True,
                "serializer_failure_rolled_back": True,
            },
            "cases": [
                {
                    "level": level,
                    "spell_id": spell,
                    "status": "validated",
                    "successful_targets": [{"effectful": True}],
                }
                for level, spell in levels_and_spells
            ],
        }

    def make_audit(self, rows=None, selected=None):
        first = [(level, spell) for level in (1, 2) for spell in (101, 102)]
        second = [(1, 201)]
        selected = [1, 2] if selected is None else selected
        rows = (
            [self.validated_row(1, first), self.validated_row(2, second)]
            if rows is None
            else rows
        )
        manifest_raw = (self.candidate / "manifest.json").read_bytes()
        return {
            "schema": "native-npc-activation-validation-v1",
            "candidate_manifest_sha256": self.sha(manifest_raw),
            "changed_document_hashes": dict(self.manifest["changed_documents"]),
            "base_revision": self.manifest["base_revision"],
            "overlay_applied": "npc_candidate",
            "class_tests": {
                "run": 25,
                "successful": True,
                "failures": [],
                "errors": [],
                "skipped": [],
            },
            "sources_stable": True,
            "preview_sources_match_current": True,
            "runtime_code_sha256": {},
            "base_document_hashes": dict(self.manifest["base_document_hashes"]),
            "monsters": rows,
        }

    def write_audit(self):
        self.validation.write_text(json.dumps(self.audit))

    def finalize(self):
        return finalizer.finalize(self.candidate, self.validation, self.output)

    def test_finalizes_all_owned_spells_at_every_level_and_preserves_inventory(self):
        candidate_before = {
            path.name: path.read_bytes()
            for path in self.candidate.iterdir()
            if path.is_file()
        }
        result = self.finalize()

        self.assertEqual(
            result, {"validated": 2, "pending": 0, "total": 3, "activated": False}
        )
        final_manifest = json.loads((self.output / "manifest.json").read_text())
        final_npc = json.loads((self.output / self.changed_names[0]).read_text())
        inventory = json.loads((self.output / "monster-status.json").read_text())
        self.assertTrue(final_manifest["execution_validated"])
        self.assertTrue(final_manifest["class_regressions_passed"])
        self.assertEqual(final_manifest["selected_references"], [1, 2])
        self.assertEqual(final_manifest["evaluated_references"], [1, 2])
        self.assertEqual(final_npc["activation_policy"]["legacy_spell_ids"], [777])
        self.assertEqual(final_npc["baseline_effects"], self.base_npc["effects"])
        self.assertEqual(
            final_npc["activation_policy"]["enabled_monsters"]["900"],
            self.base_npc["activation_policy"]["enabled_monsters"]["900"],
        )
        self.assertEqual(
            set(final_npc["activation_policy"]["enabled_monsters"]), {"1", "2", "900"}
        )
        high = next(row for row in inventory["monsters"] if row["ref"] == 99)
        self.assertEqual(high["activation_status"], "inventory_only")
        self.assertEqual(high["note"], "high-level inventory row")
        self.assertNotIn("99", final_npc["activation_policy"]["enabled_monsters"])
        for name, checksum in final_manifest["changed_documents"].items():
            self.assertEqual(checksum, finalizer.digest(self.output / name))
        self.assertEqual(
            candidate_before,
            {
                path.name: path.read_bytes()
                for path in self.candidate.iterdir()
                if path.is_file()
            },
        )

    def test_inventory_must_be_unique_complete_and_match_hashed_policy_metadata(self):
        inventory_path = self.candidate / "monster-status.json"
        cases = [
            (
                "missing-selected-ref",
                "Inventory must contain",
                lambda rows: rows.pop(1),
            ),
            (
                "duplicate-ref",
                "Inventory must contain",
                lambda rows: rows.append(dict(rows[0])),
            ),
            (
                "reduced-spell-ownership",
                "Inventory differs",
                lambda rows: rows[0].update(spell_ids=[101]),
            ),
            (
                "reduced-native-level-range",
                "Inventory differs",
                lambda rows: rows[0].update(max_level=1),
            ),
        ]
        for label, error, mutate in cases:
            with self.subTest(label=label):
                inventory_path.write_text(
                    json.dumps(
                        {
                            "schema": "monster-spell-activation-inventory-v1",
                            "base_revision": "base-1",
                            "activated": False,
                            "summary": {
                                "candidate_pending_execution_validation": 2,
                                "inventory_only": 1,
                            },
                            "monsters": json.loads(json.dumps(self.monsters)),
                        }
                    )
                )
                inventory = json.loads(inventory_path.read_text())
                mutate(inventory["monsters"])
                inventory_path.write_text(json.dumps(inventory))
                self.output = self.root / ("final-inventory-" + label)
                with self.assertRaisesRegex(ValueError, error):
                    self.finalize()
        self.output = self.root / "final"

    def test_pending_selected_reference_is_removed_but_previous_enabled_entry_survives(
        self,
    ):
        self.audit["monsters"][1]["status"] = "pending"
        self.audit["monsters"][1]["cases"] = []
        self.write_audit()

        result = self.finalize()
        policy = json.loads((self.output / self.changed_names[0]).read_text())[
            "activation_policy"
        ]
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(result["validated"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(manifest["selected_references"], [1])
        self.assertEqual(manifest["evaluated_references"], [1, 2])
        self.assertEqual(set(policy["enabled_monsters"]), {"1", "900"})
        self.assertEqual(policy["legacy_spell_ids"], [777])

    def test_all_selected_cohort_requires_exactly_one_audit_row_per_reference(self):
        selected = list(range(1, 70))
        self.manifest["selected_references"] = selected
        self.write_manifest()
        self.audit = self.make_audit(
            rows=[{"ref": ref, "cases": []} for ref in selected[:-1]]
        )
        self.audit["candidate_manifest_sha256"] = finalizer.digest(
            self.candidate / "manifest.json"
        )
        self.audit["changed_document_hashes"] = dict(self.manifest["changed_documents"])
        self.audit["base_revision"] = self.manifest["base_revision"]
        self.write_audit()
        with self.assertRaisesRegex(ValueError, "full selected cohort"):
            self.finalize()

        for rows in (
            [{"ref": ref, "cases": []} for ref in selected] + [{"ref": 1, "cases": []}],
            [{"ref": ref, "cases": []} for ref in selected[:-1]]
            + [{"ref": 68, "cases": []}],
            [{"ref": ref, "cases": []} for ref in selected[:-1]]
            + [{"ref": 100, "cases": []}],
        ):
            with self.subTest(row_count=len(rows), final_ref=rows[-1]["ref"]):
                self.audit["monsters"] = rows
                self.write_audit()
                with self.assertRaisesRegex(ValueError, "full selected cohort"):
                    self.finalize()

    def test_every_owned_spell_and_native_level_needs_effectful_validation(self):
        baseline = self.audit["monsters"]
        expected = [(level, spell) for level in (1, 2) for spell in (101, 102)]
        for missing in expected:
            with self.subTest(missing=missing):
                self.audit["monsters"] = [
                    self.validated_row(
                        1, [case for case in expected if case != missing]
                    ),
                    baseline[1],
                ]
                self.write_audit()
                self.output = self.root / (
                    "final-" + str(missing[0]) + "-" + str(missing[1])
                )
                result = self.finalize()
                manifest = json.loads((self.output / "manifest.json").read_text())
                self.assertEqual(result["validated"], 1)
                self.assertEqual(manifest["selected_references"], [2])
        self.output = self.root / "final"

    def test_duplicate_or_pending_spell_level_case_does_not_validate_reference(self):
        expected = [(level, spell) for level in (1, 2) for spell in (101, 102)]
        invalid_cases = [
            ("duplicate", [*expected[:-1], expected[0]]),
            ("pending-case", expected),
        ]
        for label, cases in invalid_cases:
            with self.subTest(label=label):
                row = self.validated_row(1, cases)
                if label == "pending-case":
                    row["cases"][0]["status"] = "pending"
                self.audit["monsters"] = [row, self.validated_row(2, [(1, 201)])]
                self.write_audit()
                self.output = self.root / ("final-case-" + label)
                result = self.finalize()
                manifest = json.loads((self.output / "manifest.json").read_text())
                self.assertEqual(result["validated"], 1)
                self.assertEqual(manifest["selected_references"], [2])
        self.output = self.root / "final"

    def test_effectless_or_pending_initialization_reference_never_enables(self):
        invalidations = [
            (
                "effectless",
                lambda row: row["cases"][0].update(
                    successful_targets=[{"effectful": False}]
                ),
            ),
            (
                "pending-initialization",
                lambda row: row.update(pending_initialization=True),
            ),
        ]
        for label, invalidate in invalidations:
            with self.subTest(label=label):
                self.audit["monsters"] = [
                    self.validated_row(
                        1, [(level, spell) for level in (1, 2) for spell in (101, 102)]
                    ),
                    self.validated_row(2, [(1, 201)]),
                ]
                invalidate(self.audit["monsters"][1])
                self.write_audit()
                self.output = self.root / ("final-" + label)
                result = self.finalize()
                npc = json.loads((self.output / self.changed_names[0]).read_text())
                self.assertEqual(result["validated"], 1)
                self.assertEqual(
                    set(npc["activation_policy"]["enabled_monsters"]), {"1", "900"}
                )
        self.output = self.root / "final"

    def test_ai_commit_proof_is_required_for_each_enabled_reference(self):
        failures = [
            ("missing", lambda row: row.pop("ai_commit")),
            ("failed", lambda row: row["ai_commit"].update(status="failed")),
            ("no-packets", lambda row: row["ai_commit"].update(packets=0)),
            (
                "forecast-mutated",
                lambda row: row["ai_commit"].update(forecast_source_unchanged=False),
            ),
            (
                "rollback-failed",
                lambda row: row["ai_commit"].update(
                    serializer_failure_rolled_back=False
                ),
            ),
        ]
        for label, invalidate in failures:
            with self.subTest(label=label):
                self.audit["monsters"] = [
                    self.validated_row(
                        1, [(level, spell) for level in (1, 2) for spell in (101, 102)]
                    ),
                    self.validated_row(2, [(1, 201)]),
                ]
                invalidate(self.audit["monsters"][1])
                self.write_audit()
                self.output = self.root / ("final-commit-" + label)
                result = self.finalize()
                npc = json.loads((self.output / self.changed_names[0]).read_text())
                self.assertEqual(result["validated"], 1)
                self.assertEqual(
                    set(npc["activation_policy"]["enabled_monsters"]), {"1", "900"}
                )
        self.output = self.root / "final"

    def test_class_regression_failures_errors_skips_or_empty_run_reject(self):
        cases = [
            {
                "run": 5,
                "successful": False,
                "failures": [],
                "errors": [],
                "skipped": [],
            },
            {
                "run": 5,
                "successful": True,
                "failures": ["failed"],
                "errors": [],
                "skipped": [],
            },
            {
                "run": 5,
                "successful": True,
                "failures": [],
                "errors": ["error"],
                "skipped": [],
            },
            {
                "run": 5,
                "successful": True,
                "failures": [],
                "errors": [],
                "skipped": ["skipped"],
            },
            {"run": 0, "successful": True, "failures": [], "errors": [], "skipped": []},
        ]
        for class_tests in cases:
            with self.subTest(class_tests=class_tests):
                self.audit["class_tests"] = class_tests
                self.write_audit()
                with self.assertRaisesRegex(
                    ValueError, "Complete passing class regressions"
                ):
                    self.finalize()
                self.output = self.root / (
                    "final-classes-" + str(cases.index(class_tests))
                )
        self.output = self.root / "final"

    def test_stale_manifest_document_or_base_attestations_are_rejected(self):
        original = dict(self.audit)
        mutations = [
            ("candidate_manifest_sha256", "0" * 64),
            (
                "changed_document_hashes",
                {
                    **self.audit["changed_document_hashes"],
                    self.changed_names[0]: "0" * 64,
                },
            ),
            ("base_revision", "stale-base"),
        ]
        for index, (field, value) in enumerate(mutations):
            with self.subTest(field=field):
                self.audit = dict(original)
                self.audit[field] = value
                self.write_audit()
                with self.assertRaisesRegex(ValueError, "does not attest"):
                    self.finalize()
                self.output = self.root / ("final-stale-" + str(index))
        self.output = self.root / "final"

    def test_unstable_runtime_sources_are_rejected(self):
        self.audit["sources_stable"] = False
        self.write_audit()
        with self.assertRaisesRegex(ValueError, "stable tested runtime sources"):
            self.finalize()

    def test_preview_sources_must_match_current_and_runtime_hashes_are_checked(self):
        self.audit["preview_sources_match_current"] = False
        self.write_audit()
        with self.assertRaisesRegex(ValueError, "currently tested runtime sources"):
            self.finalize()
        self.audit["preview_sources_match_current"] = True
        self.audit["runtime_code_sha256"] = {"AGENTS.md": "stale-runtime-hash"}
        self.write_audit()
        with self.assertRaisesRegex(ValueError, "Tested runtime source changed"):
            self.finalize()

    def test_candidate_document_changed_after_audit_is_rejected(self):
        path = self.candidate / self.changed_names[0]
        changed = json.loads(path.read_text())
        changed["tampered"] = True
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "changed after validation"):
            self.finalize()

    def test_previous_npc_policy_snapshot_is_hash_pinned(self):
        base_path = self.candidate / ("base-" + self.changed_names[0])
        tampered = json.loads(base_path.read_text())
        tampered["activation_policy"]["enabled_monsters"]["2"] = {
            "min_level": 1,
            "max_level": 1,
            "spell_ids": [201],
        }
        base_path.write_text(json.dumps(tampered))
        with self.assertRaisesRegex(ValueError, "Previous NPC policy differs"):
            self.finalize()

    def test_candidate_cannot_change_preserved_baseline_effects(self):
        npc_path = self.candidate / self.changed_names[0]
        npc = json.loads(npc_path.read_text())
        npc["baseline_effects"]["old-effect"]["parameters"] = [99]
        npc_path.write_text(json.dumps(npc, separators=(",", ":")))
        self.manifest["changed_documents"][self.changed_names[0]] = finalizer.digest(
            npc_path
        )
        self.write_manifest()
        self.audit["candidate_manifest_sha256"] = finalizer.digest(
            self.candidate / "manifest.json"
        )
        self.audit["changed_document_hashes"] = dict(self.manifest["changed_documents"])
        self.write_audit()
        with self.assertRaisesRegex(ValueError, "Preserved NPC baseline effects"):
            self.finalize()


if __name__ == "__main__":
    unittest.main()
