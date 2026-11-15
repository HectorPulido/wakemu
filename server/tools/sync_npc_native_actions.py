#!/usr/bin/env python3
"""Publish each quest conversation NPC's complete native action set.

`world_dialogue_npcs.action_ids` was seeded with a single action per speaker,
while the installed client placement carries several (the official 2026-11-12
session used Airyna's 1390 for the curriculum, 1389 for the lesson menu and
1252 for free practice). A missing action makes the server answer nothing at
all, so the client leaves the conversation hanging.

The action list is never invented: it is copied from the reviewed native
placement in `world_native_npc_placements.native_action_ids`, which comes from
the installed client data.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg.types.json import Jsonb  # noqa: E402
from wakfu_server.store import Store  # noqa: E402


def sync(db, *, apply_changes):
    rows = db.execute(
        "SELECT d.reference_id, d.actor_id, d.map_id, d.instance_id, d.action_ids AS published,"
        " n.native_action_ids AS native, n.x, n.y, n.z"
        " FROM world_dialogue_npcs d"
        " JOIN world_native_npc_placements n"
        " ON n.actor_id=d.actor_id AND n.reference_id=d.reference_id"
        " AND n.map_id=d.map_id AND n.instance_id=d.instance_id"
        " ORDER BY d.map_id, d.reference_id"
    ).fetchall()
    report = []
    for row in rows:
        native = [int(value) for value in row["native"] or ()]
        published = [int(value) for value in row["published"] or ()]
        missing = [value for value in native if value not in published]
        if not missing:
            continue
        report.append(
            dict(
                reference_id=row["reference_id"],
                map_id=row["map_id"],
                published=published,
                native=native,
                missing=missing,
            )
        )
        if apply_changes:
            # The captured contract is the authority behind the published row's
            # composite foreign key, so it must carry the same actions first.
            db.execute(
                "UPDATE native_captured_npc_contracts SET action_ids=%s,"
                " provenance=provenance || E'\\nInstalled client placement actions ' || %s"
                " || E'; official 2026-11-12 Celestial Dojo session observed these"
                " actions used on the same actor.' WHERE actor_id=%s AND reference_id=%s"
                " AND map_id=%s AND x=%s AND y=%s AND z=%s",
                (
                    Jsonb(native),
                    ",".join(str(value) for value in native),
                    row["actor_id"],
                    row["reference_id"],
                    row["map_id"],
                    row["x"],
                    row["y"],
                    row["z"],
                ),
            )
            db.execute(
                "UPDATE world_dialogue_npcs SET action_ids=%s"
                " WHERE actor_id=%s AND reference_id=%s AND map_id=%s AND instance_id=%s",
                (
                    Jsonb(native),
                    row["actor_id"],
                    row["reference_id"],
                    row["map_id"],
                    row["instance_id"],
                ),
            )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    with store.connection() as db:
        report = sync(db, apply_changes=args.apply)
    for row in report:
        print(
            "mapa %(map_id)d ref %(reference_id)d: publicado %(published)s, nativo %(native)s, falta %(missing)s"
            % row
        )
    if not report:
        print("todas las acciones nativas están publicadas")
    print("aplicado" if args.apply else "solo diagnóstico (usa --apply)")


if __name__ == "__main__":
    main()
