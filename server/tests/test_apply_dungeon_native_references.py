"""Test exact-name evidence integrity and all-before-write conflict rejection."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "resolver", Path(__file__).parents[1] / "tools/apply_dungeon_native_references.py"
)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class NativeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "archive").write_bytes(b"native")
        self.write(
            "native.json",
            {
                "source": {
                    "archive": "archive",
                    "archive_sha256": resolver.sha256(self.root / "archive"),
                },
                "monsters": [
                    {"ref": 1, "name_fr": "Name"},
                    {"ref": 2, "name_fr": "Name"},
                ],
            },
        )
        self.write("context.json", [{"id": 9, "species": [1]}])
        self.write(
            "composition.json",
            {
                "rooms": [
                    {
                        "order": 1,
                        "monsters": [
                            {
                                "name": "Name",
                                "ref_id": None,
                                "min_level": None,
                                "unknown_fields": ["ref_id", "min_level"],
                                "evidence": [],
                            }
                        ],
                    }
                ]
            },
        )
        self.record = {
            "status": "resolved",
            "composition": "composition.json",
            "room_order": 1,
            "monster_index": 0,
            "guide_name": "Name",
            "native_name_catalog": "native.json",
            "exact_name_candidates": [1, 2],
            "remaining_candidates": [1],
            "resolved_ref": 1,
            "context": {
                "catalog": "context.json",
                "catalog_sha256": resolver.sha256(self.root / "context.json"),
                "definition_id": 9,
                "species_field": "species",
                "species_refs": [1],
            },
        }

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def prepare(self):
        return resolver.prepare(self.root, {"records": [self.record]})

    def test_context_resolves_duplicate_without_inventing_level(self):
        documents, count = self.prepare()
        monster = next(iter(documents.values()))["rooms"][0]["monsters"][0]
        self.assertEqual(count, 1)
        self.assertEqual(monster["ref_id"], 1)
        self.assertIsNone(monster["min_level"])
        self.assertEqual(monster["unknown_fields"], ["min_level"])
        self.assertEqual(
            monster["evidence"][0]["source_url"], "urn:wakfu:client:content.7.1"
        )

    def test_ambiguous_preserved(self):
        self.record["status"] = "ambiguous"
        self.assertEqual(self.prepare(), ({}, 0))

    def test_no_context_cannot_resolve_duplicate(self):
        self.record["context"] = None
        with self.assertRaises(ValueError):
            self.prepare()

    def test_changed_name_rejected(self):
        self.record["guide_name"] = "Other"
        with self.assertRaises(ValueError):
            self.prepare()

    def test_context_tampering_rejected(self):
        self.write("context.json", [{"id": 9, "species": [2]}])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_native_archive_tampering_rejected(self):
        (self.root / "archive").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_conflict_leaves_files_and_backups_untouched(self):
        document = json.loads((self.root / "composition.json").read_text())
        document["rooms"][0]["monsters"][0]["ref_id"] = 2
        self.write("composition.json", document)
        original = (self.root / "composition.json").read_bytes()
        with self.assertRaises(ValueError):
            resolver.apply(self.root, {"records": [self.record]}, self.root / "backups")
        self.assertEqual((self.root / "composition.json").read_bytes(), original)
        self.assertFalse((self.root / "backups").exists())

    def test_apply_backs_up_original(self):
        original = (self.root / "composition.json").read_bytes()
        self.assertEqual(
            resolver.apply(
                self.root, {"records": [self.record]}, self.root / "backups"
            ),
            1,
        )
        self.assertEqual(
            (self.root / "backups/composition.json").read_bytes(), original
        )

    def test_invalid_indices_rejected(self):
        for index in (-1, 1, True, 0.0, "0"):
            with self.subTest(index=index):
                self.record["monster_index"] = index
                with self.assertRaises(ValueError):
                    self.prepare()

    def two_records(self):
        import copy

        (self.root / "second.json").write_bytes(
            (self.root / "composition.json").read_bytes()
        )
        second = copy.deepcopy(self.record)
        second["composition"] = "second.json"
        return {"records": [self.record, second]}

    def test_later_backup_collision_has_no_partial_backups(self):
        report = self.two_records()
        backup = self.root / "backups"
        backup.mkdir()
        (backup / "second.json").write_bytes(b"existing")
        with self.assertRaises(ValueError):
            resolver.apply(self.root, report, backup)
        self.assertEqual([p.name for p in backup.iterdir()], ["second.json"])
        self.assertEqual((backup / "second.json").read_bytes(), b"existing")

    def test_second_replace_failure_rolls_back_and_cleans(self):
        from unittest.mock import patch

        report = self.two_records()
        before = {
            p: p.read_bytes()
            for p in (self.root / "composition.json", self.root / "second.json")
        }
        replace = resolver.os.replace
        calls = 0

        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Injected second replace failure")
            return replace(source, destination)

        with patch.object(resolver.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                resolver.apply(self.root, report, self.root / "backups")
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(list((self.root / "backups").iterdir()), [])
        self.assertEqual(
            sorted(p.name for p in self.root.iterdir()),
            [
                "archive",
                "backups",
                "composition.json",
                "context.json",
                "native.json",
                "second.json",
            ],
        )

    def test_normalized_unique_reference_preserves_unknown_level(self):
        native = json.loads((self.root / "native.json").read_text())
        native["monsters"] = [
            {"ref": 1, "name_fr": "name"},
            {"ref": 2, "name_fr": "Name"},
        ]
        self.write("native.json", native)
        self.record.update(
            exact_name_candidates=[2],
            normalized_name_candidates=[1, 2],
            name_normalization_policy=resolver.NAME_NORMALIZATION_POLICY,
            normalized_guide_name="name",
        )
        documents, count = self.prepare()
        monster = next(iter(documents.values()))["rooms"][0]["monsters"][0]
        self.assertEqual(monster["ref_id"], 1)
        self.assertIsNone(monster["min_level"])
        self.assertEqual(count, 1)

    def test_normalization_policy_and_candidate_tampering_rejected(self):
        self.record.update(
            normalized_name_candidates=[1],
            name_normalization_policy=resolver.NAME_NORMALIZATION_POLICY,
            normalized_guide_name="name",
        )
        with self.assertRaisesRegex(ValueError, "candidates changed"):
            self.prepare()
        self.record["name_normalization_policy"] = "remove-accents"
        with self.assertRaisesRegex(ValueError, "Unknown native name"):
            self.prepare()
