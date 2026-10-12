"""Screening reports never substitute for full qualification evidence."""
import copy
import unittest
from reconcile_monster_offline_reports import classify_row, context_reasons, reconcile


class OfflineReportReconciliationTests(unittest.TestCase):
    def fixture(self):
        authority = dict(
            min_level=1, max_level=2, spell_ids=[7], initial_state_triples=[]
        )
        cases = [
            dict(
                level=level,
                spell_id=7,
                status="validated",
                successful_targets=[{"effectful": True}],
            )
            for level in (1, 2)
        ]
        row = dict(
            ref=1,
            status="validated",
            pending_initialization=False,
            cases=cases,
            ai_commit=dict(
                status="validated",
                packets=1,
                forecast_source_unchanged=True,
                serializer_failure_rolled_back=True,
            ),
        )
        return row, authority

    def test_complete_full_native_row_is_screening_only(self):
        row, authority = self.fixture()
        self.assertEqual(
            classify_row(row, authority, lambda *args: True, lambda case: False),
            ("screening_pass_pending_final_gates", []),
        )

    def test_completed_status_cannot_replace_missing_cases_or_ai_proof(self):
        row, authority = self.fixture()
        row["cases"] = row["cases"][:1]
        row.pop("ai_commit")
        status, reasons = classify_row(
            row, authority, lambda *args: True, lambda case: False
        )
        self.assertEqual(status, "pending_local_validation")
        self.assertIn("incomplete_full_native_owned_spell_cases", reasons)
        self.assertIn("missing_ai_commit_delivery_proof", reasons)

    def test_actual_failed_case_preserves_exact_errors(self):
        row, authority = self.fixture()
        row["cases"][0].update(status="pending", errors={"criterion false": 3})
        status, reasons = classify_row(
            row, authority, lambda *args: True, lambda case: False
        )
        self.assertEqual(status, "blocked_local_execution")
        self.assertEqual(reasons[0]["errors"], {"criterion false": 3})

    def test_forged_constructor_and_passive_boolean_fail_closed(self):
        row, authority = self.fixture()
        authority["initial_state_triples"] = [2, -1, 0]
        row["cases"][0]["status"] = "passive_initialization_only"
        status, reasons = classify_row(
            row, authority, lambda *args: False, lambda case: False
        )
        self.assertEqual(status, "pending_local_validation")
        self.assertIn("missing_native_constructor_proof", reasons)
        self.assertIn("passive_source_proof_missing", reasons)

    def test_stale_or_cross_candidate_context_is_pending(self):
        manifest = dict(
            base_revision="new",
            changed_documents={},
            base_document_hashes={},
            unchanged_documents={},
        )
        reasons = context_reasons(
            {"candidate_manifest_sha256": "old"},
            {},
            manifest,
            "current",
            {"source": "hash"},
        )
        self.assertIn("candidate_context_mismatch", reasons)
        self.assertIn("missing_or_stale_runtime_source_proof", reasons)
        self.assertIn("missing_or_failed_offline_catalog_context", reasons)

    def test_exact_scope_exclusions_preserved_and_no_receipts_never_pass(self):
        refs = list(range(1, 1811)) + [3174, 3976, 3980, 3981, 3982, 3983, 3984]
        rows = [
            dict(
                ref=ref,
                min_level=0 if ref <= 42 else 1,
                max_level=2,
                spell_ids=[7],
                status="exception" if ref <= 42 or ref >= 3174 else "pending",
                blocker="original",
            )
            for ref in refs
        ]
        selected = [row["ref"] for row in rows if row["status"] == "pending"]
        policy = {str(row["ref"]): row for row in rows if row["ref"] in selected}
        result = reconcile(
            {"monsters": rows},
            {"monsters": rows},
            {"selected_references": selected},
            "hash",
            policy,
            [],
            {},
            lambda *args: False,
        )
        self.assertEqual(
            sum(row["status"] == "exception" for row in result["monsters"]), 49
        )
        self.assertEqual(
            sum(
                row["status"] == "pending_local_validation"
                for row in result["monsters"]
            ),
            1768,
        )
        self.assertFalse(
            any(row["qualification_verified"] for row in result["monsters"])
        )
        self.assertEqual(rows[0]["blocker"], "original")

    def test_valid_catalog_context_requires_current_source_and_native_receipts(self):
        manifest = dict(
            base_revision="revision",
            changed_documents={"npc": "candidate"},
            base_document_hashes={"npc": "baseline"},
            unchanged_documents={"states": "statehash"},
        )
        report = dict(
            schema="native-npc-activation-validation-v1",
            candidate_manifest_sha256="manifest",
            base_revision="revision",
            changed_document_hashes=manifest["changed_documents"],
            base_document_hashes=manifest["base_document_hashes"],
            overlay_applied="npc_candidate",
            runtime_code_sha256={"source": "current"},
            sources_stable=True,
            preview_sources_match_current=True,
            native_monsters_stable=True,
            native_monsters_sha256="native",
        )
        wrapper = dict(
            status="validator_completed",
            catalog=dict(
                schema="offline-monster-catalog-consumption-v1",
                manifest_sha256="manifest",
                base_revision="revision",
                authority="declared_offline_candidate_base_not_active_database",
                verified_documents={"npc": {"sha256": "baseline"}},
                failed_reads=[],
            ),
        )
        self.assertEqual(
            context_reasons(
                report, wrapper, manifest, "manifest", {"source": "current"}
            ),
            [],
        )
        wrapper["catalog"]["verified_documents"]["npc"]["sha256"] = "forged"
        self.assertIn(
            "offline_catalog_seal_mismatch",
            context_reasons(
                report, wrapper, manifest, "manifest", {"source": "current"}
            ),
        )

    def test_duplicate_case_cannot_replace_other_native_level(self):
        row, authority = self.fixture()
        row["cases"][1] = copy.deepcopy(row["cases"][0])
        status, reasons = classify_row(
            row, authority, lambda *args: True, lambda case: False
        )
        self.assertEqual(status, "pending_local_validation")
        self.assertIn("incomplete_full_native_owned_spell_cases", reasons)

    def test_no_attempt_pending_case_is_missing_evidence_not_runtime_failure(self):
        row, authority = self.fixture()
        row["cases"][0].update(status="pending", attempts=0, errors={})
        status, reasons = classify_row(
            row, authority, lambda *args: True, lambda case: False
        )
        self.assertEqual(status, "pending_local_validation")
        self.assertIn("missing_case_execution_receipt", reasons)

    def test_batch_catalog_receipt_cannot_be_reused_for_another_report(self):
        from reconcile_monster_offline_reports import catalog_reference_binding

        self.assertTrue(
            catalog_reference_binding(
                {"monsters": [{"ref": 1}, {"ref": 2}]}, {"reference": "batch-1-2"}
            )
        )
        self.assertFalse(
            catalog_reference_binding(
                {"monsters": [{"ref": 1}, {"ref": 3}]}, {"reference": "batch-1-2"}
            )
        )
        self.assertFalse(catalog_reference_binding({"monsters": [{"ref": 1}]}, {}))
