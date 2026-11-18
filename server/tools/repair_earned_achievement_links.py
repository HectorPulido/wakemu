"""Inspect or repair earned native story achievements on named local characters.

No quest is forced complete. The shared adapter requires each original owned
victory, scene receipt and parent objective. Existing entitlements remain once.
"""

import argparse
import json
import os

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.postgres import Database
from wakfu_server.store import Store
from wakfu_server.achievements import earned_achievement_links, service


def inspect(db, identity):
    row = db.execute(
        "SELECT id,account_id,name FROM characters WHERE id=%s AND deleted_at IS NULL",
        (identity,),
    ).fetchone()
    if row is None:
        raise ValueError("Character does not exist")
    links = db.execute(
        "SELECT achievement_id,reward_key,delivered_at IS NOT NULL AS delivered "
        "FROM character_achievement_reward_outbox WHERE character_id=%s "
        "AND achievement_id=ANY(%s) ORDER BY achievement_id,reward_key",
        (
            identity,
            [entry["achievement_id"] for entry in earned_achievement_links.BINDINGS],
        ),
    ).fetchall()
    return dict(row, rewards=[dict(value) for value in links])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", action="append", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = os.environ["WAKFU_DATABASE_URL"]
    connection = conninfo_to_dict(url)
    if connection.get("host") not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("This repair command only targets local PostgreSQL")
    if not connection.get("dbname", "").startswith("wakemu"):
        raise ValueError("This repair command requires a Wakemu database")
    store = Store(url, password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"))
    try:
        results = []
        for identity in sorted(set(args.character)):
            if identity <= 0:
                raise ValueError("Invalid character identity")
            with store.connection() as db:
                before = inspect(db, identity)
                packets = []
                if args.apply:
                    db.execute(
                        "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                        (before["account_id"],),
                    )
                    character = store.character(before["account_id"], identity, db)
                    packets = earned_achievement_links.recover(db, store, character)
                    packets.extend(service.drain_rewards(db, store, character))
                results.append(
                    dict(
                        character_id=identity,
                        applied=args.apply,
                        before=before,
                        after=inspect(db, identity),
                        packets=len(packets),
                    )
                )
        print(json.dumps(results, ensure_ascii=False, default=str))
    finally:
        store.close()


if __name__ == "__main__":
    main()
