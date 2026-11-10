"""Source-bound LOS derivatives in the existing SQL/Redis compiled publication.

Decode only at the original lazy topology operand. No decoded RAM memo is added.
"""

import base64
from collections.abc import Mapping
import hashlib
import io
import json
import marshal
import re
import sys
import zlib

SCHEMA = "native-los-columns-zlib-marshal-v1"
COLLECTION = "derived.los_columns.v1"
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_DECODED_BYTES = 32 * 1024 * 1024
ABI = (sys.implementation.name, sys.implementation.cache_tag, marshal.version)
_COMPILER_INPUTS = (
    "wakfu_server/storage/prepared_los_compiled.py",
    "wakfu_server/combat/combat_native_los_ray.py",
    "wakfu_server/combat/combat_los_runtime_seal.py",
    "tools/publish_compiled_combat_catalog.py",
)
_FIELDS = frozenset(
    (
        "schema",
        "map_id",
        "source_revision",
        "source_sha256",
        "abi",
        "decoded_bytes",
        "decoded_sha256",
        "columns",
        "payload",
    )
)


class DerivativeUnavailable(ValueError):
    """Use the unchanged authoritative JSON topology path."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _unavailable(reason):
    return {"schema": SCHEMA, "unavailable": reason}


def build_record(source_raw, *, map_id, revision, source_sha256):
    """Offline transformation of one authenticated original map, then release it."""
    from wakfu_server.combat_native_los_ray import prepare_columns
    from wakfu_server.combat_los_runtime_seal import _columns_valid

    if (
        type(map_id) is not int
        or map_id <= 0
        or not _digest(revision)
        or not _digest(source_sha256)
        or _sha(source_raw) != source_sha256
    ):
        raise ValueError("Prepared LOS source identity mismatch")
    try:
        data = json.loads(source_raw)
    except (ValueError, TypeError, OverflowError):
        return _unavailable("unsupported_original_geometry")
    if (
        type(data) is dict
        and "map_id" in data
        and (type(data["map_id"]) is not int or data["map_id"] != map_id)
    ):
        raise ValueError("Prepared LOS source map identity mismatch")
    try:
        columns = prepare_columns(data, map_id)
        if not _columns_valid(columns):
            return _unavailable("unsupported_original_columns")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        # Optional preparation cannot make an unused malformed map mandatory.
        return _unavailable("unsupported_original_geometry")
    raw = marshal.dumps((SCHEMA, map_id, revision, source_sha256, columns), 4)
    if len(raw) > MAX_DECODED_BYTES:
        return _unavailable("decoded_size_limit")
    record = dict(
        schema=SCHEMA,
        map_id=map_id,
        source_revision=revision,
        source_sha256=source_sha256,
        abi=list(ABI),
        decoded_bytes=len(raw),
        decoded_sha256=_sha(raw),
        columns=len(columns),
        payload=base64.b64encode(zlib.compress(raw, 6)).decode("ascii"),
    )
    if len(json.dumps(record, separators=(",", ":")).encode()) > MAX_RECORD_BYTES:
        return _unavailable("redis_record_size_limit")
    return record


def decode_record(raw, *, map_id, revision, source_sha256):
    """The caller must authenticate raw against the compiled record's SQL SHA."""
    if (
        type(raw) is not bytes
        or len(raw) > MAX_RECORD_BYTES
        or type(map_id) is not int
        or map_id <= 0
        or not _digest(revision)
        or not _digest(source_sha256)
    ):
        raise DerivativeUnavailable("Invalid prepared LOS authority or record size")
    try:
        record = json.loads(raw)
        if (
            type(record) is not dict
            or set(record) != _FIELDS
            or record["schema"] != SCHEMA
            or type(record["map_id"]) is not int
            or record["map_id"] != map_id
            or record["source_revision"] != revision
            or record["source_sha256"] != source_sha256
            or type(record["abi"]) is not list
            or len(record["abi"]) != 3
            or tuple(type(v) for v in record["abi"]) != (str, str, int)
            or record["abi"] != list(ABI)
            or type(record["decoded_bytes"]) is not int
            or not 0 < record["decoded_bytes"] <= MAX_DECODED_BYTES
            or not _digest(record["decoded_sha256"])
            or type(record["columns"]) is not int
            or record["columns"] < 0
            or type(record["payload"]) is not str
        ):
            raise ValueError("Prepared LOS scope, format or size mismatch")
        packed = base64.b64decode(record["payload"], validate=True)
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(packed, record["decoded_bytes"] + 1)
        if (
            len(decoded) != record["decoded_bytes"]
            or not inflater.eof
            or inflater.unconsumed_tail
            or inflater.unused_data
            or _sha(decoded) != record["decoded_sha256"]
        ):
            raise ValueError("Prepared LOS compressed payload mismatch")
        stream = io.BytesIO(decoded)
        payload = marshal.load(stream)
        if (
            stream.read(1)
            or type(payload) is not tuple
            or len(payload) != 5
            or payload[:4] != (SCHEMA, map_id, revision, source_sha256)
            or type(payload[1]) is not int
            or type(payload[4]) is not dict
            or len(payload[4]) != record["columns"]
        ):
            raise ValueError("Prepared LOS decoded container mismatch")
        return payload[4]
    except (
        ValueError,
        TypeError,
        KeyError,
        EOFError,
        zlib.error,
        OverflowError,
    ) as error:
        raise DerivativeUnavailable(str(error)) from error


class CompilerRecords(Mapping):
    """One map working set at a time in the normal publisher's spool loop."""

    def __init__(self, identity):
        self.identity = identity
        self.names = {
            int(match[1]): name
            for name in identity["source_documents"]
            if (match := re.fullmatch(r"native-los-topology/([1-9][0-9]*)\.json", name))
        }
        self.maps = tuple(sorted(self.names))

    def __len__(self):
        return len(self.maps)

    def __iter__(self):
        return iter(self.maps)

    def __getitem__(self, map_id):
        from wakfu_server import native_catalog

        name = self.names[map_id]
        revision = self.identity["source_revision"]
        if native_catalog.release() != revision:
            raise ValueError("Native LOS compiler source release changed")
        raw = native_catalog.read_published_bytes(name)
        if native_catalog.release() != revision:
            raise ValueError("Native LOS compiler source release changed")
        return build_record(
            raw,
            map_id=map_id,
            revision=revision,
            source_sha256=self.identity["source_documents"][name],
        )


def compilation_fingerprint(identity):
    """Exact map inputs, independent of unrelated release/compiler changes."""
    sources = identity["compiler_sources"]
    compiler = {name: sources[name] for name in _COMPILER_INPUTS}
    maps = {
        name: checksum
        for name, checksum in identity["source_documents"].items()
        if re.fullmatch(r"native-los-topology/([1-9][0-9]*)\.json", name)
    }
    raw = json.dumps(
        dict(schema=SCHEMA, abi=ABI, compiler=compiler, maps=maps),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return _sha(raw)


def publish_map_collection(spool, identity):
    """Attach authenticated existing map content without loading any map rows."""
    from wakfu_server import native_catalog

    fingerprint = compilation_fingerprint(identity)
    with native_catalog._database().connection() as db:
        storage = db.execute(
            "SELECT relkind FROM pg_class "
            "WHERE oid=to_regclass('native_compiled_catalog_records')"
        ).fetchone()
        row = None
        if storage is not None and storage["relkind"] == "v":
            row = db.execute(
                "SELECT r.manifest->'prepared_los' AS prepared_los,"
                "r.manifest->'collections'->c.collection AS metadata,c.ordered_keys_raw "
                "FROM native_compiled_catalog_releases r "
                "JOIN native_compiled_catalog_collections c USING(generation) "
                "JOIN native_compiled_collection_contents p USING(content_id) "
                "WHERE r.complete AND p.complete AND c.collection=%s "
                "AND r.manifest->'prepared_los'->>'inputs_sha256'=%s "
                "ORDER BY r.created_at DESC LIMIT 1",
                (COLLECTION, fingerprint),
            ).fetchone()
    if row is not None:
        entry = row["prepared_los"]
        metadata = row["metadata"]
        keys = bytes(row["ordered_keys_raw"])
        if (
            entry["schema"] != SCHEMA
            or entry["collection"] != COLLECTION
            or not _digest(entry.get("compiled_source_revision"))
            or metadata["collection"] != COLLECTION
            or _sha(keys) != metadata["ordered_keys_sha256"]
        ):
            raise ValueError("Reusable map collection authority mismatch")
        spool.collections[COLLECTION] = metadata
        spool.keys[COLLECTION] = keys
        return dict(entry), True
    spool.collection(COLLECTION, CompilerRecords(identity))
    return (
        dict(
            schema=SCHEMA,
            collection=COLLECTION,
            inputs_sha256=fingerprint,
            compiled_source_revision=identity["source_revision"],
        ),
        False,
    )


class NoRetentionBytes:
    """Operation-local backend adapter: Redis holds reusable derivative bytes."""

    __slots__ = ()

    def get(self, key):
        return None

    def put(self, key, raw):
        return None


def published_columns(map_id):
    """Optional derivative; all authoritative source failures remain in fallback."""
    if type(map_id) is not int or map_id <= 0:
        return None
    try:
        from wakfu_server import native_catalog
        from wakfu_server.native_compiled_catalog import (
            CompiledCatalogBackend,
            descriptor_for,
            resolve_publication,
        )

        revision = native_catalog.release()
        publication = resolve_publication(source_revision=revision)
        name = f"native-los-topology/{map_id}.json"
        source_sha = publication.get("source_documents", {}).get(name)
        entry = publication.get("prepared_los")
        if type(entry) is not dict or not _digest(source_sha):
            return None
        legacy_entry = {"schema": SCHEMA, "collection": COLLECTION}
        compiled_revision = revision
        if entry != legacy_entry:
            if (
                set(entry)
                != set(legacy_entry) | {"inputs_sha256", "compiled_source_revision"}
                or entry.get("schema") != SCHEMA
                or entry.get("collection") != COLLECTION
                or not _digest(entry.get("compiled_source_revision"))
                or not _digest(entry.get("inputs_sha256"))
            ):
                return None
            # The authenticated manifest binds the offline reuse decision.
            # Verify this map's current source hash below; do not rehash the
            # complete map/compiler inventories on every topology cache miss.
            compiled_revision = entry["compiled_source_revision"]
        if not _digest(compiled_revision):
            return None
        descriptor = descriptor_for(publication, COLLECTION)
        if native_catalog.release() != revision:
            return None
        # Initial resolve already fenced the selected generation; backend SQL
        # verifies this descriptor, and the final resolve detects cutover.
        # Match the normal backend's defaults/providers, changing only retention.
        backend = CompiledCatalogBackend(
            native_catalog._database, native_catalog._redis, cache=NoRetentionBytes()
        )
        collection = backend.collection(descriptor)
        raw = collection.record_bytes(map_id)
        columns = decode_record(
            raw, map_id=map_id, revision=compiled_revision, source_sha256=source_sha
        )
        if native_catalog.release() != revision:
            return None
        current = resolve_publication(source_revision=revision)
        if descriptor["revision"] != current["generation"]:
            return None
        return columns, revision, source_sha
    except Exception:
        # This new optional read cannot suppress errors from the old JSON path.
        return None
