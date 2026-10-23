"""Stage immutable native JSON documents and atomically activate their release."""

import argparse
from collections import Counter
import hashlib
import json
import os
import sys
from pathlib import Path, PurePosixPath
import re

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
    for path in sorted(
        directory.rglob("*.json"),
        key=lambda item: item.relative_to(directory).as_posix(),
    ):
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


def _manifest_rows(manifest):
    rows = []
    seen = set()
    for path, checksum, size in manifest:
        if (
            not isinstance(path, str)
            or not path
            or "\\" in path
            or PurePosixPath(path).is_absolute()
            or any(part in ("", ".", "..") for part in path.split("/"))
            or not path.endswith(".json")
            or "\0" in path
            or not isinstance(checksum, str)
            or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
            or type(size) is not int
            or not 0 <= size <= MAX_DOCUMENT_BYTES
            or path in seen
        ):
            raise ValueError("Invalid or duplicate native manifest document")
        seen.add(path)
        rows.append((path, checksum, size))
    if not rows:
        raise ValueError("Empty native release manifest")
    return sorted(rows, key=lambda row: row[0])


def _line_revision(rows):
    digest = hashlib.sha256()
    for path, checksum, _ in rows:
        digest.update(path.encode("utf8"))
        digest.update(b"\0")
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def release_revision(manifest):
    """Canonical content identity uses POSIX string order, never Path order."""
    return _line_revision(_manifest_rows(manifest))


def release_identity(manifest, *, expected_revision=None, identity_scheme=None):
    """Prove a published ID with its original algorithm, without relabeling it.

    Fishing navigation was published with compact JSON triples. Older importers
    sorted Path components, unlike SQL/C POSIX string ordering. Both historical
    algorithms are explicit provenance; the canonical digest is always returned.
    """
    rows = _manifest_rows(manifest)
    canonical = _line_revision(rows)
    candidates = {
        "posix-path-sha256-v1": canonical,
        "legacy-path-sha256-v1": _line_revision(
            sorted(rows, key=lambda row: PurePosixPath(row[0]).parts)
        ),
    }
    if all(row[0].startswith("fishing-navigation/") for row in rows):
        candidates["fishing-json-manifest-v1"] = hashlib.sha256(
            json.dumps(rows, separators=(",", ":")).encode()
        ).hexdigest()
    if expected_revision is not None and (
        not isinstance(expected_revision, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_revision) is None
    ):
        raise ValueError("Invalid expected native release identity")
    if identity_scheme is not None:
        if identity_scheme not in candidates:
            raise ValueError("Unsupported native release identity scheme")
        scheme = identity_scheme
    elif expected_revision is None:
        scheme = "posix-path-sha256-v1"
    else:
        scheme = next(
            (name for name, value in candidates.items() if value == expected_revision),
            None,
        )
        if scheme is None:
            raise ValueError(
                "Published native release identity does not match source inventory"
            )
    revision = candidates[scheme]
    if expected_revision is not None and revision != expected_revision:
        raise ValueError(
            "Native release identity scheme does not match published identity"
        )
    return dict(
        revision=revision,
        identity_scheme=scheme,
        manifest_sha256=canonical,
        record_policy=(
            "raw-only" if scheme == "fishing-json-manifest-v1" else "catalog-records-v1"
        ),
    )


def validate_release_inventory(manifest, release):
    """Require the complete exported document inventory, not just a claimed ID."""
    rows = _manifest_rows(manifest)
    if (
        not isinstance(release, dict)
        or release.get("complete") is not True
        or not isinstance(release.get("revision"), str)
        or re.fullmatch(r"[0-9a-f]{64}", release["revision"]) is None
        or type(release.get("document_count")) is not int
        or type(release.get("source_bytes")) is not int
        or release["document_count"] != len(rows)
        or release["source_bytes"] != sum(row[2] for row in rows)
        or not isinstance(release.get("documents"), list)
    ):
        raise ValueError("Incomplete native release inventory")
    try:
        expected = _manifest_rows(
            (item["path"], item["sha256"], item["source_bytes"])
            for item in release["documents"]
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid native release document inventory") from error
    for item in release["documents"]:
        if "record_count" in item and (
            type(item["record_count"]) is not int or item["record_count"] < 0
        ):
            raise ValueError("Invalid exported native record count")
    if rows != expected:
        raise ValueError(
            "Native release source differs from complete exported inventory"
        )
    identity = release_identity(
        rows,
        expected_revision=release["revision"],
        identity_scheme=release.get("identity_scheme"),
    )
    if (
        release.get("record_policy", identity["record_policy"])
        != identity["record_policy"]
    ):
        raise ValueError("Native release record policy differs from original producer")
    if identity["record_policy"] == "raw-only" and any(
        item.get("record_count", 0) != 0 for item in release["documents"]
    ):
        raise ValueError("Raw-only native release cannot contain indexed records")
    if (
        release.get("manifest_sha256", identity["manifest_sha256"])
        != identity["manifest_sha256"]
    ):
        raise ValueError("Native canonical manifest checksum differs")
    return identity


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


def import_catalogs(
    database,
    directory,
    *,
    activate=True,
    expected_release=None,
    expected_revision=None,
    identity_scheme=None,
):
    from psycopg.types.json import Jsonb

    manifest = source_manifest(directory)
    if expected_release is not None:
        identity = validate_release_inventory(manifest, expected_release)
        if (
            expected_revision is not None and identity["revision"] != expected_revision
        ) or (
            identity_scheme is not None
            and identity["identity_scheme"] != identity_scheme
        ):
            raise ValueError(
                "Explicit native release pin conflicts with export inventory"
            )
    else:
        identity = release_identity(
            manifest,
            expected_revision=expected_revision,
            identity_scheme=identity_scheme,
        )
    revision = identity["revision"]
    expected_records = (
        {}
        if expected_release is None
        else {
            row["path"]: row["record_count"]
            for row in expected_release["documents"]
            if "record_count" in row
        }
    )
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
                if (
                    path in expected_records
                    and existing["record_count"] != expected_records[path]
                    or identity["record_policy"] == "raw-only"
                    and existing["record_count"] != 0
                ):
                    raise ValueError(f"Immutable native record count differs: {path}")
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
                records = (
                    ()
                    if identity["record_policy"] == "raw-only"
                    else catalog_records(path, document)
                )
                for collection, key, payload in records:
                    copy.write_row((revision, path, collection, key, Jsonb(payload)))
                    count += 1
            if path in expected_records and count != expected_records[path]:
                raise ValueError(
                    f"Derived native record count differs from published inventory: {path}"
                )
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
        **identity,
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
    parser.add_argument("--expected-revision")
    parser.add_argument(
        "--identity-scheme",
        choices=(
            "posix-path-sha256-v1",
            "legacy-path-sha256-v1",
            "fishing-json-manifest-v1",
        ),
    )
    parser.add_argument("--release-manifest", type=Path)

    args = parser.parse_args()
    expected_release = None
    if args.release_manifest is not None:
        exported = json.loads(args.release_manifest.read_text())
        releases = exported.get("releases", [exported])
        matches = [
            row for row in releases if row.get("revision") == args.expected_revision
        ]
        if len(matches) != 1:
            parser.error("--release-manifest requires one exact --expected-revision")
        expected_release = matches[0]
    from wakfu_server.postgres import Database

    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        print(
            json.dumps(
                import_catalogs(
                    database,
                    args.directory,
                    activate=not args.stage_only,
                    expected_release=expected_release,
                    expected_revision=args.expected_revision,
                    identity_scheme=args.identity_scheme,
                ),
                sort_keys=True,
            )
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
