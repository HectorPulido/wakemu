"""Bounded record-reader contracts; SQL and Redis transports are isolated doubles."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
import subprocess
import threading
import time
import tempfile
from pathlib import Path
import unittest
import uuid
from unittest.mock import MagicMock, patch


class CacheRedis:
    """Transport double for envelopes; this does not qualify the Lua program."""

    def __init__(self):
        self.rows = OrderedDict()
        self.fail = False
        self.reads = 0

    def mget(self, keys):
        self.reads += 1
        if self.fail:
            raise ConnectionError("isolated Redis outage")
        return [self.rows.get(key) for key in keys]

    def pipeline(self, transaction=False):
        return self

    def eval(self, script, count, *args):
        if "STRLEN" in script:
            keys, sizes = args[:count], args[count : count * 2]
            limit = args[-1]
            return [
                value
                if value is not None and len(value) == size and len(value) <= limit
                else None
                for key, size in zip(keys, sizes)
                for value in [self.rows.get(key)]
            ]
        key = args[0]
        raw, ttl, byte_limit, entry_limit = args[5:]
        self.rows.pop(key, None)
        self.rows[key] = raw
        while (
            len(self.rows) > entry_limit
            or sum(len(k.encode()) + len(v) for k, v in self.rows.items()) > byte_limit
        ):
            self.rows.popitem(last=False)

    def execute(self):
        if self.fail:
            raise ConnectionError("isolated Redis outage")


class ExternalCatalogBackendTests(unittest.TestCase):
    def test_real_redis_lua_admission_and_bounded_reads_use_isolated_keys(self):
        from wakfu_server.native_catalog_index import redis_admit
        from wakfu_server.native_compiled_catalog import _BOUNDED_MGET

        container = os.environ.get("WAKFU_QA_REDIS_CONTAINER")
        if not container:
            raise RuntimeError("Explicit existing QA Redis container required")
        prefix = "wakemu:qa:external-catalog:" + uuid.uuid4().hex + ":"
        touched = set()

        def command(*args):
            result = subprocess.run(
                ["docker", "exec", container, "redis-cli", "--json", *map(str, args)],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return json.loads(result.stdout)

        class Pipeline:
            calls = 0

            def eval(inner, script, count, *args):
                # Only isolate the supplied KEYS, never alter the production Lua.
                keys = list(args[:count])
                keys[1:] = [prefix + key.rsplit(":", 1)[-1] for key in keys[1:]]
                touched.update(keys)
                inner.calls += 1
                values = [
                    v.decode("ascii") if isinstance(v, bytes) else v
                    for v in args[count:]
                ]
                return command("EVAL", script, count, *keys, *values)

        pipe = Pipeline()
        keys = [prefix + str(index) for index in range(4)]
        try:
            for index, key in enumerate(keys[:3]):
                self.assertTrue(
                    redis_admit(
                        pipe,
                        key,
                        bytes([65 + index]) * 20,
                        60,
                        max_bytes=300,
                        max_entries=2,
                        max_record_bytes=40,
                    )
                )
            self.assertIsNone(command("GET", keys[0]))
            self.assertEqual(command("GET", keys[1]), "B" * 20)
            self.assertEqual(command("GET", keys[2]), "C" * 20)
            self.assertEqual(command("ZCARD", prefix + "order"), 2)
            expected_size = sum(len(key.encode()) + 20 for key in keys[1:3])
            self.assertEqual(int(command("GET", prefix + "bytes")), expected_size)
            calls = pipe.calls
            self.assertFalse(
                redis_admit(
                    pipe,
                    keys[3],
                    b"x" * 41,
                    60,
                    max_bytes=300,
                    max_entries=2,
                    max_record_bytes=40,
                )
            )
            self.assertEqual(pipe.calls, calls)
            # Actual Lua checks STRLEN before GET, with SQL-expected byte sizes.
            self.assertEqual(
                command("EVAL", _BOUNDED_MGET, 2, keys[1], keys[2], 20, 19, 40),
                ["B" * 20, None],
            )
            self.assertEqual(command("EVAL", _BOUNDED_MGET, 1, keys[1], 20, 19), [None])
            self.assertTrue(
                redis_admit(
                    pipe,
                    keys[2],
                    b"updated",
                    60,
                    max_bytes=300,
                    max_entries=2,
                    max_record_bytes=40,
                )
            )
            self.assertEqual(command("ZCARD", prefix + "order"), 2)
            self.assertEqual(
                int(command("GET", prefix + "bytes")), expected_size - 20 + 7
            )
        finally:
            if touched:
                command("DEL", *sorted(touched))

    def test_pinned_generic_and_derived_bounds_corruption_concurrency_and_order(self):
        from wakfu_server.native_catalog_index import (
            IndexedCatalog,
            BoundedByteCache,
            UnindexedCollection,
        )
        from wakfu_server.native_compiled_catalog import (
            CompiledCatalogBackend,
            canonical_bytes,
            descriptor_for,
        )

        sha = lambda raw: hashlib.sha256(raw).hexdigest()
        native_revision = "a" * 64
        native_sha = "b" * 64
        source_rows = {
            "2": {"id": 2, "children": [10]},
            "10": {"id": 10, "children": []},
            "2#1": {"id": 2, "literal": True},
        }
        redis = CacheRedis()
        database, connection = MagicMock(), MagicMock()
        database.connection.return_value.__enter__.return_value = connection
        state = dict(
            total=3,
            selected=3,
            native_reads=0,
            raw_reads=0,
            metadata_reads=0,
            corrupt_raw=False,
            ordinal_bad=False,
        )
        ordered = ["2", "10", "2#1"]
        collection_name = "player/effects"
        manifest = dict(
            policy="wakemu.compiled-combat-catalog.v1",
            source_revision=native_revision,
            source_inventory_sha256="c" * 64,
            compiler_contract_sha256="d" * 64,
            config_sha256="e" * 64,
            collections={
                collection_name: dict(
                    collection=collection_name,
                    kind="dict",
                    representation="native_json",
                    count=3,
                    ordered_keys_sha256=sha(canonical_bytes(ordered)),
                )
            },
        )
        manifest_raw = canonical_bytes(manifest)
        generation = sha(manifest_raw)
        compiled_rows = {
            json.dumps(key): dict(
                record_key=json.dumps(key),
                ordinal=index,
                raw=canonical_bytes(source_rows[key]),
                sha256=sha(canonical_bytes(source_rows[key])),
                source_bytes=len(canonical_bytes(source_rows[key])),
            )
            for index, key in enumerate(ordered)
        }
        entered, release = threading.Event(), threading.Event()
        block = {"enabled": False}

        def query(sql, parameters=()):
            result = MagicMock()
            if sql.startswith("SELECT d.sha256"):
                result.fetchone.return_value = dict(sha256=native_sha, record_count=3)
            elif sql.startswith("SELECT count(*) AS total"):
                result.fetchone.return_value = dict(
                    total=state["total"], selected=state["selected"]
                )
            elif sql.startswith(
                "SELECT record_key,payload FROM native_catalog_records"
            ):
                state["native_reads"] += 1
                if block["enabled"]:
                    entered.set()
                    self.assertTrue(release.wait(3))
                result.fetchall.return_value = [
                    dict(record_key=k, payload=deepcopy(source_rows[k]))
                    for k in parameters[3]
                    if k in source_rows
                ]
            elif sql.startswith("SELECT record_key FROM native_catalog_records"):
                previous = parameters[3]
                result.fetchall.return_value = [
                    dict(record_key=k)
                    for k in sorted(source_rows)
                    if previous is None or k > previous
                ][: parameters[-1]]
            elif sql.startswith("SELECT r.policy,r.source_revision"):
                result.fetchone.return_value = dict(
                    **{
                        field: manifest[field]
                        for field in (
                            "policy",
                            "source_revision",
                            "source_inventory_sha256",
                            "compiler_contract_sha256",
                            "config_sha256",
                        )
                    },
                    manifest_raw=manifest_raw,
                    manifest=deepcopy(manifest),
                )
            elif sql.startswith("SELECT kind,record_count"):
                result.fetchone.return_value = dict(
                    kind="dict",
                    record_count=3,
                    ordered_keys_sha256=manifest["collections"][collection_name][
                        "ordered_keys_sha256"
                    ],
                )
            elif sql.startswith("SELECT record_key,ordinal,sha256"):
                state["metadata_reads"] += 1
                if block.get("derived"):
                    entered.set()
                    self.assertTrue(release.wait(3))
                result.fetchall.return_value = [
                    deepcopy(compiled_rows[k])
                    for k in parameters[2]
                    if k in compiled_rows
                ]
            elif sql.startswith("SELECT record_key,ordinal,raw"):
                state["raw_reads"] += 1
                rows = [
                    deepcopy(compiled_rows[k])
                    for k in parameters[2]
                    if k in compiled_rows
                ]
                if state["corrupt_raw"]:
                    rows[0]["raw"] = b'{"wrong":true}'
                result.fetchall.return_value = rows
            elif sql.startswith("SELECT record_key,ordinal FROM"):
                rows = [
                    deepcopy(row)
                    for row in compiled_rows.values()
                    if row["ordinal"] >= parameters[2]
                ][: parameters[3]]
                if state["ordinal_bad"] and rows:
                    rows[0]["ordinal"] += 1
                result.fetchall.return_value = rows
            else:
                raise AssertionError(sql)
            return result

        connection.execute.side_effect = query
        catalog = IndexedCatalog(
            database,
            lambda: redis,
            max_cache_bytes=1400,
            max_cache_entries=2,
            batch_size=2,
        )
        native = catalog.collection(
            native_revision, "original.json", "effects", expected_count=3
        )
        self.assertEqual(
            list(native), sorted(source_rows)
        )  # Generic index explicitly has key order.
        self.assertEqual(list(native.get_many(["2#1", "2", "10"])), ["2#1", "2", "10"])
        value = native["2"]
        value["children"].append(999)
        self.assertEqual(native["2"], source_rows["2"])
        self.assertLessEqual(catalog.cache_info()["bytes"], 1400)
        self.assertLessEqual(catalog.cache_info()["entries"], 2)
        catalog.clear()
        reads = state["native_reads"]
        self.assertEqual(native["2"], source_rows["2"])
        self.assertEqual(
            state["native_reads"], reads
        )  # Warm Redis, cold process cache.
        catalog.clear()
        cache_key = catalog._key(native.identity, "2")
        redis.rows[cache_key] = catalog._encode(
            native.identity, "10", True, {"foreign": True}
        )
        self.assertEqual(native["2"], source_rows["2"])
        catalog.clear()
        redis.rows[cache_key] = b"invalid-checksum\n{}"
        self.assertEqual(native["2"], source_rows["2"])
        catalog.clear()
        redis.fail = True
        self.assertEqual(native["10"], source_rows["10"])
        redis.fail = False
        with self.assertRaises(KeyError):
            native["absent"]
        state["total"] = 2
        with self.assertRaises(UnindexedCollection):
            catalog.collection(native_revision, "original.json", "effects")
        state["total"] = 3
        for path in ("../a", "a//b", "/a", "a\\b"):
            with self.assertRaises(ValueError):
                catalog.collection(native_revision, path, "effects")

        catalog.clear()
        redis.rows.clear()
        block["enabled"] = True
        before = state["native_reads"]
        barrier = threading.Barrier(6)

        def concurrent():
            barrier.wait(3)
            return native["2"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(concurrent) for _ in range(6)]
            self.assertTrue(entered.wait(3))
            deadline = time.monotonic() + 3
            while (
                catalog._flights.statistics()["shared_calls"] < 5
                and time.monotonic() < deadline
            ):
                time.sleep(0.001)
            release.set()
            values = [future.result(3) for future in futures]
        self.assertEqual(state["native_reads"] - before, 1)
        self.assertEqual(len({id(v) for v in values}), 6)
        block["enabled"] = False

        cache = BoundedByteCache(max_bytes=2400, max_entries=8)
        backend = CompiledCatalogBackend(
            lambda: database, lambda: redis, cache=cache, batch_size=2
        )
        descriptor = descriptor_for(
            dict(manifest, generation=generation), collection_name
        )
        reader = backend.collection(descriptor)
        self.assertEqual(
            list(reader), ordered
        )  # Derived publication preserves actual ordinal order.
        self.assertEqual(reader["2"], source_rows["2"])
        with patch.object(
            backend._flights,
            "run",
            side_effect=AssertionError("Warm hit must not allocate a Future"),
        ):
            self.assertEqual(reader["2"], source_rows["2"])
        encoded = json.dumps("2")
        original_raw = compiled_rows[encoded]
        raw_key = backend._raw_key(descriptor, encoded, original_raw["sha256"])
        cache.put(raw_key, b"corrupt-local")
        redis.rows[raw_key] = b"corrupt-redis"
        raw_reads_before = state["raw_reads"]
        self.assertEqual(reader["2"], source_rows["2"])
        self.assertEqual(state["raw_reads"], raw_reads_before + 1)
        # Cold derived callers still share one complete authority/payload load.
        cache.clear()
        redis.rows.clear()
        block["derived"] = True
        entered.clear()
        release.clear()
        barrier = threading.Barrier(6)
        metadata_before, raw_before = state["metadata_reads"], state["raw_reads"]
        shared_before = backend._flights.statistics()["shared_calls"]

        def derived_concurrent():
            barrier.wait(3)
            return reader["2"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(derived_concurrent) for _ in range(6)]
            self.assertTrue(entered.wait(3))
            deadline = time.monotonic() + 3
            while (
                backend._flights.statistics()["shared_calls"] - shared_before < 5
                and time.monotonic() < deadline
            ):
                time.sleep(0.001)
            release.set()
            outputs = [future.result(3) for future in futures]
        block["derived"] = False
        self.assertEqual(state["metadata_reads"] - metadata_before, 1)
        self.assertEqual(state["raw_reads"] - raw_before, 1)
        self.assertEqual(len({id(value) for value in outputs}), 6)
        first = reader["2"]
        first["children"].append(999)
        self.assertEqual(reader["2"], source_rows["2"])
        cache.clear()
        for key in list(redis.rows):
            if key.startswith("wakemu:compiled:record:"):
                redis.rows[key] = b'{"selfConsistentButWrong":true}'
        self.assertEqual(
            reader["2"], source_rows["2"]
        )  # PostgreSQL SHA remains authority.
        cache.clear()
        redis.rows.clear()
        state["corrupt_raw"] = True
        with self.assertRaisesRegex(ValueError, "checksum"):
            reader["2"]
        state["corrupt_raw"] = False
        state["ordinal_bad"] = True
        with self.assertRaisesRegex(ValueError, "ordinal"):
            list(reader)
        state["ordinal_bad"] = False
        wrong = dict(descriptor, count=4)
        with self.assertRaisesRegex(ValueError, "manifest"):
            backend.collection(wrong)
        with self.assertRaises(KeyError):
            reader["absent"]
        from wakfu_server import native_compiled_catalog as public

        expected = {field: manifest[field] for field in public._PIN_FIELDS}
        with patch.object(
            public, "expected_publication_identity", return_value=expected
        ), patch.object(public, "_store", return_value=backend), patch.object(
            public.native_catalog, "release", return_value=native_revision
        ), patch.dict(
            "os.environ", {"WAKFU_COMPILED_CATALOG_GENERATION": generation}
        ):
            self.assertEqual(
                public.published_collection(descriptor)["2"], source_rows["2"]
            )
            with self.assertRaisesRegex(ValueError, "stale publication"):
                public.published_collection(
                    dict(descriptor, revision="f" * 64, manifest_sha256="f" * 64)
                )
            with patch.object(
                public,
                "expected_publication_identity",
                return_value=dict(expected, config_sha256="f" * 64),
            ):
                with self.assertRaisesRegex(ValueError, "source/compiler/config"):
                    public.published_collection(descriptor)
        self.assertLessEqual(cache.cache_info()["bytes"], 2400)
        self.assertLessEqual(cache.cache_info()["entries"], 8)
        oversized = BoundedByteCache(max_bytes=5, max_entries=1)
        oversized.put("key", b"oversized")
        self.assertEqual(oversized.cache_info()["entries"], 0)

        # Compiler identity covers publisher and schema as well as gameplay code.
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / "server"
            package = server / "wakfu_server"
            (package / "storage").mkdir(parents=True)
            module_path = package / "storage/native_compiled_catalog.py"
            module_path.write_bytes(b"reader-source")
            (package / "fixture.py").write_bytes(b"gameplay-source")
            publisher_path = server / "tools/publish_compiled_combat_catalog.py"
            schema_path = server / "migrations/320_native_compiled_catalogs.sql"
            publisher_path.parent.mkdir()
            schema_path.parent.mkdir()
            publisher_path.write_bytes(b"publisher-v1")
            schema_path.write_bytes(b"schema-v1")
            with patch.object(public, "__file__", str(module_path)):
                public._compiler_source_bytes.cache_clear()
                try:
                    before = public._compiler_source_bytes()
                    inventory = json.loads(before)
                    self.assertEqual(
                        inventory["tools/publish_compiled_combat_catalog.py"],
                        sha(b"publisher-v1"),
                    )
                    self.assertEqual(
                        inventory["migrations/320_native_compiled_catalogs.sql"],
                        sha(b"schema-v1"),
                    )
                    self.assertEqual(
                        inventory["wakfu_server/fixture.py"], sha(b"gameplay-source")
                    )
                    publisher_path.write_bytes(b"publisher-v2")
                    public._compiler_source_bytes.cache_clear()
                    self.assertNotEqual(public._compiler_source_bytes(), before)
                    schema_path.unlink()
                    public._compiler_source_bytes.cache_clear()
                    with self.assertRaisesRegex(FileNotFoundError, "compiler input"):
                        public._compiler_source_bytes()
                finally:
                    public._compiler_source_bytes.cache_clear()

    def test_verified_authority_survives_raw_eviction_without_metadata_queries(self):
        from wakfu_server.native_catalog_index import BoundedByteCache
        from wakfu_server.native_compiled_catalog import (
            CompiledCatalogBackend,
            CompiledBatchLimit,
            canonical_bytes,
            descriptor_for,
        )
        from types import SimpleNamespace

        def fixture(*, cache=None, redis=None, changed=False):
            cache = (
                cache
                if cache is not None
                else BoundedByteCache(max_bytes=4096, max_entries=8)
            )
            redis = redis if redis is not None else CacheRedis()
            value = {"id": 200 if changed else 2, "children": [10]}
            raw = canonical_bytes(value)
            checksum = hashlib.sha256(raw).hexdigest()
            name, encoded = "player/effects", json.dumps("2")
            manifest = dict(
                policy="wakemu.compiled-combat-catalog.v1",
                source_revision="a" * 64,
                source_inventory_sha256="b" * 64,
                compiler_contract_sha256="c" * 64,
                config_sha256=("d" if changed else "e") * 64,
                collections={
                    name: dict(
                        collection=name,
                        kind="dict",
                        representation="native_json",
                        count=1,
                        ordered_keys_sha256=hashlib.sha256(
                            canonical_bytes(["2"])
                        ).hexdigest(),
                    )
                },
            )
            manifest_raw = canonical_bytes(manifest)
            generation = hashlib.sha256(manifest_raw).hexdigest()
            state = dict(metadata=0, payload=0, queries=0, corrupt=False, block=False)
            entered, release = threading.Event(), threading.Event()
            source = dict(
                record_key=encoded,
                ordinal=0,
                raw=raw,
                sha256=checksum,
                source_bytes=len(raw),
            )

            def query(sql, params):
                state["queries"] += 1
                if sql.startswith("SELECT r.policy,r.source_revision"):
                    self.assertEqual(params[0], generation)
                    row = {
                        key: manifest[key]
                        for key in (
                            "policy",
                            "source_revision",
                            "source_inventory_sha256",
                            "compiler_contract_sha256",
                            "config_sha256",
                        )
                    }
                    row.update(manifest_raw=manifest_raw, manifest=deepcopy(manifest))
                    return SimpleNamespace(fetchone=lambda: row)
                if sql.startswith("SELECT kind,record_count"):
                    self.assertEqual(tuple(params), (generation, name))
                    row = dict(
                        kind="dict",
                        record_count=1,
                        ordered_keys_sha256=manifest["collections"][name][
                            "ordered_keys_sha256"
                        ],
                    )
                    return SimpleNamespace(fetchone=lambda: row)
                self.assertEqual(tuple(params[:2]), (generation, name))
                self.assertEqual(params[2], [encoded])
                if sql.startswith("SELECT record_key,ordinal,sha256"):
                    state["metadata"] += 1
                    if state["block"]:
                        entered.set()
                        self.assertTrue(release.wait(3))
                    return SimpleNamespace(fetchall=lambda: [deepcopy(source)])
                if sql.startswith("SELECT record_key,ordinal,raw"):
                    state["payload"] += 1
                    row = deepcopy(source)
                    if state["corrupt"]:
                        row["raw"] = b"wrong source bytes"
                    return SimpleNamespace(fetchall=lambda: [row])
                raise AssertionError("Unexpected query: " + sql)

            database, connection = MagicMock(), MagicMock()
            database.connection.return_value.__enter__.return_value = connection
            connection.execute.side_effect = query
            backend = CompiledCatalogBackend(
                lambda: database, lambda: redis, cache=cache, batch_size=2
            )
            descriptor = descriptor_for(dict(manifest, generation=generation), name)
            reader = backend.collection(descriptor)
            return SimpleNamespace(
                cache=cache,
                redis=redis,
                backend=backend,
                descriptor=descriptor,
                reader=reader,
                value=value,
                raw=raw,
                checksum=checksum,
                encoded=encoded,
                state=state,
                entered=entered,
                release=release,
            )

        f = fixture()
        self.assertEqual(f.reader["2"], f.value)
        self.assertEqual((f.state["metadata"], f.state["payload"]), (1, 1))
        authority_key = f.backend._authority_key(f.descriptor, f.encoded)
        raw_key = f.backend._raw_key(f.descriptor, f.encoded, f.checksum)
        authority = f.cache.get(authority_key)

        def evict_raw():
            # Real bounded-LRU eviction, not removal of private cache internals:
            # keep the verified link MRU, then evict header/raw with one filler.
            f.cache.max_entries = 2
            self.assertEqual(f.cache.get(authority_key), authority)
            f.cache.put("evict-raw-only", b"x")
            self.assertIsNone(f.cache.get(raw_key))
            self.assertEqual(f.cache.get(authority_key), authority)

        evict_raw()
        counts = (f.state["metadata"], f.state["payload"], f.state["queries"])
        self.assertEqual(f.reader["2"], f.value)
        self.assertEqual(
            (f.state["metadata"], f.state["payload"], f.state["queries"]), counts
        )
        self.assertLessEqual(f.cache.cache_info()["bytes"], 4096)

        evict_raw()
        f.redis.rows[raw_key] = bytes([f.raw[0] ^ 1]) + f.raw[1:]
        counts = (f.state["metadata"], f.state["payload"])
        self.assertEqual(f.reader["2"], f.value)
        self.assertEqual(
            (f.state["metadata"], f.state["payload"]), (counts[0], counts[1] + 1)
        )
        self.assertEqual(f.redis.rows[raw_key], f.raw)
        private = f.reader["2"]
        private["children"].append(999)
        self.assertEqual(f.reader["2"], f.value)

        evict_raw()
        f.redis.rows[raw_key] = b"bad redis"
        f.state["corrupt"] = True
        with self.assertRaisesRegex(ValueError, "checksum/size"):
            f.reader["2"]
        f.state["corrupt"] = False
        f.cache.put(authority_key, canonical_bytes([1, f.checksum, len(f.raw)]))
        with self.assertRaisesRegex(ValueError, "cached compiled record authority"):
            f.reader["2"]
        f.cache.put(authority_key, canonical_bytes([0, "bad checksum", len(f.raw)]))
        with self.assertRaisesRegex(ValueError, "SHA256"):
            f.reader["2"]
        f.cache.put(authority_key, authority)
        f.backend.max_batch_bytes = len(f.raw) - 1
        with self.assertRaises(CompiledBatchLimit):
            f.reader["2"]
        f.backend.max_batch_bytes = 16 * 1024 * 1024
        f.backend.max_record_bytes = len(f.raw) - 1
        with self.assertRaisesRegex(ValueError, "cached compiled record authority"):
            f.reader["2"]
        f.backend.max_record_bytes = 16 * 1024 * 1024

        # Same logical key in another immutable generation cannot use this link.
        f.cache.max_entries = 8
        other = fixture(cache=f.cache, redis=f.redis, changed=True)
        self.assertNotEqual(other.descriptor["revision"], f.descriptor["revision"])
        self.assertEqual(other.reader["2"], other.value)
        self.assertEqual((other.state["metadata"], other.state["payload"]), (1, 1))
        self.assertEqual(f.cache.get(authority_key), authority)

        # The changed cold-metadata branch still shares one real authority load.
        cold = fixture()
        cold.cache.clear()
        cold.redis.rows.clear()
        cold.state["block"] = True
        barrier = threading.Barrier(6)

        def read_cold():
            barrier.wait(3)
            return cold.reader["2"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(read_cold) for _ in range(6)]
            self.assertTrue(cold.entered.wait(3))
            deadline = time.monotonic() + 3
            while (
                cold.backend._flights.statistics()["shared_calls"] < 5
                and time.monotonic() < deadline
            ):
                time.sleep(0.001)
            cold.release.set()
            values = [future.result(3) for future in futures]
        self.assertEqual(values, [cold.value] * 6)
        self.assertEqual(len({id(value) for value in values}), 6)
        self.assertEqual((cold.state["metadata"], cold.state["payload"]), (1, 1))
