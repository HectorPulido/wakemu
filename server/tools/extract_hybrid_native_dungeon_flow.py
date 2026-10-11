"""Combine literal native walking gates and teleports for offline dungeon review."""
from collections import defaultdict, deque


def extract(geometry, objects, transports, entry, exterior_map_id):
    """Return native component graph, retaining unresolvable endpoint evidence."""
    from extract_dungeon_topology import components

    cells = set(map(tuple, geometry["cells"]))
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    gates = [
        o for o in objects if o["type"] == "Door" and o["map_id"] == geometry["map_id"]
    ]
    gate_positions = {tuple(int(o[k]) for k in ("x", "y", "z")) for o in gates}
    labels, sizes = components(cells - gate_positions, adjacency)
    if tuple(entry) not in labels:
        raise ValueError("Native entry has no gate-closed walk component")
    links = []
    unresolved = []
    exits = []
    for gate in gates:
        center = tuple(int(gate[k]) for k in ("x", "y", "z"))
        regions = sorted({labels[p] for p in adjacency[center] if p in labels})
        if len(regions) == 2:
            for source, destination in (regions, regions[::-1]):
                links.append(
                    dict(
                        kind="physical_gate",
                        source_id=gate["id"],
                        source_region=source,
                        destination_region=destination,
                        position=list(center),
                    )
                )
        elif len(regions) == 1:
            links.append(
                dict(
                    kind="physical_annex_gate",
                    source_id=gate["id"],
                    source_region=regions[0],
                    destination_region=regions[0],
                    position=list(center),
                )
            )
        else:
            unresolved.append(
                dict(
                    kind="physical_gate",
                    source_id=gate["id"],
                    reason="No unique adjacent region pair",
                    regions=regions,
                    position=list(center),
                )
            )
    for source in transports:
        if source["map_id"] != geometry["map_id"]:
            continue
        approaches = {
            tuple(p[k] for k in ("x", "y", "z"))
            for p in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(tuple(int(source[k]) for k in ("x", "y", "z")))
        memberships = {labels[p] for p in approaches if p in labels}
        for destination in source["destinations"]:
            if destination.get("criterion", "").strip() == "IsNeoServer()":
                continue
            row = dict(
                kind="native_transport",
                source_id=source["id"],
                destination_id=destination["destination_id"],
                source_regions=sorted(memberships),
                source_position=[int(source[k]) for k in ("x", "y", "z")],
                native_approach_cells=[
                    list(p) for p in sorted(approaches) if p in labels
                ],
                destination_map_id=destination["map_id"],
                destination_position=[destination[k] for k in ("x", "y", "z")],
                criterion=destination.get("criterion", ""),
            )
            if len(memberships) != 1:
                unresolved.append(
                    dict(
                        row,
                        reason="Literal source approaches do not identify one walk component",
                    )
                )
                continue
            row["source_region"] = next(iter(memberships))
            if (
                destination.get("criterion", "").strip()
                not in ("", "not IsNeoServer()")
                or destination.get("cyZ", -1) >= 0
                or destination.get("cyX", 0)
                or destination.get("cyW", 0)
            ):
                unresolved.append(
                    dict(
                        row,
                        reason="Native criterion/transaction is not an ordinary free classic transition",
                    )
                )
                continue
            if destination["map_id"] != geometry["map_id"]:
                exits.append(
                    dict(
                        row,
                        matches_entry_exterior=destination["map_id"] == exterior_map_id,
                    )
                )
                continue
            target = tuple(row["destination_position"])
            if target not in labels:
                unresolved.append(
                    dict(row, reason="Literal native arrival has no walk component")
                )
                continue
            links.append(dict(row, destination_region=labels[target]))
    reachable = {labels[tuple(entry)]}
    while True:
        following = reachable | {
            l["destination_region"] for l in links if l["source_region"] in reachable
        }
        if following == reachable:
            break
        reachable = following
    return dict(
        map_id=geometry["map_id"],
        entry=list(entry),
        entry_region=labels[tuple(entry)],
        component_sizes=sizes,
        components=[
            dict(region=i, cells=[list(p) for p in sorted(labels) if labels[p] == i])
            for i in range(len(sizes))
        ],
        links=links,
        exits=exits,
        unresolved=unresolved,
        reachable_regions=sorted(reachable),
    )


def main_spine(graph, required_rooms):
    """Find literal exit path, then retain largest native arena components.

    This is explicitly local staging. Native definition room count bounds the
    encounter stages; small path components remain transit terrain, never erased.
    """
    endpoints = {
        e["source_region"] for e in graph["exits"] if e["matches_entry_exterior"]
    }
    paths = []
    iterations = 0

    def visit(path):
        nonlocal iterations
        iterations += 1
        if iterations > 100000:
            raise ValueError(
                "Native graph path enumeration exceeds bounded offline review budget"
            )
        if path[-1] in endpoints and len(path) > 1:
            paths.append(path)
        next_regions = sorted(
            {
                l["destination_region"]
                for l in graph["links"]
                if l["source_region"] == path[-1]
                and l["destination_region"] not in path
            }
        )
        for region in next_regions:
            visit(path + [region])

    visit([graph["entry_region"]])
    paths = [p for p in paths if len(p) >= required_rooms]
    if not paths:
        raise ValueError(
            "No literal entry-to-native-exterior path can contain the required encounter count"
        )
    path = max(
        paths,
        key=lambda p: (
            sum(graph["component_sizes"][i] for i in p),
            len(p),
            tuple(-i for i in p),
        ),
    )
    chosen = {path[0], path[-1]}
    chosen.update(
        sorted(path[1:-1], key=lambda i: (-graph["component_sizes"][i], i))[
            : required_rooms - 2
        ]
    )
    arenas = [i for i in path if i in chosen]
    stage_by_region = {}
    for index, region in enumerate(path):
        # Corridors after a gate belong to the upcoming encounter stage.
        stage = next(
            (j + 1 for j, arena in enumerate(arenas) if path.index(arena) >= index),
            len(arenas),
        )
        stage_by_region[region] = stage
    # Retain literal reachable optional branches in the stage of their attachment.
    # Ambiguous cross-stage branch attachments are blockers, not guessed order.
    pending = set(graph["reachable_regions"]) - set(stage_by_region)
    while pending:
        changed = False
        for region in sorted(pending):
            neighboring = {
                stage_by_region[l["source_region"]]
                for l in graph["links"]
                if l["destination_region"] == region
                and l["source_region"] in stage_by_region
            }
            neighboring |= {
                stage_by_region[l["destination_region"]]
                for l in graph["links"]
                if l["source_region"] == region
                and l["destination_region"] in stage_by_region
            }
            if len(neighboring) > 1:
                raise ValueError(
                    "Optional native branch has contradictory encounter-stage attachments"
                )
            if neighboring:
                stage_by_region[region] = next(iter(neighboring))
                pending.remove(region)
                changed = True
                break
        if not changed:
            raise ValueError(
                "Reachable native branch cannot be assigned to a proved stage"
            )
    return dict(
        region_path=path,
        encounter_regions=arenas,
        stage_by_region=stage_by_region,
        policy="Explicit local arena/transit staging; largest components on literal entry/exterior spine; exact native room count; optional native branch terrain retained",
    )
