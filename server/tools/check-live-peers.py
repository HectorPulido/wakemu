#!/usr/bin/env python3
"""Verify reciprocal visibility/positions in two running local GUI clients."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wakfu_server.profiles import profile_root


def inspect(profile, endpoint):
    config = json.loads((profile_root(profile) / "inspector.json").read_text())
    request = urllib.request.Request(
        f"http://127.0.0.1:{config['port']}/{endpoint}",
        headers={"X-Inspector-Key": config["secret"]},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def verify(first, second):
    positions = {profile: inspect(profile, "position") for profile in (first, second)}
    for profile, position in positions.items():
        if position.get("status") == "not_loaded":
            raise ValueError(f"{profile} has no loaded character")
    actors = {profile: inspect(profile, "actors") for profile in (first, second)}
    for observer, other in ((first, second), (second, first)):
        position = positions[other]
        if position.get("status") == "not_loaded":
            raise ValueError(f"{other} has no loaded character")
        matches = [
            actor for actor in actors[observer] if actor["name"] == position["name"]
        ]
        if len(matches) != 1:
            raise ValueError(
                f'{observer} sees {len(matches)} actors named {position["name"]}'
            )
        for axis in ("x", "y", "z"):
            if matches[0][axis] != position[axis]:
                raise ValueError(
                    f"{observer} sees a different {axis} position for {other}; retry after movement ends"
                )
    return {
        "profiles": [first, second],
        "positions": positions,
        "reciprocal_visibility": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", nargs="?", default="alpha")
    parser.add_argument("second", nargs="?", default="beta")
    args = parser.parse_args()
    print(json.dumps(verify(args.first, args.second), ensure_ascii=False, indent=2))
