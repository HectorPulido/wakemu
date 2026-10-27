"""Published static codec boundary; reader doubles never load a gameplay catalog."""
import copy
import builtins
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AI = Path(__file__).resolve().parents[1] / "ai-service"
if str(_AI) not in sys.path:
    sys.path.insert(0, str(_AI))

from wakfu_ai.context import native_context, native_fingerprint
from wakfu_server import combat_reproduction_state as reproduction
from wakfu_server.combat_static_catalogs import ImmutableCatalog
from wakfu_server.combat_published_catalogs import (
    POLICY,
    resolve_static_catalog_descriptor,
    validate_static_catalog_descriptor,
)


class _PublishedReader:
    def __init__(self, descriptor):
        self.descriptor = dict(descriptor)
        self.representation = "frozen_effect"
        self.row_reads = 0
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        raise AssertionError("Codecs must not enumerate a published collection")

    def __contains__(self, key):
        raise AssertionError("Codecs must not probe published records")

    def record_bytes(self, key):
        self.row_reads += 1
        if key != "17":
            raise KeyError(key)
        return b'{"effect_class":400,"parameters":[1,0]}'


class PublishedCatalogCodecTests(unittest.TestCase):
    def test_pinned_codecs_preserve_aliases_without_reader_state_or_eager_rows(self):
        descriptor = dict(
            policy=POLICY,
            revision="a" * 64,
            manifest_sha256="a" * 64,
            collection="effects/original",
            count=1,
            ordered_keys_sha256="b" * 64,
        )
        reader = _PublishedReader(descriptor)
        resolutions = []

        def published_collection(record):
            # Stand-in for the authoritative immutable-generation lookup only.
            # There is deliberately no "active generation" fallback.
            canonical = validate_static_catalog_descriptor(record)
            resolutions.append(canonical)
            if canonical != descriptor:
                raise ValueError("Unavailable exact published generation")
            return reader

        with patch(
            "wakfu_server.native_compiled_catalog.published_collection",
            side_effect=published_collection,
        ):
            catalog = resolve_static_catalog_descriptor(descriptor)
            source = {"left": catalog, "right": catalog, "mutable": {"hp": 123}}
            self.assertIs(copy.deepcopy(catalog), catalog)
            encoded = native_context.encode(source)
            encoded_bytes = native_context.encode_bytes(source)
            fingerprint = native_fingerprint.fingerprint(source)
            reproduced = reproduction.encode_state(source)
            self.assertEqual(reader.row_reads, 0)
            self.assertEqual(reader.iterations, 0)
            self.assertEqual(len(resolutions), 1)
            graph = native_context.NativeGraph(encoded_bytes)
            left = graph.field(encoded["root"], "left")
            right = graph.field(encoded["root"], "right")
            self.assertEqual(left, right)
            self.assertEqual(
                graph.resolve(left), {"type": "staticCatalog", "descriptor": descriptor}
            )
            with self.assertRaises(ValueError):
                graph.plain(left)
            self.assertLess(len(encoded_bytes), 2048)
            self.assertEqual(len(resolutions), 1)

            # Warming one authentic record changes neither graph nor custody hash.
            row = catalog["17"]
            self.assertEqual(row["effect_class"], 400)
            self.assertEqual(reader.row_reads, 1)
            self.assertEqual(native_context.encode(source), encoded)
            self.assertEqual(native_context.encode_bytes(source), encoded_bytes)
            self.assertEqual(native_fingerprint.fingerprint(source), fingerprint)
            self.assertEqual(reproduction.encode_state(source), reproduced)
            self.assertEqual(reader.row_reads, 1)
            self.assertEqual(reader.iterations, 0)
            self.assertNotIn(b"_reader", encoded_bytes)
            self.assertNotIn(b"row_reads", encoded_bytes)

            resolved = graph.static_catalog(left)
            self.assertEqual(dict(resolved._descriptor), descriptor)
            restored = reproduction.decode_state(json.loads(json.dumps(reproduced)))
            self.assertIs(restored["left"], restored["right"])
            self.assertEqual(dict(restored["left"]._descriptor), descriptor)
            self.assertIsNot(restored["mutable"], source["mutable"])
            restored["mutable"]["hp"] = 50
            self.assertEqual(source["mutable"]["hp"], 123)
            self.assertEqual(reader.row_reads, 1)

            # Metadata validation is local; executable resolution authenticates
            # the exact generation and never substitutes an available one.
            for update in (
                {"extra": "reader"},
                {"count": True},
                {"manifest_sha256": "c" * 64},
                {"collection": "../effects"},
            ):
                bad = copy.deepcopy(encoded)
                bad["nodes"][left["ref"]]["descriptor"].update(update)
                before = len(resolutions)
                with self.assertRaises(ValueError):
                    native_context.NativeGraph(bad)
                self.assertEqual(len(resolutions), before)
            unknown = copy.deepcopy(encoded)
            unknown["nodes"][left["ref"]]["descriptor"].update(
                revision="c" * 64, manifest_sha256="c" * 64
            )
            unknown_graph = native_context.NativeGraph(unknown)
            with self.assertRaises(ValueError):
                unknown_graph.static_catalog(left)
            forged = copy.deepcopy(reproduced)
            static_node = next(
                n for n in forged["nodes"] if n["kind"] == "staticCatalog"
            )
            static_node["descriptor"]["ordered_keys_sha256"] = "d" * 64
            with self.assertRaises(ValueError):
                reproduction.decode_state(forged)

        # Existing full graph types retain the exact prior codec/fingerprint path.
        old = {
            "catalog": ImmutableCatalog({"nested": {"values": [1, 2]}}),
            "mutable": {"hp": 123},
        }
        current_graph = native_context.encode(old)
        current_bytes = native_context.encode_bytes(old)
        current_hash = native_fingerprint.fingerprint(old)
        current_reproduction = reproduction.encode_state(old)
        with patch.object(
            native_context, "_static_catalog_descriptor", return_value=None
        ):
            self.assertEqual(native_context.encode(old), current_graph)
            self.assertEqual(native_context.encode_bytes(old), current_bytes)
        with patch.object(
            native_fingerprint, "_static_catalog_descriptor", return_value=None
        ):
            self.assertEqual(native_fingerprint.fingerprint(old), current_hash)
        with patch.object(
            reproduction, "_static_catalog_descriptor", return_value=None
        ):
            self.assertEqual(reproduction.encode_state(old), current_reproduction)

        # A same-named Python object cannot manufacture the internal static seal.
        fake_type = type(
            "PublishedStaticMapping",
            (),
            {"__module__": "wakfu_server.combat_published_catalogs"},
        )
        fake = fake_type()
        fake.reader = {"mutable": True}
        self.assertIsNone(native_context._static_catalog_descriptor(fake))
        self.assertFalse(
            any(
                n["type"] == "staticCatalog"
                for n in native_context.encode(fake)["nodes"]
            )
        )

        original_import = builtins.__import__
        for missing in ("wakfu_server.combat_published_catalogs", "reader_dependency"):

            def import_module(name, *args, **kwargs):
                if name == "wakfu_server.combat_published_catalogs":
                    raise ModuleNotFoundError("Missing implementation", name=missing)
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=import_module):
                if missing == "wakfu_server.combat_published_catalogs":
                    self.assertIsNone(native_context._static_catalog_descriptor(fake))
                else:
                    with self.assertRaises(ModuleNotFoundError):
                        native_context._static_catalog_descriptor(fake)
