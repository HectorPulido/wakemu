"""Inspect or explicitly repair available legacy NPCs; never start services."""
import argparse
import json
import os
from wakfu_server.postgres import Database
from wakfu_server.npc_actor_identity import lua_exact_identity
from wakfu_server.npc_actor_identity_repair import (
    repair_available_group,
    repair_pending_birth,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--map-id", type=int)
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        if args.apply:
            # A loaded world holds cached actor IDs and active harvest tickets.
            # Its existing singleton lock fences an offline identity repair.
            database.acquire_runtime_lock()
        with database.connection() as db:
            query = (
                "SELECT map_id,instance_id,group_id,members,status FROM combat_groups"
            )
            params = ()
            if args.map_id is not None:
                query += " WHERE map_id=%s"
                params = (args.map_id,)
            rows = list(
                db.execute(query + " ORDER BY map_id,instance_id,group_id", params)
            )
            births = list(
                db.execute(
                    "SELECT resource_uid,group_payload FROM planting_growth_outbox "
                    "WHERE NOT published AND group_payload IS NOT NULL ORDER BY resource_uid"
                )
            )
        results = []
        for row in rows:
            if all(lua_exact_identity(member["id"]) for member in row["members"]):
                continue
            key = (row["map_id"], row["instance_id"], row["group_id"])
            if args.apply:
                with database.connection() as db:
                    result = repair_available_group(db, key)
            else:
                result = dict(
                    status="would_remap"
                    if row["status"] == "available"
                    else "skipped_unavailable",
                    key=key,
                )
            results.append(result)
        for birth in births:
            payload = birth["group_payload"]
            if args.map_id is not None and payload["key"][0] != args.map_id:
                continue
            if all(lua_exact_identity(member["id"]) for member in payload["members"]):
                continue
            if args.apply:
                with database.connection() as db:
                    result = repair_pending_birth(db, birth["resource_uid"])
            else:
                result = dict(
                    status="would_remap_pending_birth",
                    key=payload["key"],
                    resource_uid=birth["resource_uid"],
                )
            results.append(result)
        print(json.dumps(dict(applied=args.apply, groups=results), sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
