"""Compact derived catalogs and retain current readers plus two recent releases.

Only immutable, reproducible compiled catalog relations are modified. Player
and original source catalog tables are never rewritten by this tool.
"""

import argparse
import hashlib
import json
import os
import time

from wakfu_server.compiled_catalog_retention import (
    MAINTENANCE_LOCK,
    delete_publications,
    retained_publications,
)


def _log(event, **fields):
    print(json.dumps(dict(event=event, **fields)), flush=True)


def _verify_content(db, content_id, metadata):
    """Stream one copy and verify the complete preexisting manifest contract."""
    from tools.publish_compiled_combat_catalog import ordered_bytes

    content = hashlib.sha256()
    keys = hashlib.sha256(b"[")
    count = 0
    with db.cursor(name="verify_compiled_content") as cursor:
        cursor.itersize = 256
        cursor.execute(
            "SELECT record_key,ordinal,raw,sha256 FROM native_compiled_content_records "
            "WHERE content_id=%s ORDER BY ordinal",
            (content_id,),
        )
        for row in cursor:
            key = json.loads(row["record_key"])
            if (
                row["ordinal"] != count
                or ordered_bytes(key).decode() != row["record_key"]
                or hashlib.sha256(bytes(row["raw"])).hexdigest() != row["sha256"]
            ):
                raise ValueError("Invalid compiled content bytes/key/ordinal")
            content.update(ordered_bytes([key, count, row["sha256"]]) + b"\n")
            if count:
                keys.update(b",")
            keys.update(ordered_bytes(key))
            count += 1
    keys.update(b"]")
    if (
        count != metadata["count"]
        or keys.hexdigest() != metadata["ordered_keys_sha256"]
        or content.hexdigest() != metadata["records_sha256"]
    ):
        raise ValueError("Compiled collection differs from its release manifest")


def compact(database, *, keep=(), retain=2):
    began = time.monotonic()
    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(" + MAINTENANCE_LOCK + ")")
        retained, removed = retained_publications(db, keep=keep, retain=retain)
        kind = db.execute(
            "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
        ).fetchone()["relkind"]
        if kind == "v":
            unused = delete_publications(db, removed)
            return dict(
                retained=retained,
                removed=removed,
                removed_contents=unused,
                compacted=False,
            )
        if kind != "r":
            raise RuntimeError("Unknown compiled catalog storage relation")
        rows = db.execute(
            "SELECT c.*,r.manifest->'collections'->c.collection AS metadata "
            "FROM native_compiled_catalog_collections c "
            "JOIN native_compiled_catalog_releases r USING(generation) "
            "WHERE c.generation=ANY(%s) ORDER BY c.generation,c.collection",
            (retained,),
        ).fetchall()
        identities = {}
        links = []
        copied = 0
        for row in rows:
            metadata = row["metadata"]
            identity = (
                row["collection"],
                metadata["kind"],
                metadata["representation"],
                metadata["count"],
                metadata["ordered_keys_sha256"],
                metadata["records_sha256"],
            )
            content_id = identities.get(identity)
            if content_id is None:
                content_id = db.execute(
                    "INSERT INTO native_compiled_collection_contents "
                    "(collection,kind,representation,record_count,ordered_keys_sha256,records_sha256) "
                    "VALUES(%s,%s,%s,%s,%s,%s) RETURNING content_id",
                    identity,
                ).fetchone()["content_id"]
                db.execute(
                    "INSERT INTO native_compiled_content_records "
                    "(content_id,record_key,ordinal,raw,sha256) "
                    "SELECT %s,record_key,ordinal,raw,sha256 FROM native_compiled_catalog_records "
                    "WHERE generation=%s AND collection=%s ORDER BY ordinal",
                    (content_id, row["generation"], row["collection"]),
                )
                _verify_content(db, content_id, metadata)
                db.execute(
                    "UPDATE native_compiled_collection_contents SET complete=true WHERE content_id=%s",
                    (content_id,),
                )
                identities[identity] = content_id
                copied += metadata["count"]
                _log(
                    "collection_compacted",
                    collection=row["collection"],
                    records=metadata["count"],
                    total_records=copied,
                )
            links.append((content_id, row["generation"], row["collection"]))
        # Only the legacy immutability trigger is disabled; the new content
        # reference validator checks each attachment against its manifest.
        db.execute(
            "ALTER TABLE native_compiled_catalog_collections DISABLE TRIGGER native_compiled_catalog_collection_immutable"
        )
        with db.cursor() as cursor:
            cursor.executemany(
                "UPDATE native_compiled_catalog_collections SET content_id=%s "
                "WHERE generation=%s AND collection=%s",
                links,
            )
        db.execute(
            "ALTER TABLE native_compiled_catalog_collections ENABLE TRIGGER native_compiled_catalog_collection_immutable"
        )
        # All copied bytes have been authenticated before dropping the old
        # relation. The transaction rolls back both DDL and attachments on error.
        db.execute("SET LOCAL lock_timeout='15s'")
        db.execute("DROP TABLE native_compiled_catalog_records")
        db.execute(
            "CREATE VIEW native_compiled_catalog_records AS "
            "SELECT c.generation,c.collection,r.record_key,r.ordinal,r.raw,r.sha256 "
            "FROM native_compiled_catalog_collections c "
            "JOIN native_compiled_content_records r USING(content_id)"
        )
        unused = delete_publications(db, removed)
        db.execute("ANALYZE native_compiled_content_records")
        db.execute("ANALYZE native_compiled_catalog_collections")
        result = dict(
            retained=retained,
            removed=removed,
            removed_contents=unused,
            compacted=True,
            contents=len(identities),
            records=copied,
            seconds=round(time.monotonic() - began, 2),
        )
    _log("catalog_compaction_committed", **result)
    return result


def main():
    from wakfu_server.postgres import Database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="append", default=[])
    parser.add_argument("--retain", type=int, default=2)
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        result = compact(database, keep=args.keep, retain=args.retain)
        _log("catalog_retention_complete", **result)
    finally:
        database.close()


if __name__ == "__main__":
    main()
