#!/usr/bin/env python3
"""Validate or install reviewed local quest resources without restarting World."""
import argparse
import json
import os
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from install_mission_bundle import local_connection
    from wakfu_server.store import Store
    from wakfu_server.achievements import mission_toolkit
    from wakfu_server.quest_resource_slots import install

    dsn = os.environ["WAKFU_DATABASE_URL"]
    local_connection(dsn)
    profile = json.loads(args.profile.read_text())
    geometry = json.loads(args.geometry.read_text())
    store = Store(dsn, password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"))
    with store.connection() as db:
        with db.transaction(force_rollback=not args.apply):
            native = mission_toolkit.definitions(
                db,
                {
                    "bindings": [{"quest_id": profile["quest_id"]}],
                    "links": [],
                    "activations": [],
                },
            )
            count = install(db, store, profile, native, geometry)
    print(
        json.dumps(
            {"profile": profile["id"], "placements": count, "applied": args.apply}
        )
    )


if __name__ == "__main__":
    main()
