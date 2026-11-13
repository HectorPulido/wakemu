"""Publish the local reconstructed Ruel hunt provider against a pinned catalog.

No character is changed. Existing conflicting policy is never overwritten.
"""
import argparse
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.achievements import rewards, ruel_hunts


def install(db, revision, *, apply=False):
    hunts = ruel_hunts.load_catalog()
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=ANY(%s)",
        (revision, [h["quest_id"] for h in hunts]),
    ).fetchall()
    by_id = {r["definition_id"]: r["data"]["native"] for r in rows}
    if len(by_id) != len(hunts):
        raise ValueError("Pinned Ruel native catalog incomplete")
    for hunt in hunts:
        definition = by_id[hunt["quest_id"]]
        if (
            definition.get("cjG") != 681
            or definition.get("cjP") != hunt["minimum_level"]
            or definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or definition.get("cjU") != 0
            or definition.get("cjL") != 0
            or [o.get("d") for o in definition.get("cjJ", [])] != [hunt["objective_id"]]
        ):
            raise ValueError("Ruel hunt differs from pinned native definition")
        for reward in definition.get("cjK", []):
            rewards.validate(reward)
    policy = {
        "schema": ruel_hunts.SETTING,
        "enabled": True,
        "revision": revision,
        "placement_policy": "reconstructed-courthouse-adjacent-v1",
        "selection_policy": "reconstructed-deterministic-utc-daily-v1",
    }
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (ruel_hunts.SETTING,)
    ).fetchone()
    if previous is not None and previous["value"] != policy:
        raise ValueError("Existing Ruel policy differs")
    if apply and previous is None:
        db.execute(
            "INSERT INTO settings(name,value) VALUES(%s,%s)",
            (ruel_hunts.SETTING, Jsonb(policy)),
        )
    return {"hunts": len(hunts), "published": apply, "prerequisite": 3974}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    d = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with d.connection() as db:
            print(install(db, args.revision, apply=args.install))
    finally:
        d.close()


if __name__ == "__main__":
    main()
