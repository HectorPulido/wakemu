"""Publish a reconstructed Magnum weekly-hunter offer provider locally.

Installs only an actor action policy and receipt-source bindings; never creates
player progress or starts an offer. Caller selects environment explicitly.
"""
import argparse
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.weekly_hunter_npc import ACTION, ACTOR, REFERENCE, SETTING


def install(db):
    actor = db.execute(
        "SELECT * FROM world_native_npc_placements WHERE actor_id=%s AND enabled FOR SHARE",
        (ACTOR,),
    ).fetchone()
    if (
        actor is None
        or actor["reference_id"] != REFERENCE
        or ACTION not in actor["native_action_ids"]
    ):
        raise ValueError("Expected Magnum native actor/action missing")
    offers = db.execute(
        "SELECT o.* FROM recurring_hunter_native_offers o JOIN recurring_hunter_contracts c USING(definition_id,version) WHERE c.period_ms=604800000 AND o.version=(SELECT max(o2.version) FROM recurring_hunter_native_offers o2 WHERE o2.definition_id=o.definition_id)"
    ).fetchall()
    if len(offers) != 16:
        raise ValueError("Expected 16 recovered weekly native offers")
    from wakfu_server.objectives.environmental_recurring_offers import (
        compile_hunter_offers,
    )
    from wakfu_server.npc_dialogue import catalog

    decoded = compile_hunter_offers(
        catalog()["nodes"], {o["definition_id"] for o in offers}
    )
    for offer in offers:
        native = decoded[offer["definition_id"]]
        if (
            native.node_id,
            native.choice_id,
            native.minimum_level,
            native.category_id,
            native.criterion,
        ) != (
            offer["node_id"],
            offer["choice_id"],
            offer["minimum_level"],
            offer["category_id"],
            offer["criterion"],
        ):
            raise ValueError("Published hunter offer differs from native client")
        db.execute(
            "INSERT INTO recurring_hunter_acceptance_sources(definition_id,version,source_kind,source_reference,action_id,source_authority) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                offer["definition_id"],
                offer["version"],
                "npc_dialogue",
                REFERENCE,
                ACTION,
                "wakemu.reconstructed-magnum-weekly-bracket.v1",
            ),
        )
    desired = {"enabled": True, "actor_id": ACTOR, "action_id": ACTION}
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if previous and previous["value"] != desired:
        raise ValueError("Hunter provider already has different policy")
    db.execute(
        "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT DO NOTHING",
        (SETTING, Jsonb(desired)),
    )
    return len(offers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit provider configuration to selected database",
    )
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            if not args.apply:
                raise ValueError("Explicit --apply required")
            print("Weekly native offers published:", install(db))
    finally:
        database.close()


if __name__ == "__main__":
    main()
