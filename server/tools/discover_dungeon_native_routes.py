"""Discover dungeon identities and room topology from native references only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.maps.dungeon_sections import derive_sections


def discover_routes(definitions, teleporters):
    routes, diagnostics = [], []
    for definition in definitions:
        matches = [
            (source, destination)
            for source in teleporters
            for destination in source["destinations"]
            if source["map_id"] == definition["raw_arM"]
            and destination["map_id"] in definition["raw_aHA"]
            and type(destination["cyZ"]) is int
            and destination["cyZ"] > 0
        ]
        if not matches:
            matches = [
                (source, destination)
                for source in teleporters
                for destination in source["destinations"]
                if destination["map_id"] in definition["raw_aHA"]
                and type(destination["cyZ"]) is int
                and destination["cyZ"] > 0
            ]
        if len(matches) > 1 and len({(d["cyZ"], d["map_id"]) for _, d in matches}) == 1:
            matches.sort(
                key=lambda pair: (
                    pair[0]["map_id"],
                    pair[0]["id"],
                    pair[1]["destination_id"],
                )
            )
            diagnostics.append(
                {
                    "definition_id": definition["id"],
                    "reason": "equivalent_native_entry_variants",
                    "policy": "deterministic_local_canonical_entry",
                    "variants": [
                        {
                            "entry_map_id": source["map_id"],
                            "entry_object_id": source["id"],
                            "destination_id": destination["destination_id"],
                            "criterion": destination["criterion"],
                        }
                        for source, destination in matches
                    ],
                }
            )
            matches = matches[:1]
        if len(matches) != 1:
            diagnostics.append(
                {
                    "definition_id": definition["id"],
                    "reason": "missing_entry" if not matches else "ambiguous_entry",
                    "candidate_count": len(matches),
                }
            )
            continue
        source, destination = matches[0]
        routes.append(
            {
                "key": f"native_dungeon_{definition['id']}",
                "definition_id": definition["id"],
                "template_id": destination["cyZ"],
                "entry_map_id": source["map_id"],
                "entry_object_id": source["id"],
                "destination_id": destination["destination_id"],
                "start_map_id": destination["map_id"],
                "criterion": destination["criterion"],
            }
        )
    return routes, diagnostics


def criterion_allowed(criterion):
    if criterion in ("", "not IsNeoServer()"):
        return True
    if criterion == "IsNeoServer()":
        return False
    raise ValueError(f"Unsupported native topology criterion: {criterion}")


def accessible_anchor_topology(
    geometry,
    entry,
    room_count,
    *,
    enemy_counts=None,
    largest_component_only=False,
    reviewed_room_anchors=(),
    native_doors=(),
):
    """Select real native free areas for explicit local logical rooms.

    This policy supplies playable local locations, not official room ordering.
    Every anchor and edge comes from the existing walkable geometry.
    """
    from collections import defaultdict, deque

    if type(room_count) is not int or room_count <= 0:
        raise ValueError("Known positive room count is required")
    enemy_counts = enemy_counts or [8] * room_count
    if len(enemy_counts) != room_count or any(
        type(n) is not int or n < 1 for n in enemy_counts
    ):
        raise ValueError("Invalid per-room encounter capacity")
    minimum_capacity = max(enemy_counts) + 6
    cells = set(map(tuple, geometry["cells"]))
    reviewed = tuple(map(tuple, reviewed_room_anchors))
    blocked = {tuple(door[key] for key in ("x", "y", "z")) for door in native_doors}
    if reviewed and (
        len(reviewed) != room_count or not blocked or largest_component_only
    ):
        raise ValueError("Reviewed physical rooms require exact native door boundaries")
    if blocked and not reviewed:
        raise ValueError("Native door boundaries require reviewed room anchors")
    if not blocked.issubset(cells):
        raise ValueError("Reviewed native door is not walkable")
    start = tuple(entry[k] for k in ("x", "y", "z"))
    if start not in cells:
        raise ValueError("Native entry anchor is not accessible")
    cells -= blocked
    edges = defaultdict(set)
    for left, right in geometry["edges"]:
        left, right = tuple(left), tuple(right)
        if left in blocked or right in blocked:
            continue
        if left not in cells or right not in cells:
            raise ValueError("Native edge leaves walkable terrain")
        edges[left].add(right)
        edges[right].add(left)

    def distances(seed):
        result, queue = {seed: 0}, deque([seed])
        while queue:
            current = queue.popleft()
            for neighbor in sorted(edges[current]):
                if neighbor not in result:
                    result[neighbor] = result[current] + 1
                    queue.append(neighbor)
        return result

    components = []
    remaining = set(cells)
    while remaining:
        component = set(distances(min(remaining)))
        components.append(component)
        remaining -= component
    components.sort(key=lambda component: (-len(component), min(component)))
    if len(cells) < room_count:
        raise ValueError("Native terrain has fewer cells than known rooms")
    # Automatic relocation allows native free areas outside an entry lobby.
    # Reuse a large area between encounters rather than making tiny rooms.
    selected = [
        component for component in components if len(component) >= minimum_capacity
    ]
    if not selected:
        selected = components[:1]
    selected = components[:1] if largest_component_only else selected[:room_count]
    if reviewed:
        selected = []
        for anchor in reviewed:
            matches = [component for component in components if anchor in component]
            if len(matches) != 1 or matches[0] in selected:
                raise ValueError(
                    "Reviewed room anchors do not identify distinct native rooms"
                )
            if len(matches[0]) < minimum_capacity:
                raise ValueError("Reviewed native room lacks encounter capacity")
            selected.append(matches[0])
    slots = [1] * len(selected)
    while sum(slots) < room_count:
        index = min(
            range(len(selected)), key=lambda i: (-len(selected[i]) / (slots[i] + 1), i)
        )
        slots[index] += 1
    anchors, rooms = [], []
    for component, count in zip(selected, slots):
        local_anchors = []
        for _ in range(count):
            available = component - set(local_anchors)
            if not available:
                raise ValueError("Local logical rooms exhaust unique native anchors")
            if local_anchors:
                distance_maps = [distances(point) for point in local_anchors]
                anchor = min(
                    available,
                    key=lambda point: (-min(d[point] for d in distance_maps), point),
                )
            else:
                center_x = sum(point[0] for point in component) / len(component)
                center_y = sum(point[1] for point in component) / len(component)
                anchor = min(
                    available,
                    key=lambda point: (
                        -len(edges[point]),
                        (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2,
                        point,
                    ),
                )
            local_anchors.append(anchor)
        labels = {anchor: index for index, anchor in enumerate(local_anchors)}
        queue = deque(local_anchors)
        while queue:
            current = queue.popleft()
            for neighbor in sorted(edges[current]):
                if neighbor not in labels:
                    labels[neighbor] = labels[current]
                    queue.append(neighbor)
        for index, anchor in enumerate(local_anchors):
            anchors.append(anchor)
            rooms.append(
                dict(
                    order=len(rooms) + 1,
                    anchor=anchor,
                    cells=sorted(
                        point for point, label in labels.items() if label == index
                    ),
                )
            )
    from wakfu_server.maps.dungeon_encounters import enemy_formation

    for room, count in zip(rooms, enemy_counts):
        room_cells = set(map(tuple, room["cells"]))
        if len(room_cells) < count + 6:
            raise ValueError("Local room lacks encounter and six-player capacity")
        room_geometry = dict(
            geometry,
            cells=room["cells"],
            edges=[
                (a, b)
                for a, b in geometry["edges"]
                if tuple(a) in room_cells and tuple(b) in room_cells
            ],
        )
        valid_anchor = None
        ranked = sorted(
            room_cells,
            key=lambda cell: (
                -len(edges[cell] & room_cells),
                sum((cell[i] - room["anchor"][i]) ** 2 for i in range(2)),
                cell,
            ),
        )
        spread = sorted(room_cells)
        candidates = list(
            dict.fromkeys(
                ranked[:8] + [spread[i * (len(spread) - 1) // 15] for i in range(16)]
            )
        )
        for candidate in candidates:
            try:
                enemy_formation(room_geometry, candidate, count, player_slots=6)
            except ValueError:
                continue
            valid_anchor = candidate
            break
        if valid_anchor is None:
            raise ValueError("Dungeon room cannot separate party and enemy formations")
        room["anchor"] = valid_anchor
        room["validated_enemy_capacity"] = count
        room["validated_party_capacity"] = 6
    return {
        "asset_map_id": geometry["map_id"],
        "policy": "local_accessible_anchor_policy",
        "official_room_order_verified": False,
        "rooms": rooms,
        "doors": [],
        "auto_edges": [
            dict(
                source_room=order,
                destination_room=order + 1,
                anchor=rooms[order]["anchor"],
            )
            for order in range(1, room_count)
        ],
    }


def build_bundle(
    root, native_index, teleporters, documents, *, drafts=None, local_routes=None
):
    routes, errors = discover_routes(native_index["native_dungeons"], teleporters)
    for route in local_routes or []:
        source = next(
            (
                item
                for item in teleporters
                if item["map_id"] == route["entry_map_id"]
                and item["id"] == route["entry_object_id"]
            ),
            None,
        )
        destination = next(
            (
                item
                for item in (source or {}).get("destinations", [])
                if item["destination_id"] == route["destination_id"]
            ),
            None,
        )
        if (
            route.get("registration_policy") != "local_legacy_map_registry"
            or route.get("native_definition_id") is not None
            or destination is None
            or destination["map_id"] != route["start_map_id"]
        ):
            raise ValueError("Local legacy route lacks exact native entry provenance")
        routes.append(route)
    route_index = {}
    for route in sorted(
        routes,
        key=lambda item: (
            item["definition_id"],
            item["entry_map_id"],
            item["entry_object_id"],
            item["destination_id"],
        ),
    ):
        route_index.setdefault(route["definition_id"], route)
    links = {r["guide_slug"]: r for r in native_index["guide_links"]}
    draft_index = {draft["slug"]: draft for draft in (drafts or [])}
    topologies, coverage = {}, []
    for document in documents:
        slug = document["dungeon"]["slug"]
        draft = draft_index.get(slug)
        if drafts is not None and draft is None:
            continue
        if draft is not None:
            document = dict(document, rooms=draft["rooms"])
        enemy_counts = [
            max(
                8,
                sum(monster.get("count") or 0 for monster in room.get("monsters", [])),
            )
            for room in document["rooms"]
        ]
        link = links.get(slug, {})
        definition_id = (
            link.get("client_definition_id")
            if link.get("status") == "exact_unique"
            else None
        )
        if (
            draft is not None
            and draft.get("identity_policy") == "local_legacy_map_registry"
        ):
            definition_id = draft["definition_id"]
        route = route_index.get(definition_id)
        row = {
            "slug": slug,
            "definition_id": definition_id,
            "route": route,
            "topology_status": "unavailable",
        }
        if not route:
            row["reason"] = "Unresolved identity or missing native entry route"
        elif not document["rooms"]:
            row["reason"] = "No reviewed room count"
        else:
            geometry_path = (
                root / f"server/protocol/combat-maps/{route['start_map_id']}.json"
            )
            try:
                with open(geometry_path) as stream:
                    geometry = json.load(stream)
                source = next(
                    s
                    for s in teleporters
                    if s["map_id"] == route["entry_map_id"]
                    and s["id"] == route["entry_object_id"]
                )
                entry = next(
                    d
                    for d in source["destinations"]
                    if d["destination_id"] == route["destination_id"]
                )
                if [room["order"] for room in document["rooms"]] != list(
                    range(1, len(document["rooms"]) + 1)
                ):
                    raise ValueError(
                        "Reviewed room orders do not establish a complete room count"
                    )
                try:
                    if draft is not None:
                        raise ValueError("Explicit local roster room-count policy")
                    topology = derive_sections(
                        geometry,
                        teleporters,
                        entry,
                        len(document["rooms"]),
                        criterion_allowed=criterion_allowed,
                    )
                    status = "verified"
                except ValueError as error:
                    row["native_topology_reason"] = str(error)
                    try:
                        topology = accessible_anchor_topology(
                            geometry,
                            entry,
                            len(document["rooms"]),
                            enemy_counts=enemy_counts,
                        )
                    except ValueError:
                        topology = accessible_anchor_topology(
                            geometry,
                            entry,
                            len(document["rooms"]),
                            enemy_counts=enemy_counts,
                            largest_component_only=True,
                        )
                    status = "local_accessible_anchor_policy"
                    if draft is not None:
                        topology["room_count_source"] = draft["room_count_source"]
                        topology["room_count_official"] = False
                if topology.get("policy") == "local_accessible_anchor_policy":
                    exterior_geometry_path = (
                        root / f"server/protocol/combat-maps/{source['map_id']}.json"
                    )
                    with open(exterior_geometry_path) as stream:
                        exterior_cells = set(map(tuple, json.load(stream)["cells"]))
                    approved = [
                        tuple(point[k] for k in ("x", "y", "z"))
                        for point in source.get("approach_positions", ())
                    ]
                    approved = sorted(
                        point for point in approved if point in exterior_cells
                    )
                    if not approved and source.get("approach_mask") == 0:
                        native_source_cell = tuple(source[k] for k in ("x", "y", "z"))
                        if native_source_cell in exterior_cells:
                            approved = [native_source_cell]
                    if not approved:
                        raise ValueError(
                            "Native exterior entry has no approved walkable approach cell"
                        )
                    topology["completion_destination"] = dict(
                        map_id=source["map_id"],
                        **dict(zip(("x", "y", "z"), map(int, approved[0]))),
                        entry_object_id=source["id"],
                        approach_mask=source["approach_mask"],
                        approach_orientation=source["approach_orientation"],
                        provenance={
                            "policy": "native_entry_approved_walkable_approach",
                            "catalog_path": "server/protocol/native-generic-teleporters.json",
                            "catalog_sha256": hashlib.sha256(
                                (
                                    root
                                    / "server/protocol/native-generic-teleporters.json"
                                ).read_bytes()
                            ).hexdigest(),
                            "method": "approach_position"
                            if source.get("approach_mask")
                            else "walkable_source_zero_mask",
                            "geometry_path": str(
                                exterior_geometry_path.relative_to(root)
                            ),
                            "geometry_sha256": hashlib.sha256(
                                exterior_geometry_path.read_bytes()
                            ).hexdigest(),
                        },
                    )
                topologies[slug] = topology
                row.update(
                    topology_status=status,
                    geometry_path=str(geometry_path.relative_to(root)),
                    geometry_sha256=hashlib.sha256(
                        geometry_path.read_bytes()
                    ).hexdigest(),
                )
            except (OSError, ValueError, StopIteration) as error:
                row["reason"] = str(error)
        coverage.append(row)
    return {
        "schema_version": 1,
        "runtime_imported": False,
        "criterion_mode": "Non-Neo server; only exact empty/native mode criteria are evaluated",
        "routes": routes,
        "route_diagnostics": errors,
        "topologies": topologies,
        "coverage": coverage,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--native-index", type=Path)
    parser.add_argument(
        "--entry-routes",
        type=Path,
        help="Exact native routes for optional local legacy registrations",
    )
    parser.add_argument(
        "--drafts",
        type=Path,
        help="Optional local roster batch; writes separate local policy artifacts",
    )
    parser.add_argument(
        "--archive", type=Path, default=Path(".runtime/local/methodwakfu-dungeons")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    archive = root / args.archive
    index_path = (
        (root / args.native_index).resolve()
        if args.native_index
        else archive / "native-dungeon-index.json"
    )
    teleporter_path = root / "server/protocol/native-generic-teleporters.json"
    documents = [
        json.loads(p.read_text())
        for p in sorted((archive / "compositions").glob("*.json"))
    ]
    drafts_path = (root / args.drafts).resolve() if args.drafts else None
    drafts = json.loads(drafts_path.read_text())["drafts"] if drafts_path else None
    routes_path = (root / args.entry_routes).resolve() if args.entry_routes else None
    local_routes = (
        json.loads(routes_path.read_text())["routes"] if routes_path else None
    )
    bundle = build_bundle(
        root,
        json.loads(index_path.read_text()),
        json.loads(teleporter_path.read_text()),
        documents,
        drafts=drafts,
        local_routes=local_routes,
    )
    bundle["sources"] = [
        {
            "path": str(p.relative_to(root)),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in [index_path, teleporter_path]
    ]
    if drafts_path:
        bundle["sources"].append(
            {
                "path": str(drafts_path.relative_to(root)),
                "sha256": hashlib.sha256(drafts_path.read_bytes()).hexdigest(),
            }
        )
    if routes_path:
        bundle["sources"].append(
            {
                "path": str(routes_path.relative_to(root)),
                "sha256": hashlib.sha256(routes_path.read_bytes()).hexdigest(),
            }
        )
    outputs = (
        [
            ("local-legacy-topology-bundle.json", bundle),
            ("local-legacy-topologies.json", bundle["topologies"]),
        ]
        if routes_path
        else [
            ("local-policy-topology-bundle.json", bundle),
            ("local-policy-topologies.json", bundle["topologies"]),
        ]
        if drafts_path
        else [
            ("native-route-topology-bundle.json", bundle),
            ("native-bulk-entry-routes.json", bundle["routes"]),
            ("native-bulk-topologies.json", bundle["topologies"]),
        ]
    )
    for filename, value in outputs:
        (archive / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                "routes": len(bundle["routes"]),
                "topologies": len(bundle["topologies"]),
                "guides": len(bundle["coverage"]),
            }
        )
    )
