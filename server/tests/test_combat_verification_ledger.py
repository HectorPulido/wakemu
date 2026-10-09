"""Evidence classifications must not inflate incomplete spell verification."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "tools/build_combat_verification_ledger.py"
SPEC = importlib.util.spec_from_file_location("combat_verification_ledger", PATH)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)

NOW = "2026-10-07T12:00:00+00:00"


class VerificationLedgerTests(unittest.TestCase):
    def inventory(self):
        return {
            "sources_sha256": {"server/protocol/spells.json": "abc"},
            "spells": [
                {
                    "id": 100,
                    "breed": 1,
                    "kind": "active",
                    "unlock_level": 1,
                    "families": [304],
                    "states": [4],
                }
            ],
        }

    def report(self, rows):
        return {
            "generated_at": NOW,
            "sources_stable": True,
            "provenance": {"spells.json": "abc"},
            "rows": rows,
        }

    def build(self, rows, **kwargs):
        return ledger.build_ledger(
            self.inventory(),
            [("active.json", self.report(rows))],
            reference_time=NOW,
            **kwargs
        )

    def test_every_spell_is_kept_without_a_scenario_or_gameplay_claim(self):
        inventory = self.inventory()
        inventory["spells"][0]["game_verified"] = True
        result = ledger.build_ledger(inventory, reference_time=NOW)
        row = result["spells"][0]
        self.assertTrue(row["catalog_imported"])
        self.assertTrue(row["missing_scenarios"])
        self.assertEqual(len(row["planned_cases"]), 12)
        self.assertFalse(row["semantic_verified"])
        self.assertFalse(row["client_verified"])
        self.assertTrue(
            all(c["status"] == "pending" for c in row["contracts"].values())
        )
        self.assertEqual(
            row["contracts"]["summon_lifecycle"]["applicability"], "unknown"
        )

    def test_no_effect_and_rejection_cannot_pass_even_with_claimed_checks(self):
        checks = [
            {
                "contract": name,
                "authority": "semantic",
                "evidence_id": "probe",
                "passed": True,
                "expected": 1,
                "actual": 1,
            }
            for name in ledger.CONTRACTS
        ]
        for status in ("no_effect", "accepted_no_effect", "cast_rejected", "cost_only"):
            with self.subTest(status=status):
                row = self.build(
                    [{"spell_id": 100, "status": status, "contract_checks": checks}]
                )["spells"][0]
                self.assertFalse(row["offline_execution"])
                self.assertFalse(row["semantic_verified"])
                self.assertEqual(row["status"], "pending")
                self.assertTrue(
                    all(c["status"] == "pending" for c in row["contracts"].values())
                )

    def test_execution_is_not_semantic_verification_and_ready_is_not_spell_evidence(
        self,
    ):
        result = self.build(
            [
                {"spell_id": 100, "status": "actor_state_changed"},
                {"breed": 1, "status": "passed", "level": 1},
            ]
        )
        row = result["spells"][0]
        self.assertTrue(row["offline_execution"])
        self.assertFalse(row["semantic_verified"])
        self.assertEqual(len(row["observed_cases"]), 1)

    def test_stale_hashes_changed_sources_or_missing_manifest_downgrade_evidence(self):
        original = self.report([{"spell_id": 100, "status": "executed"}])
        for mutation in (
            {"provenance": {"spells.json": "old"}},
            {"sources_stable": False},
            {"provenance": {}},
            {
                "sources_before": {"spells.json": "abc"},
                "sources_after": {"spells.json": "changed"},
            },
        ):
            report = dict(original, **mutation)
            result = ledger.build_ledger(
                self.inventory(), [("old.json", report)], reference_time=NOW
            )
            self.assertFalse(result["reports"][0]["freshness"]["eligible"])
            self.assertFalse(result["spells"][0]["offline_execution"])

    def test_age_is_informational_unless_caller_sets_an_explicit_policy(self):
        report = self.report([{"spell_id": 100, "status": "executed"}])
        report["generated_at"] = "2026-01-01T00:00:00+00:00"
        default = ledger.build_ledger(
            self.inventory(), [("old.json", report)], reference_time=NOW
        )
        cutoff = ledger.build_ledger(
            self.inventory(),
            [("old.json", report)],
            reference_time=NOW,
            max_age_hours=24,
        )
        self.assertTrue(default["spells"][0]["offline_execution"])
        self.assertFalse(cutoff["spells"][0]["offline_execution"])
        self.assertIn("stale_report", cutoff["reports"][0]["freshness"]["reasons"])

    def test_extra_deduplication_preserves_all_18_classes_and_multiple_owners(self):
        breeds = list(range(1, 17)) + [18, 19]
        inventory = {
            "spells": [{"id": 100 + b, "breed": b} for b in breeds],
            "extra_spells": [{"id": 900, "breeds": [1, 19], "tree_exported": True}],
        }
        extras = {
            "extras": [
                {"id": 900, "links": [{"breed": 2}]},
                {"id": 101, "links": [{"breed": 3}]},
            ]
        }
        result = ledger.build_ledger(inventory, extras=extras, reference_time=NOW)
        self.assertEqual(result["summary"]["breed_count"], 18)
        self.assertEqual(result["summary"]["class_spells"], 18)
        self.assertEqual(result["summary"]["extra_spells"], 1)
        extra = next(r for r in result["spells"] if r["spell_id"] == 900)
        self.assertEqual(extra["breeds"], [1, 2, 19])
        self.assertTrue(extra["catalog_imported"])

    def test_partial_or_mismatching_contract_checks_do_not_certify_whole_spell(self):
        row = self.build(
            [
                {
                    "spell_id": 100,
                    "breed": 1,
                    "level": 1,
                    "variant": "enemy",
                    "status": "executed",
                    "contract_checks": [
                        {
                            "contract": "effects",
                            "authority": "semantic",
                            "evidence_id": "damage",
                            "passed": True,
                            "expected": 10,
                            "actual": 10,
                        },
                        {
                            "contract": "resources",
                            "authority": "semantic",
                            "evidence_id": "ap",
                            "passed": True,
                            "expected": 4,
                            "actual": 3,
                        },
                    ],
                }
            ]
        )["spells"][0]
        self.assertEqual(row["contracts"]["effects"]["status"], "passed")
        self.assertEqual(row["contracts"]["resources"]["status"], "pending")
        self.assertFalse(row["semantic_verified"])
        self.assertTrue(all(p["status"] == "pending" for p in row["planned_cases"]))

    def test_complete_one_scenario_does_not_certify_missing_planned_scenarios(self):
        checks = [
            {
                "contract": name,
                "authority": "semantic",
                "evidence_id": name,
                "passed": True,
                "expected": 1,
                "actual": 1,
            }
            for name in ledger.CONTRACTS
        ]
        row = self.build(
            [
                {
                    "spell_id": 100,
                    "breed": 1,
                    "level": 1,
                    "variant": "enemy",
                    "status": "executed",
                    "contract_checks": checks,
                }
            ]
        )["spells"][0]
        self.assertFalse(row["semantic_verified"])
        self.assertEqual(
            sum(p["status"] == "semantic_verified" for p in row["planned_cases"]), 1
        )

    def test_backlog_groups_shared_failures_across_classes_and_is_deterministic(self):
        inventory = self.inventory()
        inventory["spells"].append({"id": 200, "breed": 2})
        report = self.report(
            [
                {
                    "spell_id": sid,
                    "status": "cast_rejected",
                    "reason": "Missing native effect definition: reference=" + str(sid),
                }
                for sid in (100, 200)
            ]
        )
        first = ledger.build_ledger(
            inventory, [("active.json", report)], reference_time=NOW
        )
        second = ledger.build_ledger(
            inventory, [("active.json", report)], reference_time=NOW
        )
        self.assertEqual(
            json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
        )
        self.assertEqual(
            first["shared_system_backlog"][0]["affected_spell_ids"], [100, 200]
        )
        self.assertEqual(first["shared_system_backlog"][0]["breeds"], [1, 2])

    def test_current_source_resolution_verifies_additional_sources_and_rejects_collision(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            combat = root / "server/wakfu_server/combat/runtime.py"
            combat.parent.mkdir(parents=True)
            combat.write_text("actual runtime source")
            report = self.report([])
            report["sources_before"] = {"runtime.py": "old"}
            current, resolved = ledger.current_report_hashes(
                [("active.json", report)], root
            )
            self.assertIn("runtime.py", current)
            self.assertEqual(
                resolved[0]["path"], "server/wakfu_server/combat/runtime.py"
            )
            report["sources_before"]["runtime.py"] = current["runtime.py"]
            report["sources_after"] = report["sources_before"]
            hashes = dict(self.inventory()["sources_sha256"], **current)
            self.assertTrue(ledger.report_freshness(report, hashes, NOW)["eligible"])
            other = root / "server/tools/runtime.py"
            other.parent.mkdir(parents=True)
            other.write_text("another source")
            self.assertIsNone(ledger.resolve_report_source("runtime.py", root))
            self.assertIsNone(ledger.resolve_report_source("../outside.py", root))
            self.assertEqual(
                ledger.resolve_report_source(
                    "server/wakfu_server/combat/runtime.py", root
                ),
                combat.resolve(),
            )

    def test_passives_plan_events_and_unknown_cast_contracts(self):
        inventory = self.inventory()
        inventory["spells"][0]["kind"] = "passive"
        row = ledger.build_ledger(inventory, reference_time=NOW)["spells"][0]
        self.assertEqual(row["contracts"]["range"]["applicability"], "unknown")
        self.assertEqual(row["contracts"]["resources"]["applicability"], "unknown")
        self.assertEqual(
            {p["target"] for p in row["planned_cases"]},
            {"installation", "activation", "removal", "turn_boundary"},
        )
        self.assertEqual({p["branch"] for p in row["planned_cases"]}, {"event"})

    def test_grouping_removes_leaf_ids_and_preserves_unsupported_predicate(self):
        self.assertEqual(
            ledger.shared_cause({"reason": "Missing native state 11"}),
            ledger.shared_cause({"reason": "Missing native state 22"}),
        )
        self.assertEqual(
            ledger.shared_cause({"reason": "Unsupported native criterion: GetFoo(11)"}),
            "Unsupported native criterion: GetFoo",
        )
        self.assertEqual(
            ledger.shared_cause({"reason": "No handler for native effect class 1038"}),
            "No handler for native effect class 1038",
        )

    def test_client_pass_claim_requires_matching_request_acceptance_and_delivery(self):
        checks = [
            {
                "contract": name,
                "authority": "client",
                "evidence_id": name,
                "passed": True,
                "expected": 1,
                "actual": 1,
            }
            for name in ledger.CONTRACTS
        ]
        case = {
            "spell_id": 100,
            "status": "PASS",
            "contract_checks": checks,
            "evidence_scope": "actual client GUI, no simulation or packet injection",
        }
        observed = self.build([case])["spells"][0]
        self.assertTrue(
            all(c["status"] == "pending" for c in observed["contracts"].values())
        )
        expected = {"spell_id": 100, "actor_id": 7, "target": [1, 0, 0]}
        case.update(
            expected=expected,
            requests=[dict(expected, opcode=13260)],
            received_client_update=True,
            server={"status": "completed", "rejections": []},
        )
        self.assertTrue(ledger.client_chain_present(case))
        case["requests"][0]["spell_id"] = 999
        self.assertFalse(ledger.client_chain_present(case))

    def test_passive_id_maps_installation_cycle_and_activation_without_cast_or_semantic_pass(
        self,
    ):
        inventory = self.inventory()
        inventory["spells"][0]["kind"] = "passive"
        inventory["spells"].append({"id": 200, "breed": 2, "kind": "passive"})
        report = self.report(
            [
                {
                    "passive_id": 100,
                    "breed": 1,
                    "level": 1,
                    "status": "cycle_observed",
                    "installed": True,
                    "activation_observed": True,
                    "trace_complete": True,
                    "stages": [
                        {
                            "stage": "own_end",
                            "status": "completed",
                            "activated_effects": [
                                {"effect_reference": 10, "effect_class": 349}
                            ],
                        }
                    ],
                },
                {
                    "passive_id": 200,
                    "breed": 2,
                    "level": 1,
                    "status": "blocked",
                    "installed": True,
                    "reason": "Unsupported native predicate: IsOnBorderCell",
                },
            ]
        )
        result = ledger.build_ledger(
            inventory, [("passive.json", report)], reference_time=NOW
        )
        row = result["spells"][0]
        self.assertTrue(row["passive_observations"]["installed"])
        self.assertTrue(row["passive_observations"]["cycle_observed"])
        self.assertTrue(row["passive_observations"]["activation_observed"])
        self.assertFalse(row["offline_execution"])
        self.assertFalse(row["semantic_verified"])
        self.assertEqual(row["status"], "pending")
        self.assertEqual(
            row["observed_cases"][0]["event_stages"][0]["stage"], "own_end"
        )
        self.assertEqual(result["summary"]["offline_execution"], 0)
        self.assertEqual(result["summary"]["passive_cycle_observed"], 1)
        self.assertEqual(
            result["shared_system_backlog"][0]["affected_spell_ids"], [200]
        )


if __name__ == "__main__":
    unittest.main()
