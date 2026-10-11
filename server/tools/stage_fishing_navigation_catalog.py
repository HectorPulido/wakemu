"""Stage a compact immutable fishing navigation release without activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.fishing_navigation import _incoming


def stage(connection, directory, *, dry_run=True):
    documents = []
    for path in sorted(Path(directory).glob("*.json")):
        if path.name == "index.json":
            continue
        raw = path.read_bytes()
        data = json.loads(raw)
        _incoming(data, int(path.stem))
        data = {
            key: data[key]
            for key in ("map_id", "profile", "provenance", "resource_approaches")
        }
        data["provenance"] = dict(
            data["provenance"], source_export_sha256=hashlib.sha256(raw).hexdigest()
        )
        data["cells"] = [
            list(cell)
            for cell in sorted(
                {
                    tuple(cell)
                    for row in data["resource_approaches"]
                    for cell in row["approaches"]
                }
            )
        ]
        _incoming(data, int(path.stem))
        raw = json.dumps(data, separators=(",", ":")).encode()
        documents.append(
            (f"fishing-navigation/{path.name}", raw, hashlib.sha256(raw).hexdigest())
        )
    if not documents:
        raise ValueError("No fishing navigation documents")
    revision = hashlib.sha256(
        json.dumps(
            [(p, h, len(b)) for p, b, h in documents], separators=(",", ":")
        ).encode()
    ).hexdigest()
    if not dry_run:
        with connection.transaction():
            row = connection.execute(
                "SELECT complete FROM native_catalog_releases WHERE revision=%s",
                (revision,),
            ).fetchone()
            if row and not row[0]:
                raise ValueError("Existing release is incomplete")
            if not row:
                connection.execute(
                    "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) VALUES(%s,%s,%s)",
                    (revision, len(documents), sum(len(b) for p, b, h in documents)),
                )
                for path, raw, digest in documents:
                    connection.execute(
                        "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,0)",
                        (revision, path, raw, digest, len(raw)),
                    )
                connection.execute(
                    "UPDATE native_catalog_releases SET complete=true,completed_at=now() WHERE revision=%s",
                    (revision,),
                )
    return dict(
        revision=revision,
        navigation_maps=len(documents),
        source_bytes=sum(len(b) for p, b, h in documents),
        staged=not dry_run,
        activated=False,
    )


def main():
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"]) as connection:
        print(json.dumps(stage(connection, args.directory, dry_run=not args.stage)))


if __name__ == "__main__":
    main()
