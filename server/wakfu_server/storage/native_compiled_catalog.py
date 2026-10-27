"""Pinned derived publications read by bounded, SHA-verified record batches.

PostgreSQL holds immutable complete generations and authoritative record hashes.
Redis is disposable. Native and derived readers share one bounded byte cache;
no decoded record, ordered-key inventory or database client is retained here.
"""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path

from wakfu_server import native_catalog
from .native_catalog_index import shared_byte_cache, redis_admit
from .native_source_singleflight import NativeSourceFlights

LOG = logging.getLogger(__name__)
PUBLICATION_POLICY = "wakemu.compiled-combat-catalog.v1"
COLLECTION_POLICY = "wakemu.published-static-collection.v1"
_DESCRIPTOR_FIELDS = frozenset(
    (
        "policy",
        "revision",
        "manifest_sha256",
        "collection",
        "count",
        "ordered_keys_sha256",
    )
)
_PIN_FIELDS = (
    "policy",
    "source_revision",
    "source_inventory_sha256",
    "compiler_contract_sha256",
    "config_sha256",
)


class CompiledBatchLimit(ValueError):
    """A caller must split an otherwise valid request into smaller batches."""


_BOUNDED_MGET = """
local selected = {}
local indexes = {}
local output = {}
for i, key in ipairs(KEYS) do
    output[i] = false
    local expected = tonumber(ARGV[i])
    if expected <= tonumber(ARGV[#KEYS + 1]) and redis.call('STRLEN', key) == expected then
        selected[#selected + 1] = key
        indexes[#indexes + 1] = i
    end
end
if #selected > 0 then
    local values = redis.call('MGET', unpack(selected))
    for i, value in ipairs(values) do output[indexes[i]] = value end
end
return output
"""


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode("utf8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Invalid compiled catalog SHA256 identity")
    return value


def _name(value):
    if type(value) is not str or not value or "\0" in value:
        raise ValueError("Invalid compiled collection identity")
    return value


def _encoded_key(key):
    if type(key) not in (str, int):
        raise TypeError("Compiled record keys must be original strings or integers")
    return json.dumps(key, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


@lru_cache(maxsize=1)
def _compiler_source_bytes():
    # Installed server code is immutable for this process generation. Cache
    # only this small source inventory; no decoded gameplay records live here.
    package = Path(__file__).resolve().parents[1]
    inventory = {}
    for path in sorted(package.rglob("*.py")):
        if "__pycache__" not in path.parts:
            inventory["wakfu_server/" + path.relative_to(package).as_posix()] = _sha(
                path.read_bytes()
            )
    server = package.parent
    for name in (
        "tools/publish_compiled_combat_catalog.py",
        "migrations/320_native_compiled_catalogs.sql",
    ):
        path = server / name
        if not path.is_file():
            raise FileNotFoundError(
                "Missing compiled publication compiler input: " + name
            )
        inventory[name] = _sha(path.read_bytes())
    return canonical_bytes(inventory)


def expected_publication_identity(source_revision=None):
    """Compute original source/compiler/config pins without importing combat."""
    revision = _digest(native_catalog.release())
    if source_revision is not None and _digest(source_revision) != revision:
        raise ValueError(
            "Compiled publication source differs from pinned native release"
        )
    cache = shared_byte_cache()
    cache_key = "wakemu:compiled:source-inventory:v1:" + revision
    inventory_raw = cache.get(cache_key)
    if inventory_raw is None:
        documents = native_catalog.document_hashes()
        if native_catalog.release() != revision or not documents:
            raise ValueError("Native source changed while computing compiled identity")
        for name, checksum in documents.items():
            _name(name)
            _digest(checksum)
        inventory_raw = canonical_bytes(documents)
        cache.put(cache_key, inventory_raw)
    documents = json.loads(inventory_raw)
    compiler_raw = _compiler_source_bytes()
    settings = ("rift_native_gameplay_policy", "dungeon_combat_scaling_catalog")
    with native_catalog._database().connection() as db:
        rows = db.execute(
            "SELECT name,value FROM settings WHERE name=ANY(%s)", (list(settings),)
        ).fetchall()
    values = {row["name"]: row["value"] for row in rows}
    config = {name: values.get(name) for name in settings}
    return dict(
        policy=PUBLICATION_POLICY,
        source_revision=revision,
        source_inventory_sha256=_sha(inventory_raw),
        compiler_contract_sha256=_sha(compiler_raw),
        config_sha256=_sha(canonical_bytes(config)),
        source_documents=documents,
        compiler_sources=json.loads(compiler_raw),
        config=config,
    )


class CompiledCatalogBackend:
    """Immutable release authority plus a shared bounded cache of raw bytes."""

    def __init__(
        self,
        database_provider,
        redis_provider,
        *,
        cache=None,
        batch_size=128,
        max_record_bytes=16 * 1024 * 1024,
        max_manifest_bytes=8 * 1024 * 1024,
        max_batch_bytes=16 * 1024 * 1024,
        redis_max_record_bytes=2 * 1024 * 1024,
        ttl=3600
    ):
        for value in (
            batch_size,
            max_record_bytes,
            max_manifest_bytes,
            max_batch_bytes,
            redis_max_record_bytes,
            ttl,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("Compiled catalog bounds must be positive integers")
        self.database_provider = database_provider
        self.redis_provider = redis_provider
        self.cache = shared_byte_cache() if cache is None else cache
        self.batch_size = batch_size
        self.max_record_bytes = max_record_bytes
        self.max_batch_bytes = max_batch_bytes
        self.max_manifest_bytes = max_manifest_bytes
        self.redis_max_record_bytes = redis_max_record_bytes
        self.ttl = ttl
        self._flights = NativeSourceFlights()

    @contextmanager
    def connection(self):
        provider = self.database_provider
        database = provider() if callable(provider) else provider
        with database.connection() as db:
            yield db

    def header(self, generation):
        generation = _digest(generation)
        cache_key = "wakemu:compiled:manifest:v1:" + generation
        raw = self.cache.get(cache_key)
        if raw is None:
            with self.connection() as db:
                row = db.execute(
                    "SELECT r.policy,r.source_revision,r.source_inventory_sha256,r.compiler_contract_sha256,"
                    "r.config_sha256,r.manifest_raw,r.manifest FROM native_compiled_catalog_releases r "
                    "JOIN native_catalog_releases n ON n.revision=r.source_revision "
                    "WHERE r.generation=%s AND r.complete AND n.complete "
                    "AND octet_length(r.manifest_raw)<=%s",
                    (generation, self.max_manifest_bytes),
                ).fetchone()
            if row is None:
                raise FileNotFoundError("No complete compiled catalog generation")
            raw = bytes(row["manifest_raw"])
            manifest = self._manifest(generation, raw)
            if manifest != row["manifest"] or any(
                manifest[field] != row[field] for field in _PIN_FIELDS
            ):
                raise ValueError("Compiled manifest differs from authoritative release")
            self.cache.put(cache_key, raw)
        return self._manifest(generation, raw)

    def _manifest(self, generation, raw):
        if len(raw) > self.max_manifest_bytes or _sha(raw) != generation:
            raise ValueError("Compiled generation manifest checksum/size mismatch")
        manifest = json.loads(raw)
        if (
            type(manifest) is not dict
            or manifest.get("policy") != PUBLICATION_POLICY
            or canonical_bytes(manifest) != raw
        ):
            raise ValueError("Invalid canonical compiled publication manifest")
        for field in _PIN_FIELDS[1:]:
            _digest(manifest.get(field))
        collections = manifest.get("collections")
        if type(collections) is not dict:
            raise ValueError("Missing compiled collection inventory")
        for name, collection in collections.items():
            _name(name)
            if (
                type(collection) is not dict
                or collection.get("collection") != name
                or collection.get("kind") not in ("dict", "list")
                or collection.get("representation")
                not in ("native_json", "frozen_effect")
                or type(collection.get("count")) is not int
                or collection["count"] < 0
            ):
                raise ValueError("Invalid compiled collection manifest")
            _digest(collection.get("ordered_keys_sha256"))
        return manifest

    def collection(self, descriptor):
        if type(descriptor) is not dict or set(descriptor) != _DESCRIPTOR_FIELDS:
            raise ValueError("Invalid published static collection descriptor")
        if (
            descriptor["policy"] != COLLECTION_POLICY
            or descriptor["manifest_sha256"] != descriptor["revision"]
            or type(descriptor["count"]) is not int
            or descriptor["count"] < 0
        ):
            raise ValueError("Published collection generation identity differs")
        generation = _digest(descriptor["revision"])
        name = _name(descriptor["collection"])
        manifest = self.header(generation)
        declared = manifest["collections"].get(name)
        if declared is None or descriptor != descriptor_for(
            dict(manifest, generation=generation), name
        ):
            raise ValueError("Published collection descriptor differs from manifest")
        with self.connection() as db:
            row = db.execute(
                "SELECT kind,record_count,ordered_keys_sha256 FROM native_compiled_catalog_collections "
                "WHERE generation=%s AND collection=%s",
                (generation, name),
            ).fetchone()
        if (
            row is None
            or row["kind"] != declared["kind"]
            or row["record_count"] != declared["count"]
            or row["ordered_keys_sha256"] != declared["ordered_keys_sha256"]
        ):
            raise ValueError("Published collection authority differs from manifest")
        return PublishedCollectionReader(
            self, descriptor, declared["kind"], declared["representation"]
        )

    def _authority_key(self, descriptor, encoded):
        suffix = _sha(
            canonical_bytes([descriptor["revision"], descriptor["collection"], encoded])
        )
        return "wakemu:compiled:authority:v1:" + suffix

    def _raw_key(self, descriptor, encoded, checksum):
        suffix = _sha(
            canonical_bytes(
                [descriptor["revision"], descriptor["collection"], encoded, checksum]
            )
        )
        return "wakemu:compiled:record:v1:" + suffix

    def many_bytes(self, descriptor, keys):
        encoded = []
        for key in keys:
            if len(encoded) == self.batch_size:
                raise CompiledBatchLimit("Compiled record batch exceeds its bound")
            encoded.append(_encoded_key(key))
        encoded = tuple(dict.fromkeys(encoded))
        if not encoded:
            return {}
        rows, pending = self._cached_bytes(descriptor, encoded)
        if pending:
            # Completed immutable cache hits do not need a Future or a flight
            # registry entry. Concurrent misses still use the existing gate.
            rows = self._flights.run(
                (
                    descriptor["revision"],
                    descriptor["collection"],
                    tuple(sorted(encoded)),
                ),
                lambda: self._many_bytes(descriptor, encoded),
            )
        return {json.loads(key): rows[key] for key in encoded if key in rows}

    def _cached_authority(self, descriptor, key):
        """Read only an authority link previously filled from PostgreSQL.

        Redis never supplies these links. Complete generations are immutable;
        retaining their small verified metadata does not retain decoded records.
        """
        link = self.cache.get(self._authority_key(descriptor, key))
        if link is None:
            return None
        values = json.loads(link)
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError("Invalid cached compiled record authority")
        ordinal, checksum, size = values
        _digest(checksum)
        if (
            type(ordinal) is not int
            or not 0 <= ordinal < descriptor["count"]
            or type(size) is not int
            or not 0 <= size <= self.max_record_bytes
        ):
            raise ValueError("Invalid cached compiled record authority")
        return ordinal, checksum, size

    def _cached_bytes(self, descriptor, keys):
        """Keep the same authoritative checksum checks on the local fast path."""
        found, pending = {}, []
        for key in keys:
            authority = self._cached_authority(descriptor, key)
            if authority is not None:
                ordinal, checksum, size = authority
                raw = self.cache.get(self._raw_key(descriptor, key, checksum))
                if raw is not None and len(raw) == size and _sha(raw) == checksum:
                    found[key] = raw
                    continue
            pending.append(key)
        if sum(map(len, found.values())) > self.max_batch_bytes:
            raise CompiledBatchLimit("Compiled record batch byte limit exceeded")
        return found, pending

    def _many_bytes(self, descriptor, keys):
        found, pending = self._cached_bytes(descriptor, keys)
        if not pending:
            return found
        authority, source_sizes, ordinals = {}, {}, {}
        metadata_pending = []
        for key in pending:
            cached = self._cached_authority(descriptor, key)
            if cached is None:
                metadata_pending.append(key)
            else:
                ordinal, checksum, size = cached
                authority[key], source_sizes[key], ordinals[key] = (
                    checksum,
                    size,
                    ordinal,
                )
        # Redis bytes still require PostgreSQL authority. A raw-byte eviction
        # does not invalidate an existing local link from that immutable source.
        metadata = []
        if metadata_pending:
            with self.connection() as db:
                metadata = db.execute(
                    "SELECT record_key,ordinal,sha256,octet_length(raw) AS source_bytes FROM native_compiled_catalog_records "
                    "WHERE generation=%s AND collection=%s AND record_key=ANY(%s)",
                    (
                        descriptor["revision"],
                        descriptor["collection"],
                        metadata_pending,
                    ),
                ).fetchall()
        for row in metadata:
            key, ordinal, checksum = (
                row["record_key"],
                row["ordinal"],
                _digest(row["sha256"]),
            )
            if (
                key not in metadata_pending
                or key in authority
                or type(ordinal) is not int
                or not 0 <= ordinal < descriptor["count"]
            ):
                raise ValueError("Invalid compiled record authority")
            size = row["source_bytes"]
            if type(size) is not int or not 0 <= size <= self.max_record_bytes:
                raise ValueError("Compiled record exceeds its source byte bound")
            authority[key] = checksum
            source_sizes[key] = size
            ordinals[key] = ordinal
            self.cache.put(
                self._authority_key(descriptor, key),
                canonical_bytes([ordinal, checksum, size]),
            )
        if (
            sum(map(len, found.values())) + sum(source_sizes.values())
            > self.max_batch_bytes
        ):
            raise CompiledBatchLimit("Compiled record batch byte limit exceeded")
        ordered = [key for key in pending if key in authority]
        cache_keys = [self._raw_key(descriptor, key, authority[key]) for key in ordered]
        try:
            cached = (
                self.redis_provider().eval(
                    _BOUNDED_MGET,
                    len(cache_keys),
                    *cache_keys,
                    *(source_sizes[key] for key in ordered),
                    self.redis_max_record_bytes,
                )
                if cache_keys
                else []
            )
            if len(cached) != len(ordered):
                raise ValueError("Compiled Redis batch population differs")
        except Exception as error:
            LOG.warning("Compiled Redis read failed: %s", type(error).__name__)
            cached = [None] * len(ordered)
        missing = []
        for key, cache_key, raw in zip(ordered, cache_keys, cached):
            if (
                raw is not None
                and len(raw) == source_sizes[key]
                and _sha(raw) == authority[key]
            ):
                found[key] = bytes(raw)
                self.cache.put(cache_key, bytes(raw))
            else:
                missing.append(key)
        filled = []
        if missing:
            with self.connection() as db:
                rows = db.execute(
                    "SELECT record_key,ordinal,raw,sha256 FROM native_compiled_catalog_records "
                    "WHERE generation=%s AND collection=%s AND record_key=ANY(%s) AND octet_length(raw)<=%s",
                    (
                        descriptor["revision"],
                        descriptor["collection"],
                        missing,
                        self.max_record_bytes,
                    ),
                ).fetchall()
            for row in rows:
                key, raw = row["record_key"], bytes(row["raw"])
                if (
                    key not in missing
                    or key in found
                    or row["sha256"] != authority[key]
                    or row["ordinal"] != ordinals[key]
                    or len(raw) != source_sizes[key]
                    or len(raw) > self.max_record_bytes
                    or _sha(raw) != authority[key]
                ):
                    raise ValueError(
                        "Compiled PostgreSQL record checksum/size mismatch"
                    )
                found[key] = raw
                cache_key = self._raw_key(descriptor, key, authority[key])
                self.cache.put(cache_key, raw)
                filled.append((cache_key, raw))
            if any(key not in found for key in missing):
                raise ValueError("Published compiled record disappeared")
        if filled:
            try:
                pipe = self.redis_provider().pipeline(transaction=False)
                for key, raw in filled:
                    redis_admit(
                        pipe,
                        key,
                        raw,
                        self.ttl,
                        max_record_bytes=self.redis_max_record_bytes,
                    )
                pipe.execute()
            except Exception as error:
                LOG.warning("Compiled Redis fill failed: %s", type(error).__name__)
        return {key: found[key] for key in keys if key in found}


class PublishedCollectionReader:
    """Ordered immutable record identity, with fresh private JSON decodes."""

    def __init__(self, backend, descriptor, kind, representation):
        self.backend = backend
        self._descriptor = dict(descriptor)
        self.kind = kind
        self.representation = representation

    @property
    def descriptor(self):
        return dict(self._descriptor)

    def __len__(self):
        return self._descriptor["count"]

    def original_output_index(self):
        """Return the generation-proven native mask6 publisher index only."""
        manifest = self.backend.header(self._descriptor["revision"])
        variants = manifest.get("variants", {})
        matching = []
        for name, row in variants.items():
            value = row.get("effects")
            collection = (
                value
                if type(value) is str
                else value.get("collection")
                if type(value) is dict
                else None
            )
            if collection == self._descriptor["collection"]:
                matching.append(name)
        if len(matching) != 1 or self.representation != "frozen_effect":
            raise ValueError(
                "Collection has no unique original compiled producer index"
            )
        index = manifest.get("original_output_index", {}).get(matching[0])
        if type(index) is not list:
            raise ValueError("Missing original compiled producer index")
        seen = set()
        for row in index:
            if (
                type(row) is not list
                or len(row) != 3
                or type(row[0]) is not str
                or not row[0].isdigit()
                or str(int(row[0])) != row[0]
                or int(row[0]) <= 0
                or type(row[1]) is not int
                or row[0] in seen
                or type(row[2]) is not list
                or any(type(event) is not int or event < 0 for event in row[2])
            ):
                raise ValueError("Invalid original compiled producer index")
            seen.add(row[0])
        return index

    def record_bytes(self, key):
        rows = self.backend.many_bytes(self._descriptor, [key])
        if key not in rows:
            raise KeyError(key)
        return rows[key]

    def __getitem__(self, key):
        return json.loads(self.record_bytes(key))

    def get_many_bytes(self, keys):
        return self.backend.many_bytes(self._descriptor, keys)

    def get_many(self, keys):
        return {key: json.loads(raw) for key, raw in self.get_many_bytes(keys).items()}

    def __contains__(self, key):
        encoded = _encoded_key(key)
        if (
            self.backend.cache.get(
                self.backend._authority_key(self._descriptor, encoded)
            )
            is not None
        ):
            return True
        with self.backend.connection() as db:
            row = db.execute(
                "SELECT 1 FROM native_compiled_catalog_records WHERE generation=%s "
                "AND collection=%s AND record_key=%s",
                (self._descriptor["revision"], self._descriptor["collection"], encoded),
            ).fetchone()
        return row is not None

    def __iter__(self):
        expected = 0
        digest = hashlib.sha256(b"[")
        while expected < len(self):
            with self.backend.connection() as db:
                rows = db.execute(
                    "SELECT record_key,ordinal FROM native_compiled_catalog_records "
                    "WHERE generation=%s AND collection=%s AND ordinal>=%s "
                    "ORDER BY ordinal LIMIT %s",
                    (
                        self._descriptor["revision"],
                        self._descriptor["collection"],
                        expected,
                        self.backend.batch_size,
                    ),
                ).fetchall()
            if not rows:
                raise ValueError("Published compiled ordered index is incomplete")
            keys = []
            for row in rows:
                if row["ordinal"] != expected or expected >= len(self):
                    raise ValueError("Published compiled ordinal sequence differs")
                key = json.loads(row["record_key"])
                if _encoded_key(key) != row["record_key"]:
                    raise ValueError("Noncanonical compiled record key")
                if expected:
                    digest.update(b",")
                digest.update(row["record_key"].encode("utf8"))
                expected += 1
                keys.append(key)
            for key in keys:
                yield key
        digest.update(b"]")
        if digest.hexdigest() != self._descriptor["ordered_keys_sha256"]:
            raise ValueError("Published compiled ordered-key SHA256 differs")


_default_store = None


def _store():
    global _default_store
    if _default_store is None:
        _default_store = CompiledCatalogBackend(
            native_catalog._database, native_catalog._redis
        )
    return _default_store


def descriptor_for(header, collection):
    row = header["collections"][_name(collection)]
    generation = _digest(header["generation"])
    return dict(
        policy=COLLECTION_POLICY,
        revision=generation,
        manifest_sha256=generation,
        collection=collection,
        count=row["count"],
        ordered_keys_sha256=row["ordered_keys_sha256"],
    )


def published_collection(descriptor):
    if type(descriptor) is not dict or set(descriptor) != _DESCRIPTOR_FIELDS:
        raise ValueError("Invalid published static collection descriptor")
    generation = _digest(descriptor["revision"])
    # A valid old sealed descriptor must not silently reopen a different
    # source/compiler/config generation after a process publication cutover.
    current = resolve_publication(source_revision=native_catalog.release())
    if generation != current["generation"]:
        raise ValueError(
            "Serialized compiled descriptor belongs to a stale publication"
        )
    return _store().collection(descriptor)


def resolve_publication(
    *,
    source_revision,
    compiler_contract_sha256=None,
    config_sha256=None,
    generation=None
):
    expected = expected_publication_identity(source_revision)
    for field, supplied in (
        ("compiler_contract_sha256", compiler_contract_sha256),
        ("config_sha256", config_sha256),
    ):
        if supplied is not None and _digest(supplied) != expected[field]:
            raise ValueError("Expected compiled publication pin differs: " + field)
    selected = (
        generation
        if generation is not None
        else os.environ.get("WAKFU_COMPILED_CATALOG_GENERATION")
    )
    store = _store()
    if selected is None:
        with store.connection() as db:
            rows = db.execute(
                "SELECT generation FROM native_compiled_catalog_releases WHERE complete "
                "AND policy=%s AND source_revision=%s AND source_inventory_sha256=%s "
                "AND compiler_contract_sha256=%s AND config_sha256=%s LIMIT 2",
                tuple(expected[field] for field in _PIN_FIELDS),
            ).fetchall()
        if len(rows) != 1:
            raise RuntimeError(
                "No unique complete compiled publication matches current source/compiler/config"
            )
        selected = rows[0]["generation"]
    manifest = store.header(_digest(selected))
    if any(manifest.get(field) != expected[field] for field in _PIN_FIELDS):
        raise ValueError(
            "Pinned compiled publication differs from source/compiler/config"
        )
    header = dict(manifest, generation=selected, manifest_sha256=selected)
    header["descriptors"] = {
        name: descriptor_for(header, name) for name in manifest["collections"]
    }
    return header


def redis_record_key(generation, collection, key, checksum):
    """Shared publisher/reader cache key; the expected SHA is SQL authority."""
    return _store()._raw_key(
        dict(revision=_digest(generation), collection=_name(collection)),
        _encoded_key(key),
        _digest(checksum),
    )


def warm_publication(generation, *, max_records=8192, max_bytes=32 * 1024 * 1024):
    """Warm a deterministic bounded prefix, never the whole compiled universe."""
    if any(type(value) is not int or value <= 0 for value in (max_records, max_bytes)):
        raise ValueError("Compiled warming bounds must be positive integers")
    store = _store()
    manifest = store.header(_digest(generation))
    header = dict(manifest, generation=generation)
    examined, warmed, total_bytes = 0, 0, 0
    for name in manifest["collections"]:
        descriptor = descriptor_for(header, name)
        after = 0
        while (
            after < descriptor["count"]
            and examined < max_records
            and total_bytes < max_bytes
        ):
            with store.connection() as db:
                rows = db.execute(
                    "SELECT record_key,ordinal,octet_length(raw) AS source_bytes "
                    "FROM native_compiled_catalog_records WHERE generation=%s AND collection=%s "
                    "AND ordinal>=%s ORDER BY ordinal LIMIT %s",
                    (
                        generation,
                        name,
                        after,
                        min(store.batch_size, max_records - examined),
                    ),
                ).fetchall()
            if not rows:
                raise ValueError(
                    "Incomplete compiled publication during bounded warming"
                )
            keys, batch_bytes = [], 0
            for row in rows:
                if row["ordinal"] != after:
                    raise ValueError("Noncontiguous compiled warming index")
                after += 1
                examined += 1
                size = row["source_bytes"]
                if size > store.redis_max_record_bytes:
                    continue
                if (
                    total_bytes + batch_bytes + size > max_bytes
                    or batch_bytes + size > store.max_batch_bytes
                ):
                    break
                keys.append(json.loads(row["record_key"]))
                batch_bytes += size
            if keys:
                values = store.many_bytes(descriptor, keys)
                warmed += len(values)
                total_bytes += sum(map(len, values.values()))
            if total_bytes + batch_bytes >= max_bytes:
                break
        if examined >= max_records or total_bytes >= max_bytes:
            break
    return dict(
        generation=generation,
        examined_records=examined,
        warmed_records=warmed,
        source_bytes=total_bytes,
        max_records=max_records,
        max_bytes=max_bytes,
    )
