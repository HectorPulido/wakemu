"""Keep two native payload releases and live dependencies, retaining source seals."""

import argparse
import json
import os
import uuid

from psycopg import sql
from psycopg.types.json import Jsonb


def _log(event, **fields):
    print(json.dumps(dict(event=event, **fields)), flush=True)


def _replacement_metadata(db, originals):
    """Preserve reader interfaces and access when physical tables are replaced."""
    tables = []
    for name in originals:
        table = dict(
            db.execute(
                "SELECT c.oid,n.nspname AS schema,c.relname AS name,"
                "pg_get_userbyid(c.relowner) AS owner FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass(%s)",
                (name,),
            ).fetchone()
        )
        table["grants"] = db.execute(
            "SELECT a.attname,x.grantee,CASE WHEN x.grantee=0 THEN 'PUBLIC' "
            "ELSE pg_get_userbyid(x.grantee) END AS role,x.privilege_type,x.is_grantable "
            "FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) x "
            "LEFT JOIN pg_attribute a ON false WHERE c.oid=%s "
            "UNION ALL SELECT a.attname,x.grantee,CASE WHEN x.grantee=0 THEN 'PUBLIC' "
            "ELSE pg_get_userbyid(x.grantee) END,x.privilege_type,x.is_grantable "
            "FROM pg_attribute a CROSS JOIN LATERAL aclexplode(a.attacl) x "
            "WHERE a.attrelid=%s",
            (table["oid"], table["oid"]),
        ).fetchall()
        tables.append(table)
    search_path = db.execute("SHOW search_path").fetchone()["search_path"]
    db.execute("SELECT set_config('search_path','pg_catalog',true)")
    try:
        # Replacing direct reader views preserves their OIDs, so dependent views
        # continue working without being dropped or recreated themselves.
        views = db.execute(
            "SELECT DISTINCT c.oid,n.nspname AS schema,c.relname AS name,c.relkind,"
            "pg_get_viewdef(c.oid,false) AS definition FROM pg_depend d "
            "JOIN pg_rewrite r ON r.oid=d.objid AND d.classid='pg_rewrite'::regclass "
            "JOIN pg_class c ON c.oid=r.ev_class "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE d.refclassid='pg_class'::regclass AND d.refobjid=ANY(%s) "
            "AND c.oid<>d.refobjid ORDER BY c.oid",
            ([table["oid"] for table in tables],),
        ).fetchall()
    finally:
        db.execute("SELECT set_config('search_path',%s,true)", (search_path,))
    if any(view["relkind"] != "v" for view in views):
        raise RuntimeError(
            "Native catalog has a dependent materialized view; preserve it before compaction"
        )
    return tables, views


def _restore_table_access(db, table):
    target = sql.Identifier(table["schema"], table["name"])
    db.execute(
        sql.SQL("ALTER TABLE {} OWNER TO {}").format(
            target, sql.Identifier(table["owner"])
        )
    )
    # A staging table can inherit different default grants. Remove those before
    # restoring the original effective table and column privileges.
    roles = db.execute(
        "SELECT DISTINCT CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS role "
        "FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) x WHERE c.oid=%s::regclass",
        (target.as_string(db),),
    ).fetchall()
    for role in {"PUBLIC", *(row["role"] for row in roles)} - {table["owner"]}:
        grantee = sql.SQL("PUBLIC") if role == "PUBLIC" else sql.Identifier(role)
        db.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(target, grantee)
        )
    for grant in table["grants"]:
        grantee = (
            sql.SQL("PUBLIC")
            if grant["grantee"] == 0
            else sql.Identifier(grant["role"])
        )
        privilege = sql.SQL(grant["privilege_type"])
        if grant["attname"] is not None:
            privilege += sql.SQL(" ({})").format(sql.Identifier(grant["attname"]))
        db.execute(
            sql.SQL("GRANT {} ON TABLE {} TO {}{}").format(
                privilege,
                target,
                grantee,
                sql.SQL(" WITH GRANT OPTION") if grant["is_grantable"] else sql.SQL(""),
            )
        )


def plan_retention(db, *, keep=(), retain=2):
    """Choose only resident releases; callers hold the maintenance lock."""
    if type(retain) is not int or retain < 1:
        raise ValueError("At least one native payload release must be retained")
    releases = db.execute(
        "SELECT r.*,EXISTS(SELECT 1 FROM native_catalog_documents d "
        "WHERE d.revision=r.revision) AS has_payload "
        "FROM native_catalog_releases r ORDER BY created_at DESC,revision DESC"
    ).fetchall()
    known = {row["revision"]: row for row in releases}
    retained = set(keep)
    retained.update(row["revision"] for row in releases if not row["complete"])
    retained.update(
        [row["revision"] for row in releases if row["complete"] and row["has_payload"]][
            :retain
        ]
    )
    retained.update(
        row["revision"]
        for row in db.execute("SELECT revision FROM native_catalog_active")
    )
    retained.update(
        row["source_revision"]
        for row in db.execute(
            "SELECT DISTINCT source_revision FROM native_compiled_catalog_releases"
        )
    )
    if retained - known.keys():
        raise ValueError("Required native release does not exist")
    if any(
        known[revision]["complete"]
        and known[revision]["document_count"] > 0
        and not known[revision]["has_payload"]
        for revision in retained
    ):
        raise ValueError("Required native payload has already been retired")
    removed = []
    for row in releases:
        revision = row["revision"]
        if revision in retained or not row["has_payload"]:
            continue
        locked = db.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended("
            "current_database()||':'||current_schema()||':native_revision:'||%s,0)) AS acquired",
            (revision,),
        ).fetchone()["acquired"]
        if locked:
            removed.append(revision)
        else:
            retained.add(revision)
    return known, sorted(retained), removed


def archive_revisions(db, known, removed):
    """Keep cryptographically authenticated provenance while retiring payloads."""
    from wakfu_server.native_catalog_compatibility import _inventory

    for revision in removed:
        documents = [
            dict(row)
            for row in db.execute(
                "SELECT path,sha256,source_bytes,record_count FROM native_catalog_documents "
                'WHERE revision=%s ORDER BY path COLLATE "C"',
                (revision,),
            )
        ]
        inventory = {
            key: value
            for key, value in known[revision].items()
            if key in ("revision", "document_count", "source_bytes", "complete")
        }
        inventory["documents"] = documents
        _inventory(inventory, revision)
        db.execute(
            "INSERT INTO native_catalog_retired_inventories(revision,inventory) "
            "VALUES(%s,%s) ON CONFLICT(revision) DO UPDATE SET "
            "inventory=excluded.inventory,retired_at=now()",
            (revision, Jsonb(inventory)),
        )


def compact(database, *, keep=(), retain=2):
    """Rebuild payload relations from retained revisions; never touch player data.

    Headers and authenticated historical inventories remain available for frozen
    gameplay source seals. Unchanged maintenance runs do no record copying.
    """
    if type(retain) is not int or retain < 1:
        raise ValueError("At least one native payload release must be retained")
    from wakfu_server.native_shared_storage import garbage_collect, shared_storage

    with database.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended("
            "current_database()||':'||current_schema()||':native_catalog_maintenance',0))"
        )
        # Stage tools also write these tables directly. Protect their committed
        # rows even when they do not yet know the maintenance advisory protocol.
        db.execute("LOCK TABLE native_catalog_releases IN SHARE ROW EXCLUSIVE MODE")
        db.execute(
            "LOCK TABLE native_catalog_documents,native_catalog_records IN SHARE MODE"
        )
        known, retained, removed = plan_retention(db, keep=keep, retain=retain)
        normalized = shared_storage(db)
        if not removed:
            result = dict(compacted=False, retained=sorted(retained), retired=[])
            if normalized:
                result.update(garbage_collect(db))
            return result
        originals = (
            "native_catalog_documents",
            "native_catalog_records",
            "native_catalog_document_index_contracts",
        )
        if not normalized:
            tables, views = _replacement_metadata(db, originals)
        archive_revisions(db, known, removed)
        if normalized:
            db.execute(
                "DELETE FROM native_catalog_document_index_contracts WHERE revision=ANY(%s)",
                (removed,),
            )
            db.execute(
                "DELETE FROM native_catalog_document_links WHERE revision=ANY(%s)",
                (removed,),
            )
            result = dict(
                compacted=True,
                retained=sorted(retained),
                retired=removed,
                **garbage_collect(db),
            )
            _log("native_catalog_shared_retention", **result)
            return result
        suffix = uuid.uuid4().hex[:12]
        docs_name = "native_catalog_documents_" + suffix
        records_name = "native_catalog_records_" + suffix
        contracts_name = "native_catalog_contracts_" + suffix
        for name, original in (
            (docs_name, "native_catalog_documents"),
            (records_name, "native_catalog_records"),
            (contracts_name, "native_catalog_document_index_contracts"),
        ):
            db.execute(
                sql.SQL("CREATE TABLE {} (LIKE {} INCLUDING ALL)").format(
                    sql.Identifier(name), sql.Identifier(original)
                )
            )
        db.execute(
            sql.SQL(
                "INSERT INTO {} SELECT * FROM native_catalog_documents WHERE revision=ANY(%s)"
            ).format(sql.Identifier(docs_name)),
            (sorted(retained),),
        )
        _log("native_retained_documents_copied", revisions=len(retained))
        # PostgreSQL hashes each bytea once without transferring or decoding
        # multi-gigabyte JSON catalogs in the maintenance Python process.
        documents = db.execute(
            sql.SQL(
                "SELECT revision,path,sha256,source_bytes,record_count FROM {} ORDER BY revision,path"
            ).format(sql.Identifier(docs_name))
        ).fetchall()
        if (
            db.execute(
                sql.SQL(
                    "SELECT 1 FROM {} WHERE encode(sha256(raw),'hex')<>sha256 LIMIT 1"
                ).format(sql.Identifier(docs_name))
            ).fetchone()
            is not None
        ):
            raise ValueError("Retained native document checksum mismatch")
        db.execute(
            sql.SQL(
                "INSERT INTO {} SELECT * FROM native_catalog_records WHERE revision=ANY(%s)"
            ).format(sql.Identifier(records_name)),
            (sorted(retained),),
        )
        db.execute(
            sql.SQL(
                "INSERT INTO {} SELECT * FROM native_catalog_document_index_contracts WHERE revision=ANY(%s)"
            ).format(sql.Identifier(contracts_name)),
            (sorted(retained),),
        )
        counts = {
            (row["revision"], row["path"]): row["records"]
            for row in db.execute(
                sql.SQL(
                    "SELECT revision,path,count(*) AS records FROM {} GROUP BY revision,path"
                ).format(sql.Identifier(records_name))
            )
        }
        if any(
            counts.get((row["revision"], row["path"]), 0) != row["record_count"]
            for row in documents
        ):
            raise ValueError("Retained native index count differs from its document")
        db.execute("SET LOCAL lock_timeout='15s'")
        for table in tables:
            table["retired_name"] = table["name"] + "_retired_" + suffix
            db.execute(
                sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                    sql.Identifier(table["schema"], table["name"]),
                    sql.Identifier(table["retired_name"]),
                )
            )
        for name, original in (
            (docs_name, "native_catalog_documents"),
            (records_name, "native_catalog_records"),
            (contracts_name, "native_catalog_document_index_contracts"),
        ):
            db.execute(
                sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                    sql.Identifier(name), sql.Identifier(original)
                )
            )
        for table in tables:
            _restore_table_access(db, table)
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
            "ALTER TABLE native_catalog_documents ADD FOREIGN KEY(revision) REFERENCES native_catalog_releases(revision)"
        )
        db.execute(
            "ALTER TABLE native_catalog_records ADD FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path)"
        )
        db.execute(
            "ALTER TABLE native_catalog_document_index_contracts ADD FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path)"
        )
        db.execute("ANALYZE native_catalog_documents")
        db.execute("ANALYZE native_catalog_records")
        result = dict(
            compacted=True,
            retained=sorted(retained),
            retired=removed,
            retained_documents=len(documents),
            retained_records=sum(counts.values()),
        )
    _log("native_catalog_compaction_committed", **result)
    return result


def main():
    from wakfu_server.postgres import Database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="append", default=[])
    parser.add_argument("--retain", type=int, default=2)
    args = parser.parse_args()
    # These are independent, active navigation payloads, not previous gameplay
    # versions. Preserve their explicit deployment pins on every maintenance run.
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
        _log(
            "native_catalog_retention_complete",
            **compact(database, keep=keep, retain=args.retain),
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
