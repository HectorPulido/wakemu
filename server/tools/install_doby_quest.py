"""Install the reconstructed Doby mission conversation into a local world."""
import json
from copy import deepcopy
from psycopg.types.json import Jsonb
import os
from pathlib import Path

from wakfu_server.postgres import Database
from wakfu_server.quest_npc import install

ACTOR = -2251799934991217


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
                previous = connection.execute(
                    "SELECT value FROM settings WHERE name='native_quest_conversation_contracts' FOR UPDATE"
                ).fetchone()
                if previous is not None and previous["value"] != document:
                    prior = deepcopy(document)
                    prior["definitions"] = [
                        d for d in prior["definitions"] if d["d"] != 1220
                    ]
                    prior["activation_links"] = [
                        v
                        for v in prior["activation_links"]
                        if v.get("after_quest") != 1217
                    ]
                    if previous["value"] != prior:
                        raise ValueError(
                            "Existing quest publication differs from expected Doby predecessor"
                        )
                    connection.execute(
                        "UPDATE settings SET value=%s WHERE name='native_quest_conversation_contracts'",
                        (Jsonb(document),),
                    )
                install(connection, document, actor_ids={ACTOR})
        print("Installed reconstructed Father Doby mission conversation")
    finally:
        db.close()


if __name__ == "__main__":
    main()
