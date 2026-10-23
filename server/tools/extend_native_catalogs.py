"""Stage an immutable catalog revision with explicit additions/replacements, without activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from psycopg.types.json import Jsonb

from tools.import_native_catalogs import catalog_records, release_revision
from wakfu_server.postgres import Database


def _manifest(rows):
    result = []
    for path, checksum, size in rows:
        if (
            not isinstance(path, str)
            or not path.endswith(".json")
            or str(PurePosixPath(path)) != path
            or path.startswith("/")
            or ".." in PurePosixPath(path).parts
        ):
            raise ValueError("Invalid catalog document path")
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError("Invalid catalog document checksum")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("Invalid catalog document size")
        result.append((path, checksum, size))
    if len({row[0] for row in result}) != len(result) or not result:
        raise ValueError("Duplicate or empty catalog manifest")
    return sorted(result)


def stage_extension(database, base_manifest, additions, *, replacements=None):
    """Clone a complete pinned release and append exact documents atomically.

    Additions cannot collide with existing paths. Replacements must explicitly
    name existing pinned paths. Both map paths to exact bytes. The old release
    remains untouched; the caller selects the DB and no activation API is used.
    """
    base = _manifest(base_manifest["documents"])
    base_revision = base_manifest["receipt"]["revision"]
    if release_revision(base) != base_revision:
        raise ValueError("Base manifest revision does not match its documents")
    replacements = {} if replacements is None else replacements
    if not additions and not replacements:
        raise ValueError("No catalog additions or explicit replacements")
    if additions.keys() & replacements.keys():
        raise ValueError("Catalog path is both added and explicitly replaced")
    extra = []
    records = {}
    old_paths = {row[0] for row in base}
    for path in additions:
        if path in old_paths:
            raise ValueError(f"Append-only catalog path already exists: {path}")
    for path in replacements:
        if path not in old_paths:
            raise ValueError(f"Explicit replacement path is absent from base: {path}")
    documents = dict(additions, **replacements)
    for path, raw in documents.items():
        if not isinstance(raw, bytes):
            raise ValueError("Catalog source must be exact bytes")
        extra.append((path, hashlib.sha256(raw).hexdigest(), len(raw)))
        records[path] = list(catalog_records(path, json.loads(raw)))
    full = _manifest([row for row in base if row[0] not in replacements] + extra)
    revision = release_revision(full)
    source_bytes = sum(row[2] for row in full)
    with database.connection() as db:
        # Transaction-scoped serialization affects only this new revision.
        db.execute(
            "SELECT pg_advisory_xact_lock(%s)", (int(revision[:16], 16) - (1 << 63),)
        )
        release = db.execute(
            "SELECT * FROM native_catalog_releases WHERE revision=%s FOR SHARE",
            (base_revision,),
        ).fetchone()
        if release is None or not release["complete"]:
            raise ValueError("Base catalog release is absent or incomplete")
        existing_base = db.execute(
            "SELECT path,sha256,source_bytes,record_count FROM native_catalog_documents "
            "WHERE revision=%s ORDER BY path",
            (base_revision,),
        ).fetchall()
        actual_base = [
            (row["path"], row["sha256"], row["source_bytes"]) for row in existing_base
        ]
        if (
            actual_base != base
            or release["document_count"] != len(base)
            or release["source_bytes"] != sum(row[2] for row in base)
        ):
            raise ValueError("Base catalog does not match the pinned manifest")
        base_records = sum(row["record_count"] for row in existing_base)
        actual_base_records = db.execute(
            "SELECT count(*) AS n FROM native_catalog_records WHERE revision=%s",
            (base_revision,),
        ).fetchone()["n"]
        if actual_base_records != base_records:
            raise ValueError("Base catalog record count is incomplete")
        replaced_records = sum(
            row["record_count"] for row in existing_base if row["path"] in replacements
        )
        expected_records = (
            base_records
            - replaced_records
            + sum(len(value) for value in records.values())
        )
        present = db.execute(
            "SELECT * FROM native_catalog_releases WHERE revision=%s FOR UPDATE",
            (revision,),
        ).fetchone()
        if present is None:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) VALUES(%s,%s,%s)",
                (revision, len(full), source_bytes),
            )
            db.execute(
                "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
                "SELECT %s,path,raw,sha256,source_bytes,record_count FROM native_catalog_documents WHERE revision=%s AND path<>ALL(%s)",
                (revision, base_revision, list(replacements)),
            )
            db.execute(
                "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) "
                "SELECT %s,path,collection,record_key,payload FROM native_catalog_records WHERE revision=%s AND path<>ALL(%s)",
                (revision, base_revision, list(replacements)),
            )
            for path, checksum, size in sorted(extra):
                db.execute(
                    "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        revision,
                        path,
                        documents[path],
                        checksum,
                        size,
                        len(records[path]),
                    ),
                )
                with db.cursor().copy(
                    "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
                ) as copy:
                    for collection, key, payload in records[path]:
                        copy.write_row(
                            (revision, path, collection, key, Jsonb(payload))
                        )
        elif (
            present["document_count"] != len(full)
            or present["source_bytes"] != source_bytes
        ):
            raise ValueError("Existing immutable extension release differs")
        actual = db.execute(
            "SELECT path,sha256,source_bytes,record_count FROM native_catalog_documents "
            "WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
        if [
            (row["path"], row["sha256"], row["source_bytes"]) for row in actual
        ] != full:
            raise ValueError("Incomplete extension document manifest")
        count = db.execute(
            "SELECT count(*) AS n FROM native_catalog_records WHERE revision=%s",
            (revision,),
        ).fetchone()["n"]
        if (
            count != expected_records
            or sum(row["record_count"] for row in actual) != expected_records
        ):
            raise ValueError("Incomplete extension record count")
        db.execute(
            "UPDATE native_catalog_releases SET complete=true,completed_at=coalesce(completed_at,now()) "
            "WHERE revision=%s",
            (revision,),
        )
    return {
        "receipt": {
            "revision": revision,
            "documents": len(full),
            "source_bytes": source_bytes,
            "records": expected_records,
            "base_revision": base_revision,
            "base_documents": len(base),
            "base_records": base_records,
            "added_documents": len(additions),
            "added_paths": sorted(additions),
            "replaced_documents": len(replacements),
            "replaced_paths": sorted(replacements),
            "activated": False,
            "reused": present is not None,
            "source": "Immutable PostgreSQL clone of pinned complete release with explicit exact native additions/replacements",
        },
        "documents": full,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--source-directory", type=Path, required=True)
    parser.add_argument("--add", action="append", default=[])
    parser.add_argument("--replace", action="append", default=[])
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()
    _manifest([(path, "0" * 64, 0) for path in args.add + args.replace])
    additions = {path: (args.source_directory / path).read_bytes() for path in args.add}
    replacements = {
        path: (args.source_directory / path).read_bytes() for path in args.replace
    }
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        max_size=2,
    )
    try:
        result = stage_extension(
            database,
            json.loads(args.base_manifest.read_text()),
            additions,
            replacements=replacements,
        )
    finally:
        database.close()
    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output_manifest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["receipt"], sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
