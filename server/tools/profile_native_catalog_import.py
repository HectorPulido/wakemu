"""Isolated, capped-worker import measurement; never writes a runtime database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


def emit(event, **values):
    print(json.dumps(dict(event=event, **values)), flush=True)


def index_digest(db, revision, path):
    digest, count = hashlib.sha256(), 0
    with db.cursor(name="importbench_digest") as cursor:
        cursor.itersize = 128
        cursor.execute(
            "SELECT collection,record_key,payload FROM native_catalog_records "
            "WHERE revision=%s AND path=%s ORDER BY collection,record_key",
            (revision, path),
        )
        for row in cursor:
            digest.update(
                json.dumps(
                    (row["collection"], row["record_key"], row["payload"]),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf8")
                + b"\n"
            )
            count += 1
    return digest.hexdigest(), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--mode", choices=("legacy", "stream"), required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-bytes", type=int, required=True)
    parser.add_argument("--records", type=int, required=True)
    parser.add_argument("--reference-database")
    parser.add_argument("--reference-revision")
    parser.add_argument("--expected-index-sha256")
    args = parser.parse_args()
    if not re.fullmatch(r"importbench_[a-z0-9_]{1,45}", args.schema):
        raise ValueError("An exclusively owned importbench schema is required")
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg import sql
    from wakfu_server.postgres import Database
    from tools import import_native_catalogs as importer

    dsn = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(dsn).get("dbname") != "wakemu_migration_test":
        raise ValueError(
            "Benchmark writes require the isolated migration-test database"
        )
    password = os.environ["WAKFU_DATABASE_PASSWORD_FILE"]
    actual = hashlib.sha256()
    with args.source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            actual.update(block)
    if (
        actual.hexdigest() != args.sha256
        or args.source.stat().st_size != args.source_bytes
    ):
        raise ValueError("Benchmark source identity differs")
    expected_index = args.expected_index_sha256
    if args.reference_database:
        if not args.reference_revision:
            raise ValueError("Original read-only reference revision is required")
        reference = Database(
            make_conninfo(
                dsn,
                dbname=args.reference_database,
                options="-c default_transaction_read_only=on",
            ),
            password_file=password,
            min_size=1,
            max_size=1,
        )
        try:
            with reference.connection() as db:
                db.execute("SET TRANSACTION READ ONLY")
                row = db.execute(
                    "SELECT sha256,source_bytes,record_count FROM native_catalog_documents "
                    "WHERE revision=%s AND path=%s",
                    (args.reference_revision, args.source.name),
                ).fetchone()
                if row != dict(
                    sha256=args.sha256,
                    source_bytes=args.source_bytes,
                    record_count=args.records,
                ):
                    raise ValueError("Original published reference metadata differs")
                expected_index, count = index_digest(
                    db, args.reference_revision, args.source.name
                )
                if count != args.records:
                    raise ValueError("Original reference index count differs")
                emit(
                    "importbench_reference",
                    index_sha256=expected_index,
                    records=count,
                    source_sha256=args.sha256,
                    read_only=True,
                )
        finally:
            reference.close()
    if expected_index is None:
        raise ValueError("Complete original indexed-record digest is required")
    admin = Database(dsn, password_file=password, min_size=1, max_size=1)
    try:
        with admin.connection() as db:
            db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(args.schema)))
            db.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(
                    sql.Identifier(args.schema)
                )
            )
            db.execute(
                (
                    Path(__file__).resolve().parents[1]
                    / "migrations/082_native_catalogs.sql"
                ).read_text(),
                prepare=False,
            )
    finally:
        admin.close()
    database = Database(
        make_conninfo(
            dsn, options=f"-c search_path={args.schema}", application_name=args.schema
        ),
        password_file=password,
        min_size=1,
        max_size=1,
    )
    try:
        with database.connection() as db:
            pid = db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        limits = {}
        for key in ("memory.max", "memory.swap.max", "memory.current", "memory.peak"):
            path = Path("/sys/fs/cgroup") / key
            if path.is_file():
                limits[key] = path.read_text().strip()
        emit(
            "importbench_start",
            mode=args.mode,
            schema=args.schema,
            backend_pid=pid,
            source_bytes=args.source_bytes,
            source_sha256=args.sha256,
            cgroup=limits,
        )
        os.environ["WAKFU_CATALOG_IMPORT_PROFILE"] = "1"
        if args.mode == "legacy":
            importer.STREAM_DOCUMENT_BYTES = importer.MAX_DOCUMENT_BYTES + 1
        with tempfile.TemporaryDirectory(prefix="importbench-source-") as directory:
            (Path(directory) / args.source.name).symlink_to(args.source)
            started = time.monotonic()
            result = importer.import_catalogs(database, Path(directory))
            elapsed = time.monotonic() - started
        with database.connection() as db:
            row = db.execute(
                "SELECT encode(sha256(raw),'hex') AS sha256,source_bytes,record_count "
                "FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (result["revision"], args.source.name),
            ).fetchone()
            digest, count = index_digest(db, result["revision"], args.source.name)
        if row != dict(
            sha256=args.sha256,
            source_bytes=args.source_bytes,
            record_count=args.records,
        ):
            raise ValueError("Stored raw identity or complete record count differs")
        if digest != expected_index or count != args.records:
            raise ValueError(
                "Complete indexed-record digest differs from original authority"
            )
        final_limits = {}
        for key in (
            "memory.current",
            "memory.peak",
            "memory.events",
            "memory.swap.current",
        ):
            value = Path("/sys/fs/cgroup") / key
            if value.is_file():
                final_limits[key] = value.read_text().strip()
        emit(
            "importbench_complete",
            cgroup=final_limits,
            mode=args.mode,
            schema=args.schema,
            import_seconds=elapsed,
            records=count,
            stored_raw_sha256=row["sha256"],
            index_sha256=digest,
            result=result,
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
