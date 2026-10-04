"""Inventory installed geometry and extracted transports, without capture IDs."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    map_path = ROOT / "protocol/world-maps.json"
    transport_path = ROOT / "protocol/native-transports.json"
    maps = json.loads(map_path.read_text())
    transports = json.loads(transport_path.read_text())
    object_path = ROOT / "protocol/native-transport-objects.json"
    objects = {row["id"]: row for row in json.loads(object_path.read_text())}
    transports = [
        dict(row, **{key: objects[row["id"]][key] for key in ("map_id", "z")})
        if row["id"] in objects
        else row
        for row in transports
    ]
    geometry = set(maps["available_geometry_maps"])
    identified = {row["map_id"] for row in transports if "map_id" in row}
    rows = []
    for identity in sorted(geometry | identified):
        known = [row for row in transports if row.get("map_id") == identity]
        rows.append(
            dict(
                map_id=identity,
                installed_geometry=identity in geometry,
                zaaps=[row for row in known if row["kind"] == 1],
                dragos=[row for row in known if row["kind"] == 2],
                gui_evidence=(
                    "world entry and walking"
                    if identity == 1134
                    else "user traveled from1134 and walked; return interaction failed"
                    if identity == 527
                    else "not verified by this inventory"
                ),
                complete_world_initialization_verified=False,
            )
        )
    unresolved = [row for row in transports if "map_id" not in row]
    return dict(
        schema_version=1,
        sources=[
            dict(
                path=str(p.relative_to(ROOT)),
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            )
            for p in (map_path, transport_path, object_path)
        ],
        notes=[
            "Transport definitions originate in installed client bdata via ExportNativeTransports.java.",
            "Geometry presence is not proof that a map is playable or has complete server data.",
            "Missing transport map associations are explicit; an empty dragos list does not prove absence.",
            "Known IDs for test policy are generated from the catalog, independently of captured account discoveries.",
            "Client menu criteria and missing map interactions may reduce usable destinations.",
        ],
        maps=rows,
        transports_without_map_id=unresolved,
    )


if __name__ == "__main__":
    inventory = build()
    (ROOT / "protocol/map-inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "map_id",
            "installed_geometry",
            "zaap_ids",
            "associated_drago_ids",
            "gui_evidence",
        ]
    )
    for row in inventory["maps"]:
        writer.writerow(
            [
                row["map_id"],
                row["installed_geometry"],
                " ".join(str(t["id"]) for t in row["zaaps"]),
                " ".join(str(t["id"]) for t in row["dragos"]),
                row["gui_evidence"],
            ]
        )
    (ROOT.parent / "docs/reports/map-inventory.csv").write_text(output.getvalue())
    print(
        len(inventory["maps"]),
        "maps;",
        len(inventory["transports_without_map_id"]),
        "transport map associations unresolved",
    )
