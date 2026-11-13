"""Move reconstructed Doby to a walkable neighbor of the native protector."""
import json
import os
from copy import deepcopy
from pathlib import Path

from psycopg.types.json import Jsonb
from wakfu_server.achievements.conversation import placement_signature
from wakfu_server.postgres import Database
from wakfu_server.quest_npc import publication, source_contract_digest

ACTOR = -2251799934991217
OLD_SIGNATURE = "9363b721fa3a267d70449d9bd411c44705511c0cc2007858a2a451a396a96fdc"


def main():
    path = (
        Path(__file__).resolve().parents[1]
        / "wakfu_server/maps/native_quest_conversation_contracts.json"
    )
    document = json.loads(path.read_text())
    row = next(
        i["row"] for i in document["placements"] if i["row"]["actor_id"] == ACTOR
    )
    old = deepcopy(document)
    old_row = next(i["row"] for i in old["placements"] if i["row"]["actor_id"] == ACTOR)
    old_row.update(x=9, y=-13, z=4)
    binding = next(b for b in old["bindings"] if b["quest_id"] == 1217)
    binding["placement_sha256"] = OLD_SIGNATURE
    assert placement_signature(old_row) == OLD_SIGNATURE
    assert source_contract_digest()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            with db.transaction():
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
                    print("Doby placement already updated")
                    return
                if current["value"] != old or placement_signature(npc) != OLD_SIGNATURE:
                    raise ValueError(
                        "Doby publication differs from expected predecessor"
                    )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name=%s",
                    (Jsonb(document), "native_quest_conversation_contracts"),
                )
                db.execute(
                    "UPDATE world_dialogue_npcs SET x=%s,y=%s,z=%s WHERE actor_id=%s",
                    (row["x"], row["y"], row["z"], ACTOR),
                )
                publication(db)
        print("Doby placement updated")
    finally:
        database.close()


if __name__ == "__main__":
    main()
