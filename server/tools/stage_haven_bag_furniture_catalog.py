"""Stage a full immutable catalog revision with portable furniture metadata.

Unchanged published documents and records are copied server-side. Activation is
deliberately left to the coordinated server release, never performed here.
"""

import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from import_native_catalogs import catalog_records, release_revision

PATH = "haven-bag-furniture-catalog.json"


def stage(connection, exported, expected_revision):
    with connection.transaction():
        active = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1 FOR SHARE"
        ).fetchone()[0]
        if active != expected_revision:
            raise ValueError("Published catalog changed before furniture staging")
        if (
            exported.get("schema_version") != 1
            or not exported.get("templates")
            or not exported.get("items")
        ):
            raise ValueError("Invalid portable furniture export")
        merged = exported
        raw = json.dumps(
            merged, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        checksum = hashlib.sha256(raw).hexdigest()
        replacements = {PATH: (merged, raw, checksum)}
        manifest = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents "
            "WHERE revision=%s ORDER BY path",
            (active,),
        ).fetchall()
        manifest = [
            (p, replacements[p][2], len(replacements[p][1]))
            if p in replacements
            else (p, h, n)
            for p, h, n in manifest
        ]
        if not any(path == PATH for path, _, _ in manifest):
            manifest.append((PATH, checksum, len(raw)))
        manifest.sort()
        revision = release_revision(manifest)
        existing = connection.execute(
            "SELECT complete FROM native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if existing:
            if existing[0] is not True:
                raise ValueError("Existing staged revision is incomplete")
            return {"revision": revision, "activated": False, "already_staged": True}
        connection.execute(
            "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) VALUES(%s,%s,%s)",
            (revision, len(manifest), sum(n for _, _, n in manifest)),
        )
        connection.execute(
            "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
            "SELECT %s,path,raw,sha256,source_bytes,record_count FROM native_catalog_documents "
            "WHERE revision=%s AND NOT(path=ANY(%s))",
            (revision, active, list(replacements)),
        )
        connection.execute(
            "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) "
            "SELECT %s,path,collection,record_key,payload FROM native_catalog_records "
            "WHERE revision=%s AND NOT(path=ANY(%s))",
            (revision, active, list(replacements)),
        )
        for path, (document, document_raw, document_hash) in replacements.items():
            records = list(catalog_records(path, document))
            connection.execute(
                "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    revision,
                    path,
                    document_raw,
                    document_hash,
                    len(document_raw),
                    len(records),
                ),
            )
            with connection.cursor().copy(
                "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
            ) as copy:
                for collection, key, payload in records:
                    copy.write_row((revision, path, collection, key, Jsonb(payload)))
        actual = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents "
            "WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
        if actual != manifest:
            raise ValueError("Staged full catalog manifest mismatch")
        connection.execute(
            "UPDATE native_catalog_releases SET complete=true,completed_at=now() WHERE revision=%s",
            (revision,),
        )
        return {
            "revision": revision,
            "base_revision": active,
            "documents": len(manifest),
            "templates": len(merged["templates"]),
            "items": len(merged["items"]),
            "metadata_sha256": checksum,
            "changed_documents": sorted(replacements),
            "activated": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exported", type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    args = parser.parse_args()
    exported = json.loads(args.exported.read_bytes())
    with psycopg.connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        print(
            json.dumps(
                stage(connection, exported, args.expected_revision), sort_keys=True
            )
        )


if __name__ == "__main__":
    main()
