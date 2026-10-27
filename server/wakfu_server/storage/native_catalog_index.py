"""Pinned PostgreSQL record mappings with bounded local and Redis byte caches.

This exposes the importer's exact record keys, not reconstructed JSON objects
or array order. There is no automatic whole-document fallback. PostgreSQL is
the durable authority; Redis is a disposable cache for immutable releases.
"""

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import logging
from threading import RLock
from .native_source_singleflight import NativeSourceFlights

LOG = logging.getLogger(__name__)
_MISSING = object()
# One atomic bounded cache admission across workers. Expired data may retain
# bookkeeping until eviction; this is conservative, never an unbounded index.
_REDIS_ADMIT = """
local size = string.len(KEYS[1]) + string.len(ARGV[1])
local byte_limit = tonumber(ARGV[3])
local entry_limit = tonumber(ARGV[4])
if size > byte_limit then return 0 end
local old = tonumber(redis.call('HGET', KEYS[3], KEYS[1]) or '0')
local used = tonumber(redis.call('GET', KEYS[4]) or '0') - old + size
redis.call('SETEX', KEYS[1], ARGV[2], ARGV[1])
redis.call('HSET', KEYS[3], KEYS[1], size)
local sequence = redis.call('INCR', KEYS[5])
redis.call('ZADD', KEYS[2], sequence, KEYS[1])
while used > byte_limit or redis.call('ZCARD', KEYS[2]) > entry_limit do
    local victim = redis.call('ZPOPMIN', KEYS[2], 1)
    if #victim == 0 then break end
    local key = victim[1]
    used = used - tonumber(redis.call('HGET', KEYS[3], key) or '0')
    redis.call('DEL', key)
    redis.call('HDEL', KEYS[3], key)
end
redis.call('SET', KEYS[4], used)
return 1
"""


class UnindexedCollection(ValueError):
    """The requested collection has no demonstrated complete record index."""


def _name(value):
    if type(value) is not str or not value or "\0" in value:
        raise ValueError("Expected a nonempty native index identity")
    return value


def _record_key(value):
    if type(value) not in (str, int):
        raise TypeError("Native record keys must be exact strings or integers")
    return str(value)


@dataclass(frozen=True)
class CollectionIdentity:
    revision: str
    path: str
    collection: str
    document_sha256: str
    count: int
    document_record_count: int


class BoundedByteCache:
    """Shared byte retention only; authority validation belongs to its reader."""

    def __init__(self, max_bytes=8 * 1024 * 1024, max_entries=2048):
        if any(
            type(value) is not int or value <= 0 for value in (max_bytes, max_entries)
        ):
            raise ValueError("Byte cache limits must be positive integers")
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self._cache = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    def get(self, key):
        with self._lock:
            raw = self._cache.get(key)
            if raw is not None:
                self._cache.move_to_end(key)
            return raw

    def put(self, key, raw):
        if type(key) is not str or type(raw) is not bytes:
            raise TypeError("Byte cache requires exact string keys and immutable bytes")
        size = len(key.encode()) + len(raw)
        if size > self.max_bytes:
            return
        with self._lock:
            old = self._cache.pop(key, None)
            if old is not None:
                self._bytes -= len(key.encode()) + len(old)
            self._cache[key] = raw
            self._bytes += size
            while len(self._cache) > self.max_entries or self._bytes > self.max_bytes:
                old_key, old_raw = self._cache.popitem(last=False)
                self._bytes -= len(old_key.encode()) + len(old_raw)

    def cache_info(self):
        with self._lock:
            return dict(
                entries=len(self._cache),
                bytes=self._bytes,
                max_entries=self.max_entries,
                max_bytes=self.max_bytes,
            )

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._bytes = 0


_SHARED_BYTES = BoundedByteCache()


def shared_byte_cache():
    """The original and derived readers share one process retention budget."""
    return _SHARED_BYTES


def redis_admit(
    pipe,
    key,
    raw,
    ttl,
    *,
    max_bytes=64 * 1024 * 1024,
    max_entries=16384,
    max_record_bytes=2 * 1024 * 1024
):
    """Queue one atomic admission against the common cross-worker Redis budget."""
    if type(key) is not str or type(raw) is not bytes:
        raise TypeError(
            "Redis record admission requires immutable bytes and a string key"
        )
    if any(
        type(value) is not int or value <= 0
        for value in (ttl, max_bytes, max_entries, max_record_bytes)
    ):
        raise ValueError("Redis record limits must be positive integers")
    if len(raw) > max_record_bytes or len(key.encode()) + len(raw) > max_bytes:
        return False
    budget = "wakemu:catalog-record:v1:budget:"
    pipe.eval(
        _REDIS_ADMIT,
        5,
        key,
        budget + "order",
        budget + "sizes",
        budget + "bytes",
        budget + "sequence",
        raw,
        ttl,
        max_bytes,
        max_entries,
    )
    return True


class IndexedCatalog:
    """One process-wide byte LRU, shared by arbitrarily many pinned mappings.

    A mapping validates its release and index completeness once at creation.
    Callers must only use immutable, completed releases. Creating a mapping for
    another release cannot reuse bytes from an older revision/document SHA.
    Returned JSON values are private decodes, never mutable cache entries.
    """

    def __init__(
        self,
        database,
        redis_provider,
        *,
        max_cache_bytes=8 * 1024 * 1024,
        max_cache_entries=2048,
        batch_size=128,
        ttl=3600,
        redis_max_bytes=64 * 1024 * 1024,
        redis_max_entries=16384,
        max_record_bytes=2 * 1024 * 1024
    ):
        for value in (
            max_cache_bytes,
            max_cache_entries,
            batch_size,
            ttl,
            redis_max_bytes,
            redis_max_entries,
            max_record_bytes,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("Native index cache limits must be positive integers")
        self.database = database
        self.redis_provider = redis_provider
        self.max_cache_bytes = max_cache_bytes
        self.max_cache_entries = max_cache_entries
        self.batch_size = batch_size
        self.ttl = ttl
        self.redis_max_bytes = redis_max_bytes
        self.redis_max_entries = redis_max_entries
        self.max_record_bytes = max_record_bytes
        self.byte_cache = (
            shared_byte_cache()
            if (max_cache_bytes, max_cache_entries) == (8 * 1024 * 1024, 2048)
            else BoundedByteCache(max_cache_bytes, max_cache_entries)
        )
        self._flights = NativeSourceFlights()

    def collection(
        self, revision, path, collection, *, expected_count=None, allow_empty=False
    ):
        revision, path, collection = map(_name, (revision, path, collection))
        if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError("Expected a logical published native document path")
        if len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Invalid native release identity")
        if expected_count is not None and (
            type(expected_count) is not int or expected_count < 0
        ):
            raise ValueError("Invalid expected native collection count")
        if type(allow_empty) is not bool:
            raise TypeError("Native empty-index policy must be explicit")
        with self.database.connection() as db:
            row = db.execute(
                "SELECT d.sha256,d.record_count FROM native_catalog_documents d "
                "JOIN native_catalog_releases r USING(revision) "
                "WHERE d.revision=%s AND d.path=%s AND r.complete",
                (revision, path),
            ).fetchone()
            if row is None:
                raise FileNotFoundError("No complete native document: " + path)
            counts = db.execute(
                "SELECT count(*) AS total,count(*) FILTER (WHERE collection=%s) AS selected "
                "FROM native_catalog_records WHERE revision=%s AND path=%s",
                (collection, revision, path),
            ).fetchone()
        total, selected = counts["total"], counts["selected"]
        if total != row["record_count"]:
            raise UnindexedCollection(
                "Incomplete native document record index: " + path
            )
        if expected_count is not None and selected != expected_count:
            raise UnindexedCollection("Native collection count differs from contract")
        if selected == 0 and not allow_empty:
            raise UnindexedCollection(
                "Empty, absent or raw-only native collection: " + collection
            )
        digest = row["sha256"]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Invalid native document checksum")
        identity = CollectionIdentity(
            revision, path, collection, digest, selected, total
        )
        return IndexedCollection(self, identity)

    def cache_info(self):
        return self.byte_cache.cache_info()

    def clear(self):
        self.byte_cache.clear()

    def _key(self, identity, key):
        raw = json.dumps(
            [
                identity.revision,
                identity.path,
                identity.collection,
                identity.document_sha256,
                key,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode()
        return "wakemu:catalog-record:v1:" + hashlib.sha256(raw).hexdigest()

    def _get(self, key):
        return self.byte_cache.get(key)

    def _put(self, key, raw):
        # Count key bytes too; both byte and entry ceilings are hard bounds.
        if len(raw) > self.max_record_bytes:
            return
        self.byte_cache.put(key, raw)

    @staticmethod
    def _encode(identity, key, present, payload=None):
        body = json.dumps(
            [
                identity.revision,
                identity.path,
                identity.collection,
                identity.document_sha256,
                key,
                present,
                payload,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return hashlib.sha256(body).hexdigest().encode() + b"\n" + body

    @staticmethod
    def _decode(identity, key, raw):
        try:
            checksum, separator, body = raw.partition(b"\n")
            if not separator or checksum != hashlib.sha256(body).hexdigest().encode():
                return _MISSING
            value = json.loads(body)
            if (
                type(value) is not list
                or len(value) != 7
                or value[:5]
                != [
                    identity.revision,
                    identity.path,
                    identity.collection,
                    identity.document_sha256,
                    key,
                ]
                or type(value[5]) is not bool
            ):
                return _MISSING
            return value[5], value[6]
        except (ValueError, TypeError, AttributeError):
            return _MISSING

    def _many(self, identity, keys):
        keys = tuple(dict.fromkeys(keys))
        if len(keys) > self.batch_size:
            raise ValueError("Native record request exceeds bounded batch")
        # Coalesced work shares immutable encoded bytes, never decoded objects.
        rows = self._flights.run(
            (identity, tuple(sorted(keys))), lambda: self._many_bytes(identity, keys)
        )
        return {
            key: self._decode(identity, key, rows[key])[1]
            for key in keys
            if key in rows
        }

    def _many_bytes(self, identity, keys):
        cache_keys = {key: self._key(identity, key) for key in keys}
        found, missing = {}, []
        for key in keys:
            raw = self._get(cache_keys[key])
            decoded = self._decode(identity, key, raw) if raw is not None else _MISSING
            if decoded is _MISSING:
                missing.append(key)
            elif decoded[0]:
                found[key] = raw
        if not missing:
            return found
        try:
            cached = self.redis_provider().mget([cache_keys[key] for key in missing])
            if len(cached) != len(missing):
                raise ValueError("Native Redis batch size mismatch")
        except Exception as error:
            LOG.warning("Native record Redis read failed: %s", type(error).__name__)
            cached = [None] * len(missing)
        pending = []
        for key, raw in zip(missing, cached):
            if raw is not None and len(raw) > self.max_record_bytes:
                raw = None
            decoded = self._decode(identity, key, raw) if raw is not None else _MISSING
            if decoded is _MISSING:
                pending.append(key)
            else:
                self._put(cache_keys[key], raw)
                if decoded[0]:
                    found[key] = raw
        if pending:
            with self.database.connection() as db:
                rows = db.execute(
                    "SELECT record_key,payload FROM native_catalog_records "
                    "WHERE revision=%s AND path=%s AND collection=%s AND record_key=ANY(%s)",
                    (identity.revision, identity.path, identity.collection, pending),
                ).fetchall()
            fetched = {row["record_key"]: row["payload"] for row in rows}
            encoded = []
            for key in pending:
                raw = self._encode(identity, key, key in fetched, fetched.get(key))
                decoded = self._decode(identity, key, raw)
                if decoded[0]:
                    found[key] = raw
                self._put(cache_keys[key], raw)
                if (
                    len(raw) <= self.max_record_bytes
                    and len(cache_keys[key].encode()) + len(raw) <= self.redis_max_bytes
                ):
                    encoded.append((cache_keys[key], raw))
            if encoded:
                try:
                    pipe = self.redis_provider().pipeline(transaction=False)
                    for cache_key, raw in encoded:
                        redis_admit(
                            pipe,
                            cache_key,
                            raw,
                            self.ttl,
                            max_bytes=self.redis_max_bytes,
                            max_entries=self.redis_max_entries,
                            max_record_bytes=self.max_record_bytes,
                        )
                    pipe.execute()
                except Exception as error:
                    LOG.warning(
                        "Native record Redis write failed: %s", type(error).__name__
                    )
        return found


class IndexedCollection(Mapping):
    """Lazy complete keyed collection; iteration order is index-key order.

    Arrays keep the importer's identity/suffixed duplicate keys. Original array
    order, unindexed scalar fields and document metadata are not represented.
    `allow_empty` acknowledges that schema082 cannot distinguish an empty source
    collection from an absent/raw-only collection. No such inference is made.
    """

    def __init__(self, catalog, identity):
        self.catalog = catalog
        self.identity = identity

    def __len__(self):
        return self.identity.count

    def __getitem__(self, key):
        key = _record_key(key)
        rows = self.catalog._many(self.identity, [key])
        if key not in rows:
            raise KeyError(key)
        return rows[key]

    def get_many(self, keys):
        result, batch = {}, []
        for key in keys:
            batch.append(_record_key(key))
            if len(batch) == self.catalog.batch_size:
                result.update(self.catalog._many(self.identity, dict.fromkeys(batch)))
                batch.clear()
        if batch:
            result.update(self.catalog._many(self.identity, dict.fromkeys(batch)))
        return result

    def __iter__(self):
        previous = None
        seen = 0
        while True:
            with self.catalog.database.connection() as db:
                rows = db.execute(
                    "SELECT record_key FROM native_catalog_records WHERE revision=%s "
                    "AND path=%s AND collection=%s "
                    'AND (%s::text IS NULL OR record_key COLLATE "C">%s COLLATE "C") '
                    'ORDER BY record_key COLLATE "C" LIMIT %s',
                    (
                        self.identity.revision,
                        self.identity.path,
                        self.identity.collection,
                        previous,
                        previous,
                        self.catalog.batch_size,
                    ),
                ).fetchall()
            if not rows:
                if seen != len(self):
                    raise UnindexedCollection(
                        "Pinned native collection changed during iteration"
                    )
                return
            keys = [row["record_key"] for row in rows]
            # One bounded bulk read warms Redis/local caches for Mapping.items().
            self.catalog._many(self.identity, keys)
            for key in keys:
                seen += 1
                if seen > len(self):
                    raise UnindexedCollection(
                        "Pinned native collection gained indexed rows"
                    )
                yield key
            previous = keys[-1]
