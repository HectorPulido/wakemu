"""Bounded real SQL publication; no whole combat catalog or World startup."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import publish_compiled_combat_catalog as publisher


class CompiledCatalogPublicationTests(PostgresCase):
    def test_binary_publication_types_order_immutable_rollback_and_exact_reuse(self):
        from tools import import_native_catalogs
        from wakfu_server import native_catalog
        from wakfu_server import native_compiled_catalog as storage
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source"
        source.mkdir()
        effects = {
            "27": {
                "effect_class": 1,
                "parameters": [1, 2],
                "children": [],
                "target_masks": [[], [], [], [], [], [], [166, 208]],
                "ordered": {"z": [1, {"b": 2, "a": 1}], "a": None},
            }
        }
        states = {"states": {}, "effects": {}}
        (source / "fixture.json").write_bytes(
            publisher.ordered_bytes(dict(effects=effects, states=states))
        )
        imported = import_native_catalogs.import_catalogs(self.store, source)
        import redis as redis_module
        from wakfu_server.native_catalog_index import BoundedByteCache

        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL")
        if not redis_url:
            raise RuntimeError("Explicit isolated WAKFU_REDIS_TEST_URL required")
        redis = redis_module.Redis.from_url(redis_url)
        redis.ping()
        self.addCleanup(redis.close)
        with patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(
            native_catalog, "release", return_value=imported["revision"]
        ), patch.object(
            native_catalog, "_redis", return_value=redis
        ):
            identity = storage.expected_publication_identity()
            spool = publisher.PublicationSpool(str(root / "spool.sqlite"))
            self.addCleanup(spool.db.close)
            # This compound qualifies publication bytes and SQL authority. The
            # compiler's original graph semantics have their own bounded proof.
            spool.collection(
                "player.effects",
                ImmutableCatalog(effects),
                representation="frozen_effect",
            )
            spool.collection("player.source_effects", effects)
            # Integer and string keys remain separate, including nested insertion order.
            raw = {7: {"z": [1, 2], "a": {"b": 2, "a": 1}}, "7": [True, None, -0.0]}
            spool.collection("raw.keys", raw)
            document = spool.document(
                "small", {"schema": "fixture", "fields": ["b", "a"], "items": raw}
            )
            manifest = dict(
                identity,
                collections=spool.collections,
                variants={
                    "player": {
                        "effects": "player.effects",
                        "source_effects": "player.source_effects",
                    }
                },
                original_output_index={"player": [["27", 1, [166, 208]]]},
                documents={"small": document},
            )
            with self.store.connection() as db:
                generation = publisher.publish(
                    db, spool, manifest, storage.canonical_bytes
                )
            backend = storage.CompiledCatalogBackend(
                self.store, lambda: redis, cache=BoundedByteCache()
            )
            header = dict(backend.header(generation), generation=generation)
            descriptor = storage.descriptor_for(header, "raw.keys")
            reader = backend.collection(descriptor)
            self.assertEqual(list(reader), [7, "7"])
            self.assertEqual(reader[7], raw[7])
            self.assertEqual(reader["7"], raw["7"])
            self.assertEqual(reader.record_bytes(7), publisher.ordered_bytes(raw[7]))
            self.assertEqual(list(reader[7]["a"]), ["b", "a"])
            self.assertIs(type(reader[7]["z"]), list)
            reader[7]["z"].append(99)
            self.assertEqual(reader[7], raw[7])
            self.assertEqual(reader.get_many(["7", 7]), {"7": raw["7"], 7: raw[7]})
            self.assertEqual(document["header"]["fields"], ["b", "a"])
            self.assertLessEqual(document["header_bytes"], 65536)
            with self.store.connection() as db:
                stored = db.execute(
                    "SELECT raw,sha256 FROM native_compiled_catalog_records WHERE generation=%s AND collection='raw.keys' AND record_key='7'",
                    (generation,),
                ).fetchone()
            self.assertEqual(bytes(stored["raw"]), publisher.ordered_bytes(raw[7]))
            self.assertEqual(
                stored["sha256"], hashlib.sha256(bytes(stored["raw"])).hexdigest()
            )
            redis_key = backend._raw_key(descriptor, "7", stored["sha256"])
            self.addCleanup(redis.delete, redis_key)
            redis.setex(redis_key, 60, b"corrupt")
            cold = storage.CompiledCatalogBackend(
                self.store, lambda: redis, cache=BoundedByteCache()
            )
            self.assertEqual(cold.collection(descriptor)[7], raw[7])
            for statement in (
                "UPDATE native_compiled_catalog_records SET raw='tamper'::bytea WHERE generation=%s",
                "DELETE FROM native_compiled_catalog_collections WHERE generation=%s",
                "UPDATE native_compiled_catalog_releases SET complete=false WHERE generation=%s",
            ):
                with self.assertRaises(Exception), self.store.connection() as db:
                    db.execute(statement, (generation,))
            changed = dict(manifest, config_sha256="f" * 64)
            with self.assertRaisesRegex(
                ValueError, "changed"
            ), self.store.connection() as db:
                publisher.publish(
                    db,
                    spool,
                    changed,
                    storage.canonical_bytes,
                    identity_check=lambda: (_ for _ in ()).throw(ValueError("changed")),
                )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM native_compiled_catalog_releases"
                    ).fetchone()["n"],
                    1,
                )
            with patch.dict(os.environ), patch.object(
                publisher,
                "compile_manifest",
                side_effect=AssertionError("unexpected compilation"),
            ):
                self.assertEqual(publisher.ensure_publication(), generation)
            with patch.object(storage, "_default_store", backend):
                warmed = storage.warm_publication(
                    generation, max_records=10, max_bytes=65536
                )
                self.assertGreater(warmed["warmed_records"], 0)
                self.assertEqual(
                    storage.resolve_publication(
                        source_revision=imported["revision"], generation=generation
                    )["generation"],
                    generation,
                )
                with self.assertRaises(ValueError):
                    storage.resolve_publication(
                        source_revision=imported["revision"],
                        generation=generation,
                        config_sha256="e" * 64,
                    )
