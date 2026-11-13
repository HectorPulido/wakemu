"""Publish Doby's native visual position and separate accessible interaction anchor."""
import json
import os
from copy import deepcopy
from pathlib import Path

from psycopg.types.json import Jsonb
from wakfu_server.achievements.conversation import placement_signature
from wakfu_server.postgres import Database
from wakfu_server.quest_npc import publication

ACTOR = -2251799934991217


def main():
    path = (
        Path(__file__).resolve().parents[1]
        / "wakfu_server/maps/native_quest_conversation_contracts.json"
    )
    document = json.loads(path.read_text())
    item = next(i for i in document["placements"] if i["row"]["actor_id"] == ACTOR)
    row = item["row"]
    old = deepcopy(document)
    old_item = next(i for i in old["placements"] if i["row"]["actor_id"] == ACTOR)
    old_item.pop("interaction_anchor")
    old_item["row"].update(x=8, y=-13, z=1)
    old_signature = placement_signature(old_item["row"])
    next(b for b in old["bindings"] if b["quest_id"] == 1217)[
        "placement_sha256"
    ] = old_signature
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db, db.transaction():
            current = db.execute(
                "SELECT value FROM settings WHERE name=%s FOR UPDATE",
                ("native_quest_conversation_contracts",),
            ).fetchone()
            npc = db.execute(
                "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s FOR UPDATE",
                (ACTOR,),
            ).fetchone()
            if current is None or npc is None:
                raise ValueError("Doby publication is missing")
            if current["value"] == document and placement_signature(
                npc
            ) == placement_signature(row):
                print("Doby native position already published")
                return
            if current["value"] != old or placement_signature(npc) != old_signature:
                raise ValueError("Doby publication differs from expected predecessor")
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(document), "native_quest_conversation_contracts"),
            )
            db.execute(
                "UPDATE world_dialogue_npcs SET x=%s,y=%s,z=%s WHERE actor_id=%s",
                (row["x"], row["y"], row["z"], ACTOR),
            )
            publication(db)
        print("Doby native position and interaction anchor published")
    finally:
        database.close()


if __name__ == "__main__":
    main()
