"""Prepare a complete immutable spell resource-cost catalog; never activate it.

Default dry run validates full resource maps and computes the resulting full revision.
--stage copies unchanged documents/records server-side and writes an inactive
complete release. A later coordinated deployment must select that revision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from import_native_catalogs import catalog_records, release_revision


def documents(directory):
    path = Path(directory) / "native-spell-resource-costs.json"
    raw = path.read_bytes()
    document = json.loads(raw)
    if document.get("schema") != "native-spell-resource-costs-v1" or not document.get(
        "spells"
    ):
        raise ValueError("Missing complete native spell resource-cost export")
    from wakfu_server.combat_spell_resource_costs import table_values

    for reference, record in document["spells"].items():
        if not reference.isdecimal() or type(record["maximum_level"]) is not int:
            raise ValueError("Invalid native resource-cost spell identity")
        for table in [record["baseline"], *record["conditional"]]:
            for level in range(record["maximum_level"] + 1):
                table_values(table, level)
    return [
        dict(
            path=path.name,
            source=path,
            sha256=hashlib.sha256(raw).hexdigest(),
            source_bytes=len(raw),
        )
    ]


def full_manifest(published, exported):
    replacements = {
        d["path"]: (d["path"], d["sha256"], d["source_bytes"]) for d in exported
    }
    if len(replacements) != len(exported):
        raise ValueError("Duplicate navigation replacement path")
    combined = {p: (p, h, n) for p, h, n in published}
    combined.update(replacements)
    return sorted(combined.values())


def stage(
    connection,
    directory,
    expected_revision,
    *,
    base_revision=None,
    dry_run=True,
    document_provider=None
):
    exported = (documents if document_provider is None else document_provider)(
        directory
    )
    with connection.transaction():
        if dry_run:
            connection.execute("SET TRANSACTION READ ONLY")
        active_row = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
            + ("" if dry_run else " FOR SHARE")
        ).fetchone()
        if active_row is None or active_row[0] != expected_revision:
            raise ValueError("Published catalog changed before resource-cost staging")
        active = active_row[0]
        base = active if base_revision is None else base_revision
        complete = connection.execute(
            "SELECT complete FROM native_catalog_releases WHERE revision=%s", (base,)
        ).fetchone()
        if complete is None or complete[0] is not True:
            raise ValueError("Resource-cost staging base is not complete")
        published = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (base,),
        ).fetchall()
        manifest = full_manifest(published, exported)
        revision = release_revision(manifest)
        result = dict(
            revision=revision,
            base_revision=base,
            expected_active_revision=active,
            documents=len(manifest),
            resource_cost_documents=len(exported),
            changed_documents=[d["path"] for d in exported],
            activated=False,
            dry_run=dry_run,
            staged=False,
        )
        existing = connection.execute(
            "SELECT complete FROM native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if existing:
            if existing[0] is not True:
                raise ValueError("Existing staged revision is incomplete")
            result.update(already_staged=True, staged=True)
            return result
        if dry_run:
            return result
        connection.execute(
            "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) VALUES(%s,%s,%s)",
            (revision, len(manifest), sum(n for _, _, n in manifest)),
        )
        paths = [d["path"] for d in exported]
        connection.execute(
            "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
            "SELECT %s,path,raw,sha256,source_bytes,record_count FROM native_catalog_documents "
            "WHERE revision=%s AND NOT(path=ANY(%s))",
            (revision, base, paths),
        )
        connection.execute(
            "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) "
            "SELECT %s,path,collection,record_key,payload FROM native_catalog_records "
            "WHERE revision=%s AND NOT(path=ANY(%s))",
            (revision, base, paths),
        )
        from psycopg.types.json import Jsonb

        for entry in exported:
            raw = entry["source"].read_bytes()
            if (
                len(raw) != entry["source_bytes"]
                or hashlib.sha256(raw).hexdigest() != entry["sha256"]
            ):
                raise ValueError("Resource-cost source changed during staging")
            document = json.loads(raw)
            records = list(catalog_records(entry["path"], document))
            connection.execute(
                "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,%s)",
                (revision, entry["path"], raw, entry["sha256"], len(raw), len(records)),
            )
            with connection.cursor().copy(
                "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
            ) as copy:
                for collection, key, payload in records:
                    copy.write_row(
                        (revision, entry["path"], collection, key, Jsonb(payload))
                    )
        actual = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
        if actual != manifest:
            raise ValueError("Staged full resource-cost catalog manifest mismatch")
        connection.execute(
            "UPDATE native_catalog_releases SET complete=true,completed_at=now() WHERE revision=%s",
            (revision,),
        )
        result["staged"] = True
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--base-revision")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Write inactive immutable release; default is read-only dry run",
    )
    args = parser.parse_args()
    import psycopg

    with psycopg.connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        print(
            json.dumps(
                stage(
                    connection,
                    args.directory,
                    args.expected_revision,
                    base_revision=args.base_revision,
                    dry_run=not args.stage,
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
