"""Independent native Palacio Zollo hub/return route and formation evidence."""
import json
import sys
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parent),
]
from extract_hybrid_native_dungeon_flow import extract
from audit_native_position_trigger_cuts import witness
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.dungeon_encounters import enemy_formation


def main():
    root = Path("docs/reports/dungeons")
    record = next(
        r
        for r in json.loads((root / "inventory.json").read_text())["records"]
        if r["key"] == "native:73"
    )
    geometry = json.loads(
        Path(
            ".runtime/local/all-native-dungeon-exploration/exploration-1397.json"
        ).read_text()
    )
    transports = json.loads(
        Path(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    graph = extract(geometry, record["native_objects"], transports, [0, 0, 0], 1384)
    combat = published_geometry(1397)
    cc = set(map(tuple, combat.cells))
    arenas = []
    for region in [105, 90, 91, 41, 42, 13, 18, 0]:
        cells = set(map(tuple, graph["components"][region]["cells"]))
        valid = cells & cc
        center = [sum(c[i] for c in cells) / len(cells) for i in range(3)]
        section = dict(
            map_id=1397,
            cells=list(valid),
            edges=[
                e for e in combat.edges if tuple(e[0]) in valid and tuple(e[1]) in valid
            ],
        )
        placements = []
        for anchor in sorted(
            valid, key=lambda c: sum((c[i] - center[i]) ** 2 for i in range(3))
        ):
            try:
                enemies = list(enemy_formation(section, anchor, 8, player_slots=6))
            except ValueError:
                continue
            placements.append(dict(anchor=list(anchor), enemies=enemies))
            if len(placements) == 3:
                break
        arenas.append(dict(region=region, cells=len(cells), formations=placements))
    sequence = [105, 90, 41, 13, 0, 105]
    alternate = [105, 91, 42, 18, 0, 105]
    transitions = []
    for source, target in list(zip(sequence, sequence[1:])) + list(
        zip(alternate, alternate[1:])
    ):
        links = [
            l
            for l in graph["links"]
            if l["source_region"] == source and l["destination_region"] == target
        ]
        transitions.append(dict(source=source, target=target, links=links))
        assert links, (source, target)
    access = []
    for link in graph["links"]:
        target = next(
            (a for a in arenas if a["region"] == link["destination_region"]), None
        )
        if link["kind"] == "native_transport" and target and target["formations"]:
            path = witness(
                geometry["edges"],
                link["destination_position"],
                target["formations"][0]["anchor"],
                set(),
            )
            access.append(
                dict(
                    source_id=link["source_id"],
                    destination_region=link["destination_region"],
                    arrival=link["destination_position"],
                    anchor=target["formations"][0]["anchor"],
                    directed_walk_path=path,
                )
            )
            assert path
    departure_walks = []
    for transition in transitions:
        arena = next(a for a in arenas if a["region"] == transition["source"])
        for link in transition["links"]:
            approaches = link.get("native_approach_cells", [link.get("position")])
            candidates = [
                witness(
                    geometry["edges"], arena["formations"][0]["anchor"], approach, set()
                )
                for approach in approaches
            ]
            paths = [path for path in candidates if path]
            assert paths
            departure_walks.append(
                dict(
                    source_id=link["source_id"],
                    source_region=link["source_region"],
                    directed_walk_path=paths[0],
                )
            )
    entry_walk = witness(
        geometry["edges"], [0, 0, 0], arenas[0]["formations"][0]["anchor"], set()
    )
    assert entry_walk
    result = dict(
        map_id=1397,
        entry=[0, 0, 0],
        native_route=sequence,
        alternate_route=alternate,
        arenas=arenas,
        transitions=transitions,
        arrival_walk_witnesses=access,
        departure_walk_witnesses=departure_walks,
        entry_walk_witness=entry_walk,
        native_graph=graph,
        authority="Literal native geometry; symmetric branches retained; encounter versus transit authority requires separate review",
    )
    (root / "PALACIO-ZOLLO-NATIVE-GEOMETRY-REVIEW-20261010.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    colors = {
        r: c
        for r, c in zip(
            [105, 90, 91, 41, 42, 13, 18, 0],
            [
                "#248994",
                "#538d38",
                "#538d38",
                "#d28b28",
                "#d28b28",
                "#aaa",
                "#aaa",
                "#9559ac",
            ],
        )
    }
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1250" viewBox="0 0 1500 1250">',
        '<rect width="1500" height="650" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;font-size:13px}</style>",
        '<text x="25" y="30">Palacio Zollo / map1397: parallel routes105→90/91→41/42→13/18→0→105</text>',
    ]
    for index, arena in enumerate(arenas):
        cells = graph["components"][arena["region"]]["cells"]
        xmin = min(c[0] for c in cells)
        xmax = max(c[0] for c in cells)
        ymin = min(c[1] for c in cells)
        ymax = max(c[1] for c in cells)
        scale = min(310 / max(xmax - xmin, 1), 410 / max(ymax - ymin, 1))
        left = 30 + (index % 4) * 370
        row_top = (index // 4) * 570

        def project(x, y):
            return left + (x - xmin) * scale, 110 + row_top + (y - ymin) * scale

        svg.append(
            f'<text x="{left}" y="{80+row_top}">Region{arena["region"]}: {arena["cells"]}cells</text>'
        )
        for x, y, z in cells:
            px, py = project(x, y)
            svg.append(
                f'<circle cx="{px}" cy="{py}" r="2.5" fill="{colors[arena["region"]]}"><title>{x},{y},{z}</title></circle>'
            )
        for o in record["native_objects"]:
            if xmin <= o["x"] <= xmax and ymin <= o["y"] <= ymax:
                px, py = project(o["x"], o["y"])
                svg.append(
                    f'<rect x="{px-4}" y="{py-4}" width="8" height="8" fill="black"/><text x="{px+5}" y="{py-5}">{o["id"]}</text>'
                )
    svg += [
        '<text x="25" y="1160">Parallel native routes shown in paired colors. Gray regions13/18 retain their native terrain.</text>',
        '<text x="25" y="1186">34746 returns boss0→entry105;34747 exits. Four native doors separate intermediate regions.</text>',
        '<text x="25" y="1212">All eight large regions tested for six players/eight enemies. XYZ source retained; each panel uses independent XY bounds.</text>',
        "</svg>",
    ]
    (root / "PALACIO-ZOLLO-NATIVE-GEOMETRY-ANNOTATED-20261010.svg").write_text(
        "\n".join(svg) + "\n"
    )
    print(
        json.dumps(
            dict(
                arenas=[
                    dict(
                        region=a["region"],
                        cells=a["cells"],
                        anchor=a["formations"][0]["anchor"]
                        if a["formations"]
                        else None,
                    )
                    for a in arenas
                ],
                exits=graph["exits"],
            )
        )
    )


if __name__ == "__main__":
    main()
