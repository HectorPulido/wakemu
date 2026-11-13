"""Publish the reviewed turn-in extension without replacing existing NPCs.

This operator command modifies only the quest contract and explicitly added NPCs.
It never creates, edits, or resets player progress or inventory.
"""
import json
import os
from pathlib import Path
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.quest_npc import install, publication

SETTING = "native_quest_conversation_contracts"
# Only these newly reconstructed actors are published by this extension.
NEW_REFS = {2358, 2873}


def _preserves(previous, new):
    """Reject removed data and changed existing actors or their existing edges."""
    if not isinstance(previous, dict) or not isinstance(new, dict):
        return False
    for key, value in previous.items():
        if key not in new:
            return False
        if key == "placements":
            if not isinstance(value, list) or not isinstance(new[key], list):
                return False
            for old in value:
                candidates = [
                    r
                    for r in new[key]
                    if r["row"]["actor_id"] == old["row"]["actor_id"]
                ]
                if len(candidates) != 1:
                    return False
                current = candidates[0]
                if any(
                    current.get(k) != old.get(k)
                    for k in set(old) | set(current)
                    if k != "graph"
                ):
                    return False
                if any(edge not in current["graph"] for edge in old["graph"]):
                    return False
        elif isinstance(value, list):
            if not isinstance(new[key], list) or any(
                row not in new[key] for row in value
            ):
                return False
        elif value != new[key]:
            return False
    return True


def publish(db, document):
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Quest publication requires an active transaction")
    before = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if before is None or not _preserves(before["value"], document):
        raise ValueError("Current quest publication is not an additive predecessor")
    # Protect live placements: only new, explicitly reviewed actors may be added.
    previous_refs = {p["row"]["reference_id"] for p in before["value"]["placements"]}
    additions = [
        p
        for p in document["placements"]
        if p["row"]["reference_id"] not in previous_refs
    ]
    if any(p["row"]["reference_id"] not in NEW_REFS for p in additions):
        raise ValueError("Unexpected new quest NPC in source contract")
    if before["value"] != document:
        db.execute(
            "UPDATE settings SET value=%s WHERE name=%s", (Jsonb(document), SETTING)
        )
    actors = {
        p["row"]["actor_id"]
        for p in document["placements"]
        if p["row"]["reference_id"] in NEW_REFS
    }
    install(db, document, actor_ids=actors)
    if publication(db) is None:
        raise ValueError("Published quest contract failed validation")
    return {
        "added_references": sorted({p["row"]["reference_id"] for p in additions}),
        "actors_checked": len(actors),
    }


def main():
    source = (
        Path(__file__).resolve().parents[1]
        / "wakfu_server/maps/native_quest_conversation_contracts.json"
    )
    document = json.loads(source.read_text())
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            with db.transaction():
                print(publish(db, document))
    finally:
        database.close()


if __name__ == "__main__":
    main()
