"""Import extracted client quest/achievement metadata without enabling gameplay.

The input is the output of ExportNativeQuestDefinitions. Imports are immutable
and content-addressed; they do not change player state or achievement rules.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def prepare(raw):
    document = json.loads(raw)
    if type(document) is not dict or document.get("schema_version") != 1:
        raise ValueError("Unsupported native quest export")
    definitions = document.get("definitions")
    translations = document.get("translations")
    sources = document.get("source_sha256")
    reward_types = document.get("reward_types")
    if (
        not isinstance(definitions, list)
        or not definitions
        or not isinstance(translations, dict)
        or not isinstance(sources, dict)
        or not isinstance(reward_types, list)
    ):
        raise ValueError("Invalid native quest export")
    names = {}
    for row in reward_types:
        if (
            type(row.get("id")) is not int
            or type(row.get("name")) is not str
            or row["id"] in names
        ):
            raise ValueError("Invalid reward type")
        names[row["id"]] = row["name"]

    def localized(kind, identity):
        key = f"content.{kind}.{identity}"
        return {
            language: values[key]
            for language, values in translations.items()
            if isinstance(values, dict) and key in values
        }

    seen, seen_objectives, rows = set(), set(), []
    for item in definitions:
        if type(item) is not dict:
            raise ValueError("Invalid definition")
        identity = item.get("d")
        if type(identity) is not int or identity <= 0 or identity in seen:
            raise ValueError("Invalid or duplicate definition ID")
        seen.add(identity)
        objectives, rewards = item.get("cjJ"), item.get("cjK")
        if not isinstance(objectives, list) or not isinstance(rewards, list):
            raise ValueError("Invalid definition contents")
        localized_objectives = {}
        for objective in objectives:
            oid = objective.get("d")
            if type(oid) is not int or oid <= 0 or oid in seen_objectives:
                raise ValueError("Invalid or duplicate objective ID")
            seen_objectives.add(oid)
            localized_objectives[str(oid)] = localized(64, oid)
        for reward in rewards:
            if type(reward.get("aeV")) is not int or reward["aeV"] not in names:
                raise ValueError("Unknown reward type")
        rows.append(
            (
                identity,
                {
                    "native": item,
                    "title": localized(62, identity),
                    "description": localized(63, identity),
                    "category": localized(61, item.get("cjG")),
                    "objective_texts": localized_objectives,
                    "reward_types": {str(r["aeV"]): names[r["aeV"]] for r in rewards},
                },
            )
        )
    return hashlib.sha256(raw).hexdigest(), sources, rows


def stage(connection, raw, *, dry_run=True):
    revision, sources, rows = prepare(raw)
    if not dry_run:
        with connection.transaction():
            # Same content-addressed export can safely be imported concurrently.
            inserted = connection.execute(
                "INSERT INTO native_quest_metadata_releases (revision, source_sha256, source_export, definition_count) VALUES (%s,%s::jsonb,%s,%s) ON CONFLICT DO NOTHING RETURNING revision",
                (revision, json.dumps(sources), raw, len(rows)),
            ).fetchone()
            if inserted:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO native_quest_metadata_definitions (revision, definition_id, data) VALUES (%s,%s,%s::jsonb)",
                        [
                            (revision, identity, json.dumps(data, ensure_ascii=False))
                            for identity, data in rows
                        ],
                    )
            else:
                existing = connection.execute(
                    "SELECT definition_count, (SELECT count(*) FROM native_quest_metadata_definitions WHERE revision=%s) AS actual FROM native_quest_metadata_releases WHERE revision=%s",
                    (revision, revision),
                ).fetchone()
                counts = (
                    (existing["definition_count"], existing["actual"])
                    if isinstance(existing, dict)
                    else existing
                )
                if counts is None or counts[0] != len(rows) or counts[1] != len(rows):
                    raise ValueError("Existing metadata release is incomplete")
    return {
        "revision": revision,
        "definitions": len(rows),
        "objectives": sum(len(data["native"]["cjJ"]) for _, data in rows),
        "staged": not dry_run,
        "activated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument(
        "--stage", action="store_true", help="Write inert metadata to PostgreSQL"
    )
    args = parser.parse_args()
    raw = args.export.read_bytes()
    if args.stage:
        import psycopg

        with psycopg.connect(os.environ["WAKFU_DATABASE_URL"]) as connection:
            result = stage(connection, raw, dry_run=False)
    else:
        result = stage(None, raw)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
