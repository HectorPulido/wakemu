import unittest
from collections import defaultdict
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import audit_class_normal_casts as audit
from audit_class_normal_casts import (
    deck_cases,
    root_failure,
    numeric_summary,
    NormalCastAudit,
)
from wakfu_server.combat_class_initialization import BREEDS
from wakfu_server.combat_conditions import UnknownCondition
from wakfu_server.spells import available_spells, encode_deck, validate_deck


class ClassNormalCastInventoryTests(unittest.TestCase):
    def test_optional_commit_policy_preserves_default_representatives(self):
        representative = NormalCastAudit()
        self.assertTrue(representative.should_commit(set(), (9, 20)))
        representative.committed_classes.add((9, 20))
        representative.committed_families.add(2)
        self.assertFalse(representative.should_commit({2}, (9, 20)))
        self.assertTrue(representative.should_commit({3}, (9, 20)))
        self.assertTrue(representative.should_commit({2}, (9, 200)))
        every = NormalCastAudit(commit_each_prepared=True)
        every.committed_classes.add((9, 20))
        every.committed_families.add(2)
        self.assertTrue(every.should_commit({2}, (9, 20)))
        self.assertTrue(every.should_commit(set(), (9, 20)))
        with self.assertRaises(ValueError):
            NormalCastAudit(commit_each_prepared=1)

    def test_private_commits_start_from_same_baseline_and_record_actual_outputs(self):
        actor = SimpleNamespace(
            id=7,
            effect_stats={1: 60, 2: 6, 3: 3, 4: 6},
            state_ledger=SimpleNamespace(entries=[]),
        )
        fight = SimpleNamespace(actors={7: actor}, phase="active", current=actor)
        baseline = SimpleNamespace(fight=fight)
        transaction = SimpleNamespace(
            plan={"costs": {"ap": 2, "mp": 0, "wp": 0}}, packets=[(13497, b"effect")]
        )
        branches = []

        def commit(branch, prepared, *, stats_serializer):
            self.assertIs(prepared, transaction)
            self.assertIsNot(branch, baseline)
            self.assertEqual(branch.fight.actors[7].effect_stats[2], 6)
            branch.fight.actors[7].effect_stats[2] -= 2
            branches.append(branch)
            return [(13497, b"effect"), (13912, b"actual stats")]

        def checkpoint(current):
            return {"resources": deepcopy(current.actors[7].effect_stats)}

        with patch.object(
            audit, "commit_spell_transaction", side_effect=commit
        ), patch.object(audit, "snapshot", side_effect=checkpoint), patch.object(
            audit, "granted_spells", return_value={}
        ):
            inspector = NormalCastAudit(commit_each_prepared=True)
            first = inspector.commit_prepared(baseline, transaction, None, 7, {2})
            second = inspector.commit_prepared(baseline, transaction, None, 7, set())
        self.assertIsNot(branches[0], branches[1])
        self.assertEqual(actor.effect_stats[2], 6)
        self.assertEqual(first["costs"], {"ap": 2, "mp": 0, "wp": 0})
        self.assertEqual(first["net_resource_changes"]["2"], -2)
        self.assertEqual(first["packet_opcode_counts"], {"13497": 1, "13912": 1})
        self.assertEqual(first["prepared_effect_packet_opcode_counts"], {"13497": 1})
        self.assertEqual(first["checkpoint_sha256"], second["checkpoint_sha256"])
        self.assertTrue(first["plain_json_snapshot"] and first["baseline_preserved"])

    def test_failed_private_commit_cannot_publish_its_partial_branch(self):
        actor = SimpleNamespace(id=7, effect_stats={2: 6})
        baseline = SimpleNamespace(fight=SimpleNamespace(actors={7: actor}))

        def fail(branch, *args, **kwargs):
            branch.fight.actors[7].effect_stats[2] = 0
            raise ValueError("Actual commit failure")

        with patch.object(
            audit,
            "snapshot",
            side_effect=lambda fight: deepcopy(fight.actors[7].effect_stats),
        ), patch.object(
            audit, "commit_spell_transaction", side_effect=fail
        ), self.assertRaisesRegex(
            ValueError, "Actual commit failure"
        ):
            NormalCastAudit(commit_each_prepared=True).commit_prepared(
                baseline, None, None, 7, set()
            )
        self.assertEqual(actor.effect_stats[2], 6)

    def test_all_prepared_summary_counts_attempts_and_keeps_pair_denominator(self):
        attempts = [
            dict(prepared=True, commit=dict(status=status))
            for status in ("committed", "rejected")
        ]
        rows = [
            dict(
                breed=9,
                level=20,
                runtime_access=dict(
                    actions=[
                        dict(
                            reference=91, origin="normal_owned_deck", attempts=attempts
                        )
                    ]
                ),
            )
        ]
        result = numeric_summary(
            [dict(breed=9, level=20, active_references=[91])], rows
        )["normal"]
        self.assertEqual(result["prepared_attempt_count"], 2)
        self.assertEqual(result["commit_attempt_count"], 2)
        self.assertEqual(result["prepared_attempts_without_commit"], 0)
        self.assertEqual(result["commit_mixed_outcome_spell_level_pairs"], 1)
        self.assertEqual(result["expected_spell_level_pairs"], 1)

    def test_prepared_cast_never_hides_commit_rejection_or_repeated_grants(self):
        direct = dict(
            reference=91,
            origin="normal_owned_deck",
            status="prepared_transaction",
            attempts=[
                dict(prepared=True, representative_commit=dict(status="rejected"))
            ],
        )
        grant = dict(
            reference=92,
            origin="actual_ready_grant",
            status="prepared_transaction",
            attempts=[],
        )
        rows = [
            dict(breed=9, level=20, runtime_access=dict(actions=[direct, grant])),
            dict(breed=9, level=20, runtime_access=dict(actions=[grant])),
        ]
        result = numeric_summary(
            [dict(breed=9, level=20, active_references=[91, 93])], rows
        )
        self.assertEqual(result["normal"]["expected_spell_level_pairs"], 2)
        self.assertEqual(result["normal"]["prepared_percent"], 50)
        self.assertEqual(result["normal"]["commit_rejected_spell_level_pairs"], 1)
        self.assertEqual(result["normal"]["commit_passed_spell_level_pairs"], 0)
        self.assertEqual(
            result["normal"]["preparation_partition"][
                "not_reached_ready_or_owned_turn"
            ],
            1,
        )
        self.assertEqual(
            result["grants"]["distinct_ready_available_spell_level_pairs"], 1
        )
        self.assertEqual(result["grants"]["repeated_rows_across_deck_chunks"], 1)

    def test_all_18_classes_all_owned_active_spells_use_legal_deck_chunks(self):
        cases, provider, inventory = deck_cases(sorted(BREEDS), (20, 200))
        actual = defaultdict(list)
        for breed, level, passive in cases:
            deck = provider(breed, level, passive)
            validate_deck(encode_deck(deck), breed, level)
            actual[breed, level].extend(deck)
        self.assertEqual(len(inventory), 36)
        for breed in BREEDS:
            for level in (20, 200):
                expected = sorted(
                    row["id"]
                    for row in available_spells(breed, level)
                    if row["kind"] == "active"
                )
                self.assertEqual(actual[breed, level], expected)
                self.assertEqual(
                    len(actual[breed, level]), len(set(actual[breed, level]))
                )

    def test_first_root_failure_uses_exception_chain_and_explicit_validation_codes(
        self,
    ):
        wrapper = ValueError("wrapped source guard")
        wrapper.__cause__ = UnknownCondition("Missing actual provider")
        self.assertEqual(root_failure(wrapper)["kind"], "unsupported_predicate")
        self.assertEqual(
            root_failure(ValueError("Invalid target"))["kind"],
            "authority_or_lifecycle_guard",
        )
        known = ValueError("Production resource rejection")
        known.cast_validation_code = "insufficient_resources"
        self.assertEqual(root_failure(known)["kind"], "resource_rejection")
        known.native_casting_result = "twH"
        known.cast_validation_code = None
        self.assertEqual(root_failure(known)["kind"], "legal_target_rejection")
