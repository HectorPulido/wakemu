"""Independent read-only native gate/transport structure audit of classic dungeons."""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components
from audit_remaining_dungeon_geometry import ordinary

REPORTS = [
    "BASELINE47-ROLE-PROGRESSIVE-MIGRATION-20261010.json",
    "FAMILY-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json",
    "PROGRESSIVE-FAMILY-BRANCH-CANDIDATES-V4-20261010.json",
    "FAMILY-OPEN-CANDIDATES-V2-20261010.json",
    "FAMILY-TRANSPORT-PROGRESSIVE-V2-20261010.json",
    "EXTRA-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json",
    "MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json",
    "HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V7-20261010.json",
    "HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V8-20261010.json",
    "PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json",
    "VID-VIL-NATIVE-HUB-CANDIDATE-V11-20261010.json",
    "PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V14-20261010.json",
    "NATIVE-EVIDENCE-NORMALIZED-CANDIDATES-V15-20261010.json",
    "REVIEWED-BOSS-LOBBY-ARENAS-20261010-V1.json",
    "THREE-NATIVE-REVIEW-CANDIDATES-V1-20261010.json",
    "REVIEWED-HUB-TRANSIT-CANDIDATES-V16-20261010.json",
    "HAMMALMEJIL-NATIVE-CYCLE-CANDIDATE-V17-20261010.json",
    "RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json",
    "BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json",
    "DANCEHALL-SHARED-ARENA-20261010-V1.json",
]


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def walk_reachable(edges, entry, *, blocked=(), links=()):
    blocked = set(map(tuple, blocked))
    adjacency = defaultdict(set)
    for a, b in list(edges) + list(links):
        a, b = tuple(a), tuple(b)
        if a not in blocked and b not in blocked:
            adjacency[a].add(b)
    entry = tuple(entry)
    seen = set() if entry in blocked else {entry}
    queue = deque(seen)
    while queue:
        for target in adjacency[queue.popleft()]:
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def runtime_path_check(topology, edges, entry, target, *, blocked, links, frontier):
    """Check a concrete offline path against actual runtime walking validation."""
    from wakfu_server import dungeon_native_flow

    if not dungeon_native_flow.enabled(topology):
        return dict(
            status="unsupported_policy",
            interpretation="Offline geometry only; runtime traversal not established",
        )
    blocked = set(map(tuple, blocked))
    walk_edges = {(tuple(a), tuple(b)) for a, b in edges}
    all_edges = walk_edges | {(tuple(a), tuple(b)) for a, b in links}
    adjacency = defaultdict(list)
    for a, b in all_edges:
        if a not in blocked and b not in blocked:
            adjacency[a].append(b)
    start = tuple(entry)
    target = tuple(target)
    previous = {start: None}
    queue = deque([start])
    while queue and target not in previous:
        current = queue.popleft()
        for end in sorted(adjacency[current]):
            if end not in previous:
                previous[end] = current
                queue.append(end)
    if target not in previous:
        return dict(status="no_path")
    path = []
    current = target
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    segments = []
    segment = [path[0]]
    for a, b in zip(path, path[1:]):
        if (a, b) in walk_edges:
            segment.append(b)
        else:
            segments.append(segment)
            segment = [b]
    segments.append(segment)
    try:
        for segment in segments:
            request = dict(
                start_position=dict(zip(("x", "y", "z"), segment[0])),
                end_position=dict(zip(("x", "y", "z"), segment[-1])),
                steps=[
                    dict(zip(("dx", "dy", "dz"), [b[i] - a[i] for i in range(3)]))
                    for a, b in zip(segment, segment[1:])
                ],
            )
            dungeon_native_flow.validate_movement(
                topology, request, unlocked_room=frontier
            )
    except ValueError as error:
        return dict(
            status="rejected",
            reason=str(error),
            path=[list(c) for c in path],
            interpretation="Offline path is blocked by the runtime validator; possible invisible boundary, not demonstrated bypass",
        )
    return dict(
        status="accepted",
        path=[list(c) for c in path],
        interpretation="Every walking segment passes the actual runtime validator; portal edges use only frontier-enabled configured bindings",
    )


def literal_links(geometry, transports):
    """Retain exact free same-map links and unresolved endpoints separately."""
    cells = set(map(tuple, geometry["cells"]))
    links = []
    unresolved = []
    for source in transports:
        if source["map_id"] != geometry["map_id"]:
            continue
        approaches = {
            tuple(a[k] for k in ("x", "y", "z"))
            for a in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(tuple(source[k] for k in ("x", "y", "z")))
        for destination in source.get("destinations", []):
            if destination["map_id"] != geometry["map_id"]:
                continue
            key = dict(
                source_id=source["id"], destination_id=destination["destination_id"]
            )
            target = tuple(destination[k] for k in ("x", "y", "z"))
            valid = sorted(approaches & cells)
            if not valid or target not in cells:
                unresolved.append(
                    dict(
                        key,
                        code="literal_internal_transport_endpoint_unresolved",
                        source_approaches=[list(c) for c in sorted(approaches)],
                        destination_position=list(target),
                    )
                )
                continue
            if (
                destination.get("criterion", "").strip()
                not in ("", "not IsNeoServer()")
                or destination.get("cyX", 0)
                or destination.get("cyZ", -1) >= 0
                or (
                    destination.get("cyW", 0) > 0
                    and destination.get("item_reference", 0) > 0
                )
            ):
                unresolved.append(
                    dict(
                        key,
                        code="conditional_native_internal_transport_not_assumed_free",
                    )
                )
                continue
            links.append(
                dict(
                    key,
                    approaches=[list(c) for c in valid],
                    destination_position=list(target),
                )
            )
    return links, unresolved


def audit_trigger_frontiers(record, topology, geometry):
    """Verify literal trigger bindings and each parallel lane independently."""
    from decode_native_interactive_activation_cells import (
        literal_positions,
        payload_catalog,
    )

    native = {
        o["id"]: o
        for o in record["native_objects"]
        if o["map_id"] == geometry["map_id"]
        and o["type"] in ("PositionTrigger", "ZoneTrigger")
    }
    edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    owners = defaultdict(set)
    for room in topology.get("rooms", []):
        for cell in room.get("cells", []):
            owners[tuple(cell)].add(room["order"])
    evidence, issues, seen, seen_bindings = [], [], set(), set()
    for gate in topology.get("position_trigger_gates", []):
        identity = gate.get("source_id")
        position = tuple(gate.get("position", []))
        source, destination = gate.get("source_room"), gate.get("destination_room")
        obj = native.get(identity)
        reasons = []
        if (identity, position) in seen_bindings:
            reasons.append("duplicate_trigger_binding")
        seen.add(identity)
        seen_bindings.add((identity, position))
        try:
            positions = literal_positions(obj) if obj is not None else set()
        except (ValueError, KeyError, TypeError):
            positions = set()
        if obj is None or position not in positions:
            reasons.append("binding_not_exact_native_trigger")
        if (
            type(source) is not int
            or type(destination) is not int
            or destination != source + 1
        ):
            reasons.append("trigger_not_adjacent_forward_stage")
        if owners[position] != {destination}:
            reasons.append("trigger_cell_not_owned_only_by_destination")
        incoming = sorted(
            a for a, b in edges if b == position and owners[a] == {source}
        )
        outgoing = sorted(
            b for a, b in edges if a == position and owners[b] == {destination}
        )
        if obj is not None and obj["type"] == "ZoneTrigger" and position in positions:
            # A literal native zone may be several cells deep. Its interior
            # activation cells need directed paths through that same decoded
            # membership set, rather than an invented direct border edge.
            zone = {
                tuple(g.get("position", []))
                for g in topology.get("position_trigger_gates", [])
                if g.get("source_id") == identity
                and g.get("source_room") == source
                and g.get("destination_room") == destination
            }
            zone_edges = [
                (list(a), list(b)) for a, b in edges if a in zone and b in zone
            ]
            predecessor = sorted(
                a for a, b in edges if b in zone and owners[a] == {source}
            )
            successor = sorted(
                b
                for a, b in edges
                if a in zone and b not in zone and owners[b] == {destination}
            )
            entries = {b for a, b in edges if a in predecessor and b in zone}
            exits = {a for a, b in edges if a in zone and b in successor}
            if any(position in walk_reachable(zone_edges, cell) for cell in entries):
                incoming = predecessor
            if any(cell in walk_reachable(zone_edges, position) for cell in exits):
                outgoing = successor
        if not incoming or not outgoing:
            reasons.append("trigger_has_no_directed_stage_crossing")
        checks = []
        if not reasons:
            for unlocked in (source, destination):
                checks.append(
                    dict(
                        unlocked_room=unlocked,
                        **runtime_path_check(
                            topology,
                            geometry["edges"],
                            incoming[0],
                            position,
                            blocked=(),
                            links=(),
                            frontier=unlocked,
                        ),
                    )
                )
            if checks[0]["status"] != "rejected" or checks[1]["status"] != "accepted":
                reasons.append("trigger_runtime_frontier_contract_failed")
        raw = (
            obj
            if obj is not None and "payload_hex" in obj
            else payload_catalog().get((geometry["map_id"], identity))
        )
        payload_sha256 = (
            hashlib.sha256(bytes.fromhex(raw["payload_hex"])).hexdigest()
            if raw is not None and "payload_hex" in raw
            else None
        )
        evidence.append(
            dict(
                source_id=identity,
                position=list(position),
                source_room=source,
                destination_room=destination,
                reasons=reasons,
                runtime_checks=checks,
                native_payload_sha256=payload_sha256,
                literal_native_positions=[list(p) for p in sorted(positions)],
            )
        )
        if reasons:
            issues.append(
                dict(
                    code="native_position_trigger_frontier_invalid",
                    severity="blocked",
                    evidence=evidence[-1],
                )
            )
    return (
        dict(
            native_trigger_count=len(native),
            configured_frontiers=evidence,
            unbound_native_trigger_ids=sorted(set(native) - seen),
        ),
        issues,
    )


def audit_configuration(
    record,
    route,
    geometry,
    transports,
    entry,
    configuration,
    *,
    scope,
    configuration_path,
):
    issues = []

    def issue(code, severity, **evidence):
        issues.append(dict(code=code, severity=severity, evidence=evidence))

    native = record["native"]
    topology = configuration["topology"]
    rooms = topology.get("rooms", [])
    shared_arena = False
    if topology.get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        try:
            dungeon_shared_arena.validate(topology)
            shared_arena = True
        except (ValueError, KeyError, TypeError) as error:
            issue(
                "shared_arena_sequential_contract_invalid", "blocked", reason=str(error)
            )
    trigger_evidence, trigger_issues = audit_trigger_frontiers(
        record, topology, geometry
    )
    issues.extend(trigger_issues)
    if scope == "prepared_simplified_final_arena":
        issue(
            "declared_simplified_final_arena_not_full_progression",
            "review",
            interpretation="Source explicitly labels this final encounter as simplified_pending_not_progressive; never count it as completed multiroom progression",
        )
    cells = set(map(tuple, geometry["cells"]))
    native_doors = [
        o
        for o in record["native_objects"]
        if o["map_id"] == geometry["map_id"] and o["type"] == "Door"
    ]
    positions = {d["id"]: tuple(d[k] for k in ("x", "y", "z")) for d in native_doors}
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    labels, sizes = components(cells - set(positions.values()), adjacency)
    links, unresolved = literal_links(geometry, transports)
    intentional_exclusions = topology.get("disabled_native_sources", [])
    excluded_sources = {d["source_id"] for d in intentional_exclusions}
    unresolved = [r for r in unresolved if r["source_id"] not in excluded_sources]
    full_links = [
        (p, l["destination_position"]) for l in links for p in l["approaches"]
    ]
    native_access = walk_reachable(geometry["edges"], entry, links=full_links)
    expected = {"DUNGEON_2_ROOMS": 2, "DUNGEON_3_ROOMS": 3, "DUNGEON_4_ROOMS": 4}.get(
        native["type"]
    )
    hybrid_spine = None
    if expected:
        from extract_hybrid_native_dungeon_flow import extract, main_spine

        try:
            hybrid_graph = extract(
                geometry,
                record["native_objects"],
                transports,
                entry,
                route["entry_map_id"],
            )
            hybrid_spine = main_spine(hybrid_graph, expected)
        except ValueError:
            hybrid_spine = None
    if expected and len(rooms) < expected:
        issue(
            "configured_encounters_fewer_than_native_room_metadata",
            "high",
            native_type=native["type"],
            native_room_metadata=expected,
            configured_encounters=len(rooms),
            interpretation="Structural review trigger; native metadata alone does not certify official fight sequence",
        )
    if expected and len(rooms) > expected:
        issue(
            "configured_encounters_exceed_native_room_metadata",
            "review",
            native_type=native["type"],
            native_room_metadata=expected,
            configured_encounters=len(rooms),
            interpretation="Review possible optional annexes, alternative paths or historical metadata; count mismatch alone does not demonstrate broken progression",
        )
    if hybrid_spine and len(rooms) < expected:
        issue(
            "literal_native_hybrid_spine_can_contain_more_encounters_than_configuration",
            "high",
            encounter_region_candidates=hybrid_spine["encounter_regions"],
            region_path=hybrid_spine["region_path"],
            configured_encounters=len(rooms),
            candidate_encounters=expected,
            interpretation="Explicit local largest-region staging proof, not official encounter identification",
        )
    guide_counts = sorted(
        {len(g.get("rooms", [])) for g in record.get("guides", []) if g.get("rooms")}
    )
    guide_context = None
    if len(rooms) == 4 and record["key"] in ("native:141", "native:136"):
        guide_context = dict(
            status="resolved_context",
            source="docs/reports/dungeons/HYBRID-NATIVE-FULL-ROOM-RECOVERY-V7-20261010.md",
            explanation="Optional archmonster branch is not a fifth mandatory room"
            if record["key"] == "native:141"
            else "Exterior and mine entrances are alternative routes sharing one boss; their rooms must not be concatenated",
        )
    if guide_counts and len(rooms) < max(guide_counts) and guide_context is None:
        issue(
            "configured_encounters_fewer_than_archived_guide",
            "review",
            guide_room_counts=guide_counts,
            configured_encounters=len(rooms),
        )
    bound_physical = {d["source_id"] for d in topology.get("physical_doors", [])}
    physical_reached = []
    for identity, position in positions.items():
        neighbors = {labels[n] for n in adjacency[position] if n in labels}
        reachable_gate = position in native_access
        if identity not in bound_physical and len(neighbors) >= 2:
            issue(
                "native_separator_door_not_bound",
                "review",
                source_id=identity,
                position=list(position),
                adjacent_closed_regions=sorted(neighbors),
                reachable_in_native_hybrid_graph=reachable_gate,
            )
        physical_reached.append(
            dict(
                source_id=identity,
                position=list(position),
                regions=sorted(neighbors),
                bound=identity in bound_physical,
                reachable=reachable_gate,
            )
        )
    bound_transports = {
        (d["source_id"], d["destination_id"])
        for d in topology.get("doors", [])
        if "destination_id" in d
    }
    for d in topology.get("same_stage_transports", []):
        if "destination_id" in d:
            bound_transports.add((d["source_id"], d["destination_id"]))
    room_membership = defaultdict(set)
    for room in rooms:
        for c in room.get("cells", []):
            room_membership[tuple(c)].add(room["order"])
    for link in links:
        if (link["source_id"], link["destination_id"]) in bound_transports or link[
            "source_id"
        ] in excluded_sources:
            continue
        source_access = any(tuple(p) in native_access for p in link["approaches"])
        target = tuple(link["destination_position"])
        source_regions = {labels.get(tuple(p)) for p in link["approaches"]}
        target_region = labels.get(target)
        same_region = source_regions == {target_region}
        issue(
            "native_internal_transport_not_bound",
            "review",
            source_id=link["source_id"],
            destination_id=link["destination_id"],
            source_closed_regions=sorted(r for r in source_regions if r is not None),
            destination_closed_region=target_region,
            destination_position=link["destination_position"],
            native_source_reachable=source_access,
            same_closed_region=same_region,
            source_config_rooms=sorted(
                {r for p in link["approaches"] for r in room_membership[tuple(p)]}
            ),
            destination_config_rooms=sorted(room_membership[target]),
        )
    configured_links = []
    for link in links:
        if (link["source_id"], link["destination_id"]) in bound_transports:
            configured_links.extend(
                (p, link["destination_position"]) for p in link["approaches"]
            )
    anchor_observations = []
    for room in rooms:
        frontier = room["order"]
        blocked = [
            d["position"]
            for d in list(topology.get("physical_doors", []))
            + list(topology.get("position_trigger_gates", []))
            if d.get("destination_room", frontier) > frontier
        ]
        enabled_ids = {
            (d["source_id"], d["destination_id"])
            for d in topology.get("doors", [])
            if "destination_id" in d
            and max(d["source_room"], d["destination_room"]) <= frontier
        }
        enabled_ids |= {
            (d["source_id"], d["destination_id"])
            for d in topology.get("same_stage_transports", [])
            if "destination_id" in d
            and max(d["source_room"], d["destination_room"]) <= frontier
        }
        enabled_links = [
            (p, l["destination_position"])
            for l in links
            if (l["source_id"], l["destination_id"]) in enabled_ids
            for p in l["approaches"]
        ]
        reached = walk_reachable(
            topology.get("exploration_geometry", geometry)["edges"],
            entry,
            blocked=blocked,
            links=enabled_links,
        )
        anchor = tuple(room["anchor"])
        native_reachable = anchor in native_access
        configured_reachable = anchor in reached
        if not native_reachable:
            issue(
                "encounter_anchor_unreachable_in_complete_native_hybrid_graph",
                "blocked",
                room_order=frontier,
                anchor=list(anchor),
            )
        elif not configured_reachable:
            issue(
                "encounter_anchor_unreachable_with_configured_gate_transport_bindings",
                "blocked",
                room_order=frontier,
                anchor=list(anchor),
                native_hybrid_reachable=True,
            )
        # Validated shared arenas reuse one native floor for successive fights.
        # Their frontier controls encounter creation, never walking admission.
        future = (
            set()
            if shared_arena
            else {
                tuple(c)
                for r in rooms
                if r["order"] > frontier
                for c in r.get("cells", [])
            }
        )
        leaked = sorted(future & reached)
        if leaked:
            runtime_result = runtime_path_check(
                topology,
                topology.get("exploration_geometry", geometry)["edges"],
                entry,
                leaked[0],
                blocked=blocked,
                links=enabled_links,
                frontier=frontier,
            )
            issue(
                "future_room_terrain_reachable_before_its_frontier",
                "high" if runtime_result["status"] == "accepted" else "review",
                room_order=frontier,
                counterexample_position=list(leaked[0]),
                reachable_future_cell_count=len(leaked),
                runtime_validation=runtime_result,
            )
        anchor_observations.append(
            dict(
                room_order=frontier,
                anchor=list(anchor),
                native_hybrid_reachable=native_reachable,
                configured_frontier_reachable=configured_reachable,
            )
        )
    omitted_regions = []
    for region, size in enumerate(sizes):
        selected = {c for c, l in labels.items() if l == region}
        if (
            size >= 100
            and selected & native_access
            and not any(room_membership[c] for c in selected)
        ):
            omitted_regions.append(dict(closed_region=region, size=size))
    if omitted_regions:
        issue(
            "reachable_large_native_regions_omitted_from_encounter_topology",
            "review",
            regions=omitted_regions,
            interpretation="Possible annexes or transit, not automatically official encounter rooms",
        )
    if unresolved:
        issue(
            "native_internal_transport_endpoints_or_conditions_require_review",
            "review",
            records=unresolved,
        )
    status = (
        "blocked"
        if any(i["severity"] == "blocked" for i in issues)
        else "needs_manual_review"
        if issues
        else "passed"
    )
    return dict(
        schema_version=1,
        key=record["key"],
        native_id=native["id"],
        name=record["name_es"],
        native_name=native["name_fr"],
        route=route["key"],
        scope=scope,
        configuration_path=configuration_path,
        configuration_hash=digest(configuration),
        native_input_hashes=dict(
            client=geometry.get("client_sha256"),
            topology=geometry.get("topology_sha256"),
            inventory_record=digest(record),
            literal_transports=digest(
                [t for t in transports if t["map_id"] == geometry["map_id"]]
            ),
        ),
        configured_encounters=len(rooms),
        native_room_metadata=expected,
        native_type=native["type"],
        guide_count_context=guide_context,
        closed_region_sizes=sizes,
        native_gate_evidence=physical_reached,
        native_trigger_evidence=trigger_evidence,
        native_internal_transport_count=len(links),
        intentional_native_source_exclusions=intentional_exclusions,
        native_hybrid_spine_candidate=hybrid_spine,
        encounter_anchor_evidence=anchor_observations,
        structural_fullflow_status=status,
        issues=issues,
        limits="Start asset map only; official ordering, optional annexes, boss AI and rewards are not certified by this structural audit",
    )


def active_configurations():
    import psycopg

    password = Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], password=password) as db:
        db.execute("SET TRANSACTION READ ONLY")
        pointers = db.execute(
            "SELECT active.route_key,active.policy_version,versions.configuration "
            "FROM dungeon_runtime_active_configurations AS active "
            "JOIN dungeon_runtime_configurations AS versions "
            "ON versions.route_key=active.route_key AND versions.policy_version=active.policy_version "
            "WHERE active.route_key LIKE 'native_dungeon_%'"
        ).fetchall()
        output = {}
        for route_key, version, configuration in pointers:
            output[route_key] = (
                configuration,
                f"postgres.dungeon_runtime_configurations:{route_key}:v{version}",
            )
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-active-database", action="store_true")
    parser.add_argument("--active-snapshot", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "docs/reports/dungeons/ALL-CLASSIC-HYBRID-STRUCTURE-AUDIT-20261010.json"
        ),
    )
    args = parser.parse_args()
    load = lambda p: json.loads(Path(p).read_text())
    inventory = [
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if ordinary(r)
    ]
    flows = {
        r["route"]["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    proposed = {}
    for report in REPORTS:
        path = Path("docs/reports/dungeons") / report
        if not path.exists():
            continue
        for row in load(path).get("records", []):
            candidate = Path(row.get("path", ""))
            if (
                row.get("status") == "offline_configuration_prepared"
                and candidate.is_file()
            ):
                config = load(candidate)
                proposed[config["route"]["key"]] = (config, str(candidate))
    simplified = {}
    simplified_report = Path(
        "docs/reports/dungeons/FAMILY-FINAL-ARENA-CANDIDATES-V2-20261010.json"
    )
    if simplified_report.exists():
        for row in load(simplified_report)["records"]:
            candidate = Path(row.get("path", ""))
            if (
                row.get("status") == "simplified_pending_not_progressive"
                and candidate.is_file()
            ):
                simplified[row["route"]] = (load(candidate), str(candidate))
    active = active_configurations() if args.read_active_database else {}
    if args.active_snapshot:
        active = {
            r["route"]: (
                r["configuration"],
                str(args.active_snapshot) + "#" + r["route"],
            )
            for r in load(args.active_snapshot)["records"]
        }
    baseline_routes = {
        r["route"]
        for r in load(
            "docs/reports/dungeons/MAXIMUM-ACTIVATION-READBACK-20261010.json"
        )["records"]
    }
    records = []
    missing = []
    geometry_cache = {}
    for native in inventory:
        for route in native["native_entry_routes"]:
            route_key = route["key"]
            flow = flows.get(route_key)
            map_id = route["start_map_id"]
            path = Path(
                f".runtime/local/all-native-dungeon-exploration/exploration-{map_id}.json"
            )
            variants = []
            for scope, mapping in [
                ("active_database", active),
                ("prepared_latest", proposed),
                ("prepared_simplified_final_arena", simplified),
            ]:
                if route_key in mapping:
                    variants.append((scope, mapping[route_key]))
            if not variants:
                missing.append(
                    dict(
                        key=native["key"],
                        name=native["name_es"],
                        native_id=native["native"]["id"],
                        route=route_key,
                        reason="no_active_or_latest_prepared_configuration",
                    )
                )
                continue
            if flow is None or not path.exists():
                missing.append(
                    dict(
                        key=native["key"],
                        route=route_key,
                        reason="missing_native_entry_or_geometry_evidence",
                    )
                )
                continue
            geometry_cache.setdefault(map_id, load(path))
            geometry = geometry_cache[map_id]
            for scope, (config, config_path) in variants:
                effective_scope = (
                    (
                        "active_validated_baseline37"
                        if route_key in baseline_routes
                        else "active_other_configuration"
                    )
                    if scope == "active_database"
                    else scope
                )
                records.append(
                    audit_configuration(
                        native,
                        route,
                        geometry,
                        transports,
                        flow["entry"],
                        config,
                        scope=effective_scope,
                        configuration_path=config_path,
                    )
                )
        if not native["native_entry_routes"]:
            missing.append(
                dict(
                    key=native["key"],
                    name=native["name_es"],
                    native_id=native["native"]["id"],
                    reason="no_native_entry_route",
                )
            )
    report = dict(
        schema_version=1,
        configuration_selection_precedence=REPORTS,
        simplified_final_arena_report=str(simplified_report),
        scope="All 109 classic ordinary definitions / 107 native names; independent hybrid structural audit; no runtime writes",
        inventory_definitions=len(inventory),
        inventory_distinct_names=len({r["native"]["name_fr"] for r in inventory}),
        active_database_read=args.read_active_database,
        active_snapshot=str(args.active_snapshot) if args.active_snapshot else None,
        active_snapshot_sha256=hashlib.sha256(
            args.active_snapshot.read_bytes()
        ).hexdigest()
        if args.active_snapshot
        else None,
        counts=dict(
            Counter(f"{r['scope']}:{r['structural_fullflow_status']}" for r in records)
        ),
        records=records,
        unconfigured_or_unavailable=missing,
    )
    report["definition_coverage"] = [
        dict(
            key=r["key"],
            native_id=r["native"]["id"],
            native_name=r["native"]["name_fr"],
            name=r["name_es"],
            route_keys=[route["key"] for route in r["native_entry_routes"]],
            audited_configurations=[
                dict(
                    scope=q["scope"],
                    route=q["route"],
                    structural_fullflow_status=q["structural_fullflow_status"],
                )
                for q in records
                if q["key"] == r["key"]
            ],
            missing_configuration_records=[q for q in missing if q["key"] == r["key"]],
        )
        for r in inventory
    ]
    target = args.output
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in ("records", "unconfigured_or_unavailable", "definition_coverage")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
