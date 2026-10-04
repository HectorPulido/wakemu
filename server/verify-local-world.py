#!/usr/bin/env python3
"""Read actual client state and verify mutual visibility against SQLite."""
import argparse
import json
from pathlib import Path
import sqlite3
import urllib.request
import urllib.error
from wakfu_server.profiles import profile_root

parser = argparse.ArgumentParser()
parser.add_argument("--profiles", nargs="+", required=True)
args = parser.parse_args()
if len(args.profiles) < 2:
    parser.error("At least two connected client profiles are required")


def inspect(profile, action):
    try:
        config = json.loads((profile_root(profile) / "inspector.json").read_text())
        request = urllib.request.Request(
            f"http://127.0.0.1:{config['port']}/{action}",
            headers={"X-Inspector-Key": config["secret"]},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except (OSError, urllib.error.URLError) as error:
        raise SystemExit(
            f"{profile}: client inspector unavailable ({type(error).__name__})"
        )


positions = {profile: inspect(profile, "position") for profile in args.profiles}
actors = {profile: inspect(profile, "actors") for profile in args.profiles}
with sqlite3.connect(profile_root("main") / "world.sqlite3") as database:
    database.row_factory = sqlite3.Row
    for source, position in positions.items():
        if "name" not in position:
            raise SystemExit(f"{source}: character has not loaded")
        row = database.execute(
            "SELECT id,name,x,y,z FROM characters WHERE name=?", (position["name"],)
        ).fetchone()
        if row is None:
            raise SystemExit(f"{source}: no persisted character")
        for coordinate in ("x", "y", "z"):
            if position[coordinate] != row[coordinate]:
                raise SystemExit(f"{source}: client/database position mismatch")
        for target, entries in actors.items():
            seen = [actor for actor in entries if actor["id"] == row["id"]]
            if len(seen) != 1 or seen[0]["name"] != row["name"]:
                raise SystemExit(f"{target}: {source} is missing or duplicated")
            if any(
                seen[0][coordinate] != position[coordinate]
                for coordinate in ("x", "y", "z")
            ):
                raise SystemExit(f"{target}: {source} has a different position")
        print(
            f"{source}: {row['name']} at ({row['x']},{row['y']},{row['z']}), visible in every client"
        )
evidence = {"positions": positions, "actors": actors}
(profile_root("main") / "visibility-verification.json").write_text(
    json.dumps(evidence, indent=2) + "\n"
)
