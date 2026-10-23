"""Prepare an unbound native supreme entry without installing routes or policies."""
import copy
from collections import defaultdict, deque


def prepare(
    inventory,
    native,
    source,
    exit_source,
    geometry,
    approach_proof,
    *,
    catalog_sha256,
    source_url,
    evidence_sha256,
    version=1
):
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )

    routes = inventory["native_entry_routes"]
    pool = inventory["native_species_pool"]
    if (
        inventory["native"]["type"] != "ULTIMATE_BOSS"
        or len(routes) != 1
        or len(pool) != 1
        or type(version) is not int
        or version <= 0
    ):
        raise ValueError("A unique native ultimate identity and entry are required")
    route = copy.deepcopy(routes[0])
    if (
        native["ref"] != pool[0]["ref_id"]
        or 49 not in native["raw_visual_arrays"]["csc"]
        or (native["min_level"], native["max_level"])
        != (pool[0]["min_level"], pool[0]["max_level"])
    ):
        raise ValueError("Native ultimate identity or grade differs")
    destinations = [
        d
        for d in source["destinations"]
        if d["destination_id"] == route["destination_id"]
    ]
    if (
        len(destinations) != 1
        or source["id"] != route["entry_object_id"]
        or source["map_id"] != route["entry_map_id"]
    ):
        raise ValueError("Native entry source is absent or ambiguous")
    destination = destinations[0]
    if (
        destination["map_id"] != route["start_map_id"]
        or destination["cyZ"] != route["template_id"]
        or destination["criterion"] != route["criterion"]
        or destination.get("native_altitude_walkable") is not True
        or geometry["map_id"] != route["start_map_id"]
    ):
        raise ValueError("Native entry destination differs from dungeon identity")
    if exit_source["map_id"] != route["start_map_id"] or not any(
        d["map_id"] == route["entry_map_id"]
        and d.get("native_altitude_walkable") is True
        for d in exit_source["destinations"]
    ):
        raise ValueError("Native exterior exit is not established")
    approach = tuple(approach_proof["approved_entry_approach"])
    approved = {
        tuple(p[k] for k in ("x", "y", "z"))
        for p in source.get("approach_positions", [])
    }
    if (
        approach not in approved
        or approach_proof.get("walkable") is not True
        or approach_proof["map_id"] != route["entry_map_id"]
    ):
        raise ValueError(
            "Exterior return lacks an actual approved walkable entry approach"
        )
    entry = tuple(destination[k] for k in ("x", "y", "z"))
    cells = {tuple(p) for p in geometry["cells"]}
    if entry not in cells:
        raise ValueError("Native arrival leaves exported terrain")
    adjacent = defaultdict(list)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        if a not in cells or b not in cells:
            raise ValueError("Native edge leaves exported terrain")
        adjacent[a].append(b)
    seen, queue = {entry}, deque([entry])
    while queue:
        for point in adjacent[queue.popleft()]:
            if point not in seen:
                seen.add(point)
                queue.append(point)
    n = len(seen)
    sx, sy = sum(p[0] for p in seen), sum(p[1] for p in seen)
    anchor = min(seen, key=lambda p: ((p[0] * n - sx) ** 2 + (p[1] * n - sy) ** 2, p))
    provenance = (
        "Wakemu reconstructed native supreme scene entry; actual native route, "
        "template, terrain and approved exterior approach; deterministic arena "
        "placement, not recovered official coordinates; scene mechanics separately qualified"
    )
    monster = dict(
        ref_id=native["ref"],
        name=native["name"],
        count=1,
        role="boss",
        native_min_level=native["min_level"],
        native_max_level=native["max_level"],
        guide_min_level=None,
        guide_max_level=None,
    )
    rooms = [dict(order=1, monsters=[monster], diagnostics=[])]
    plan = dict(
        slug=inventory["native"]["name_fr"].lower().replace(" ", "-"),
        source_url=source_url,
        source_sha256=evidence_sha256,
        definition_id=route["definition_id"],
        template_id=route["template_id"],
        asset_map_id=route["start_map_id"],
        document_sha256=canonical_hash(rooms),
        rooms=rooms,
        diagnostics=[],
        roster_ready=True,
        official=False,
        policy_mode="reviewed_local_native_ultimate_scene",
        boss_references=[native["ref"]],
        roster_policy_evidence=dict(
            authority=provenance,
            source_url=source_url,
            native_species_pool=copy.deepcopy(pool),
        ),
    )
    completion = dict(
        map_id=source["map_id"],
        **dict(zip(("x", "y", "z"), approach)),
        entry_object_id=source["id"],
        approach_mask=source["approach_mask"],
        approach_orientation=source["approach_orientation"],
        provenance=dict(
            policy="native_entry_approved_walkable_approach",
            method="approach_position",
            catalog_path="server/protocol/native-generic-teleporters.json",
            catalog_sha256=catalog_sha256,
            geometry_path="server/protocol/" + approach_proof["geometry_path"],
            geometry_sha256=approach_proof["sha256"],
        )
    )
    topology = dict(
        asset_map_id=geometry["map_id"],
        policy="local_accessible_anchor_policy",
        rooms=[
            dict(order=1, anchor=list(anchor), cells=[list(p) for p in sorted(seen)])
        ],
        doors=[],
        auto_edges=[],
        official_room_order_verified=False,
        room_count_official=False,
        room_count_source="native_singleton_identity_and_gameplay_guide",
        completion_destination=completion,
        reconstructed_scene_evidence=dict(
            native_arrival=list(entry),
            native_exit_source=copy.deepcopy(exit_source),
            placement_authority="Native entry-reachable component centroid, explicitly reconstructed",
            source_url=source_url,
            evidence_sha256=evidence_sha256,
        ),
    )
    return prepare_configuration(
        plan, topology, route, version=version, provenance=provenance
    )
