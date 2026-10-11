"""Render native four-arena Base Susurro activation-frontier evidence."""
import json
from pathlib import Path


def main():
    root = Path("docs/reports/dungeons")
    config = json.loads(
        Path(
            ".runtime/local/base-susurro-zone-v22-20261010/native_dungeon_53.json"
        ).read_text()
    )
    topology = config["topology"]
    colors = ["#247e90", "#459139", "#d98b29", "#9657ad"]
    cells = topology["exploration_geometry"]["cells"]
    xmin = min(c[0] for c in cells)
    ymin = min(c[1] for c in cells)

    def project(p):
        return 70 + (p[0] - xmin) * 15, 90 + (p[1] - ymin) * 8

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="1050" viewBox="0 0 1100 1050">',
        '<rect width="1100" height="1050" fill="white"/>',
        "<style>text{font-family:Arial,sans-serif;font-size:14px}</style>",
        '<text x="30" y="30">Base Susurro / native map448: four arenas and decoded activation-set frontier</text>',
    ]
    for room in topology["rooms"]:
        for cell in room["cells"]:
            x, y = project(cell)
            svg.append(
                f'<circle cx="{x}" cy="{y}" r="3.2" fill="{colors[room["order"]-1]}"><title>stage{room["order"]}: {cell}</title></circle>'
            )
        x, y = project(room["anchor"])
        svg.append(f'<text x="{x+8}" y="{y}">Encounter{room["order"]}</text>')
    for gate in topology["physical_doors"]:
        x, y = project(gate["position"])
        svg.append(
            f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="#df2424"/><text x="{x+8}" y="{y-8}">{gate["source_id"]}</text>'
        )
    for point in topology["native_activation_evidence"]["activation_cells"]:
        x, y = project(point)
        svg.append(
            f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="black"><title>Zone16538 exact activation point {point}</title></rect>'
        )
    svg += [
        '<text x="30" y="930">Native arena order:438cells →63cells →333cells →374cells; all support six players/eight enemies.</text>',
        '<text x="30" y="956">Black: nine exact Re.bkT activation cells, not polygon vertices or a decoded collision footprint.</text>',
        '<text x="30" y="982">Red: four literal native Door cells. Local victory frontiers preserve all native terrain and directed edges.</text>',
        '<text x="30" y="1008">Native trigger scripts and boss mechanics are not implemented by this structural review.</text>',
        "</svg>",
    ]
    path = root / "BASE-SUSURRO-NATIVE-GEOMETRY-ANNOTATED-V22-20261010.svg"
    path.write_text("\n".join(svg) + "\n")
    print(path)


if __name__ == "__main__":
    main()
