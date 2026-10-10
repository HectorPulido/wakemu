"""Offline literal internal transport audit against proven physical room chains."""
import json, sys
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parent),
    str(Path(__file__).resolve().parents[1]),
]
from build_physical_dungeon_configuration import topology_for
from extract_native_door_flow import shortest_path

rows = json.load(open(".runtime/local/all-native-dungeon-flows.json"))["records"]
out = []
for r in rows:
    if r["status"] != "mixed_transport_physical_review":
        continue
    g = json.load(
        open(
            f".runtime/local/all-native-dungeon-exploration/exploration-{r['route']['start_map_id']}.json"
        )
    )
    inv = next(
        x
        for x in json.load(open("docs/reports/dungeons/inventory.json"))["records"]
        if x["key"] == r["key"]
    )
    doors = [
        x
        for x in inv["native_objects"]
        if x["map_id"] == g["map_id"] and x["type"] == "Door"
    ]
    t = topology_for(g, doors, r["entry"], r["directed_physical_flows"][0]["exit"], [])
    labels = {tuple(c): q["order"] for q in t["rooms"] for c in q["cells"]}
    links = []
    for s in r["native_internal_teleports"]:
        positions = [
            tuple(p[k] for k in ("x", "y", "z")) for p in s["approach_positions"]
        ]
        center = tuple(s[k] for k in ("x", "y", "z"))
        if not s["approach_blocks_center"]:
            positions.append(center)
        for d in s["destinations"]:
            if d["map_id"] != g["map_id"]:
                continue
            target = tuple(d[k] for k in ("x", "y", "z"))
            links.append(
                dict(
                    source_id=s["id"],
                    destination_id=d["destination_id"],
                    source_positions=[list(p) for p in positions],
                    source_rooms=sorted({labels[p] for p in positions if p in labels}),
                    destination=list(target),
                    destination_room=labels.get(target),
                    criterion=d["criterion"],
                )
            )
    out.append(
        dict(
            key=r["key"],
            name=r["name"],
            map_id=g["map_id"],
            physical_door_chain=r["directed_physical_flows"][0]["door_chain"],
            links=links,
        )
    )
for row in out:
    for link in row["links"]:
        destination = link["destination_room"]
        sources = link["source_rooms"]
        if destination is None or len(sources) != 1:
            link["blocker"] = "native_transport_endpoint_outside_physical_room_chain"
        elif destination > sources[0] + 1:
            link["blocker"] = "native_transport_skips_locked_physical_rooms"
        elif destination == sources[0]:
            link[
                "blocker"
            ] = "same_room_native_transport_not_supported_by_adjacent_room_runtime"
        elif abs(destination - sources[0]) > 1:
            link[
                "blocker"
            ] = "nonadjacent_native_return_not_supported_by_adjacent_room_runtime"
        else:
            link["blocker"] = None
    row["status"] = (
        "blocked" if any(l["blocker"] for l in row["links"]) else "candidate"
    )
report = dict(
    schema_version=1,
    authority="Read-only native geometry and exact transport endpoints; no runtime activation",
    records=out,
)
print(json.dumps(report, indent=2))
