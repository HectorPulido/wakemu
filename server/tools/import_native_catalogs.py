"""Stage immutable native JSON documents and atomically activate their release."""
import argparse
from collections import Counter
import hashlib
import json
import os
import sys
from pathlib import Path

from psycopg.types.json import Jsonb

from wakfu_server.postgres import Database


# Spatial grids are retained verbatim without duplicating millions of grid cells.
SPATIAL_DIRECTORIES = frozenset(
    {
        "combat-maps",
        "combat-los",
        "native-sn-columns",
        "forced-transitions",
    }
)
SPATIAL_COLLECTIONS = frozenset(
    {
        "cells",
        "edges",
        "visible_pairs",
        "dynamic_probe_cells",
        "columns",
    }
)
IDENTITY_FIELDS = (
    "id",
    "reference",
    "ref",
    "ref_id",
    "reference_id",
    "item_id",
    "spell_id",
)
MAX_DOCUMENT_BYTES = 1_000_000_000


def source_manifest(directory):
    """Hash in bounded chunks, with canonical POSIX relative paths."""
    result = []
    for path in sorted(directory.rglob("*.json")):
        size = path.stat().st_size
        if size > MAX_DOCUMENT_BYTES:
            raise ValueError(f"Native document exceeds PostgreSQL bytea limit: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        result.append(
            (path.relative_to(directory).as_posix(), digest.hexdigest(), size)
        )
    if not result:
        raise ValueError("No native JSON documents found")
    return result


def release_revision(manifest):
    digest = hashlib.sha256()
    for path, checksum, _ in manifest:
        digest.update(path.encode("utf8"))
        digest.update(b"\0")
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def entity_key(record, ordinal):
    if isinstance(record, dict):
        for field in IDENTITY_FIELDS:
            value = record.get(field)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                return str(value)
    return str(ordinal)


def catalog_records(path, document):
    """Expose keyed entity collections; metadata remains in the source document."""
    if Path(path).parts[0] in SPATIAL_DIRECTORIES:
        return
    collections = document.items() if isinstance(document, dict) else [("$", document)]
    for collection, values in collections:
        if collection in SPATIAL_COLLECTIONS:
            continue
        if isinstance(values, dict):
            for key, value in values.items():
                yield str(collection), str(key), value
        elif isinstance(values, list):
            keys = [entity_key(value, ordinal) for ordinal, value in enumerate(values)]
            counts = Counter(keys)
            reserved = set(keys)
            emitted = set()
            for ordinal, value in enumerate(values):
                key = keys[ordinal]
                if counts[key] > 1:
                    key = f"{key}@{ordinal}"
                    while key in reserved or key in emitted:
                        key = f"{key}@{ordinal}"
                emitted.add(key)
                yield str(collection), key, value


def get_record(db, revision, path, collection, record_key):
    row = db.execute(
        """SELECT payload FROM native_catalog_records
        WHERE revision=%s AND path=%s AND collection=%s AND record_key=%s""",
        (revision, path, collection, str(record_key)),
    ).fetchone()
    return None if row is None else row["payload"]


def import_catalogs(database, directory, *, activate=True):
    manifest = source_manifest(directory)
    revision = release_revision(manifest)
    total_bytes = sum(size for _, _, size in manifest)
    imported = skipped = total_records = 0
    # Locking the release row serializes concurrent imports of this exact revision.
    with database.connection() as db:
        db.execute(
            """INSERT INTO native_catalog_releases(revision,document_count,source_bytes)
            VALUES(%s,%s,%s) ON CONFLICT(revision) DO NOTHING""",
            (revision, len(manifest), total_bytes),
        )
    for position, (path, checksum, size) in enumerate(manifest, 1):
        if size >= 50_000_000:
            print(
                json.dumps(
                    {
                        "event": "native_catalog_import_large_document",
                        "position": position,
                        "total": len(manifest),
                        "path": path,
                        "source_bytes": size,
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
        with database.connection() as db:
            db.execute(
                "SELECT revision FROM native_catalog_releases WHERE revision=%s FOR UPDATE",
                (revision,),
            )
            existing = db.execute(
                """SELECT sha256,source_bytes,record_count FROM native_catalog_documents
                WHERE revision=%s AND path=%s""",
                (revision, path),
            ).fetchone()
            if existing is not None:
                if existing["sha256"] != checksum or existing["source_bytes"] != size:
                    raise ValueError(f"Immutable native document differs: {path}")
                skipped += 1
                total_records += existing["record_count"]
                if position % 100 == 0 or position == len(manifest):
                    report_progress(
                        position, len(manifest), imported, skipped, total_records
                    )
                continue
            raw = (directory / path).read_bytes()
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != checksum:
                raise ValueError(f"Native source changed during import: {path}")
            document = json.loads(raw)
            db.execute(
                """INSERT INTO native_catalog_documents
                (revision,path,raw,sha256,source_bytes,record_count)
                VALUES(%s,%s,%s,%s,%s,0)""",
                (revision, path, raw, checksum, size),
            )
            count = 0
            with db.cursor().copy(
                "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
            ) as copy:
                for collection, key, payload in catalog_records(path, document):
                    copy.write_row((revision, path, collection, key, Jsonb(payload)))
                    count += 1
            db.execute(
                """UPDATE native_catalog_documents SET record_count=%s
                WHERE revision=%s AND path=%s""",
                (count, revision, path),
            )
            total_records += count
            imported += 1
            del document, raw
        if position % 100 == 0 or position == len(manifest):
            report_progress(position, len(manifest), imported, skipped, total_records)
    with database.connection() as db:
        db.execute(
            "SELECT revision FROM native_catalog_releases WHERE revision=%s FOR UPDATE",
            (revision,),
        )
        actual = db.execute(
            """SELECT count(*) AS documents,coalesce(sum(source_bytes),0) AS bytes
            FROM native_catalog_documents WHERE revision=%s""",
            (revision,),
        ).fetchone()
        if actual["documents"] != len(manifest) or actual["bytes"] != total_bytes:
            raise ValueError("Incomplete native release; activation refused")
        db.execute(
            """UPDATE native_catalog_releases SET complete=true,
            completed_at=coalesce(completed_at,now()) WHERE revision=%s""",
            (revision,),
        )
        if activate:
            db.execute(
                """INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)
                ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,activated_at=now()""",
                (revision,),
            )
    return {
        "revision": revision,
        "documents": len(manifest),
        "source_bytes": total_bytes,
        "records": total_records,
        "imported": imported,
        "skipped": skipped,
        "activated": activate,
    }


def report_progress(position, total, imported, skipped, records):
    print(
        json.dumps(
            {
                "event": "native_catalog_import_progress",
                "position": position,
                "total": total,
                "imported": imported,
                "skipped": skipped,
                "records": records,
            }
        ),
        file=sys.stderr,
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "protocol",
    )
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        print(
            json.dumps(
                import_catalogs(database, args.directory, activate=not args.stage_only),
                sort_keys=True,
            )
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
