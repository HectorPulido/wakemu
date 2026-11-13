"""Install explicitly reconstructed native quest interactions transactionally.

This is a publication tool, not an inference engine: only entries that have
been reviewed and contain their evidence may be installed. Existing conflicting
bindings are never changed. The same manifest can safely be applied again.
"""
import argparse
import json
import os
from pathlib import Path

from wakfu_server.achievements import rewards
from wakfu_server.postgres import Database

FIELDS = (
    "map_id",
    "object_id",
    "action_id",
    "parameter",
    "x",
    "y",
    "z",
    "object_type",
    "max_distance",
    "required_item",
    "required_quantity",
    "quest_id",
    "objective_id",
    "revision",
    "evidence",
    "script_id",
)
KEYS = FIELDS[:4]


def validate_manifest(document, revision):
    if (
        type(document) is not dict
        or document.get("schema") != "quest-interaction-batch-v1"
        or not isinstance(document.get("bindings"), list)
    ):
        raise ValueError("Invalid quest interaction manifest")
    if len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Invalid client revision")
    records, seen = [], set()
    for row in document["bindings"]:
        if type(row) is not dict or row.get("status") != "reviewed":
            raise ValueError("Only reviewed quest bindings can be installed")
        item = {key: row.get(key) for key in FIELDS if key != "revision"}
        item["script_id"] = row.get("script_id", 0)
        item["revision"] = revision
        for key in ("map_id", "object_id", "quest_id", "objective_id"):
            if type(item[key]) is not int or item[key] <= 0:
                raise ValueError(f"Invalid {key}")
        for key in ("action_id", "parameter"):
            if type(item[key]) is not int or not 0 <= item[key] <= 65535:
                raise ValueError(f"Invalid {key}")
        if type(item["script_id"]) is not int or not 0 <= item["script_id"] < 2**31:
            raise ValueError("Invalid native interactive script")
        for key in ("x", "y", "z"):
            if type(item[key]) is not int:
                raise ValueError(f"Invalid {key}")
        if type(item["max_distance"]) is not int or not 1 <= item["max_distance"] <= 4:
            raise ValueError("Invalid interaction distance")
        if any(
            type(item[k]) is not int or item[k] < 0
            for k in ("required_item", "required_quantity")
        ):
            raise ValueError("Invalid interaction cost")
        if (item["required_item"] == 0) != (item["required_quantity"] == 0):
            raise ValueError("Incomplete interaction cost")
        if not isinstance(item["object_type"], str) or not item["object_type"].strip():
            raise ValueError("Missing interactive type")
        if not isinstance(item["evidence"], str) or not item["evidence"].strip():
            raise ValueError("Missing reconstruction evidence")
        key = tuple(item[k] for k in KEYS)
        if key in seen:
            raise ValueError("Conflicting duplicate interaction in batch")
        seen.add(key)
        records.append(item)
    return records


def install(db, document, revision):
    records = validate_manifest(document, revision)
    with db.transaction():
        for item in records:
            source = db.execute(
                "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
                (revision, item["quest_id"]),
            ).fetchone()
            if source is None:
                raise ValueError("Missing native mission definition")
            definition = source["data"]["native"]
            if (
                definition.get("native_class") != "aJM"
                or definition.get("aqb") is not False
            ):
                raise ValueError("Unsupported native mission lifecycle")
            if item["objective_id"] not in {o["d"] for o in definition["cjJ"]}:
                raise ValueError("Objective does not belong to mission")
            for reward in definition["cjK"]:
                rewards.validate(reward)
            values = tuple(item[k] for k in FIELDS)
            db.execute(
                "INSERT INTO quest_interactive_bindings (" + ",".join(FIELDS) + ") "
                "VALUES (" + ",".join(["%s"] * len(FIELDS)) + ") "
                "ON CONFLICT (map_id,object_id,action_id,parameter) DO NOTHING",
                values,
            )
            current = db.execute(
                "SELECT * FROM quest_interactive_bindings WHERE map_id=%s AND object_id=%s AND action_id=%s AND parameter=%s",
                values[:4],
            ).fetchone()
            if current is None or tuple(current[k] for k in FIELDS) != values:
                raise ValueError("Existing binding conflicts with batch")
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--install", action="store_true", help="Publish reviewed bindings to PostgreSQL"
    )
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text())
    records = validate_manifest(document, args.revision)
    if not args.install:
        print(f"Validated {len(records)} reviewed bindings (dry run)")
        return
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            count = install(db, document, args.revision)
        print(f"Installed or verified {count} reviewed bindings")
    finally:
        database.close()


if __name__ == "__main__":
    main()
