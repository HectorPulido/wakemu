"""Export exact catalog releases as deduplicated deterministic gzip chunks.

Read-only database access; no bootstrap captures, player tables, activation,
release rewriting or normalization. Public distribution needs a separate review
of embedded source documents; --plan never writes document bodies.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

from tools.unpack_native_catalog_pack import FORMAT, PART_BYTES


def inventory(db, revisions):
    from tools.import_native_catalogs import release_identity

    active = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()
    if active is None:
        raise ValueError("No active native catalog")
    releases = []
    for revision in dict.fromkeys([active["revision"], *revisions]):
        release = db.execute(
            "SELECT revision,document_count,source_bytes,complete "
            "FROM native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if release is None or release["complete"] is not True:
            raise ValueError("Missing complete catalog release")
        documents = [
            dict(row)
            for row in db.execute(
                "SELECT path,sha256,source_bytes,record_count FROM native_catalog_documents "
                'WHERE revision=%s ORDER BY path COLLATE "C"',
                (revision,),
            )
        ]
        if (
            len(documents) != release["document_count"]
            or sum(row["source_bytes"] for row in documents) != release["source_bytes"]
        ):
            raise ValueError("Catalog release inventory mismatch")
        release = dict(release)
        release.update(
            release_identity(
                [
                    (row["path"], row["sha256"], row["source_bytes"])
                    for row in documents
                ],
                expected_revision=revision,
            )
        )
        release["documents"] = documents
        releases.append(release)
    return {
        "format": FORMAT,
        "active_revision": active["revision"],
        "releases": releases,
    }


def export(db, output_directory, revisions=()):
    pack = inventory(db, revisions)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    (output_directory / "INCOMPLETE").write_text("Catalog export incomplete\n")
    parts_directory = output_directory / "parts"
    parts_directory.mkdir()
    blobs = {}
    for release in pack["releases"]:
        for row in release["documents"]:
            checksum = row["sha256"]
            if checksum in blobs:
                if blobs[checksum]["source_bytes"] != row["source_bytes"]:
                    raise ValueError("Conflicting catalog checksum sizes")
                continue
            parts = []
            full_hash = hashlib.sha256()
            for offset in range(0, max(row["source_bytes"], 1), PART_BYTES):
                record = db.execute(
                    "SELECT substring(raw FROM %s FOR %s) AS part "
                    "FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (offset + 1, PART_BYTES, release["revision"], row["path"]),
                ).fetchone()
                raw = bytes(record["part"])
                expected = min(PART_BYTES, row["source_bytes"] - offset)
                if len(raw) != expected:
                    raise ValueError("Catalog chunk size mismatch")
                full_hash.update(raw)
                raw_hash = hashlib.sha256(raw).hexdigest()
                relative = f"parts/{raw_hash}.json.gz"
                destination = output_directory / relative
                buffer = io.BytesIO()
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
                ) as compressed:
                    compressed.write(raw)
                encoded = buffer.getvalue()
                if not destination.exists():
                    destination.write_bytes(encoded)
                elif destination.read_bytes() != encoded:
                    raise ValueError("Non-deterministic compressed catalog part")
                parts.append(
                    {
                        "path": relative,
                        "sha256": raw_hash,
                        "source_bytes": len(raw),
                        "compressed_bytes": len(encoded),
                        "compressed_sha256": hashlib.sha256(encoded).hexdigest(),
                    }
                )
            if full_hash.hexdigest() != checksum:
                raise ValueError("Catalog document checksum mismatch")
            blobs[checksum] = {"source_bytes": row["source_bytes"], "parts": parts}
    pack["blobs"] = blobs
    encoded = (json.dumps(pack, sort_keys=True, indent=2) + "\n").encode()
    (output_directory / "manifest.json").write_bytes(encoded)
    (output_directory / "manifest.sha256").write_text(
        hashlib.sha256(encoded).hexdigest() + "\n"
    )
    (output_directory / "INCOMPLETE").unlink()
    return pack


def main():
    from psycopg import connect
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--revision", action="append", default=[])
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    if not args.plan and args.output is None:
        parser.error("--output is required unless --plan is used")
    config = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"])
    config["options"] = "-c default_transaction_read_only=on"
    password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    kwargs = (
        {}
        if password_file is None
        else {"password": Path(password_file).read_text().strip()}
    )
    with connect(make_conninfo(**config), row_factory=dict_row, **kwargs) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        if args.plan:
            print(json.dumps(inventory(db, args.revision), sort_keys=True, indent=2))
        else:
            pack = export(db, args.output, args.revision)
            print(
                json.dumps(
                    {
                        "manifest": str(args.output / "manifest.json"),
                        "releases": len(pack["releases"]),
                        "unique_documents": len(pack["blobs"]),
                    }
                )
            )


if __name__ == "__main__":
    main()
