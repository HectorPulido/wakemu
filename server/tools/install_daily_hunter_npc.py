"""Publish explicitly reconstructed hunter choice for selected daily offers.

Does not activate player missions. Existing weekly offers remain available;
actual player acceptance occurs only on an authenticated native NPC choice.
"""
import argparse
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.maps import daily_hunter_npc as daily, weekly_hunter_npc as weekly
from wakfu_server.objectives import environmental_recurring_storage as recurring


def install(db, *, apply=False):
    actor = db.execute(
        "SELECT * FROM world_native_npc_placements WHERE actor_id=%s AND enabled FOR SHARE",
        (weekly.ACTOR,),
    ).fetchone()
    if (
        actor is None
        or actor["reference_id"] != weekly.REFERENCE
        or weekly.ACTION not in actor["native_action_ids"]
    ):
        raise ValueError("Expected hunter actor/action missing")
    active = db.execute(
        "SELECT a.pool_version,p.sealed,p.interpretation_policy FROM recurring_hunter_daily_active a JOIN recurring_hunter_daily_pools p USING(pool_version) WHERE a.singleton FOR UPDATE OF a"
    ).fetchone()
    if (
        not active
        or not active["sealed"]
        or active["interpretation_policy"]
        != "wakemu.daily-hunter-utc-sorted-rotation-v1"
    ):
        raise ValueError("Daily hunter rotation source missing")
    sources = db.execute(
        "SELECT m.definition_id,m.version,m.category_id,c.interpretation_policy FROM recurring_hunter_daily_members m JOIN recurring_hunter_contracts c USING(definition_id,version) WHERE m.pool_version=%s AND c.interpretation_policy=ANY(%s) ORDER BY m.definition_id",
        (
            active["pool_version"],
            [recurring.DAILY_POLICY, recurring.DAILY_NATIVE_POLICY],
        ),
    ).fetchall()
    if len({row["definition_id"] for row in sources}) != 65:
        raise ValueError("Expected 65 qualified daily hunts")
    # Validate all categories against native weekly dialogue criteria (not just
    # the highest-level root selected for presentation).
    offer_rows = db.execute(
        "SELECT o.* FROM recurring_hunter_native_offers o JOIN recurring_hunter_contracts c USING(definition_id,version) WHERE c.period_ms=604800000 AND o.version=(SELECT max(o2.version) FROM recurring_hunter_native_offers o2 WHERE o2.definition_id=o.definition_id)"
    ).fetchall()
    from wakfu_server.objectives.environmental_recurring_offers import (
        hunter_acceptance_condition,
    )

    categories = set()
    for offer in offer_rows:
        minimum, category = hunter_acceptance_condition(
            offer["criterion"], definition_id=offer["definition_id"]
        )
        if minimum != offer["minimum_level"] or category != offer["category_id"]:
            raise ValueError("Native hunter offer drift")
        categories.add(category)
    if any(row["category_id"] not in categories for row in sources):
        raise ValueError("Daily category has no qualified native hunter choice")
    if len(offer_rows) != 16:
        raise ValueError("Expected 16 native weekly hunter offers")
    weekly_sources = db.execute(
        "SELECT definition_id,version FROM recurring_hunter_acceptance_sources WHERE source_kind=%s AND source_reference=%s AND action_id=%s",
        ("npc_dialogue", weekly.REFERENCE, weekly.ACTION),
    ).fetchall()
    existing_sources = {(r["definition_id"], r["version"]) for r in weekly_sources}
    if any(
        (o["definition_id"], o["version"]) not in existing_sources for o in offer_rows
    ):
        raise ValueError("Weekly offer acceptance sources are not installed")
    desired = {"enabled": True, "policy": daily.POLICY}
    old = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (daily.SETTING,)
    ).fetchone()
    if old and old["value"] != desired:
        raise ValueError("Daily hunter provider has incompatible policy")
    weekly_desired = {
        "enabled": True,
        "actor_id": weekly.ACTOR,
        "action_id": weekly.ACTION,
    }
    weekly_old = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (weekly.SETTING,)
    ).fetchone()
    if weekly_old and weekly_old["value"] not in (
        weekly_desired,
        dict(weekly_desired, enabled=False),
    ):
        raise ValueError("Weekly hunter provider has incompatible policy")
    if apply:
        for row in sources:
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources(definition_id,version,source_kind,source_reference,action_id,source_authority) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    row["definition_id"],
                    row["version"],
                    "npc_dialogue",
                    weekly.REFERENCE,
                    weekly.ACTION,
                    daily.POLICY,
                ),
            )
        db.execute(
            "UPDATE recurring_hunter_daily_active SET enabled=true WHERE singleton"
        )
        db.execute(
            "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
            (weekly.SETTING, Jsonb(weekly_desired)),
        )
        db.execute(
            "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (daily.SETTING, Jsonb(desired)),
        )
    return {
        "definitions": len(sources),
        "categories": len({r["category_id"] for r in sources}),
        "installed": apply,
        "reconstruction": daily.POLICY,
    }


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
