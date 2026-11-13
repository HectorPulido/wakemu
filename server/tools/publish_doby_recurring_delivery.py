"""Publish the reconstructed Doby daily delivery without altering players."""
from copy import deepcopy
import json
import os
from pathlib import Path
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.quest_npc import publication

ACTOR = -2251799934991217
EDGES = [[1986, 4650, 2005], [2005, 4652, 0], [1986, 4651, 0]]


def publish(db, document):
    row = db.execute(
        "SELECT value FROM settings WHERE name='native_quest_conversation_contracts' FOR UPDATE"
    ).fetchone()
    if row is None:
        raise ValueError("Missing quest conversation publication")
    if row["value"] == document:
        return False
    previous = deepcopy(document)
    previous.pop("recurring_deliveries")
    previous["definitions"] = [d for d in previous["definitions"] if d["d"] != 1215]
    placement = next(p for p in previous["placements"] if p["row"]["actor_id"] == ACTOR)
    for edge in EDGES:
        placement["graph"].remove(edge)
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
                print("Doby recurring delivery updated:", publish(connection, document))
    finally:
        db.close()


if __name__ == "__main__":
    main()
