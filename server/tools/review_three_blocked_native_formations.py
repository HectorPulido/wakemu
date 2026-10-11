"""Read-only actual-entry geometry/formation review for classic13,155,84."""
import json, sys
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parent),
]
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.dungeon_encounters import enemy_formation

results = []
for i, mid, entry in [
    (13, 483, [-60, -74, 0]),
    (155, 1256, [0, 3, 0]),
    (84, 806, [-38, 1, 0]),
]:
    from extract_hybrid_native_dungeon_flow import extract
    from audit_native_position_trigger_cuts import witness

    inventory = json.load(open("docs/reports/dungeons/inventory.json"))["records"]
    record = next(r for r in inventory if r["key"] == f"native:{i}")
    route = record["native_entry_routes"][0]
    geometry = json.load(
        open(f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json")
    )
    transports = json.load(
        open(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        )
    )
    graph = extract(
        geometry, record["native_objects"], transports, entry, route["entry_map_id"]
    )
    p = published_geometry(mid)
    pc = set(map(tuple, p.cells))
    rooms = []
    for comp in graph["components"]:
        if len(comp["cells"]) < 10:
            continue
        cells = set(map(tuple, comp["cells"])) & pc
        section = dict(
            map_id=mid,
            cells=list(cells),
            edges=[e for e in p.edges if tuple(e[0]) in cells and tuple(e[1]) in cells],
        )
        checks = []
        for players in [6, 3, 1]:
            for qty in [8, 4, 1]:
                chosen = None
                for anchor in sorted(cells):
                    try:
                        positions = list(
                            enemy_formation(section, anchor, qty, player_slots=players)
                        )
                    except ValueError:
                        continue
                    chosen = dict(anchor=anchor, enemies=positions)
                    break
                checks.append(dict(players=players, enemies=qty, formation=chosen))
        rooms.append(dict(region=comp["region"], cells=len(cells), checks=checks))
    walks = []
    for room in rooms:
        formation = room["checks"][0]["formation"]
        if formation:
            path = witness(geometry["edges"], entry, formation["anchor"], set())
            walks.append(dict(region=room["region"], entry_to_anchor_path=path))
    results.append(
        dict(
            key=f"native:{i}",
            map_id=mid,
            entry=entry,
            regions=rooms,
            native_graph=graph,
            entry_walk_witnesses=walks,
        )
    )
Path(
    "docs/reports/dungeons/THREE-BLOCKED-NATIVE-FORMATIONS-V1-20261010.json"
).write_text(json.dumps(results, indent=2) + "\n")
for r in results:
    print(
        r["key"],
        [
            (
                a["region"],
                a["cells"],
                [
                    (c["players"], c["enemies"], c["formation"]["anchor"])
                    for c in a["checks"]
                    if c["formation"]
                ],
            )
            for a in r["regions"]
        ],
    )
