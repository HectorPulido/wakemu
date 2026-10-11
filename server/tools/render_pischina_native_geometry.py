"""Render independent Pischina arena cuts and verify native combat formations.

Run from repository root with read-only native catalog access. No runtime writes.
"""
import json, sys
from pathlib import Path
from collections import defaultdict

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parent),
]
from extract_dungeon_topology import components
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.dungeon_encounters import enemy_formation

geom = json.loads(
    Path(
        ".runtime/local/all-native-dungeon-exploration/exploration-912.json"
    ).read_text()
)
rec = next(
    r
    for r in json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    if r["key"] == "native:143"
)
objects = rec["native_objects"]
cuts = {
    (o["x"], o["y"], o["z"])
    for o in objects
    if o["id"] in [31447, 31448, 31449, 31450, 31487]
}
adj = defaultdict(set)
for a, b in geom["edges"]:
    adj[tuple(a)].add(tuple(b))
    adj[tuple(b)].add(tuple(a))
labels, sizes = components(set(map(tuple, geom["cells"])) - cuts, adj)
p = published_geometry(912)
cc = set(map(tuple, p.cells))
rows = []
for order, region in enumerate([3, 2, 9, 0], 1):
    cells = {c for c, r in labels.items() if r == region}
    valid = cells & cc
    section = dict(
        map_id=912,
        cells=list(valid),
        edges=[e for e in p.edges if tuple(e[0]) in valid and tuple(e[1]) in valid],
    )
    center = [sum(c[i] for c in cells) / len(cells) for i in range(3)]
    success = []
    for anchor in sorted(
        valid, key=lambda c: sum((c[i] - center[i]) ** 2 for i in range(3))
    ):
        try:
            pos = list(enemy_formation(section, anchor, 8, player_slots=6))
        except ValueError:
            continue
        success.append(dict(anchor=list(anchor), enemies=pos))
        if len(success) == 3:
            break
    rows.append(
        dict(
            order=order,
            region=region,
            native_cells=len(cells),
            combat_cells=len(valid),
            formations=success,
        )
    )
result = dict(
    map_id=912,
    arenas=rows,
    trigger_cuts=sorted(cuts),
    component_sizes=sizes,
    footprint_hypothesis=dict(
        object_z=-4,
        terrain_z=-5,
        cells=[[60, 0, -5], [61, 0, -5], [60, 10, -5], [61, 10, -5]],
        authority="Unique terrain at identical XY; collision footprint not independently decoded",
    ),
)
directed = defaultdict(list)
for a, b in geom["edges"]:
    directed[tuple(a)].append(tuple(b))


def reachable(start, blocked):
    seen = {tuple(start)}
    queue = list(seen)
    for cell in queue:
        for neighbor in directed.get(cell, []):
            if neighbor not in blocked and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


checks = []
for index, (ids, boundary) in enumerate(
    [
        ([31447], [[24, 15, 1]]),
        ([31448], [[33, 6, 1]]),
        ([31449, 31450], [[52, -4, 1], [53, -4, 1]]),
    ]
):
    start = rows[index]["formations"][0]["anchor"]
    target = tuple(rows[index + 1]["formations"][0]["anchor"])
    check = dict(
        stage=index + 1,
        trigger_ids=ids,
        cells=boundary,
        closed_target_reachable=target in reachable(start, set(map(tuple, boundary))),
        open_target_reachable=target in reachable(start, set()),
    )
    assert not check["closed_target_reachable"] and check["open_target_reachable"]
    checks.append(check)
result["directed_frontier_checks"] = checks
result["entry_route"] = dict(
    exterior_map_id=1208,
    exterior_object_id=14589,
    exterior_position=[17, 56, -36],
    entry=[22, 38, 0],
)
Path("docs/reports/dungeons/PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(json.dumps(result))
colors = {3: "#167d8d", 2: "#448a37", 9: "#d88725", 0: "#9756af", 11: "#aaa"}
svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1050" viewBox="0 0 1100 1050">',
    '<rect width="1100" height="1050" fill="white"/>',
    "<style>text{font-family:Arial,sans-serif;font-size:14px}</style>",
    '<text x="30" y="30" font-size="22">La Pischina / native map 912: four arenas and optional annex</text>',
    '<text x="30" y="58">Exact XYZ graph; colors follow native PositionTrigger cuts. XY diagram overlaps elevation layers.</text>',
]


def project(x, y):
    return 90 + (x - 15) * 13, 100 + (y + 34) * 10


for (x, y, z), r in labels.items():
    px, py = project(x, y)
    svg.append(
        f'<circle cx="{px}" cy="{py}" r="3.6" fill="{colors.get(r,"#ddd")}"><title>region {r}: {x},{y},{z}</title></circle>'
    )
for o in objects:
    if o["type"] not in ["Door", "PositionTrigger", "Teleporter", "LootChest"]:
        continue
    px, py = project(o["x"], o["y"])
    color = {
        "Door": "#d62728",
        "PositionTrigger": "#111",
        "Teleporter": "#247ce4",
        "LootChest": "#ca9a00",
    }[o["type"]]
    svg.append(
        f'<rect x="{px-5}" y="{py-5}" width="10" height="10" fill="{color}"/><text x="{px+8}" y="{py-5}">{o["id"]} z={o["z"]}</text>'
    )
for row in rows:
    if row["formations"]:
        a = row["formations"][0]["anchor"]
        px, py = project(a[0], a[1])
        svg.append(
            f'<text x="{px-20}" y="{py}" font-weight="bold">ROOM {row["order"]}</text>'
        )
svg += [
    '<text x="30" y="900">Black: PositionTriggers 31447, 31448, and parallel frontier 31449/31450.</text>',
    '<text x="30" y="926">Red: Door objects. Door 31487 leads from room 3 into the gray optional annex.</text>',
    '<text x="30" y="952">Four annex doors at z=-4 project onto terrain z=-5: footprint hypothesis, not decoded collision authority.</text>',
    '<text x="30" y="978">Blue: literal exterior transporters 24196 (entry) and 24197 (boss arena). Gold: annex chest.</text>',
    '<text x="30" y="1004">All four arenas accommodate six players and eight enemies with native combat geometry.</text>',
    "</svg>",
]
Path(
    "docs/reports/dungeons/PISCHINA-NATIVE-GEOMETRY-ANNOTATED-20261010.svg"
).write_text("\n".join(svg) + "\n")
