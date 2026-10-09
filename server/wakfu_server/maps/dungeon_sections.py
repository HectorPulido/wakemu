"""Derive linear dungeon room sections from native terrain and teleporters."""
from collections import defaultdict


def derive_sections(
    geometry, teleporters, entry_destination, room_count, *, criterion_allowed
):
    """Return room anchors and door room orders, with native identity evidence.

    Only the entry-reachable chain is used; decorative disconnected terrain is
    irrelevant. Branched, missing, same-section and cross-map links never imply
    an arbitrary room order. Criteria require an authoritative evaluator.
    """
    if (
        type(room_count) is not int
        or room_count <= 0
        or not callable(criterion_allowed)
    ):
        raise ValueError("Invalid dungeon topology contract")
    map_id = geometry["map_id"]
    if entry_destination["map_id"] != map_id:
        raise ValueError("Dungeon entry asset differs from geometry")
    cells = set(map(tuple, geometry["cells"]))
    edges = defaultdict(set)
    for start, end in geometry["edges"]:
        start, end = tuple(start), tuple(end)
        if start not in cells or end not in cells:
            raise ValueError("Terrain edge leaves native cells")
        edges[start].add(end)
        edges[end].add(start)
    labels, components = {}, []
    for seed in sorted(cells):
        if seed in labels:
            continue
        index, queue = len(components), [seed]
        labels[seed] = index
        for cell in queue:
            for neighbor in sorted(edges[cell]):
                if neighbor not in labels:
                    labels[neighbor] = index
                    queue.append(neighbor)
        components.append(tuple(queue))

    def position(row):
        values = tuple(row[k] for k in ("x", "y", "z"))
        if any(type(v) not in (int, float) or int(v) != v for v in values):
            raise ValueError("Non-integral native teleporter coordinate")
        return tuple(map(int, values))

    anchor = position(entry_destination)
    if anchor not in labels:
        raise ValueError("Native entry is not walkable")
    links, neighbors = [], defaultdict(set)
    for source in teleporters:
        if source["map_id"] != map_id:
            continue
        for destination in source["destinations"]:
            if (
                destination["map_id"] != map_id
                or criterion_allowed(destination["criterion"]) is not True
            ):
                continue
            source_cell, destination_cell = position(source), position(destination)
            if source_cell not in labels or destination_cell not in labels:
                raise ValueError("Native dungeon door is not walkable")
            start, end = labels[source_cell], labels[destination_cell]
            if start == end:
                continue
            neighbors[start].add(end)
            links.append(
                dict(
                    source_id=source["id"],
                    destination_id=destination["destination_id"],
                    source_component=start,
                    destination_component=end,
                    anchor=destination_cell,
                    criterion=destination["criterion"],
                    source_position=source_cell,
                )
            )
    chain, anchors = [labels[anchor]], [anchor]
    while True:
        next_components = neighbors[chain[-1]] - set(chain)
        if not next_components:
            break
        if len(next_components) != 1:
            raise ValueError("Native dungeon topology branches")
        target = next(iter(next_components))
        candidates = [
            link
            for link in links
            if link["source_component"] == chain[-1]
            and link["destination_component"] == target
        ]
        if len(candidates) != 1:
            raise ValueError("Native dungeon forward anchor is ambiguous")
        chain.append(target)
        anchors.append(candidates[0]["anchor"])
        if len(chain) > room_count:
            raise ValueError("Native topology exceeds reviewed room count")
    if len(chain) != room_count:
        raise ValueError("Native topology does not cover reviewed room count")
    orders = {component: index + 1 for index, component in enumerate(chain)}
    doors = []
    for link in links:
        if link["source_component"] not in orders:
            continue
        if link["destination_component"] not in orders:
            raise ValueError("Native room has an unexplained outgoing door")
        start, end = (
            orders[link["source_component"]],
            orders[link["destination_component"]],
        )
        if abs(start - end) != 1:
            raise ValueError("Native dungeon topology has a cycle or shortcut")
        doors.append(dict(link, source_room=start, destination_room=end))
    return dict(
        asset_map_id=map_id,
        rooms=[
            dict(order=index + 1, anchor=anchors[index], cells=components[component])
            for index, component in enumerate(chain)
        ],
        doors=doors,
    )
