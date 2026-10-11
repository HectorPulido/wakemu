"""Native English map labels and bounded administrative map inspection.

Labels are exported from installed texts_en.properties content.77.<map_id>.
Unknown labels remain explicit technical identifiers rather than invented names.
"""
import json
from pathlib import Path

MAP_NAMES = json.loads(Path(__file__).with_name("admin_map_names.json").read_text())
ACTIVE = "(SELECT revision FROM native_catalog_active WHERE id=1)"


def label(row):
    result = dict(row)
    if result.get("name"):
        result["name_source"] = "operator"
    elif str(result["id"]) in MAP_NAMES:
        result["name"] = MAP_NAMES[str(result["id"])]
        result["name_source"] = "native"
    else:
        result["name"] = f"Map #{result['id']}"
        result["name_source"] = "technical"
    return result


def records(db, path, map_id):
    return [
        r["payload"]
        for r in db.execute(
            "SELECT payload FROM native_catalog_records WHERE revision="
            + ACTIVE
            + " AND path=%s AND payload->>'map_id'=%s ORDER BY record_key",
            (path, str(map_id)),
        )
    ]


def details(db, map_id):
    transports = records(db, "native-transport-objects.json", map_id)
    objects = records(db, "native-map-objects.json", map_id)
    native = records(db, "map-inventory.json", map_id)
    ecology = records(db, "ecology-regions.json", map_id)
    row = db.execute(
        "SELECT raw FROM native_catalog_documents WHERE revision="
        + ACTIVE
        + " AND path=%s",
        (f"combat-maps/{map_id}.json",),
    ).fetchone()
    geometry = json.loads(bytes(row["raw"])) if row else {}
    cells = geometry.get("cells", [])
    walkable = {tuple(c) for c in cells}
    destinations = []
    for transport in transports:
        for z in transport.get("arrival_heights", []):
            position = (transport.get("arrival_x"), transport.get("arrival_y"), z)
            if position in walkable:
                destinations.append(
                    dict(
                        label=f"{transport['type']} #{transport['id']}",
                        map_id=map_id,
                        x=position[0],
                        y=position[1],
                        z=z,
                    )
                )
    if cells:
        # Deterministic real walkable surface close to the origin; never guess z.
        cell = min(cells, key=lambda c: (abs(c[0]) + abs(c[1]), abs(c[2]), c))
        destinations.append(
            dict(
                label="Native walkable surface",
                map_id=map_id,
                x=cell[0],
                y=cell[1],
                z=cell[2],
            )
        )
    resources = [
        dict(r)
        for r in db.execute(
            "SELECT resource_uid,instance_id,x,y,z,resource_reference,stage FROM planted_resources WHERE map_id=%s ORDER BY resource_uid LIMIT 200",
            (map_id,),
        )
    ]
    groups = [
        dict(r)
        for r in db.execute(
            "SELECT instance_id,group_id,members,status FROM combat_groups WHERE map_id=%s ORDER BY group_id LIMIT 200",
            (map_id,),
        )
    ]
    resource_count = db.execute(
        "SELECT count(*) n FROM planted_resources WHERE map_id=%s", (map_id,)
    ).fetchone()["n"]
    group_count = db.execute(
        "SELECT count(*) n FROM combat_groups WHERE map_id=%s", (map_id,)
    ).fetchone()["n"]
    bounds = (
        dict(
            x_min=min(c[0] for c in cells),
            x_max=max(c[0] for c in cells),
            y_min=min(c[1] for c in cells),
            y_max=max(c[1] for c in cells),
        )
        if cells
        else None
    )
    return dict(
        native=native[0] if native else None,
        bounds=bounds,
        walkable_cells_count=len(cells),
        destinations=destinations[:100],
        transports=[
            {k: v for k, v in t.items() if k not in ("payload_hex", "chunk")}
            for t in transports[:200]
        ],
        objects=[
            {k: v for k, v in o.items() if k in ("id", "type", "x", "y", "z", "auto")}
            for o in objects[:200]
        ],
        native_objects_count=len(objects),
        resources=resources,
        resources_count=resource_count,
        monster_groups=groups,
        monster_groups_count=group_count,
        regions=ecology[0].get("regions", []) if ecology else [],
        geometry_note="Static native walkable surfaces. Teleport admission also checks current character state and destination policy.",
    )
