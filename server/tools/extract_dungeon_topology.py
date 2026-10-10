"""Offline native terrain topology evidence; never invent gameplay progression."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def components(cells, adjacency):
    labels, sizes = {}, []
    for seed in sorted(cells):
        if seed in labels:
            continue
        number, queue = len(sizes), [seed]
        labels[seed] = number
        for cell in queue:
            for neighbor in adjacency.get(cell, ()):
                if neighbor in cells and neighbor not in labels:
                    labels[neighbor] = number
                    queue.append(neighbor)
        sizes.append(len(queue))
    return labels, sizes


def analyze(geometry, objects, entry_positions=(), teleports=()):
    """Use exact Door coordinates only; footprints and gate triggers stay unknown.

    Weak components describe physical region candidates, not directed travel
    permission. A region graph is evidence only if native gate coordinates cut
    the graph. Neither IDs nor proximity define room order.
    """
    cells = {tuple(c) for c in geometry["cells"]}
    adjacency = defaultdict(set)
    asymmetric = set()
    for start, end in geometry["edges"]:
        start, end = tuple(start), tuple(end)
        if start not in cells or end not in cells:
            raise ValueError("Native terrain edge leaves walkable cells")
        adjacency[start].add(end)
        adjacency[end].add(start)
        asymmetric.add((start, end))
    open_labels, open_sizes = components(cells, adjacency)
    doors = [o for o in objects if o["type"] == "Door"]
    door_cells = {tuple(o[k] for k in ("x", "y", "z")) for o in doors} & cells
    closed_labels, closed_sizes = components(cells - door_cells, adjacency)
    evidence = []
    for door in doors:
        position = tuple(door[k] for k in ("x", "y", "z"))
        regions = sorted(
            {
                closed_labels[n]
                for n in adjacency.get(position, ())
                if n in closed_labels
            }
        )
        evidence.append(
            {
                "object_id": door["id"],
                "position": position,
                "exact_cell_walkable": position in cells,
                "adjacent_closed_regions": regions,
                "candidate_separator": len(regions) >= 2,
            }
        )
    entries = [
        {
            "position": list(p),
            "open_component": open_labels.get(tuple(p)),
            "closed_region": closed_labels.get(tuple(p)),
        }
        for p in entry_positions
    ]
    links = []
    for t in teleports:
        position = tuple(t[k] for k in ("x", "y", "z"))
        for d in t["destinations"]:
            destination = tuple(d[k] for k in ("x", "y", "z"))
            links.append(
                {
                    "source_id": t["id"],
                    "source_position": position,
                    "source_region": closed_labels.get(position),
                    "destination_map": d["map_id"],
                    "destination_position": destination,
                    "destination_region": closed_labels.get(destination)
                    if d["map_id"] == geometry["map_id"]
                    else None,
                    "criterion": d.get("criterion"),
                    "destination_id": d.get("destination_id"),
                }
            )
    return {
        "map_id": geometry["map_id"],
        "cell_count": len(cells),
        "asymmetric_native_edges": sum((b, a) not in asymmetric for a, b in asymmetric),
        "open_component_sizes": open_sizes,
        "closed_region_sizes": closed_sizes,
        "doors": evidence,
        "entries": entries,
        "teleport_links": links,
        "scope": "Weak native connectivity; exact single-cell Door blocking hypothesis, not authoritative door footprint or trigger state",
        "unknowns": [
            "Dynamic door collision footprint and state",
            "Fight-to-door unlock dependency",
            "Directed movement validity and scripted transitions",
            "Encounter and boss region binding",
        ],
    }


def build(inventory_path, snapshot_path, output):
    from wakfu_server import native_catalog

    inventory = json.loads(inventory_path.read_text())
    transports = json.loads(
        (snapshot_path / "native-generic-teleporters.json").read_text()
    )
    maps = sorted(
        {m for r in inventory["records"] if r["native"] for m in r["native"]["raw_aHA"]}
    )
    objects = defaultdict(list)
    for r in inventory["records"]:
        for obj in r["native_objects"]:
            if obj not in objects[obj["map_id"]]:
                objects[obj["map_id"]].append(obj)
    revision = native_catalog.release()
    records = []
    with native_catalog._database().connection() as db:
        db.execute("SET TRANSACTION READ ONLY")
        for map_id in maps:
            path = f"combat-maps/{map_id}.json"
            row = db.execute(
                "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (revision, path),
            ).fetchone()
            if row is None:
                records.append({"map_id": map_id, "status": "missing_native_geometry"})
                continue
            raw = bytes(row["raw"])
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Native geometry digest mismatch")
            geometry = json.loads(raw)
            entry_positions = []
            for t in transports:
                if t["map_id"] == map_id:
                    continue
                for d in t["destinations"]:
                    if d["map_id"] == map_id:
                        entry_positions.append(tuple(d[k] for k in ("x", "y", "z")))
            result = analyze(
                geometry,
                objects[map_id],
                sorted(set(entry_positions)),
                [t for t in transports if t["map_id"] == map_id],
            )
            result.update(status="extracted", geometry_sha256=row["sha256"])
            records.append(result)
    summary = {
        "native_maps": len(maps),
        "extracted_maps": sum(r["status"] == "extracted" for r in records),
        "maps_with_doors": sum(bool(r.get("doors")) for r in records),
        "maps_with_separator_candidates": sum(
            any(d["candidate_separator"] for d in r.get("doors", ())) for r in records
        ),
        "door_objects": sum(len(r.get("doors", ())) for r in records),
        "exact_separator_candidates": sum(
            d["candidate_separator"] for r in records for d in r.get("doors", ())
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "topology.json").write_text(
        json.dumps(
            {"catalog_release": revision, "summary": summary, "maps": records}, indent=2
        )
        + "\n"
    )
    lines = [
        "# Automatic native dungeon geometry extraction",
        "",
        "**Follow-up:** [Native Tofu exploration flow](TOFU-NATIVE-FLOW.md) resolves the entry gap below using the installed player movement profile `Sm(6,0,4,true)`. This bulk extraction retains published combat profile `Sm(3,0,2,true)` as input.",
        "",
        "Offline evidence only. No runtime configuration or services changed.",
        "",
        "Exact native coordinates and movement edges are used. Native bBk → bEG → Nm → Re inherits bet() = false; bEG collision writes VD.a(x,y,z,blocked), which marks the exact native surface. The analysis deliberately models all exported Door cells closed; hidden/inactive baseline objects may not block in game. Scripts and combat unlock triggers are not inferred.",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "| Map | Native cells | Open regions | Door-blocked regions | Doors | Separator candidates |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in records:
        if r["status"] == "extracted":
            lines.append(
                f"| {r['map_id']} | {r['cell_count']} | {len(r['open_component_sizes'])} | {len(r['closed_region_sizes'])} | {len(r['doors'])} | {sum(d['candidate_separator'] for d in r['doors'])} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "A separator candidate connects two or more regions when its exact cell is removed along with the other Door cells. This establishes a possible physical gate, not room identity, progression order or victory condition. Nearby cells are never snapped to the door, because that would create unsupported evidence.",
        "",
        "For map 1087 (Tofu), inspect the three exact Door records in topology.json. For map 1086 (Jalato), native teleport links connect separated regions. Both analyses use the same graph extraction.",
        "",
        "102 inventory records with doors comprise 98 native definitions and four legacy-guide-only records/maps; this extractor covers the 151 native definition maps. The next automatic step is to bind native visibility/state and script/event dependencies to these candidate regions; ambiguous branches and missing native cells require explicit evidence before gameplay changes.",
    ]
    lines += [
        "",
        "## Tofu and Jalato evidence"
        + "\n\nTofu (1087) has 671 native walkable cells. Removing all three exported Door cells splits the main 622-cell component into regions of 182, 207 and 230 cells. Door 26874 connects the first two, and 26875 connects the last two. Hidden Door 26873 is not a separator and its native baseline visibility prevents blocking. The entrance destination `(14,-25,0)` belongs to a separate 37-cell component. The missing connection between that entry region and the encounter chain remains unresolved; neither the door IDs nor geometric distance establish the natural entry direction.\n\nJalato (1086) has 1088 native cells. Its internal native teleports connect region 0 → 5 → 3, with return links. Those connected components contain 247, 252 and 328 cells, respectively; decorative disconnected regions are preserved in the evidence rather than counted as encounter rooms. Alternate Neo-server teleport destinations and their criteria are preserved, not silently treated as reachable.\n\n## Native collision evidence\n\nInstalled client bytecode confirms `bBk` extends `bEG`, then `Nm`, then `Re`. `Re.bet()` returns false and no intermediate override exists. The `bEG.a(VD,boolean)` collision updater calls `VD.a(int x,int y,short z,boolean blocked)`. That function writes a coordinate-specific surface obstacle (using a column optimization only when the column has one surface). `bEK` checks co-located interactive elements before clearing an obstacle; `Re.beu()` requires both its blocking flag and visibility. This supports exact-cell geometry analysis for native Door instances, but does not prove that every exported door starts closed or must unlock after a particular combat. The export itself omits dynamic obstacles by design.\n",
    ]
    (output / "GEOMETRY-TOPOLOGY.md").write_text("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(".runtime/local/methodwakfu-dungeons/inventory-native-snapshot"),
    )
    parser.add_argument("--output", type=Path, default=Path("docs/reports/dungeons"))
    args = parser.parse_args()
    print(json.dumps(build(args.inventory, args.snapshot, args.output), indent=2))
