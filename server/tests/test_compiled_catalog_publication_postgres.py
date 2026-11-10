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
            # Different logical collections may contain the same exact bytes;
            # the later body-pool compactor should share only the body.
            repeated_record = {"same": {"same": True}}
            spool.collection("fixture.duplicate_one", repeated_record)
            spool.collection("fixture.duplicate_two", repeated_record)
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
                # Exercise the old-table publication path even though this
                # migration converts an initially empty table into a view.
                db.execute("DROP VIEW native_compiled_catalog_records")
                db.execute("DROP VIEW native_compiled_content_records")
                db.execute(
                    "CREATE TABLE native_compiled_content_records ("
                    "content_id bigint NOT NULL REFERENCES "
                    "native_compiled_collection_contents(content_id),"
                    "record_key text NOT NULL,ordinal integer NOT NULL CHECK(ordinal>=0),"
                    "raw bytea NOT NULL,sha256 text NOT NULL,"
                    "PRIMARY KEY(content_id,record_key),UNIQUE(content_id,ordinal))"
                )
                db.execute(
                    "CREATE TABLE native_compiled_catalog_records ("
                    "generation text NOT NULL,collection text NOT NULL,"
                    "record_key text NOT NULL,ordinal integer NOT NULL CHECK(ordinal>=0),"
                    "raw bytea NOT NULL,sha256 text NOT NULL,"
                    "PRIMARY KEY(generation,collection,record_key),"
                    "UNIQUE(generation,collection,ordinal),"
                    "FOREIGN KEY(generation,collection) REFERENCES "
                    "native_compiled_catalog_collections(generation,collection))"
                )
                generation = publisher.publish(
                    db, spool, manifest, storage.canonical_bytes
                )
                second_generation = publisher.publish(
                    db,
                    spool,
                    dict(manifest, config_sha256="e" * 64),
                    storage.canonical_bytes,
                )
            from tools.compact_compiled_catalog import compact
            from tools.compact_compiled_bodies import compact as compact_bodies

            self.assertTrue(compact(self.store.database)["compacted"])
            with self.store.connection() as db:
                content_id = db.execute(
                    "SELECT content_id FROM native_compiled_catalog_collections "
                    "WHERE generation=%s AND collection='fixture.duplicate_one'",
                    (generation,),
                ).fetchone()["content_id"]
                body = publisher.ordered_bytes({"same": True})
                body_hash = hashlib.sha256(body).hexdigest()
                db.execute(
                    "INSERT INTO native_compiled_content_records "
                    "(content_id,record_key,ordinal,raw,sha256) "
                    "VALUES(%s,'corrupt-fixture',99,%s,%s)",
                    (content_id, b"corrupt bytes", body_hash),
                )
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                compact_bodies(self.store.database)
            with self.store.connection() as db:
                relation = db.execute(
                    "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_content_records')"
                ).fetchone()["relkind"]
                corrupt = db.execute(
                    "SELECT raw FROM native_compiled_content_records "
                    "WHERE record_key='corrupt-fixture'"
                ).fetchone()
                self.assertEqual(relation, "r")
                self.assertEqual(bytes(corrupt["raw"]), b"corrupt bytes")
                db.execute(
                    "DELETE FROM native_compiled_content_records "
                    "WHERE record_key='corrupt-fixture'"
                )
            self.assertTrue(compact_bodies(self.store.database)["compacted"])
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
                shared = db.execute(
                    "SELECT c.content_id,c.collection,c.kind,cc.representation,cc.complete,r.record_key,r.ordinal,r.raw,r.sha256 "
                    "FROM native_compiled_catalog_collections c "
                    "JOIN native_compiled_collection_contents cc ON cc.content_id=c.content_id "
                    "JOIN native_compiled_content_records r ON r.content_id=cc.content_id "
                    "WHERE c.generation=%s AND c.collection='raw.keys' AND r.record_key='7'",
                    (generation,),
                ).fetchone()
            self.assertEqual(bytes(stored["raw"]), publisher.ordered_bytes(raw[7]))
            self.assertEqual(
                stored["sha256"], hashlib.sha256(bytes(stored["raw"])).hexdigest()
            )
            self.assertEqual(shared["representation"], "native_json")
            self.assertTrue(shared["complete"])
            self.assertEqual(shared["record_key"], "7")
            self.assertEqual(bytes(shared["raw"]), bytes(stored["raw"]))
            # The legacy relation remains a read-compatible view after compaction.
            with self.store.connection() as db:
                compat = db.execute(
                    "SELECT record_key,ordinal,raw,sha256 FROM native_compiled_catalog_records "
                    "WHERE generation=%s AND collection='raw.keys' AND record_key='7'",
                    (generation,),
                ).fetchone()
            self.assertEqual(bytes(compat["raw"]), bytes(stored["raw"]))
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
                    2,
                )
                shared_ids = db.execute(
                    "SELECT content_id FROM native_compiled_catalog_collections "
                    "WHERE collection='raw.keys' AND generation=ANY(%s) ORDER BY generation",
                    ([generation, second_generation],),
                ).fetchall()
            self.assertEqual(len(shared_ids), 2)
            self.assertEqual(shared_ids[0]["content_id"], shared_ids[1]["content_id"])
            with self.store.connection() as db:
                reused_bodies = db.execute(
                    "SELECT c.collection,c.content_id,l.body_id,b.raw "
                    "FROM native_compiled_catalog_collections c "
                    "JOIN native_compiled_record_links l USING(content_id) "
                    "JOIN native_compiled_record_bodies b USING(body_id) "
                    "WHERE c.generation=%s AND c.collection=ANY(%s) ORDER BY c.collection",
                    (generation, ["fixture.duplicate_one", "fixture.duplicate_two"]),
                ).fetchall()
            self.assertEqual(len(reused_bodies), 2)
            self.assertNotEqual(
                reused_bodies[0]["content_id"], reused_bodies[1]["content_id"]
            )
            self.assertEqual(reused_bodies[0]["body_id"], reused_bodies[1]["body_id"])
            self.assertEqual(
                bytes(reused_bodies[0]["raw"]), publisher.ordered_bytes({"same": True})
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
