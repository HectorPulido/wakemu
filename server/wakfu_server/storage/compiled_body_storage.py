"""Exact immutable record bytes shared by compact, independently owned links."""

from wakfu_server.compiled_catalog_retention import MAINTENANCE_LOCK


def enabled(db):
    row = db.execute(
        "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_content_records')"
    ).fetchone()
    return row is not None and row["relkind"] == "v"


def publish_records(db, content_id, records):
    """COPY one new collection, authenticate its bytes, then intern bodies in bulk."""
    db.execute("SELECT pg_advisory_xact_lock_shared(" + MAINTENANCE_LOCK + ")")
    db.execute(
        "CREATE TEMP TABLE IF NOT EXISTS compiled_body_stage ("
        "record_key text PRIMARY KEY,ordinal integer NOT NULL UNIQUE CHECK(ordinal>=0),"
        "raw bytea NOT NULL,sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$')) "
        "ON COMMIT DROP"
    )
    db.execute("TRUNCATE compiled_body_stage")
    count = 0
    with db.cursor().copy(
        "COPY compiled_body_stage(record_key,ordinal,raw,sha256) FROM STDIN (FORMAT BINARY)"
    ) as copy:
        copy.set_types(["text", "int4", "bytea", "text"])
        for row in records:
            copy.write_row(row)
            count += 1
    if (
        db.execute(
            "SELECT 1 FROM compiled_body_stage WHERE encode(sha256(raw),'hex')<>sha256 LIMIT 1"
        ).fetchone()
        is not None
    ):
        raise ValueError("Compiled record body checksum mismatch during publication")
    # Stable lock order also allows simultaneous different collections to share
    # newly encountered bodies without unique-index lock-order inversions.
    db.execute(
        "INSERT INTO native_compiled_record_bodies(sha256,raw,source_bytes) "
        "SELECT decode(s.sha256,'hex'),s.raw,octet_length(s.raw) "
        "FROM (SELECT DISTINCT ON(sha256) sha256,raw FROM compiled_body_stage "
        "ORDER BY sha256) s ORDER BY s.sha256 ON CONFLICT(sha256) DO NOTHING"
    )
    if (
        db.execute(
            "SELECT 1 FROM compiled_body_stage s JOIN native_compiled_record_bodies b "
            "ON b.sha256=decode(s.sha256,'hex') "
            "WHERE b.source_bytes<>octet_length(s.raw) OR b.raw<>s.raw LIMIT 1"
        ).fetchone()
        is not None
    ):
        raise ValueError("Compiled record body conflicts with stored bytes")
    result = db.execute(
        "INSERT INTO native_compiled_record_links(content_id,record_key,ordinal,body_id) "
        "SELECT %s,s.record_key,s.ordinal,b.body_id FROM compiled_body_stage s "
        "JOIN native_compiled_record_bodies b ON b.sha256=decode(s.sha256,'hex')",
        (content_id,),
    )
    if result.rowcount != count:
        raise ValueError("Compiled body mapping count differs after COPY")
    return count


def collect_unreferenced_bodies(db):
    """Call under the exclusive publication maintenance lock after link removal."""
    db.execute("SET LOCAL wakemu.compiled_catalog_maintenance='on'")
    return db.execute(
        "DELETE FROM native_compiled_record_bodies b WHERE NOT EXISTS("
        "SELECT 1 FROM native_compiled_record_links l WHERE l.body_id=b.body_id)"
    ).rowcount
