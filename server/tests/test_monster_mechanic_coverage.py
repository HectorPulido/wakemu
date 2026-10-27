"""Coverage promotion and source-bound proposal regressions; no game runtime."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_monster_mechanic_coverage import (
    BRIZLON_REFERENCES,
    COMPONENT_CHECKS,
    DURABLE_CHECKS,
    ENCOUNTER_CHECKS,
    brizlon_evidence,
    build_matrix,
    qualified_level,
    source_strategy_references,
    streamed_fact_rows,
    witness_plan,
    fact_catalog_revision,
    read_small,
)

REVISION = "a" * 64


def row(
    reference,
    rule="direct_player_attack_geometry_or_team_condition",
    classification="player_or_native",
):
    return dict(
        reference=reference,
        rule=rule,
        classification=classification,
        name=str(reference),
    )


def sample():
    owned = [
        row(7),
        row(8, "only_optional_owned_protection"),
        row(9, "native_passive_321_or_exact_421_removal_route"),
        row(4251, "morph_missing", "engine_content_issue"),
        row(4280, "morph_missing", "engine_content_issue"),
        row(3510, "scene_missing", "engine_content_issue"),
        row(5482, "admin", "intentional_noncombat"),
    ]
    return dict(rows=owned), dict(
        rows=[dict(reference=ref, group="scene") for ref in (4251, 4280, 3510)]
    )


def proof(reference, scope="native_component", checks=COMPONENT_CHECKS):
    return dict(
        schema="monster-mechanic-qualification-v1",
        reference=reference,
        passed=True,
        gifts=False,
        backend="jondo",
        catalog_revision=REVISION,
        scope=scope,
        checks={key: True for key in checks},
        source_receipt="unit-fixture.json",
        source_receipt_sha256="c" * 64,
    )


class MechanicCoverageTests(unittest.TestCase):
    def matrix(self, *, evidence=(), previews=(), frameworks=()):
        ownership, integration = sample()
        return build_matrix(
            ownership,
            integration,
            strategy_references=BRIZLON_REFERENCES,
            evidence=evidence,
            preview_documents=previews,
            frameworks=frameworks,
            catalog_revision=REVISION,
        )

    def test_source_strategy_framework_and_recipe_do_not_close_an_encounter(self):
        result = self.matrix(frameworks=(3510,))
        self.assertEqual(result["summary"]["active_references"], 6)
        self.assertEqual(
            result["summary"]["source_work_allocation"],
            dict(normal_jondo=3, specific_source=2, integration_work=1),
        )
        self.assertEqual(result["summary"]["proposed_recipes"], 3)
        self.assertEqual(result["summary"]["post_brizlon_backlog"], 1)
        self.assertEqual(result["summary"]["post_brizlon_remaining"], 1)
        self.assertTrue(
            next(r for r in result["rows"] if r["reference"] == 3510)[
                "framework_available"
            ]
        )
        self.assertTrue(
            all(
                r["evidence_level"] == "S0" and not r["case_closed"]
                for r in result["rows"]
            )
        )
        self.assertTrue(all(not r["executed"] for r in result["proposed_recipes"]))

    def test_paid_component_does_not_close_pair_or_post_pair_cases(self):
        result = self.matrix(evidence=[proof(4251)])
        target = next(r for r in result["rows"] if r["reference"] == 4251)
        self.assertTrue(target["earned_component_passed"])
        self.assertFalse(target["complete_encounter_passed"])
        self.assertFalse(target["case_closed"])
        self.assertIsNone(target["deployed"])
        self.assertEqual(result["summary"]["post_brizlon_closed"], 0)

    def test_complete_encounter_is_separate_from_durable_closure(self):
        result = self.matrix(
            evidence=[proof(3510, "complete_encounter", ENCOUNTER_CHECKS)]
        )
        target = result["post_brizlon_closure"][0]
        self.assertTrue(target["complete_encounter_passed"])
        self.assertFalse(target["case_closed"])
        self.assertEqual(result["summary"]["post_brizlon_remaining"], 1)
        closed = self.matrix(
            evidence=[proof(3510, "durable_encounter", DURABLE_CHECKS)]
        )
        self.assertEqual(closed["summary"]["post_brizlon_closed"], 1)
        self.assertEqual(closed["summary"]["post_brizlon_remaining"], 0)
        self.assertTrue(all(r["deployed"] is None for r in closed["rows"]))

    def test_gifts_missing_failure_branch_and_wrong_revision_cannot_promote(self):
        gifted = proof(3510)
        gifted["gifts"] = True
        incomplete = proof(3510, "complete_encounter", COMPONENT_CHECKS)
        wrong_revision = proof(3510)
        wrong_revision["catalog_revision"] = "b" * 64
        result = self.matrix(evidence=[gifted, incomplete, wrong_revision])
        self.assertEqual(len(result["rejected_evidence"]), 3)
        self.assertTrue(all(r["evidence_level"] == "S0" for r in result["rows"]))

    def test_validated_spell_preview_is_s1_not_earned_mechanic(self):
        document = dict(
            schema="native-npc-activation-validation-v1",
            catalog_revision=REVISION,
            monsters=[
                dict(
                    ref=7,
                    status="validated",
                    cases=[
                        dict(
                            spell_id=99,
                            status="validated",
                            successful_targets=[
                                dict(
                                    effectful=True, native_preview_source_unchanged=True
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        result = self.matrix(previews=[document])
        target = next(r for r in result["rows"] if r["reference"] == 7)
        self.assertEqual(target["evidence_level"], "S1")
        self.assertFalse(target["earned_component_passed"])
        del document["catalog_revision"]
        legacy = self.matrix(previews=[document])
        self.assertEqual(
            next(r for r in legacy["rows"] if r["reference"] == 7)["evidence_level"],
            "S0",
        )
        self.assertEqual(len(legacy["rejected_evidence"]), 1)

    def test_unknown_duplicate_and_admin_evidence_are_rejected(self):
        for reference in (99999, 5482):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.matrix(evidence=[proof(reference)])
        ownership, integration = sample()
        ownership["rows"].append(deepcopy(ownership["rows"][0]))
        with self.assertRaises(ValueError):
            build_matrix(ownership, integration, strategy_references=BRIZLON_REFERENCES)

    def test_source_removal_recipe_preserves_exact_guard_and_unknown_producer(self):
        fact = dict(
            reference=9,
            initial_states=[10],
            owned_spells=[7527],
            protection=[],
            protected_state_removals=[
                dict(
                    source="innate",
                    effect_id=31,
                    family=321,
                    path=["state:10", "effect:31"],
                    criteria=['HasState(12, "caster")'],
                    listeners=[dict(effect=30, masks=[None] * 5 + [[10016], None])],
                )
            ],
            protected_effect_dispels=[],
            innate=dict(missing=[]),
            owned=dict(missing=[]),
        )
        original = deepcopy(fact)
        recipe = witness_plan(
            row(9, "native_passive_321_or_exact_421_removal_route"), fact
        )
        self.assertEqual(recipe["removal_candidates"][0]["effect_id"], 31)
        self.assertEqual(
            recipe["removal_candidates"][0]["criteria"], ['HasState(12, "caster")']
        )
        self.assertEqual(recipe["unknown_event_producers"], [10016])
        self.assertIn("actual_native_event_producer", recipe["missing_bindings"])
        self.assertFalse(recipe["executable_without_scene_binding"])
        self.assertEqual(fact, original)
        self.assertFalse(
            any(step["operation"].startswith("assign_") for step in recipe["steps"])
        )

    def test_existing_native_preparations_are_reused_without_executing_them(self):
        recipe = witness_plan(
            row(5361, "only_optional_owned_protection"),
            dict(reference=5361, owned_spells=[7527]),
        )
        preparation = recipe["existing_preparations"][0]
        self.assertEqual(preparation["recipe"]["opponent"]["reference"], 1987)
        self.assertEqual(preparation["recipe"]["required_opponent_states"], [7318])
        self.assertFalse(preparation["validated"])

    def test_literal_source_declarations_are_not_treated_as_native_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "profiles.cs"
            p.write_text(
                "References => new[] { 7 };\nReferences { get; } = new[] { 4251, 4280 };"
            )
            self.assertEqual(source_strategy_references([p]), {7, 4251, 4280})
            p.write_text(p.read_text() + "\nReferences => new[] { 7 };")
            with self.assertRaises(ValueError):
                source_strategy_references([p])

    def test_streamed_fact_rows_are_bounded_and_reject_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "facts.json"
            rows = [dict(reference=7, name="Árbol"), dict(reference=8)]
            p.write_text(
                json.dumps(
                    dict(catalog_revision=REVISION, rows=rows), ensure_ascii=False
                )
            )
            self.assertEqual(list(streamed_fact_rows(p)), rows)
            p.write_text('{"rows":[{"reference":7}')
            with self.assertRaisesRegex(ValueError, "Truncated"):
                list(streamed_fact_rows(p))
            p.write_text(json.dumps(dict(rows=[dict(reference=7, detail="x" * 1000)])))
            with self.assertRaisesRegex(ValueError, "oversized"):
                list(streamed_fact_rows(p, maximum_row_bytes=64))

    def test_actual_pair_adapter_requires_matching_source_and_real_payment(self):
        stages = [
            "genuine_ready",
            "selected_boss_producer_committed_owned1173",
            "actual1173_occupancy_and_player_turn_end_10016_4713",
            "real1001_4712_profile4252",
            "foreign_composite_uid_rejected_without_payment",
            "paid6007_removes4710_applies4711",
            "stale_transaction_retry_rejected_without_payment",
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "native.json"
            result = dict(
                reference=4251,
                passed=True,
                gifts=False,
                stages=stages,
                initialSnapshot=dict(source=dict(catalogRevision=REVISION)),
                actions=[
                    dict(action=dict(spellId=6011), strategyId="brizlon-prisoner")
                ],
                playerCast=dict(
                    rawUid=6007, costs=dict(ap=4), before=dict(ap=7), after=dict(ap=3)
                ),
            )
            document = dict(
                schema="jondo-brizlon-large-body-qualification-v1",
                catalog=dict(candidate=REVISION),
                nativeComponents=[
                    dict(reference=4251, passed=True, evidence="native.json")
                ],
            )
            path.write_text(json.dumps(dict(status="complete", result=result)))
            record = brizlon_evidence(document, root)[0]
            self.assertEqual(qualified_level(record, catalog_revision=REVISION), "S2")
            self.assertIn("separate earned branch", record["limits"][1])
            self.assertEqual(len(record["source_receipt_sha256"]), 64)
            for field, value in (("gifts", True), ("reference", 4280)):
                wrong = deepcopy(result)
                wrong[field] = value
                path.write_text(json.dumps(dict(status="complete", result=wrong)))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    brizlon_evidence(document, root)
            wrong = deepcopy(result)
            wrong["playerCast"]["after"]["ap"] = 4
            path.write_text(json.dumps(dict(status="complete", result=wrong)))
            with self.assertRaisesRegex(ValueError, "AP payment"):
                brizlon_evidence(document, root)

    def test_header_and_small_document_reader_keep_large_inputs_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "facts.json"
            p.write_text(json.dumps(dict(catalog_revision=REVISION, rows=[])))
            self.assertEqual(fact_catalog_revision(p), REVISION)
            with self.assertRaisesRegex(ValueError, "bounded reader"):
                read_small(p, limit=4)

    def test_runtime_generation_cannot_transfer_a_paid_witness(self):
        record = proof(3510)
        record["runtime_generation"] = "d" * 64
        self.assertEqual(
            qualified_level(
                record, catalog_revision=REVISION, runtime_generation="d" * 64
            ),
            "S2",
        )
        with self.assertRaisesRegex(ValueError, "runtime generation"):
            qualified_level(
                record, catalog_revision=REVISION, runtime_generation="e" * 64
            )

    def test_unbound_receipt_claim_cannot_close_a_case(self):
        record = proof(3510, "durable_encounter", DURABLE_CHECKS)
        del record["source_receipt_sha256"]
        result = self.matrix(evidence=[record])
        self.assertEqual(result["summary"]["post_brizlon_closed"], 0)
        self.assertIn("hash-bound", result["rejected_evidence"][0]["reason"])

    def test_partial_component_claim_cannot_request_full_encounter(self):
        record = proof(7, "complete_encounter", COMPONENT_CHECKS)
        with self.assertRaisesRegex(ValueError, "Incomplete earned checks"):
            qualified_level(record, catalog_revision=REVISION)


if __name__ == "__main__":
    unittest.main()
