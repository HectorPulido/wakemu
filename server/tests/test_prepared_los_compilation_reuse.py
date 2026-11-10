"""Map input fingerprints skip compilation without weakening source fences."""

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import native_catalog, native_compiled_catalog as storage
from wakfu_server import prepared_los_compiled as prepared


def identity():
    return dict(
        source_revision="a" * 64,
        source_documents={
            "native-los-topology/7.json": "b" * 64,
            "spell-costs.json": "c" * 64,
        },
        compiler_sources={name: "d" * 64 for name in prepared._COMPILER_INPUTS},
    )


class MapCompilationReuseTests(unittest.TestCase):
    def test_exact_inputs_invalidate_but_unrelated_release_code_and_data_do_not(self):
        original = identity()
        fingerprint = prepared.compilation_fingerprint(original)
        unrelated = deepcopy(original)
        unrelated["source_revision"] = "e" * 64
        unrelated["source_documents"]["spell-costs.json"] = "e" * 64
        unrelated["compiler_sources"]["wakfu_server/combat/combat_spell.py"] = "e" * 64
        self.assertEqual(prepared.compilation_fingerprint(unrelated), fingerprint)
        for change in ("map", "added_map", "removed_map", "compiler", "abi"):
            with self.subTest(change=change):
                altered = deepcopy(original)
                if change == "map":
                    altered["source_documents"]["native-los-topology/7.json"] = "f" * 64
                elif change == "added_map":
                    altered["source_documents"]["native-los-topology/8.json"] = "f" * 64
                elif change == "removed_map":
                    altered["source_documents"].pop("native-los-topology/7.json")
                elif change == "compiler":
                    altered["compiler_sources"][prepared._COMPILER_INPUTS[0]] = "f" * 64
                with patch.object(
                    prepared,
                    "ABI",
                    ("changed", "abi", 4) if change == "abi" else prepared.ABI,
                ):
                    self.assertNotEqual(
                        prepared.compilation_fingerprint(altered), fingerprint
                    )

    def test_existing_content_skips_rows_and_missing_content_builds(self):
        inputs = identity()
        fingerprint = prepared.compilation_fingerprint(inputs)
        keys = b"[7]"
        metadata = dict(
            collection=prepared.COLLECTION,
            kind="dict",
            count=1,
            ordered_keys_sha256=hashlib.sha256(keys).hexdigest(),
            records_sha256="f" * 64,
            representation="native_json",
        )
        entry = dict(
            schema=prepared.SCHEMA,
            collection=prepared.COLLECTION,
            inputs_sha256=fingerprint,
            compiled_source_revision="a" * 64,
        )
        for available in (True, False):
            with self.subTest(available=available):
                row = (
                    dict(prepared_los=entry, metadata=metadata, ordered_keys_raw=keys)
                    if available
                    else None
                )
                db = Mock()
                db.execute.side_effect = [
                    SimpleNamespace(fetchone=lambda: {"relkind": "v"}),
                    SimpleNamespace(fetchone=lambda: row),
                ]

                @contextmanager
                def connection():
                    yield db

                spool = SimpleNamespace(collections={}, keys={}, collection=Mock())
                with patch.object(
                    native_catalog,
                    "_database",
                    return_value=SimpleNamespace(connection=connection),
                ), patch.object(
                    prepared, "CompilerRecords", return_value="lazy maps"
                ) as compiler, patch.object(
                    native_catalog,
                    "read_published_bytes",
                    side_effect=AssertionError("must not load maps"),
                ):
                    actual, reused = prepared.publish_map_collection(spool, inputs)
                self.assertEqual(actual, entry)
                self.assertEqual(reused, available)
                if available:
                    compiler.assert_not_called()
                    spool.collection.assert_not_called()
                    self.assertEqual(spool.collections, {prepared.COLLECTION: metadata})
                    self.assertEqual(spool.keys, {prepared.COLLECTION: keys})
                else:
                    compiler.assert_called_once_with(inputs)
                    spool.collection.assert_called_once_with(
                        prepared.COLLECTION, "lazy maps"
                    )

    def test_cross_release_record_reuse_keeps_current_source_fence(self):
        inputs = identity()
        raw = json.dumps(
            dict(
                map_id=7,
                schema="native-Sf-Vz-columns-v1",
                columns=[[2, 3, [[0, 2, True]]]],
            )
        ).encode()
        source_sha = hashlib.sha256(raw).hexdigest()
        inputs["source_documents"]["native-los-topology/7.json"] = source_sha
        record = prepared.build_record(
            raw, map_id=7, revision=inputs["source_revision"], source_sha256=source_sha
        )
        current_revision = "e" * 64
        publication = dict(
            inputs,
            source_revision=current_revision,
            generation="f" * 64,
            collections={
                prepared.COLLECTION: dict(count=1, ordered_keys_sha256="c" * 64)
            },
            prepared_los=dict(
                schema=prepared.SCHEMA,
                collection=prepared.COLLECTION,
                inputs_sha256=prepared.compilation_fingerprint(inputs),
                compiled_source_revision=inputs["source_revision"],
            ),
        )
        reader = SimpleNamespace(record_bytes=lambda key: json.dumps(record).encode())
        with patch.object(
            native_catalog, "release", return_value=current_revision
        ), patch.object(
            storage, "resolve_publication", return_value=publication
        ), patch.object(
            storage.CompiledCatalogBackend, "collection", return_value=reader
        ):
            columns, revision, digest = prepared.published_columns(7)
            self.assertEqual((revision, digest), (current_revision, source_sha))
            self.assertEqual(columns, {(2, 3): ((0, 2, True),)})
            publication["source_documents"]["native-los-topology/7.json"] = "0" * 64
            self.assertIsNone(prepared.published_columns(7))


if __name__ == "__main__":
    unittest.main()
