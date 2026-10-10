"""Prove exploration door sequences with native directed paths, without unlock assumptions."""
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import analyze


def shortest_path(edges, start, target, blocked=()):
    start, target = tuple(start), tuple(target)
    blocked = set(map(tuple, blocked))
    if start in blocked or target in blocked:
        return None
    adjacency = defaultdict(list)
    for a, b in edges:
        adjacency[tuple(a)].append(tuple(b))
    previous, queue = {start: None}, deque([start])
    while queue:
        current = queue.popleft()
        if current == target:
            path = []
            while current is not None:
                path.append(current)
                current = previous[current]
            return list(reversed(path))
        for neighbor in adjacency[current]:
            if neighbor not in blocked and neighbor not in previous:
                previous[neighbor] = current
                queue.append(neighbor)
    return None


def extract(geometry, doors, entry, exit_position):
    topology = analyze(geometry, doors, [entry])
    door_positions = {d["id"]: tuple(d[k] for k in ("x", "y", "z")) for d in doors}
    links = defaultdict(list)
    candidates = []
    for d in topology["doors"]:
        regions = d["adjacent_closed_regions"]
        if len(regions) == 2:
            links[regions[0]].append((regions[1], d["object_id"]))
            links[regions[1]].append((regions[0], d["object_id"]))
            candidates.append(d["object_id"])
        elif len(regions) > 2:
            return {"status": "branched_door_footprint", "topology": topology}
    region = topology["entries"][0]["closed_region"]
    if region is None:
        return {"status": "entry_not_resolved", "topology": topology}
    region_chain = [region]
    door_chain = []
    while True:
        forward = [(r, d) for r, d in links[region] if r not in region_chain]
        if not forward:
            break
        if len(forward) != 1:
            return {"status": "branched_region_graph", "topology": topology}
        region, door = forward[0]
        region_chain.append(region)
        door_chain.append(door)
    if len(door_chain) != len(candidates):
        return {"status": "disconnected_region_graph", "topology": topology}
    stages = []
    for opened in range(len(door_chain) + 1):
        blocked = [door_positions[d] for d in door_chain[opened:]]
        target = (
            door_positions[door_chain[opened]]
            if opened < len(door_chain)
            else tuple(exit_position)
        )
        # An actor approaches a blocked door; the traversal witness includes its
        # coordinate only for that boundary test, while subsequent doors stay blocked.
        path = shortest_path(
            geometry["edges"], entry, target, [p for p in blocked if p != target]
        )
        exit_path = shortest_path(geometry["edges"], entry, exit_position, blocked)
        stages.append(
            {
                "opened_doors": door_chain[:opened],
                "blocked_doors": door_chain[opened:],
                "target": target,
                "directed_boundary_path": path,
                "exit_reachable": exit_path is not None,
                "directed_exit_path": exit_path,
            }
        )
    return {
        "status": "physical_linear_chain_proved"
        if all(s["directed_boundary_path"] for s in stages)
        and stages[-1]["exit_reachable"]
        else "directed_path_incomplete",
        "map_id": geometry["map_id"],
        "profile": geometry.get("profile"),
        "profile_authority": geometry.get("profile_authority"),
        "client_sha256": geometry.get("client_sha256"),
        "topology_sha256": geometry.get("topology_sha256"),
        "entry": entry,
        "exit": exit_position,
        "region_chain": region_chain,
        "door_chain": door_chain,
        "stages": stages,
        "topology": topology,
        "limits": "Physical directed walk sequence only; combat-clear unlock triggers and encounter spawning require separate authority",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", type=Path)
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument("--entry", type=int, nargs=3, required=True)
    parser.add_argument("--exit", type=int, nargs=3, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    geometry = json.loads(args.geometry.read_text())
    rows = json.loads(args.inventory.read_text())["records"]
    doors = {
        o["id"]: o
        for r in rows
        for o in r["native_objects"]
        if o["map_id"] == geometry["map_id"] and o["type"] == "Door"
    }
    result = extract(geometry, list(doors.values()), args.entry, args.exit)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in ("status", "map_id", "door_chain", "region_chain")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
