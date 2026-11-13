"""Publish a client-only mission journal preview for the requested character.

No player progress, rewards or server-side quest authority is changed.
"""
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database

REVISION = "3d1e48353eef085e9d2159340ea170ac51d6a878093e90f1214a60ab2eed4a06"


def install(db):
    character = db.execute(
        "SELECT id FROM characters WHERE id=40 AND lower(name)='hiperbufona' AND deleted_at IS NULL"
    ).fetchone()
    if character is None:
        raise ValueError("Expected local character not found")
    state = db.execute(
        "SELECT state FROM character_achievement_progress WHERE character_id=40"
    ).fetchone()
    rows = db.execute(
        "SELECT definition_id FROM native_quest_metadata_definitions WHERE revision=%s AND (data->'native'->>'aeV')::int BETWEEN 1 AND 5 ORDER BY definition_id",
        (REVISION,),
    ).fetchall()
    ids = [r["definition_id"] for r in rows]
    if (
        len(ids) != 1430
        or state is None
        or not set(ids) <= set(state["state"]["completed"])
    ):
        raise ValueError("Mission preview requires the complete native journal")
    value = {
        "schema": "mission_journal_preview_v1",
        "character_id": 40,
        "active": ids,
        "completed": [5165],
    }
    db.execute(
        "INSERT INTO settings(name,value) VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
        ("mission_journal_preview", Jsonb(value)),
    )
    return len(ids)


if __name__ == "__main__":
    pool = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with pool.connection() as db:
            print("Mission preview definitions:", install(db))
    finally:
        pool.close()
