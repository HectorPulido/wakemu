import csv, json, hashlib
from pathlib import Path
from wakfu_server.planting_cells import cells

source = Path(
    "agents_docs/reports/parallel-readiness-20261021/environmental-original-scenario-locations.csv"
)
scopes = sorted(
    {
        (int(r["map_id"]), int(r["region_id"]))
        for r in csv.DictReader(source.open())
        if r["map_id"] and r["native_cells_present"] == "True"
    }
)
by_map = {}
for map_id, region_id in scopes:
    by_map.setdefault(map_id, set()).add(region_id)
output = Path(
    ".runtime/parallel-readiness-20261021/environmental-original-native-cells.csv"
)
n = 0
with output.open("w") as stream:
    writer = csv.DictWriter(stream, fieldnames=["map_id", "region_id", "x", "y", "z"])
    writer.writeheader()
    for map_id, regions in by_map.items():
        for (x, y), rows in sorted(cells(map_id).items()):
            for r in rows:
                if r["region_id"] in regions:
                    writer.writerow(
                        dict(
                            map_id=map_id, region_id=r["region_id"], x=x, y=y, z=r["z"]
                        )
                    )
                    n += 1
output.with_suffix(".receipt.json").write_text(
    json.dumps(
        dict(
            rows=n,
            maps=len(by_map),
            scopes=len(scopes),
            sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        )
    )
)
