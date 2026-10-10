"""Report installed dungeon access limits without treating installation as acceptance.

Input is the configuration bundle exported by install_dungeon_bulk. This command
is read-only and deliberately never changes access criteria or native objects.
"""
import argparse
import json
import re
from pathlib import Path


SUPPORTED_PREDICATES = {
    "IsNeoServer",
    "GetBooleanSystemConfiguration",
    "GetRealLevel",
    "GetItemQuantity",
    "IsAfter",
    "IsBefore",
    "not",
    "and",
    "or",
}


def audit(bundle):
    rows = []
    for config in bundle["configurations"]:
        route, topology = config["route"], config["topology"]
        automatic = topology.get("policy") == "local_accessible_anchor_policy"
        missing = sorted(
            set(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", route["criterion"]))
            - SUPPORTED_PREDICATES
        )
        rooms = topology["rooms"]
        links = topology.get("auto_edges" if automatic else "doors", ())
        gaps = [
            order
            for order in range(1, len(rooms))
            if sum(
                edge["source_room"] == order and edge["destination_room"] == order + 1
                for edge in links
            )
            != 1
        ]
        bad_anchors = [
            room["order"]
            for room in rooms
            if tuple(room["anchor"]) not in set(map(tuple, room["cells"]))
        ]
        rows.append(
            {
                "slug": config["slug"],
                "route_key": route["key"],
                "room_count": len(rooms),
                "travel": "victory_automatic" if automatic else "native_doors",
                "native_doors_enabled": not automatic,
                "entry_missing_authority": missing,
                "forward_link_gaps": gaps,
                "invalid_room_anchors": bad_anchors,
                "client_accepted": False,
            }
        )
    return {
        "configuration_count": len(rows),
        "entry_authority_blocked": sum(
            bool(row["entry_missing_authority"]) for row in rows
        ),
        "automatic_travel_count": sum(
            row["travel"] == "victory_automatic" for row in rows
        ),
        "dungeons": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(json.loads(args.bundle.read_text())), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
