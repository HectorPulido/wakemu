"""Real isolated SQL/Redis transport authenticates optional LOS derivatives."""
from contextlib import contextmanager
import base64
import hashlib
import json
import marshal
import os
from pathlib import Path
import tempfile
import uuid
import weakref
import zlib
from unittest.mock import patch
from urllib.parse import urlsplit

from postgres_case import PostgresCase


class PreparedLosCompiledTransportTests(PostgresCase):
    def test_actual_helper_miss_hit_and_self_consistent_forgery_use_sql_authority(self):
        import redis as redis_module
        from tools import import_native_catalogs
        from tools import publish_compiled_combat_catalog as publisher
        from wakfu_server import native_catalog, native_compiled_catalog as storage
        from wakfu_server import prepared_los_compiled as prepared
        from wakfu_server.native_catalog_index import (
            BoundedByteCache,
            shared_byte_cache,
        )

        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL")
        if not redis_url:
            self.skipTest("Explicit isolated WAKFU_REDIS_TEST_URL is not configured")
        if urlsplit(redis_url).path in ("", "/", "/0"):
            raise RuntimeError(
                "Explicit isolated Redis database required; never flush caches"
            )
        client = redis_module.Redis.from_url(redis_url)
        client.ping()
        self.addCleanup(client.close)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source"
        (source / "native-los-topology").mkdir(parents=True)
        topology = dict(
            schema="native-Sf-Vz-columns-v1",
            map_id=7,
            columns=[
                [2, 3, [[0, 2, True]]],
                [1, 1, [[0, 2, True]]],
                [2, 3, [[4, 3, False], [1, 1, True]]],
                [9, 9, [[0, 2, True]]],
            ],
        )
        source_raw = json.dumps(topology).encode()
        (source / "native-los-topology/7.json").write_bytes(source_raw)
        (source / "unique-fixture.json").write_text(
            json.dumps({"nonce": uuid.uuid4().hex})
        )
        imported = import_native_catalogs.import_catalogs(self.store, source)
        queries = []

        class ObservedConnection:
            def __init__(self, original):
                self.original = original

            def execute(self, query, *args, **kwargs):
                queries.append(str(query))
                return self.original.execute(query, *args, **kwargs)

        original_database = self.store

        class ObservedDatabase:
            @contextmanager
            def connection(self):
                with original_database.connection() as connection:
                    yield ObservedConnection(connection)

        observed_database = ObservedDatabase()
        backends = []
        original_init = storage.CompiledCatalogBackend.__init__

        def backend_constructed(backend, *args, **kwargs):
            answer = original_init(backend, *args, **kwargs)
            backends.append((weakref.ref(backend), kwargs.get("cache")))
            return answer

        with patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(native_catalog, "_redis", return_value=client), patch.object(
            native_catalog, "release", return_value=imported["revision"]
        ):
            identity = storage.expected_publication_identity()
            spool = publisher.PublicationSpool(str(root / "spool.sqlite"))
            self.addCleanup(spool.db.close)
            rows = prepared.CompilerRecords(identity)
            self.assertEqual(list(rows), [7])
            spool.collection(prepared.COLLECTION, rows)
            # Record JSON is allowed to contain whitespace. Give the authentic
            # SQL record a size budget so the valid forgery can be equal-sized.
            original_raw = spool.db.execute(
                "SELECT raw FROM records WHERE collection=?", (prepared.COLLECTION,)
            ).fetchone()[0]
            padded_raw = bytes(original_raw) + b" " * 64
            padded_sha = hashlib.sha256(padded_raw).hexdigest()
            spool.db.execute(
                "UPDATE records SET raw=?,sha256=? WHERE collection=?",
                (padded_raw, padded_sha, prepared.COLLECTION),
            )
            spool.db.commit()
            spool.collections[prepared.COLLECTION]["records_sha256"] = hashlib.sha256(
                publisher.ordered_bytes([7, 0, padded_sha]) + b"\n"
            ).hexdigest()
            manifest = dict(
                identity,
                collections=spool.collections,
                variants={},
                documents={},
                prepared_los=dict(
                    schema=prepared.SCHEMA, collection=prepared.COLLECTION
                ),
            )
            with self.store.connection() as db:
                generation = publisher.publish(
                    db, spool, manifest, storage.canonical_bytes
                )
            normal = storage.CompiledCatalogBackend(
                self.store, lambda: client, cache=BoundedByteCache()
            )
            with patch.object(storage, "_default_store", normal), patch.dict(
                os.environ, WAKFU_COMPILED_CATALOG_GENERATION=generation
            ):
                header = storage.resolve_publication(
                    source_revision=imported["revision"]
                )
                descriptor = storage.descriptor_for(header, prepared.COLLECTION)
                with self.store.connection() as db:
                    row = db.execute(
                        "SELECT raw,sha256 FROM native_compiled_catalog_records "
                        "WHERE generation=%s AND collection=%s AND record_key=%s",
                        (generation, prepared.COLLECTION, "7"),
                    ).fetchone()
                authentic = bytes(row["raw"])
                expected = prepared.decode_record(
                    authentic,
                    map_id=7,
                    revision=imported["revision"],
                    source_sha256=hashlib.sha256(source_raw).hexdigest(),
                )
                key = normal._raw_key(descriptor, "7", row["sha256"])
                self.addCleanup(client.delete, key)
                client.delete(key)
                shared = shared_byte_cache()
                with shared._lock:
                    shared_before = dict(shared._cache)
                self.assertFalse(
                    any(prepared.COLLECTION in name for name in shared_before)
                )
                with patch.object(
                    native_catalog, "_database", return_value=observed_database
                ), patch.object(
                    storage.CompiledCatalogBackend, "__init__", backend_constructed
                ):
                    queries.clear()
                    first = prepared.published_columns(7)
                    self.assertIsNotNone(first)
                    self.assertEqual(first[0], expected)
                    self.assertTrue(
                        any(
                            "SELECT record_key,ordinal,raw,sha256" in q for q in queries
                        )
                    )
                    self.assertEqual(client.get(key), authentic)
                    # A second actual helper call constructs a fresh non-retaining
                    # backend; the record comes from Redis, not local RAM or SQL raw.
                    queries.clear()
                    second = prepared.published_columns(7)
                    self.assertEqual(second[0], expected)
                    self.assertFalse(
                        any(
                            "SELECT record_key,ordinal,raw,sha256" in q for q in queries
                        )
                    )
                    self.assertTrue(any("octet_length(raw)" in q for q in queries))
                    # Forge a valid inner record with the same outer byte size.
                    # Only the SQL checksum can distinguish this from publication.
                    record = json.loads(authentic)
                    payload = marshal.loads(
                        zlib.decompress(base64.b64decode(record["payload"]))
                    )
                    columns = dict(payload[4])
                    columns[(2, 3)] = ((-100, 3, False), (1, 1, True))
                    changed = marshal.dumps((*payload[:4], columns), 4)
                    entry = dict(
                        record,
                        payload=base64.b64encode(zlib.compress(changed)).decode(),
                        decoded_bytes=len(changed),
                        decoded_sha256=hashlib.sha256(changed).hexdigest(),
                    )
                    raw = json.dumps(entry, separators=(",", ":")).encode()
                    self.assertLessEqual(len(raw), len(authentic))
                    forged = raw + b" " * (len(authentic) - len(raw))
                    self.assertIsNotNone(forged)
                    self.assertEqual(len(forged), len(authentic))
                    self.assertNotEqual(
                        prepared.decode_record(
                            forged,
                            map_id=7,
                            revision=imported["revision"],
                            source_sha256=hashlib.sha256(source_raw).hexdigest(),
                        ),
                        expected,
                    )
                    client.setex(key, 60, forged)
                    queries.clear()
                    recovered = prepared.published_columns(7)
                    self.assertEqual(recovered[0], expected)
                    self.assertTrue(
                        any(
                            "SELECT record_key,ordinal,raw,sha256" in q for q in queries
                        )
                    )
                    self.assertEqual(client.get(key), authentic)
                self.assertEqual(len(backends), 3)
                for reference, cache in backends:
                    self.assertIsNone(reference())
                    self.assertEqual(type(cache).__name__, "NoRetentionBytes")
                    self.assertIsNone(cache.get("irrelevant"))
                    cache.put("irrelevant", b"not retained")
                    self.assertIsNone(cache.get("irrelevant"))
                with shared._lock:
                    self.assertEqual(dict(shared._cache), shared_before)
                self.assertFalse(
                    any(prepared.COLLECTION in name for name in shared._cache)
                )
