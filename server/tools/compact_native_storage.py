"""Convert exact native source bodies/index sets to shared integer identities."""

import argparse
import json
import os
import uuid

from psycopg import sql
from psycopg.rows import dict_row

from wakfu_server.native_shared_storage import (
    MAINTENANCE_LOCK,
    _all,
    _one,
    finalize_document,
    garbage_collect,
    index_digest,
    shared_storage,
)


def _log(event, **fields):
    print(json.dumps(dict(event=event, **fields)), flush=True)


def compact(database, *, keep=(), retain=2):
    """Authenticate legacy records before sharing; rollback restores every OID."""
    from tools.compact_native_catalog import (
        _replacement_metadata,
        _restore_table_access,
        archive_revisions,
        plan_retention,
    )

    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(" + MAINTENANCE_LOCK + ")")
        db.execute("SET LOCAL application_name='wakemu-native-storage-maintenance'")
        db.execute("LOCK TABLE native_catalog_releases IN SHARE ROW EXCLUSIVE MODE")
        known, retained, removed = plan_retention(db, keep=keep, retain=retain)
        if shared_storage(db):
            archive_revisions(db, known, removed)
            db.execute(
                "DELETE FROM native_catalog_document_index_contracts WHERE revision=ANY(%s)",
                (removed,),
            )
            db.execute(
                "DELETE FROM native_catalog_document_links WHERE revision=ANY(%s)",
                (removed,),
            )
            rows = _all(
                db,
                "SELECT DISTINCT ON(d.index_set_id) d.revision,d.path "
                "FROM native_catalog_document_links d JOIN native_catalog_index_sets s USING(index_set_id) "
                "JOIN native_catalog_releases r ON r.revision=d.revision "
                "WHERE r.complete AND (NOT s.sealed OR s.records_sha256 IS NULL) "
                "ORDER BY d.index_set_id,d.revision,d.path",
            )
            for row in rows:
                finalize_document(db, row["revision"], row["path"])
            result = dict(
                compacted=False,
                retained=retained,
                retired=removed,
                authenticated_sets=len(rows),
                **garbage_collect(db)
            )
            return result
        db.execute(
            "LOCK TABLE native_catalog_documents,native_catalog_records IN SHARE MODE"
        )
        originals = ("native_catalog_documents", "native_catalog_records")
        tables, views = _replacement_metadata(db, originals)
        # Foreign keys into these two public interfaces must be understood
        # before any copy. Contract stamps move to the retained logical links.
        foreign_keys = _all(
            db,
            "SELECT c.conrelid AS relation_oid,n.nspname AS relation_schema,t.relname AS relation_name,"
            "c.conname,c.confrelid FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
            "JOIN pg_namespace n ON n.oid=t.relnamespace "
            "WHERE c.contype='f' AND c.confrelid=ANY(%s)",
            ([table["oid"] for table in tables],),
        )
        contract_oid = _one(
            db, "SELECT 'native_catalog_document_index_contracts'::regclass::oid AS oid"
        )["oid"]
        allowed_oids = {table["oid"] for table in tables} | {contract_oid}
        for reference in foreign_keys:
            if reference["relation_oid"] not in allowed_oids:
                raise RuntimeError(
                    "A foreign key references the native physical tables; preserve it before conversion"
                )
        if (
            _one(
                db,
                "SELECT 1 FROM native_catalog_documents WHERE revision=ANY(%s) AND (sha256 !~ '^[0-9a-f]{64}$' "
                "OR source_bytes<>octet_length(raw) OR encode(pg_catalog.sha256(raw),'hex')<>sha256) LIMIT 1",
                (retained,),
            )
            is not None
        ):
            raise ValueError("Native source document checksum/size mismatch")
        archive_revisions(db, known, removed)
        db.execute(
            "INSERT INTO native_catalog_bodies(sha256,raw,source_bytes) "
            "SELECT DISTINCT ON(sha256) decode(sha256,'hex'),raw,source_bytes "
            "FROM native_catalog_documents WHERE revision=ANY(%s) ORDER BY sha256",
            (retained,),
        )
        bodies = {
            bytes(row["sha256"]): row["body_id"]
            for row in _all(db, "SELECT body_id,sha256 FROM native_catalog_bodies")
        }
        db.execute(
            "INSERT INTO native_catalog_collections(name) "
            "SELECT DISTINCT collection FROM native_catalog_records WHERE revision=ANY(%s) ON CONFLICT(name) DO NOTHING",
            (retained,),
        )
        documents = _all(
            db,
            "SELECT revision,path,sha256,source_bytes,record_count FROM native_catalog_documents "
            'WHERE revision=ANY(%s) ORDER BY path COLLATE "C",revision COLLATE "C"',
            (retained,),
        )
        identities = {}
        links = []
        logical_records = physical_records = 0
        for offset, document in enumerate(documents, 1):
            complete = known[document["revision"]]["complete"]
            if complete:
                checksum, count = index_digest(
                    db, revision=document["revision"], path=document["path"]
                )
            else:
                # Legacy tools can commit a raw document before its index COPY.
                # Preserve that resumable state without publishing or sharing it.
                checksum = None
                count = _one(
                    db,
                    "SELECT count(*) AS n FROM native_catalog_records "
                    "WHERE revision=%s AND path=%s",
                    (document["revision"], document["path"]),
                )["n"]
            if complete and count != document["record_count"]:
                raise ValueError(
                    "Native index count differs from its original source document"
                )
            identity = (checksum, count)
            index_set_id = identities.get(identity) if complete else None
            if index_set_id is None:
                index_set_id = _one(
                    db,
                    "INSERT INTO native_catalog_index_sets DEFAULT VALUES RETURNING index_set_id",
                )["index_set_id"]
                written = db.execute(
                    "INSERT INTO native_catalog_index_records(index_set_id,collection_id,record_key,payload) "
                    "SELECT %s,c.collection_id,r.record_key,r.payload FROM native_catalog_records r "
                    "JOIN native_catalog_collections c ON c.name=r.collection "
                    "WHERE r.revision=%s AND r.path=%s",
                    (index_set_id, document["revision"], document["path"]),
                ).rowcount
                if written != count:
                    raise ValueError("Native index count changed during conversion")
                db.execute(
                    "UPDATE native_catalog_index_sets SET record_count=%s,records_sha256=%s,sealed=%s "
                    "WHERE index_set_id=%s",
                    (count, checksum, complete, index_set_id),
                )
                if complete:
                    identities[identity] = index_set_id
                physical_records += count
            links.append(
                (
                    document["revision"],
                    document["path"],
                    bodies[bytes.fromhex(document["sha256"])],
                    index_set_id,
                    document["record_count"],
                )
            )
            logical_records += count
            if offset % 500 == 0:
                _log(
                    "native_storage_authenticated",
                    documents=offset,
                    total=len(documents),
                    logical_records=logical_records,
                    physical_records=physical_records,
                )
        with db.cursor().copy(
            "COPY native_catalog_document_links(revision,path,body_id,index_set_id,record_count) FROM STDIN"
        ) as copy:
            for row in links:
                copy.write_row(row)
        # Check new logical coverage before atomically rebinding public names.
        coverage = _one(
            db,
            "SELECT count(*) AS documents,coalesce(sum(s.record_count),0) AS records "
            "FROM native_catalog_document_links d JOIN native_catalog_index_sets s USING(index_set_id)",
        )
        if (
            coverage["documents"] != len(documents)
            or coverage["records"] != logical_records
        ):
            raise ValueError("Shared native source coverage differs before cutover")
        db.execute("SET LOCAL lock_timeout='15s'")
        db.execute(
            "DELETE FROM native_catalog_document_index_contracts WHERE revision=ANY(%s)",
            (removed,),
        )
        for reference in foreign_keys:
            if reference["relation_oid"] == contract_oid:
                db.execute(
                    sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                        sql.Identifier(
                            reference["relation_schema"], reference["relation_name"]
                        ),
                        sql.Identifier(reference["conname"]),
                    )
                )
        suffix = uuid.uuid4().hex[:12]
        for table in tables:
            table["retired_name"] = table["name"] + "_legacy_" + suffix
            db.execute(
                sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                    sql.Identifier(table["schema"], table["name"]),
                    sql.Identifier(table["retired_name"]),
                )
            )
        db.execute("SELECT create_native_shared_catalog_views()")
        for table in tables:
            _restore_table_access(db, table)
            backing = (
                ("native_catalog_document_links", "native_catalog_bodies")
                if table["name"] == "native_catalog_documents"
                else (
                    "native_catalog_document_links",
                    "native_catalog_index_records",
                    "native_catalog_collections",
                )
            )
            for relation in backing:
                db.execute(
                    sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
                        sql.Identifier(table["schema"], relation),
                        sql.Identifier(table["owner"]),
                    )
                )
        for view in views:
            db.execute(
                sql.SQL("CREATE OR REPLACE VIEW {} AS ").format(
                    sql.Identifier(view["schema"], view["name"])
                )
                + sql.SQL(view["definition"])
            )
        for table in reversed(tables):
            db.execute(
                sql.SQL("DROP TABLE {}").format(
                    sql.Identifier(table["schema"], table["retired_name"])
                )
            )
        db.execute(
            "ALTER TABLE native_catalog_document_index_contracts ADD FOREIGN KEY(revision,path) "
            "REFERENCES native_catalog_document_links(revision,path)"
        )
        for table in (
            "native_catalog_bodies",
            "native_catalog_index_sets",
            "native_catalog_collections",
            "native_catalog_index_records",
            "native_catalog_document_links",
        ):
            db.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))
        result = dict(
            compacted=True,
            retained=retained,
            retired=removed,
            documents=len(documents),
            bodies=len(bodies),
            index_sets=len(identities),
            logical_records=logical_records,
            physical_records=physical_records,
        )
    _log("native_storage_compaction_committed", **result)
    return result


def main():
    from wakfu_server.postgres import Database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="append", default=[])
    parser.add_argument("--retain", type=int, default=2)
    args = parser.parse_args()
    keep = [
        *args.keep,
        *(
            os.environ[name]
            for name in (
                "WAKFU_MINING_CATALOG_REVISION",
                "WAKFU_FISHING_CATALOG_REVISION",
            )
            if os.environ.get(name)
        ),
    ]
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        print(json.dumps(compact(database, keep=keep, retain=args.retain)), flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()
