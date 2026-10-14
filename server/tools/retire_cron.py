"""Inspect or revoke only the managed, retired Cron credential and Redis keys.

Stop the retired Cron container before --apply. No player principal is deleted.
"""
import argparse
import json
import os
from pathlib import Path
import stat

import redis
from psycopg.types.json import Jsonb

from wakfu_server.storage.postgres import Database


SETTING = "scheduler_service_credential"
BACKUP_SETTING = "retired_scheduler_service_credential"
PREFIX = "wakfu:cron:*"


def retire(database, client, *, apply=False):
    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (5790545582,))
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
        ).fetchone()
        state = None if row is None else row["value"]
        count = 0
        if state is not None:
            if (
                not isinstance(state, dict)
                or type(state.get("account_id")) is not int
                or not isinstance(state.get("digest"), str)
            ):
                raise ValueError("Managed scheduler credential has invalid metadata")
            token = db.execute(
                "SELECT account_id,kind FROM tokens WHERE digest=%s FOR UPDATE",
                (state["digest"],),
            ).fetchone()
            if token is not None and (
                token["account_id"] != state["account_id"]
                or token["kind"] != "scheduler"
            ):
                raise ValueError("Managed scheduler credential ownership differs")
            count = int(token is not None)
            if apply:
                # Retain the metadata in SQL, including the digest, never stdout.
                db.execute(
                    "INSERT INTO settings(name,value) VALUES(%s,%s) "
                    "ON CONFLICT(name) DO NOTHING",
                    (BACKUP_SETTING, Jsonb(state)),
                )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name=%s",
                    (Jsonb(dict(state, enabled=False)), SETTING),
                )
                db.execute(
                    "DELETE FROM tokens WHERE digest=%s AND account_id=%s AND kind='scheduler'",
                    (state["digest"], state["account_id"]),
                )
    keys = 0
    # SCAN and batched UNLINK avoid a blocking KEYS/DEL operation.
    for chunk_cursor, batch in scan_batches(client):
        keys += len(batch)
        if apply and batch:
            client.unlink(*batch)
    return dict(applied=apply, managed_tokens=count, cron_keys=keys)


def scan_batches(client):
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=PREFIX, count=200)
        yield cursor, keys
        if cursor == 0:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cron-stopped", action="store_true")
    parser.add_argument("--secret-file", type=Path)
    args = parser.parse_args()
    if args.apply and not args.cron_stopped:
        parser.error(
            "--apply requires --cron-stopped after stopping the retired container"
        )
    if args.secret_file:
        info = args.secret_file.lstat()
        if not stat.S_ISREG(info.st_mode) or args.secret_file.name != "scheduler-token":
            parser.error("Secret must be a regular scheduler-token file")
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=1,
    )
    client = redis.Redis.from_url(
        os.environ["WAKFU_REDIS_URL"], socket_timeout=5, socket_connect_timeout=5
    )
    try:
        result = retire(database, client, apply=args.apply)
        if args.apply and args.secret_file:
            args.secret_file.unlink()
            result["retired_secret_removed"] = True
        print(json.dumps(result))
    finally:
        client.close()
        database.close()


if __name__ == "__main__":
    main()
