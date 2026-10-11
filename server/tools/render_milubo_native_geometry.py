"""Render literal Milubo native terrain and gate evidence as a standalone SVG."""
import json
from pathlib import Path
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components


def main():
    geometry = json.loads(
        Path(
            ".runtime/local/all-native-dungeon-exploration/exploration-1266.json"
        ).read_text()
    )
    record = next(
        r
        for r in json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
            "records"
        ]
        if r["key"] == "native:47"
    )
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    doors = [o for o in record["native_objects"] if o["type"] == "Door"]
    labels, sizes = components(
        set(map(tuple, geometry["cells"]))
        - {tuple(d[k] for k in ("x", "y", "z")) for d in doors},
        adjacency,
    )
    colors = {
        9: "#137f89",
        0: "#487c29",
        16: "#da8631",
        6: "#a454b0",
        13: "#999999",
        14: "#777777",
        15: "#4a4a4a",
    }
    panels = [
        ("Entry arena and layered transit", (-4, 41, -19, 18)),
        ("Second arena", (-23, 7, -98, -77)),
        ("Third and fourth arenas", (-14, 60, 103, 136)),
    ]
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="720" viewBox="0 0 1500 720">',
        '<rect width="1500" height="720" fill="#fafafa"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#202020}.small{font-size:12px}.title{font-size:18px;font-weight:bold}</style>",
        '<text x="30" y="34" class="title">Milubo / Donjon Mulou — exact native map 1266</text>',
        '<text x="30" y="60" class="small">Four large encounter regions linked by two physical gates and literal native teleports. Transit regions remain gray.</text>',
    ]
    for index, (title, (xmin, xmax, ymin, ymax)) in enumerate(panels):
        left = 30 + index * 490
        top = 115
        scale = min(440 / (xmax - xmin), 440 / (ymax - ymin))
        width = (xmax - xmin) * scale
        height = (ymax - ymin) * scale

        def project(x, y):
            return left + (x - xmin) * scale, top + (y - ymin) * scale

        svg.append(f'<text x="{left}" y="95" class="title">{title}</text>')
        svg.append(
            f'<rect x="{left}" y="{top}" width="{width}" height="{height}" fill="white" stroke="#ddd"/>'
        )
        for (x, y, z), region in labels.items():
            if not xmin <= x <= xmax or not ymin <= y <= ymax:
                continue
            px, py = project(x, y)
            color = colors.get(region, "#ccc")
            radius = max(1.2, scale * 0.35)
            svg.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity=".78"><title>region {region}: ({x},{y},{z})</title></circle>'
            )
        for obj in record["native_objects"]:
            x, y, z = [obj[k] for k in ("x", "y", "z")]
            if not xmin <= x <= xmax or not ymin <= y <= ymax:
                continue
            px, py = project(x, y)
            if obj["type"] == "Door":
                svg.append(
                    f'<rect x="{px-6:.2f}" y="{py-6:.2f}" width="12" height="12" fill="#e32835" stroke="black"/>'
                )
            elif obj["type"] == "Teleporter":
                svg.append(
                    f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="white" stroke="#202020" stroke-width="2"/>'
                )
            else:
                continue
            svg.append(
                f'<text x="{px+8:.2f}" y="{py-7:.2f}" class="small">{obj["id"]} z={int(z)}</text>'
            )
        svg.append(
            f'<text x="{left}" y="{top+height+23}" class="small">Native X: {xmin}…{xmax}; Y: {ymin}…{ymax}. Z is preserved in source evidence.</text>'
        )
    for index, (region, name) in enumerate(
        [
            (9, "Arena 1 / 196 cells"),
            (0, "Arena 2 / 251 cells"),
            (16, "Arena 3 / 352 cells"),
            (6, "Arena 4 / 356 cells"),
        ]
    ):
        x = 30 + index * 360
        svg.append(
            f'<rect x="{x}" y="615" width="15" height="15" fill="{colors[region]}"/><text x="{x+22}" y="628" class="small">{name}</text>'
        )
    svg.extend(
        [
            '<text x="30" y="666" class="small">Red squares: physical gates 32205 and 32212. White circles: native teleport objects. Gray: corridors / underground transfer terrain.</text>',
            '<text x="30" y="690" class="small">29 XY positions have multiple native Z layers; their topology retains XYZ. This diagram does not assert official fight triggers or boss mechanics.</text>',
            "</svg>",
        ]
    )
    target = Path("docs/reports/dungeons/MILUBO-NATIVE-GEOMETRY-ANNOTATED-20261010.svg")
    target.write_text("\n".join(svg) + "\n")
    print(target)


if __name__ == "__main__":
    main()
