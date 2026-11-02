"""Export active configured-flow inputs read-only; exclude all player data.

The explicit output is a private test fixture, not a runtime configuration
publication. Large native geometry remains outside the maintained test tree.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from wakfu_server.postgres import Database
from wakfu_server.dungeon_runtime_config import active_configuration
from tools.export_native_scene_seed import scene_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    with database.connection() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        routes = db.execute(
            "SELECT value FROM settings WHERE name='dungeon_runtime_routes'"
        ).fetchone()["value"]["routes"]
        rows = []
        for row in db.execute(
            "SELECT route_key,policy_version FROM dungeon_runtime_active_configurations ORDER BY route_key"
        ).fetchall():
            config = active_configuration(db, row["route_key"])
            rows.append(
                dict(
                    route=row["route_key"],
                    version=row["policy_version"],
                    configuration=config,
                )
            )
        tables = scene_rows(
            db,
            [
                dict(route_key=row["route"], configuration=row["configuration"])
                for row in rows
            ],
        )
        snapshot = dict(
            captured_at=datetime.now(timezone.utc).isoformat(),
            read_only=True,
            authority="Canonical active_configuration, runtime routes and sealed typed scenes in one repeatable-read transaction",
            routes=routes,
            configurations=rows,
            normalized_scene_tables=tables,
        )
    args.output.write_text(json.dumps(snapshot, default=str) + "\n")
    database.close()
    print(
        json.dumps(
            dict(
                output=str(args.output),
                canonical_routes=len(routes),
                typed_scenes=len(tables.get("native_scene_policies", ())),
            )
        )
    )


if __name__ == "__main__":
    main()
