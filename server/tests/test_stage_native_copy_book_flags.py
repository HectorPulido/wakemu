"""Immutable copy-book enrichment preserves every previously published flag."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from stage_native_copy_book_flags import merge_flags


class CopyBookStagingTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            native_elO=False,
            native_element=1,
            native_elemental_copy=True,
            native_neutral_copy=False,
        )
        self.previous = dict(
            schema=1,
            missing=[],
            scope=[1],
            spells={"1": self.row},
            source_identity={"jar": "verified"},
            copy_level_maximum=200,
        )
        self.exported = copy.deepcopy(self.previous)
        self.exported["scope"].append(2)
        self.exported["spells"]["2"] = dict(self.row)

    def test_extends_scope_without_mutating_original(self):
        before = copy.deepcopy(self.previous)
        self.assertEqual(len(merge_flags(self.previous, self.exported)["spells"]), 2)
        self.assertEqual(self.previous, before)

    def test_changed_flag_constructor_or_provenance_is_rejected(self):
        for kind in ("flag", "constructor", "identity", "scope"):
            candidate = copy.deepcopy(self.exported)
            if kind == "flag":
                candidate["spells"]["1"]["native_elO"] = True
            elif kind == "constructor":
                candidate["copy_level_maximum"] = 201
            elif kind == "identity":
                candidate["source_identity"]["jar"] = "other"
            else:
                candidate["scope"].append(2)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                merge_flags(self.previous, candidate)
