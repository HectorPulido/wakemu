"""Publish explicit local reconstructed daily-hunter victory acceptance."""
import argparse
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.objectives.recurring_combat_auto import POLICY, SETTING
from wakfu_server.objectives.environmental_recurring_storage import (
    DAILY_POLICY,
    DAILY_NATIVE_POLICY,
    MODULOX_POLICY,
)


def install(db, *, apply=False):
    rows = db.execute(
        "SELECT DISTINCT definition_id FROM recurring_hunter_contracts "
        "WHERE period_ms=86400000 AND interpretation_policy=ANY(%s)",
        ([DAILY_POLICY, DAILY_NATIVE_POLICY, MODULOX_POLICY],),
    ).fetchall()
    ids = {r["definition_id"] for r in rows}
    if len(ids) != 129:
        raise ValueError("Daily hunter authority differs from expected 129 definitions")
    policy = {"policy": POLICY, "enabled": True}
    old = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if old is not None and old["value"] != policy:
        raise ValueError("A different daily combat auto policy is already published")
    if apply and old is None:
        db.execute(
            "INSERT INTO settings(name,value) VALUES(%s,%s)", (SETTING, Jsonb(policy))
        )
    return {"definitions": len(ids), "published": apply, "policy": POLICY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            print(install(db, apply=args.install))
    finally:
        database.close()


if __name__ == "__main__":
    main()
