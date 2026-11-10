"""Exact source-body sharing and bounded verified native index-set writers."""

from contextlib import contextmanager
import hashlib
from itertools import chain
import json
import struct
import uuid

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

MAINTENANCE_LOCK = (
    "hashtextextended(current_database()||':'||current_schema()||"
    "':native_catalog_maintenance',0)"
)
INDEX_FINGERPRINT_PREFIX = b"wakemu.native-jsonb-index.v1\0"


def _one(db, query, parameters=()):
    with db.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, parameters).fetchone()


def _all(db, query, parameters=()):
    with db.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, parameters).fetchall()


def _write_lock(db):
    db.execute("SELECT pg_advisory_xact_lock_shared(" + MAINTENANCE_LOCK + ")")


def _require_staging(db, revision):
    row = _one(
        db,
        "SELECT complete FROM native_catalog_releases WHERE revision=%s FOR UPDATE",
        (revision,),
    )
    if row is None:
        raise FileNotFoundError("Native release does not exist")
    if row["complete"]:
        raise ValueError("Published native catalog is immutable")


def shared_storage(db):
    row = _one(
        db,
        "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_catalog_documents')",
    )
    return row is not None and row["relkind"] == "v"


def index_digest(db, index_set_id=None, *, revision=None, path=None):
    """Hash actual typed JSONB values in deterministic collection/key order.

    Hashing JSONB's text representation in PostgreSQL preserves distinctions
    such as integer 1 versus numeric 1.0 without decoding a whole source body.
    Only two bounded strings and a 32-byte value digest cross the connection.
    """
    digest = hashlib.sha256(INDEX_FINGERPRINT_PREFIX)
    count = 0
    if index_set_id is not None:
        query = (
            "SELECT c.name AS collection,r.record_key,"
            "pg_catalog.sha256(convert_to(r.payload::text,'UTF8')) AS payload_sha "
            "FROM native_catalog_index_records r JOIN native_catalog_collections c USING(collection_id) "
            'WHERE r.index_set_id=%s ORDER BY c.name COLLATE "C",r.record_key COLLATE "C"'
        )
        parameters = (index_set_id,)
    else:
        query = (
            "SELECT collection,record_key,"
            "pg_catalog.sha256(convert_to(payload::text,'UTF8')) AS payload_sha "
            "FROM native_catalog_records WHERE revision=%s AND path=%s "
            'ORDER BY collection COLLATE "C",record_key COLLATE "C"'
        )
        parameters = (revision, path)
    with db.cursor(
        name="native_index_digest_" + uuid.uuid4().hex, row_factory=dict_row
    ) as cursor:
        cursor.itersize = 4096
        cursor.execute(query, parameters)
        for row in cursor:
            for name in ("collection", "record_key"):
                value = row[name].encode("utf8")
                digest.update(struct.pack(">I", len(value)))
                digest.update(value)
            digest.update(bytes(row["payload_sha"]))
            count += 1
    return digest.digest(), count


def finalize_document(db, revision, path, count=None):
    """Seal and share an actual index set, never a guessed source/count match."""
    _write_lock(db)
    if not shared_storage(db):
        return None
    row = _one(
        db,
        "SELECT d.index_set_id,d.record_count,s.sealed,s.records_sha256,s.record_count AS actual_count "
        "FROM native_catalog_document_links d JOIN native_catalog_index_sets s USING(index_set_id) "
        "WHERE d.revision=%s AND d.path=%s FOR UPDATE OF d",
        (revision, path),
    )
    if row is None:
        raise FileNotFoundError("Native document does not exist")
    declared = row["record_count"]
    if count is not None and count != declared:
        raise ValueError("Native document count differs from writer count")
    if row["sealed"] and row["records_sha256"] is not None:
        if row["actual_count"] != declared:
            raise ValueError("Native document count differs from sealed index")
        return row["index_set_id"]
    checksum, actual = index_digest(db, row["index_set_id"])
    if actual != declared:
        raise ValueError("Native index count differs from its document")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("native_index_content:" + checksum.hex(),),
    )
    existing = _one(
        db,
        "SELECT index_set_id FROM native_catalog_index_sets "
        "WHERE records_sha256=%s AND record_count=%s AND sealed",
        (checksum, actual),
    )
    if existing is not None and existing["index_set_id"] != row["index_set_id"]:
        # Every reference gets the verified replacement. No body or logical
        # record changes, and snapshots retain their ordinary MVCC visibility.
        db.execute(
            "UPDATE native_catalog_document_links SET index_set_id=%s WHERE index_set_id=%s",
            (existing["index_set_id"], row["index_set_id"]),
        )
        return existing["index_set_id"]
    db.execute(
        "UPDATE native_catalog_index_sets SET record_count=%s,records_sha256=%s,sealed=true "
        "WHERE index_set_id=%s",
        (actual, checksum, row["index_set_id"]),
    )
    return row["index_set_id"]


def seal_release(db, revision):
    _write_lock(db)
    if not shared_storage(db):
        return
    rows = _all(
        db,
        "SELECT d.path FROM native_catalog_document_links d "
        "JOIN native_catalog_index_sets s USING(index_set_id) "
        "WHERE d.revision=%s AND (NOT s.sealed OR s.records_sha256 IS NULL) ORDER BY d.path",
        (revision,),
    )
    for row in rows:
        finalize_document(db, revision, row["path"])


def copy_records(db, revision, path, records):
    """COPY one bounded record stream into either physical storage layout."""
    _write_lock(db)
    rows = iter(records)
    exhausted = object()
    first = next(rows, exhausted)
    if first is exhausted:
        return 0
    rows = chain((first,), rows)
    if not shared_storage(db):
        count = 0
        with db.cursor().copy(
            "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
        ) as copy:
            for collection, key, payload in rows:
                copy.write_row(
                    (
                        revision,
                        path,
                        collection,
                        key,
                        payload if isinstance(payload, Jsonb) else Jsonb(payload),
                    )
                )
                count += 1
        return count
    selected_set = _one(
        db, "SELECT native_shared_mutable_set(%s,%s) AS id", (revision, path)
    )["id"]
    db.execute(
        "CREATE TEMP TABLE IF NOT EXISTS wakemu_native_record_stage "
        "(collection text,record_key text,payload jsonb) ON COMMIT DROP"
    )
    db.execute("TRUNCATE pg_temp.wakemu_native_record_stage")
    count = 0
    with db.cursor().copy(
        "COPY pg_temp.wakemu_native_record_stage(collection,record_key,payload) FROM STDIN"
    ) as copy:
        for collection, key, payload in rows:
            copy.write_row(
                (
                    collection,
                    key,
                    payload if isinstance(payload, Jsonb) else Jsonb(payload),
                )
            )
            count += 1
    db.execute(
        "INSERT INTO native_catalog_collections(name) SELECT DISTINCT collection "
        "FROM pg_temp.wakemu_native_record_stage ON CONFLICT(name) DO NOTHING"
    )
    db.execute(
        "INSERT INTO native_catalog_index_records(index_set_id,collection_id,record_key,payload) "
        "SELECT %s,c.collection_id,r.record_key,r.payload FROM pg_temp.wakemu_native_record_stage r "
        "JOIN native_catalog_collections c ON c.name=r.collection",
        (selected_set,),
    )
    db.execute("TRUNCATE pg_temp.wakemu_native_record_stage")
    return count


def clone_documents(
    db, target_revision, source_revision, exclude_paths=(), only_paths=None
):
    """Reuse source/index links; the legacy fallback preserves old COPY tools."""
    _write_lock(db)
    conditions = "revision=%s AND NOT(path=ANY(%s))"
    parameters = [source_revision, list(exclude_paths)]
    if only_paths is not None:
        conditions += " AND path=ANY(%s)"
        parameters.append(list(only_paths))
    if shared_storage(db):
        _require_staging(db, target_revision)
        for row in _all(
            db,
            "SELECT d.path FROM native_catalog_document_links d JOIN native_catalog_index_sets s USING(index_set_id) WHERE "
            + conditions
            + " AND (NOT s.sealed OR s.records_sha256 IS NULL)",
            parameters,
        ):
            finalize_document(db, source_revision, row["path"])
        result = db.execute(
            "INSERT INTO native_catalog_document_links(revision,path,body_id,index_set_id,record_count) "
            "SELECT %s,path,body_id,index_set_id,record_count FROM native_catalog_document_links WHERE "
            + conditions,
            [target_revision, *parameters],
        )
    else:
        result = db.execute(
            "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
            "SELECT %s,path,raw,sha256,source_bytes,record_count FROM native_catalog_documents WHERE "
            + conditions,
            [target_revision, *parameters],
        )
        db.execute(
            "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) "
            "SELECT %s,path,collection,record_key,payload FROM native_catalog_records WHERE "
            + conditions,
            [target_revision, *parameters],
        )
    db.execute(
        "INSERT INTO native_catalog_document_index_contracts(revision,path,contract_sha256) "
        "SELECT %s,path,contract_sha256 FROM native_catalog_document_index_contracts WHERE "
        + conditions
        + " ON CONFLICT(revision,path) DO NOTHING",
        [target_revision, *parameters],
    )
    return result.rowcount


def store_raw_document(db, revision, path, source, checksum, size):
    """Store a verified bytea stream without materializing its Python bytes."""
    _write_lock(db)
    if not shared_storage(db):
        from tools.native_catalog_streaming import copy_raw_document

        return copy_raw_document(db, revision, path, source, checksum, size)
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise ValueError("Invalid native source checksum")
    _require_staging(db, revision)
    expected = bytes.fromhex(checksum)
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("native_source_body:" + checksum,),
    )
    body = _one(
        db,
        "SELECT body_id,source_bytes FROM native_catalog_bodies WHERE sha256=%s",
        (expected,),
    )
    source.seek(0)
    if body is None:
        body_id = _one(
            db,
            "SELECT nextval(pg_get_serial_sequence('native_catalog_bodies','body_id')) AS id",
        )["id"]
        with db.cursor().copy(
            "COPY native_catalog_bodies(body_id,sha256,raw,source_bytes) FROM STDIN (FORMAT BINARY)"
        ) as copy:
            copy.write(b"PGCOPY\n\xff\r\n\0" + struct.pack(">ii", 0, 0))
            copy.write(struct.pack(">h", 4))
            copy.write(struct.pack(">iq", 8, body_id))
            copy.write(struct.pack(">i", 32) + expected)
            copy.write(struct.pack(">i", size))
            actual = 0
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                copy.write(chunk)
                actual += len(chunk)
            if actual != size:
                raise ValueError("Native source snapshot size changed")
            copy.write(struct.pack(">iq", 8, size))
            copy.write(struct.pack(">h", -1))
    else:
        if body["source_bytes"] != size:
            raise ValueError("Native source identity collision")
        digest = hashlib.sha256()
        actual = 0
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            actual += len(chunk)
        if actual != size or digest.digest() != expected:
            raise ValueError("Native source snapshot checksum changed")
        body_id = body["body_id"]
    selected_set = _one(
        db,
        "INSERT INTO native_catalog_index_sets DEFAULT VALUES RETURNING index_set_id",
    )["index_set_id"]
    db.execute(
        "INSERT INTO native_catalog_document_links VALUES(%s,%s,%s,%s,0)",
        (revision, path, body_id, selected_set),
    )
    source.seek(0)
    return body_id


def garbage_collect(db):
    """Delete only unreferenced immutable storage under the maintenance lock."""
    db.execute("SET LOCAL wakemu.native_catalog_maintenance='on'")
    sets = db.execute(
        "DELETE FROM native_catalog_index_sets s WHERE NOT EXISTS("
        "SELECT 1 FROM native_catalog_document_links d WHERE d.index_set_id=s.index_set_id)"
    ).rowcount
    bodies = db.execute(
        "DELETE FROM native_catalog_bodies b WHERE NOT EXISTS("
        "SELECT 1 FROM native_catalog_document_links d WHERE d.body_id=b.body_id)"
    ).rowcount
    return dict(removed_index_sets=sets, removed_bodies=bodies)
