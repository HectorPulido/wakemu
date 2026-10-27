"""Portable source-bound LOS derivative contracts; no native fight factory."""
import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import marshal
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from wakfu_server import prepared_los_compiled as prepared
from wakfu_server import combat_native_los_ray as ray
from wakfu_server import combat_los_runtime_seal as seal
from wakfu_server import native_catalog, native_compiled_catalog as storage
from wakfu_server import prepared_los, combat_input_observation as observation

REVISION = "a" * 64
SOURCE = dict(
    map_id=7,
    schema="native-Sf-Vz-columns-v1",
    columns=[
        [2, 3, [[0, 2, True]]],
        [1, 1, [[0, 2, True]]],
        [2, 3, [[4, 3, False], [1, 1, True]]],
        [9, 9, [[0, 2, True]]],
    ],
)
RAW = json.dumps(SOURCE).encode()
SHA = hashlib.sha256(RAW).hexdigest()
_VERIFIED_SOURCE = ray._verified_source


def build():
    return prepared.build_record(RAW, map_id=7, revision=REVISION, source_sha256=SHA)


def encode(record):
    return json.dumps(record, separators=(",", ":")).encode()


def decode(record):
    return prepared.decode_record(
        encode(record), map_id=7, revision=REVISION, source_sha256=SHA
    )


def changed_payload(record, transform):
    decoded = marshal.loads(zlib.decompress(base64.b64decode(record["payload"])))
    raw = transform(decoded)
    return dict(
        record,
        payload=base64.b64encode(zlib.compress(raw)).decode(),
        decoded_bytes=len(raw),
        decoded_sha256=hashlib.sha256(raw).hexdigest(),
    )


class PreparedLosCompiledTests(unittest.TestCase):
    @contextmanager
    def publication(self, *, raw=None):
        calls = []
        publication = dict(
            source_revision=REVISION,
            source_documents={"native-los-topology/7.json": SHA},
            prepared_los=dict(schema=prepared.SCHEMA, collection=prepared.COLLECTION),
            generation="b" * 64,
            collections={
                prepared.COLLECTION: dict(
                    kind="dict", count=1, ordered_keys_sha256="c" * 64
                )
            },
        )

        def record_bytes(key):
            calls.append(key)
            return encode(build()) if raw is None else raw

        reader = SimpleNamespace(record_bytes=record_bytes)
        with patch.object(
            native_catalog, "release", return_value=REVISION
        ), patch.object(
            storage, "resolve_publication", return_value=publication
        ) as resolves, patch.object(
            storage.CompiledCatalogBackend, "collection", return_value=reader
        ) as collection:
            yield calls, publication, resolves, collection

    def test_order_overwrites_shared_aliases_and_existing_source_seal(self):
        columns = decode(build())
        self.assertEqual(
            list(columns.items()), list(ray.prepare_columns(SOURCE, 7).items())
        )
        self.assertIs(columns[1, 1], columns[9, 9])
        owned = seal._publish_owned_columns(
            columns, map_id=7, release=REVISION, source_sha=SHA
        )
        self.assertIsNotNone(owned)
        self.assertFalse(hasattr(owned, "__setitem__"))

    def test_scope_abi_exact_types_and_format_mismatches(self):
        original = build()
        for key, value in [
            ("schema", "other"),
            ("map_id", True),
            ("map_id", 8),
            ("source_revision", "b" * 64),
            ("source_sha256", "c" * 64),
            ("abi", ["cpython", "other", 4]),
            ("abi", [prepared.ABI[0], prepared.ABI[1], 4.0]),
            ("decoded_bytes", True),
            ("decoded_bytes", prepared.MAX_DECODED_BYTES + 1),
            ("columns", False),
            ("decoded_sha256", "0" * 64),
            ("payload", "***"),
        ]:
            with self.subTest(key=key), self.assertRaises(
                prepared.DerivativeUnavailable
            ):
                decode(dict(original, **{key: value}))
        with self.assertRaises(prepared.DerivativeUnavailable):
            decode(dict(original, extra=True))
        with self.assertRaises(prepared.DerivativeUnavailable):
            prepared.decode_record(
                b"x" * (prepared.MAX_RECORD_BYTES + 1),
                map_id=7,
                revision=REVISION,
                source_sha256=SHA,
            )

    def test_compression_marshal_trailing_data_and_bounds(self):
        original = build()
        packed = base64.b64decode(original["payload"])
        variants = [
            dict(original, payload=base64.b64encode(packed[:-2]).decode()),
            dict(original, payload=base64.b64encode(packed + b"trailing").decode()),
            dict(original, decoded_bytes=original["decoded_bytes"] - 1),
            changed_payload(original, lambda p: marshal.dumps(p, 4) + b"trailing"),
            changed_payload(original, lambda p: marshal.dumps((p[0], True, *p[2:]), 4)),
            changed_payload(original, lambda p: marshal.dumps((*p[:4], []), 4)),
        ]
        for variant in variants:
            with self.assertRaises(prepared.DerivativeUnavailable):
                decode(variant)

    def test_source_authority_and_bounded_unavailable_records(self):
        with self.assertRaises(ValueError):
            prepared.build_record(
                RAW, map_id=7, revision=REVISION, source_sha256="f" * 64
            )
        with patch.object(prepared, "MAX_DECODED_BYTES", 1):
            self.assertEqual(build()["unavailable"], "decoded_size_limit")
        with patch.object(prepared, "MAX_RECORD_BYTES", 1):
            self.assertEqual(build()["unavailable"], "redis_record_size_limit")
        with self.assertRaises(prepared.DerivativeUnavailable):
            decode(prepared._unavailable("not prepared"))

    def test_unused_bad_geometry_unavailable_and_wrong_source_map_is_hard(self):
        for raw in (b"invalid", b"{}", b"[]", encode(dict(SOURCE, columns=True))):
            result = prepared.build_record(
                raw,
                map_id=7,
                revision=REVISION,
                source_sha256=hashlib.sha256(raw).hexdigest(),
            )
            self.assertIn("unavailable", result)
        raw = encode(dict(SOURCE, map_id=8))
        with self.assertRaises(ValueError):
            prepared.build_record(
                raw,
                map_id=7,
                revision=REVISION,
                source_sha256=hashlib.sha256(raw).hexdigest(),
            )

    def test_all_map_compiler_is_lazy_and_source_fenced(self):
        identity = dict(
            source_revision=REVISION,
            source_documents={
                "native-los-topology/7.json": SHA,
                "native-los-topology/21.json": SHA,
                "native-los-topology/07.json": SHA,
                "other.json": "0" * 64,
            },
        )
        rows = prepared.CompilerRecords(identity)
        self.assertEqual(list(rows), [7, 21])
        with patch.object(
            native_catalog, "release", return_value=REVISION
        ), patch.object(
            native_catalog, "read_published_bytes", return_value=RAW
        ) as reads:
            self.assertEqual(reads.call_count, 0)
            self.assertEqual(rows[7]["map_id"], 7)
            reads.assert_called_once_with("native-los-topology/7.json")
        with patch.object(
            native_catalog, "release", return_value="f" * 64
        ), self.assertRaises(ValueError):
            rows[7]

    def test_published_record_lazy_scope_and_two_generation_resolves(self):
        with self.publication() as (calls, publication, resolves, _):
            self.assertEqual(calls, [])
            columns, revision, digest = prepared.published_columns(7)
            self.assertEqual(calls, [7])
            self.assertEqual((revision, digest), (REVISION, SHA))
            self.assertEqual(columns, decode(build()))
            self.assertEqual(resolves.call_count, 2)

    def test_missing_corrupt_stale_or_cutover_record_falls_back(self):
        for raw in (b"invalid", encode(dict(build(), source_sha256="f" * 64))):
            with self.publication(raw=raw):
                self.assertIsNone(prepared.published_columns(7))
        with self.publication() as (_, publication, _, collection):
            publication.pop("prepared_los")
            self.assertIsNone(prepared.published_columns(7))
            collection.assert_not_called()
        with self.publication() as (_, publication, resolves, _):
            resolves.side_effect = [publication, dict(publication, generation="c" * 64)]
            self.assertIsNone(prepared.published_columns(7))
        with self.publication() as (_, _, _, collection):
            collection.side_effect = ValueError("SQL authority mismatch")
            self.assertIsNone(prepared.published_columns(7))

    def test_operation_cache_retains_no_keys_or_bytes(self):
        cache = prepared.NoRetentionBytes()
        self.assertEqual(type(cache).__slots__, ())
        self.assertIsNone(cache.get("not present"))
        cache.put("artifact", b"not retained")
        self.assertIsNone(cache.get("artifact"))
        with self.assertRaises(AttributeError):
            cache.extra = b"forbidden retention"

    @contextmanager
    def topology(self, derivative):
        with patch.object(
            prepared, "published_columns", return_value=derivative
        ) as read, patch.object(
            prepared_los, "_inventory", return_value={}
        ), patch.object(
            native_catalog, "release", return_value=REVISION
        ), patch.object(
            native_catalog, "exists", return_value=True
        ), patch.object(
            ray, "_verified_source", return_value=(SOURCE, REVISION, SHA)
        ) as source:
            yield ray.topology_columns.__wrapped__, read, source

    def test_original_topology_operand_is_lazy_and_preserves_json_fallback(self):
        with self.topology((decode(build()), REVISION, SHA)) as (
            topology,
            read,
            source,
        ):
            read.assert_not_called()
            self.assertIsNotNone(topology(7))
            read.assert_called_once_with(7)
            source.assert_not_called()
        with self.topology(None) as (topology, read, source):
            self.assertEqual(dict(topology(7)), ray.prepare_columns(SOURCE, 7))
            source.assert_called_once()

    def test_capture_replay_and_custom_prepared_reader_skip_new_derivative(self):
        for slot in (observation._active, observation._replaying):
            token = slot.set(object())
            try:
                with self.topology((decode(build()), REVISION, SHA)) as (
                    topology,
                    read,
                    _,
                ):
                    topology(7)
                    read.assert_not_called()
            finally:
                slot.reset(token)
        with self.topology((decode(build()), REVISION, SHA)) as (
            topology,
            read,
            _,
        ), patch.object(prepared_los, "published_columns", return_value=None) as legacy:
            topology(7)
            legacy.assert_called_once_with(7)
            read.assert_not_called()

    def test_custom_original_byte_reader_is_observed_before_compiled_read(self):
        with self.topology((decode(build()), REVISION, SHA)) as (
            topology,
            read,
            _,
        ), patch.object(ray, "_verified_source", _VERIFIED_SOURCE), patch.object(
            native_catalog, "read_published_bytes", return_value=RAW
        ) as original_read:
            topology(7)
            read.assert_not_called()
            original_read.assert_called_once_with("native-los-topology/7.json")

    def test_custom_loader_and_old_source_errors_keep_original_behavior(self):
        with self.topology((decode(build()), REVISION, SHA)) as (
            topology,
            read,
            _,
        ), patch.object(ray, "_verified_source", _VERIFIED_SOURCE), patch.object(
            native_catalog, "load", return_value=SOURCE
        ) as custom:
            topology(7)
            read.assert_not_called()
            custom.assert_called_once()
        with self.topology(None) as (topology, _, source):
            source.side_effect = ValueError("original source guard")
            with self.assertRaisesRegex(ValueError, "original source guard"):
                topology(7)
