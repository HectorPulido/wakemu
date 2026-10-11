"""Read-only bounded scan of published catalog records for exact references.

Outputs structural occurrences, not an inference that every numeric collision
is a gameplay consumer. Documents without keyed records are listed separately.
"""
import argparse
import json
import os
from pathlib import Path
import re

import psycopg


def occurrences(value, references, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from occurrences(child, references, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from occurrences(child, references, (*path, str(index)))
    elif type(value) in (int, float) and value in references:
        yield {"field": ".".join(path), "value": value, "kind": "numeric"}
    elif isinstance(value, str):
        for reference in references:
            if re.search(rf"(?<!\d){reference}(?!\d)", value):
                yield {"field": ".".join(path), "value": value[:512], "kind": "text"}


def scan(connection, references):
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout='60s'")
        revision = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
        ).fetchone()[0]
        pattern = r"(^|[^0-9])(" + "|".join(map(str, references)) + r")([^0-9]|$)"
        result = {"revision": revision, "references": references, "matches": []}
        result["record_count"] = connection.execute(
            "SELECT count(*) FROM native_catalog_records WHERE revision=%s", (revision,)
        ).fetchone()[0]
        with connection.cursor(name="reference_consumers") as cursor:
            cursor.execute(
                "SELECT path,collection,record_key,payload FROM native_catalog_records "
                "WHERE revision=%s AND payload::text ~ %s ORDER BY path,collection,record_key",
                (revision, pattern),
            )
            for path, collection, key, payload in cursor:
                hits = list(occurrences(payload, references))
                if hits:
                    result["matches"].append(
                        dict(
                            path=path, collection=collection, key=key, occurrences=hits
                        )
                    )
        result[
            "coverage"
        ] = "all published indexed records; unindexed documents not parsed"
        result["unindexed_documents"] = connection.execute(
            "SELECT path,source_bytes FROM native_catalog_documents WHERE revision=%s "
            "AND record_count=0 ORDER BY path",
            (revision,),
        ).fetchall()
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("references", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    password = Path(password_file).read_text().strip() if password_file else None
    with psycopg.connect(
        os.environ["WAKFU_DATABASE_URL"], password=password
    ) as connection:
        result = scan(connection, args.references)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "revision": result["revision"],
                "records": result["record_count"],
                "matching_records": len(result["matches"]),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
