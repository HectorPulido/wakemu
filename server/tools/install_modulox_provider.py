"""Prepare the reconstructed Mod'Ulo native category-offer source locally."""
import argparse
import os
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
from wakfu_server.modulox_npc import SETTING, REFERENCE, ACTION, ROOT, CHOICES
from wakfu_server.objectives.environmental_recurring_storage import (
    MODULOX_POLICY,
    _load,
)
from wakfu_server.objectives.environmental_daily_selection import POLICY


def install(db, *, apply=False):
    from wakfu_server.npc_dialogue import catalog

    nodes = catalog()["node_index"]
    node = nodes[ROOT]
    for choice_id, (category, minimum) in CHOICES.items():
        native = next((c for c in node["choices"] if c["id"] == choice_id), None)
        if native is None or native["type"] != 5:
            raise ValueError("Native Modulo offer changed")
        from wakfu_server.objectives.environmental_modulox_contracts import (
            offer_parameters,
        )

        if offer_parameters(native["criteria"]) != (minimum, category):
            raise ValueError("Native Modulo offer criterion changed")
    active = db.execute(
        "SELECT a.pool_version,p.sealed,p.interpretation_policy FROM recurring_hunter_daily_active a JOIN recurring_hunter_daily_pools p USING(pool_version) WHERE a.singleton FOR UPDATE OF a"
    ).fetchone()
    if not active or not active["sealed"] or active["interpretation_policy"] != POLICY:
        raise ValueError("No qualified daily rotation pool")
    rows = db.execute(
        "SELECT m.definition_id,m.version,m.category_id FROM recurring_hunter_daily_members m JOIN recurring_hunter_contracts c USING(definition_id,version) WHERE m.pool_version=%s AND c.interpretation_policy=%s",
        (active["pool_version"], MODULOX_POLICY),
    ).fetchall()
    if len(rows) != 64 or {r["category_id"] for r in rows} != {
        x[0] for x in CHOICES.values()
    }:
        raise ValueError("Unexpected Modulox pool")
    for row in rows:
        _load(db, row["definition_id"], row["version"])
    policy = {"enabled": True, "reference_id": REFERENCE, "action_id": ACTION}
    old = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if old and old["value"] != policy:
        raise ValueError("Conflicting Modulo provider policy")
    if apply:
        for row in rows:
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources(definition_id,version,source_kind,source_reference,action_id,source_authority) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    row["definition_id"],
                    row["version"],
                    "npc_dialogue",
                    REFERENCE,
                    ACTION,
                    "wakemu.reconstructed-modulox-haven-bag-v1",
                ),
            )
            found = db.execute(
                "SELECT source_authority FROM recurring_hunter_acceptance_sources WHERE definition_id=%s AND version=%s AND source_kind=%s AND source_reference=%s AND action_id=%s",
                (
                    row["definition_id"],
                    row["version"],
                    "npc_dialogue",
                    REFERENCE,
                    ACTION,
                ),
            ).fetchone()
            if (
                not found
                or found["source_authority"]
                != "wakemu.reconstructed-modulox-haven-bag-v1"
            ):
                raise ValueError("Conflicting Modulox acceptance source")
        db.execute(
            "UPDATE recurring_hunter_daily_active SET enabled=true WHERE singleton"
        )
        db.execute(
            "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO NOTHING",
            (SETTING, Jsonb(policy)),
        )
    return {"definitions": len(rows), "categories": len(CHOICES), "published": apply}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--install", action="store_true")
    args = p.parse_args()
    db = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with db.connection() as c:
            print(install(c, apply=args.install))
    finally:
        db.close()


if __name__ == "__main__":
    main()
