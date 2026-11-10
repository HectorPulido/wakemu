"""Replace repeated compiled byte bodies with immutable shared payloads."""

import argparse
import json
import os
import time
import uuid

from psycopg import sql

from wakfu_server.compiled_body_storage import collect_unreferenced_bodies, enabled
from wakfu_server.compiled_catalog_retention import MAINTENANCE_LOCK


def _restore_view_access(db, table):
    from tools.compact_native_catalog import _restore_table_access

    # PostgreSQL accepts the shared ALTER TABLE owner/grant syntax for views.
    _restore_table_access(db, table)


def compact(database):
    """Authenticate old records and atomically rebind existing reader views."""
    from tools.compact_native_catalog import _replacement_metadata

    began = time.monotonic()
    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(" + MAINTENANCE_LOCK + ")")
        if enabled(db):
            return dict(
                compacted=False,
                removed_bodies=collect_unreferenced_bodies(db),
            )
        kind = db.execute(
            "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
        ).fetchone()["relkind"]
        if kind != "v":
            raise RuntimeError(
                "Compact legacy compiled publications before body storage"
            )
        tables, views = _replacement_metadata(db, ("native_compiled_content_records",))
        table = tables[0]
        if (
            db.execute(
                "SELECT 1 FROM pg_constraint WHERE confrelid=%s AND contype='f' LIMIT 1",
                (table["oid"],),
            ).fetchone()
            is not None
        ):
            raise RuntimeError(
                "A foreign key references legacy compiled record storage"
            )
        db.execute("LOCK TABLE native_compiled_content_records IN SHARE MODE")
        if (
            db.execute(
                "SELECT 1 FROM native_compiled_content_records "
                "WHERE encode(sha256(raw),'hex')<>sha256 LIMIT 1"
            ).fetchone()
            is not None
        ):
            raise ValueError("Legacy compiled record checksum mismatch")
        if (
            db.execute("SELECT 1 FROM native_compiled_record_links LIMIT 1").fetchone()
            is not None
        ):
            raise RuntimeError(
                "Shared compiled record mappings already contain staged rows"
            )
        db.execute(
            "INSERT INTO native_compiled_record_bodies(sha256,raw,source_bytes) "
            "SELECT decode(r.sha256,'hex'),r.raw,octet_length(r.raw) "
            "FROM (SELECT DISTINCT ON(sha256) sha256,raw "
            "FROM native_compiled_content_records ORDER BY sha256) r "
            "ORDER BY r.sha256 ON CONFLICT(sha256) DO NOTHING"
        )
        if (
            db.execute(
                "SELECT 1 FROM native_compiled_content_records r "
                "JOIN native_compiled_record_bodies b ON b.sha256=decode(r.sha256,'hex') "
                "WHERE b.raw<>r.raw OR b.source_bytes<>octet_length(r.raw) LIMIT 1"
            ).fetchone()
            is not None
        ):
            raise ValueError("Shared compiled record body differs from legacy bytes")
        # Completed legacy collections are immutable. The exclusive maintenance
        # lock excludes publishers while their verified ownership links are copied.
        db.execute(
            "ALTER TABLE native_compiled_record_links DISABLE TRIGGER native_compiled_record_link_immutable"
        )
        copied = db.execute(
            "INSERT INTO native_compiled_record_links(content_id,record_key,ordinal,body_id) "
            "SELECT r.content_id,r.record_key,r.ordinal,b.body_id "
            "FROM native_compiled_content_records r JOIN native_compiled_record_bodies b "
            "ON b.sha256=decode(r.sha256,'hex')"
        ).rowcount
        db.execute(
            "ALTER TABLE native_compiled_record_links ENABLE TRIGGER native_compiled_record_link_immutable"
        )
        expected = db.execute(
            "SELECT count(*) AS n FROM native_compiled_content_records"
        ).fetchone()["n"]
        if copied != expected:
            raise ValueError("Compiled mapping count differs after body compaction")
        bodies = db.execute(
            "SELECT count(*) AS n FROM native_compiled_record_bodies"
        ).fetchone()["n"]
        db.execute("SET LOCAL lock_timeout='15s'")
        retired = "native_compiled_content_records_retired_" + uuid.uuid4().hex[:10]
        db.execute(
            sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                sql.Identifier(table["schema"], table["name"]), sql.Identifier(retired)
            )
        )
        db.execute(
            "CREATE VIEW native_compiled_content_records AS "
            "SELECT l.content_id,l.record_key,l.ordinal,b.raw,encode(b.sha256,'hex') AS sha256 "
            "FROM native_compiled_record_links l JOIN native_compiled_record_bodies b USING(body_id)"
        )
        _restore_view_access(db, table)
        # View rewrite checks backing reads as the preserved view owner. Keep
        # those privileges narrow; ordinary granted readers/writers still only
        # access the compatibility interface.
        db.execute(
            sql.SQL(
                "GRANT SELECT ON native_compiled_record_links,native_compiled_record_bodies TO {}"
            ).format(sql.Identifier(table["owner"]))
        )
        for view in views:
            db.execute(
                sql.SQL("CREATE OR REPLACE VIEW {} AS ").format(
                    sql.Identifier(view["schema"], view["name"])
                )
                + sql.SQL(view["definition"])
            )
        db.execute(
            "CREATE TRIGGER native_compiled_content_record_write "
            "INSTEAD OF INSERT OR UPDATE OR DELETE ON native_compiled_content_records "
            "FOR EACH ROW EXECUTE FUNCTION write_native_compiled_content_record()"
        )
        db.execute(
            sql.SQL("DROP TABLE {}").format(sql.Identifier(table["schema"], retired))
        )
        db.execute("ANALYZE native_compiled_record_bodies")
        db.execute("ANALYZE native_compiled_record_links")
        result = dict(
            compacted=True,
            mappings=copied,
            bodies=bodies,
            seconds=round(time.monotonic() - began, 3),
        )
    print(
        json.dumps(dict(event="compiled_body_compaction_committed", **result)),
        flush=True,
    )
    return result


def main():
    from wakfu_server.postgres import Database

    argparse.ArgumentParser(description=__doc__).parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        print(json.dumps(compact(database)), flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()
