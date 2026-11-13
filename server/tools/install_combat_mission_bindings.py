"""Publish reconstructed combat quest bindings without modifying player progress.

Input is generated/reviewed JSON; acceptance on a matching victory is a local
reconstruction. Existing bindings are preserved and incompatible revisions or
changed bindings are rejected. The default mode validates without writing.
"""
import argparse
import json
import os
from pathlib import Path

from psycopg.types.json import Jsonb

from wakfu_server.achievements import combat_missions, rewards
from wakfu_server.postgres import Database


def _document(value):
    if (
        not isinstance(value, dict)
        or value.get("schema") != combat_missions.SETTING
        or not isinstance(value.get("bindings"), list)
    ):
        raise ValueError("Invalid combat mission publication")
    revision = value.get("revision")
    if (
        not isinstance(revision, str)
        or len(revision) != 64
        or any(ch not in "0123456789abcdef" for ch in revision)
    ):
        raise ValueError("Invalid metadata revision")
    return value


def prepare(db, document, existing=None):
    """Merge compatible entries, validating against pinned client definitions."""
    incoming = _document(document)
    revision = incoming["revision"]
    if existing is not None:
        _document(existing)
        if existing["revision"] != revision:
            raise ValueError("Existing combat publication uses another client revision")
    combined = {}
    for row in (existing or {}).get("bindings", []) + incoming["bindings"]:
        if not isinstance(row, dict) or type(row.get("objective_id")) is not int:
            raise ValueError("Invalid combat mission binding")
        identity = row["objective_id"]
        if identity in combined and combined[identity] != row:
            raise ValueError("Conflicting existing combat objective binding")
        combined[identity] = row
    merged = {
        "schema": combat_missions.SETTING,
        "revision": revision,
        "bindings": [combined[key] for key in sorted(combined)],
    }
    quest_ids = sorted(
        {
            row.get("quest_id")
            for row in merged["bindings"]
            if type(row.get("quest_id")) is int
        }
    )
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions "
        "WHERE revision=%s AND definition_id=ANY(%s)",
        (revision, quest_ids),
    ).fetchall()
    definitions = {row["definition_id"]: row["data"]["native"] for row in rows}
    combat_missions.validate(merged, definitions)
    for definition in definitions.values():
        for reward in definition.get("cjK", []):
            rewards.validate(reward)
    return merged


def install(db, document, *, write=False):
    """Check and optionally publish under an advisory lock in one transaction."""
    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(%s)", (750943830365,))
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s FOR UPDATE",
            (combat_missions.SETTING,),
        ).fetchone()
        existing = None if row is None else row["value"]
        merged = prepare(db, document, existing)
        if write:
            migration = db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=%s", (365,)
            ).fetchone()
            if migration is None:
                raise ValueError(
                    "Apply combat mission migration 365 before publication"
                )
            if existing != merged:
                db.execute(
                    "INSERT INTO settings(name,value) VALUES (%s,%s) "
                    "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                    (combat_missions.SETTING, Jsonb(merged)),
                )
        return {
            "bindings": len(merged["bindings"]),
            "revision": merged["revision"],
            "published": write,
            "changed": write and existing != merged,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--install", action="store_true", help="Publish the validated bindings"
    )
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text())
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            print(json.dumps(install(db, document, write=args.install)))
    finally:
        database.close()


if __name__ == "__main__":
    main()
