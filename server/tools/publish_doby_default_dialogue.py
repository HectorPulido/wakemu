"""Publish the reconstructed Doby greeting graph without changing actors or progress."""
from copy import deepcopy
import json
import os
from pathlib import Path

from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.quest_npc import publication

ACTOR_ID = -2251799934991217
NEW_EDGES = [[1986, 4669, 2015], [2015, 4672, 2016], [2016, 4673, 0]]


def publish(db, document):
    row = db.execute(
        "SELECT value FROM settings WHERE name='native_quest_conversation_contracts' FOR UPDATE"
    ).fetchone()
    if row is None:
        raise ValueError("Missing quest conversation publication")
    previous = deepcopy(document)
    item = next(p for p in previous["placements"] if p["row"]["actor_id"] == ACTOR_ID)
    for edge in NEW_EDGES:
        item["graph"].remove(edge)
    if row["value"] == document:
        return False
    if row["value"] != previous:
        raise ValueError("Current quest publication differs from expected predecessor")
    db.execute(
        "UPDATE settings SET value=%s WHERE name='native_quest_conversation_contracts'",
        (Jsonb(document),),
    )
    if publication(db) is None:
        raise ValueError("Quest publication could not be validated")
    return True


def main():
    source = (
        Path(__file__).resolve().parents[1]
        / "wakfu_server/maps/native_quest_conversation_contracts.json"
    )
    document = json.loads(source.read_text())
    db = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with db.connection() as connection:
            with connection.transaction():
                print("Doby default dialogue updated:", publish(connection, document))
    finally:
        db.close()


if __name__ == "__main__":
    main()
