"""Audit planning must preserve owned legal decks and native dependency types."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_class_passive_mechanics import passive_plan, native_contracts
from wakfu_server.combat_class_initialization import BREEDS
from wakfu_server.spells import available_spells, encode_deck, validate_deck


class PassiveMechanicAuditTests(unittest.TestCase):
    def test_all_passives_use_legal_single_passive_decks_without_cartesian_cases(self):
        cases, provider, inventory = passive_plan(BREEDS)
        expected_pairs = {
            (breed, spell["id"])
            for breed in BREEDS
            for spell in available_spells(breed, 200)
            if spell["kind"] == "passive"
        }
        observed_pairs = {(breed, passive) for breed, _level, passive in cases}
        self.assertEqual(observed_pairs, expected_pairs)
        self.assertEqual(len(cases), len(observed_pairs))
        self.assertEqual(len(inventory), len(expected_pairs))
        self.assertEqual(len({breed for breed, _, _ in cases}), 18)
        for breed, level, passive in cases:
            parsed = validate_deck(
                encode_deck(provider(breed, level, passive), [passive]), breed, level
            )
            self.assertEqual(parsed["passive"], [passive])

    def test_native_removal_reference_does_not_execute_referenced_state(self):
        rows = [
            dict(kind="spell", reference=10, root_samples={"20": [1]}),
            dict(
                kind="effect",
                reference=1,
                family=321,
                children_ordered=[],
                classified_reference_samples=[
                    dict(kind="state", reference=8, sample_level=20)
                ],
            ),
            dict(kind="state", reference=8, level_samples={"20": {"roots": [999]}}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.gz"
            with gzip.open(path, "wt") as stream:
                stream.write("\n".join(json.dumps(row) for row in rows))
            contracts, _ = native_contracts([(1, 20, 10)], path)
        self.assertEqual(set(contracts["10/20"]["effect_contracts"]), {"1"})
        self.assertEqual(contracts["10/20"]["missing_effect_references"], [])
        self.assertEqual(contracts["10/20"]["applied_state_references"], [])

    def test_source_literal_ranking_is_bounded_and_quoted_calls_are_not_names(self):
        rows = [
            dict(kind="spell", reference=10, root_samples={"20": [1]}),
            dict(kind="spell", reference=100, root_samples={"20": [2]}),
            dict(kind="spell", reference=101, root_samples={"20": [3]}),
            dict(
                kind="effect",
                reference=1,
                family=430,
                children_ordered=[],
                criterion_raw='IsActivatedBySpell(101) and GetCharac("IsActivatedBySpell(100)") >= 0',
            ),
            dict(kind="effect", reference=2, family=2, children_ordered=[]),
            dict(kind="effect", reference=3, family=4, children_ordered=[]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.gz"
            with gzip.open(path, "wt") as stream:
                stream.write("\n".join(json.dumps(row) for row in rows))
            with patch(
                "audit_class_passive_mechanics.available_spells",
                return_value=[dict(id=100, kind="active"), dict(id=101, kind="active")],
            ):
                contracts, _ = native_contracts([(1, 20, 10)], path)
        plan = contracts["10/20"]["representative_action_plan"]
        self.assertEqual(plan["source_literal_spell_references"], [101])
        self.assertEqual(plan["owned_references"], [101])
        self.assertEqual(plan["omitted_owned_references"], [100])
