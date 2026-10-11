"""Additive class copy metadata must preserve the native domain and entries."""
import copy
import hashlib
import json
import tempfile
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from validate_monster_spell_activation import (
    COPY_BOOK_PATH,
    install_overlay,
    preserve_copy_book,
)


class CopyBookOverlayTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(
            schema=1,
            copy_level_minimum=0,
            copy_level_maximum=245,
            scope=[10],
            missing=[],
            spells={"10": {"flags": [1, 2]}},
        )
        self.candidate = copy.deepcopy(self.base)
        self.candidate["scope"].append(11)
        self.candidate["spells"]["11"] = {"flags": [3]}

    def test_addition_preserves_existing_entries(self):
        preserve_copy_book(self.base, self.candidate)

    def test_existing_entry_changes_or_removal_are_rejected(self):
        for replacement in ({"flags": [9]}, None):
            with self.subTest(replacement=replacement):
                candidate = copy.deepcopy(self.candidate)
                if replacement is None:
                    del candidate["spells"]["10"]
                    candidate["scope"].remove(10)
                else:
                    candidate["spells"]["10"] = replacement
                with self.assertRaises(ValueError):
                    preserve_copy_book(self.base, candidate)

    def test_native_level_domain_changes_are_rejected(self):
        for key in ("schema", "copy_level_minimum", "copy_level_maximum"):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.candidate)
                candidate[key] += 1
                with self.assertRaises(ValueError):
                    preserve_copy_book(self.base, candidate)

    def test_incomplete_or_inconsistent_metadata_is_rejected(self):
        for changes in (
            {"missing": [12]},
            {"scope": [10]},
            {"scope": [10, 11, 11]},
            {"spells": []},
        ):
            with self.subTest(changes=changes):
                candidate = copy.deepcopy(self.candidate)
                candidate.update(changes)
                with self.assertRaises(ValueError):
                    preserve_copy_book(self.base, candidate)

    def test_candidate_loads_added_copy_metadata_but_baseline_keeps_original(self):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        names = (
            "native-npc-spell-effect-trees.json",
            "native-class-casting-roots.json",
            COPY_BOOK_PATH,
        )
        baseline = lambda path: self.base if Path(path).name == COPY_BOOK_PATH else {}
        raw = lambda path: json.dumps(baseline(path)).encode()
        hashes = {name: hashlib.sha256(raw(Path(name))).hexdigest() for name in names}
        for enabled in (False, True):
            with self.subTest(
                overlay=enabled
            ), tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                directory = Path(temporary)
                changed = {}
                for name in names:
                    data = json.dumps(
                        self.candidate if name == COPY_BOOK_PATH else {}
                    ).encode()
                    (directory / name).write_bytes(data)
                    changed[name] = hashlib.sha256(data).hexdigest()
                (directory / "manifest.json").write_text(
                    json.dumps(
                        dict(
                            base_revision="base",
                            changed_documents=changed,
                            unchanged_documents={},
                        )
                    )
                )
                for name, options in [
                    ("load", dict(side_effect=baseline)),
                    ("read_bytes", dict(side_effect=raw)),
                    ("release", dict(return_value="base")),
                    ("document_hashes", dict(return_value=hashes)),
                    ("_redis", dict(return_value=None)),
                ]:
                    stack.enter_context(patch.object(native_catalog, name, **options))
                install_overlay(directory, overlay=enabled)
                self.assertEqual(
                    native_catalog.load(DATA_ROOT / COPY_BOOK_PATH),
                    self.candidate if enabled else self.base,
                )
