"""Append-only source supplement identities and domain verification."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_summon_dependencies import compact, dependency_closure
from monster_spell_supplement import (
    merge_dependency_supplement,
    validate_supplement_domains,
    verify_spell_supplement,
    sha256_file,
)


class SpellSupplementAssemblyTests(unittest.TestCase):
    def document(self):
        levels = [[0, 1, [90]]]
        return dict(
            spells={"8331": dict(levels=copy.deepcopy(levels))},
            effects={
                "90": dict(effect_class=321, children=[], parameters_by_level=[[8721]])
            },
            casting={
                "8331": dict(
                    maximum_level=1, levels=copy.deepcopy(levels), costs=[[1, 0, 0]]
                )
            },
        )

    def test_append_closes_missing_spell_without_replacing_base(self):
        tables = compact(dict(spells={}, states={}, areas={}, effects={}))
        tables["states"]["8721"] = [91]
        tables["effects"]["91"] = dict(family=649, children=[], references=[8331])
        before = copy.deepcopy(tables)
        merged = merge_dependency_supplement(tables, self.document())
        self.assertEqual(tables, before)
        closure = dependency_closure(merged, {}, [], [8721])
        self.assertEqual(closure["missing_definitions"], [])
        self.assertEqual(closure["closure_spell_ids"], [8331])
        self.assertEqual(
            validate_supplement_domains(self.document())["8331"][
                "effect_parameters_above_200_qualified"
            ],
            False,
        )

    def test_existing_identical_rows_preserved_and_conflicts_rejected(self):
        document = self.document()
        base = compact(document)
        self.assertEqual(merge_dependency_supplement(base, document), base)
        for kind, reference in [("spells", "8331"), ("effects", "90")]:
            changed = copy.deepcopy(base)
            changed[kind][reference] = {"forged": True}
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                merge_dependency_supplement(changed, document)

    def test_bad_domain_or_missing_effect_rejected(self):
        mutations = [
            lambda d: d["spells"]["8331"]["levels"].append([0, 1, [90]]),
            lambda d: d["casting"]["8331"].update(costs=[]),
            lambda d: d["casting"]["8331"].update(maximum_level=True),
            lambda d: d["casting"]["8331"].update(levels=[[0, 2, [90]]]),
            lambda d: d["effects"].clear(),
        ]
        for mutation in mutations:
            document = self.document()
            mutation(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                validate_supplement_domains(document)

    def test_verified_receipt_rejects_changed_artifacts_and_source(self):
        import json

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            document = self.document()
            (path / "supplement.json").write_text(json.dumps(document))
            receipt = dict(
                schema="native-spell-supplement-receipt-v1",
                source_sha256={"source": "abc"},
                output_sha256={
                    "supplement.json": sha256_file(path / "supplement.json")
                },
                domains=validate_supplement_domains(document),
            )
            (path / "source-receipt.json").write_text(json.dumps(receipt))
            with patch(
                "monster_spell_supplement.source_inputs", return_value={"source": "abc"}
            ):
                self.assertEqual(verify_spell_supplement(path, "unused"), document)
                (path / "supplement.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "artifact changed"):
                    verify_spell_supplement(path, "unused")
            with patch(
                "monster_spell_supplement.source_inputs",
                return_value={"source": "changed"},
            ):
                with self.assertRaisesRegex(ValueError, "source receipt changed"):
                    verify_spell_supplement(path, "unused")

    def test_merge_retains_unrelated_zero_level_roots_and_references(self):
        base = {
            "spells": {"10": [900]},
            "states": {},
            "areas": {},
            "effects": {"900": dict(family=649, children=[], references=[77])},
        }
        before = copy.deepcopy(base)
        merged = merge_dependency_supplement(base, self.document())
        self.assertEqual(base, before)
        self.assertEqual(merged["spells"]["10"], [900])
        self.assertEqual(merged["effects"]["900"], before["effects"]["900"])
