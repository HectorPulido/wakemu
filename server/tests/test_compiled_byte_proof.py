"""Immutable native byte hits reuse SHA proof; changed/custom reads revalidate."""
import hashlib
import unittest
from unittest.mock import patch

from wakfu_server import native_compiled_catalog as compiled
from wakfu_server import native_catalog_index as indexed


class CompiledByteProofTests(unittest.TestCase):
    def test_first_validation_reuse_replacement_eviction_budget_and_custom_cache(self):
        raw = b'{"payload":"' + b"x" * 65536 + b'"}'
        sha = hashlib.sha256
        checksum = sha(raw).hexdigest()
        descriptor = dict(revision="a" * 64, collection="fixture", count=2)
        cache = indexed.BoundedByteCache()
        backend = compiled.CompiledCatalogBackend(None, None, cache=cache)
        authority_key = backend._authority_key(descriptor, "1")
        raw_key = backend._raw_key(descriptor, "1", checksum)
        authority = compiled.canonical_bytes([0, checksum, len(raw)])
        cache.put(authority_key, authority)
        cache.put(raw_key, raw)
        hashed = []

        def measured(value):
            if len(value) == len(raw):
                hashed.append(value)
            return sha(value)

        with patch.object(indexed.hashlib, "sha256", new=measured):
            for _ in range(4):
                found, pending = backend._cached_bytes(descriptor, ["1"])
                self.assertEqual(found, {"1": raw})
                self.assertEqual(pending, [])
            self.assertEqual(len(hashed), 1)
            # Same content in a newly admitted object has no inherited proof.
            replacement = bytes(bytearray(raw))
            self.assertIsNot(replacement, raw)
            cache.put(raw_key, replacement)
            self.assertEqual(backend._cached_bytes(descriptor, ["1"])[0], {"1": raw})
            self.assertEqual(len(hashed), 2)
            self.assertIsNone(cache.get_verified_sha256(raw_key, "0" * 64, len(raw)))
            self.assertEqual(len(hashed), 3)
            corrupt = b"!" + raw[1:]
            cache.put(raw_key, corrupt)
            self.assertEqual(backend._cached_bytes(descriptor, ["1"]), ({}, ["1"]))
            self.assertEqual(len(hashed), 4)
            cache.clear()
            self.assertEqual(cache.cache_info()["bytes"], 0)
            cache.put(raw_key, raw)
            self.assertIs(cache.get_verified_sha256(raw_key, checksum, len(raw)), raw)
            self.assertEqual(len(hashed), 5)

        # Proof bytes consume the same configured budget, and eviction never
        # leaves a separate byte-owning proof behind.
        bounded = indexed.BoundedByteCache(max_bytes=len(raw) + 1, max_entries=1)
        bounded.put("a", raw)
        self.assertIs(bounded.get_verified_sha256("a", checksum, len(raw)), raw)
        self.assertIsNone(bounded.get("a"))
        self.assertEqual(bounded.cache_info()["entries"], 0)
        self.assertEqual(bounded.cache_info()["bytes"], 0)
        cache = indexed.BoundedByteCache(max_entries=1)
        cache.put("a", raw)
        cache.get_verified_sha256("a", checksum, len(raw))
        cache.put("b", b"b")
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.cache_info()["bytes"], 2)

        class CustomCache(indexed.BoundedByteCache):
            def get(self, key):
                value = super().get(key)
                return self.mutable if key == raw_key and value is not None else value

        custom = CustomCache()
        custom.mutable = bytearray(raw)
        custom.put(authority_key, authority)
        custom.put(raw_key, raw)
        backend = compiled.CompiledCatalogBackend(None, None, cache=custom)
        self.assertEqual(backend._cached_bytes(descriptor, ["1"])[1], [])
        custom.mutable[0] = ord("!")
        self.assertEqual(backend._cached_bytes(descriptor, ["1"]), ({}, ["1"]))

    def test_replacement_during_hash_does_not_certify_the_replacement(self):
        raw, replacement = b'{"value":1}', b'{"value":2}'
        sha = hashlib.sha256
        checksum = sha(raw).hexdigest()
        descriptor = dict(revision="a" * 64, collection="fixture", count=2)
        cache = indexed.BoundedByteCache()
        backend = compiled.CompiledCatalogBackend(None, None, cache=cache)
        raw_key = backend._raw_key(descriptor, "1", checksum)
        cache.put(
            backend._authority_key(descriptor, "1"),
            compiled.canonical_bytes([0, checksum, len(raw)]),
        )
        cache.put(raw_key, raw)
        replaced = []

        def interleaved_hash(value):
            if value is raw:
                replaced.append(True)
                cache.put(raw_key, replacement)
            return sha(value)

        with patch.object(indexed.hashlib, "sha256", new=interleaved_hash):
            # The captured immutable bytes remain valid after eviction/replacement.
            self.assertEqual(backend._cached_bytes(descriptor, ["1"]), ({"1": raw}, []))
        self.assertEqual(replaced, [True])
        self.assertIs(cache.get(raw_key), replacement)
        # The original read must not publish its proof onto different bytes.
        self.assertEqual(backend._cached_bytes(descriptor, ["1"]), ({}, ["1"]))
