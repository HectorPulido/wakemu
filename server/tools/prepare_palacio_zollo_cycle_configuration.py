"""Prepare both authentic Zollo routes with deferred branch selection."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_hybrid_native_dungeon_flow import extract
from prepare_hybrid_native_dungeons import topology_for
from prepare_vid_vil_hub_configuration import validate_hub_sequence
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog
from native_family_configuration_base import base
from validate_dungeon_flow_rosters import validate
from extract_milubo_mixed_flow import hybrid_path

BRANCHES = (
    (
        34741,
        34744,
        (90, 41, 13, 0),
        ([-86, 35, 0], [-111, 38, 8], [-140, 36, 16], [-216, -13, 2]),
        (34749, 34750),
    ),
    (
        34740,
        34745,
        (91, 42, 18, 0),
        ([-84, -41, 0], [-109, -38, 8], [-138, -40, 16], [-216, -13, 2]),
        (34751, 34752),
    ),
)


def branch_routes(graph, geometry):
    """Retain literal branch arrivals and exact native arena cells."""
    components = {r["region"]: r["cells"] for r in graph["components"]}
    result = []
    for entry_id, final_id, regions, anchors, gates in BRANCHES:
        source = next(l for l in graph["links"] if l["source_id"] == entry_id)
        arrivals = [source["destination_position"]]
        for gate_id, region in zip(gates, regions[1:3]):
            gate = next(
                l
                for l in graph["links"]
                if l["source_id"] == gate_id and l["destination_region"] == region
            )
            candidates = [
                b
                for a, b in geometry["edges"]
                if a == gate["position"] and b in components[region]
            ]
            if not candidates:
                raise ValueError("Native branch physical gate has no directed arrival")
            arrivals.append(min(candidates))
        arrivals.append(
            next(
                l["destination_position"]
                for l in graph["links"]
                if l["source_id"] == final_id
            )
        )
        result.append(
            dict(
                key=f"route_{entry_id}",
                entry_source_id=entry_id,
                source_ids=[entry_id, final_id],
                physical_source_ids=list(gates),
                rooms=[
                    dict(
                        order=i + 1,
                        cells=components[region],
                        anchor=anchor,
                        native_arrival=arrival,
                    )
                    for i, (region, anchor, arrival) in enumerate(
                        zip(regions, anchors, arrivals)
                    )
                ],
            )
        )
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, default=14)
    args = parser.parse_args()
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda path: json.loads(Path(path).read_text())
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:73"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:73"
    )
    route = flow["route"]
    geometry = load(
        f".runtime/local/all-native-dungeon-exploration/exploration-{route['start_map_id']}.json"
    )
    sources = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    graph = extract(
        geometry,
        native["native_objects"],
        sources,
        flow["entry"],
        route["entry_map_id"],
    )
    mapping = {105: 1, 90: 1, 91: 1, 41: 2, 42: 2, 13: 3, 18: 3, 0: 4}
    if set(mapping) != set(graph["reachable_regions"]):
        raise ValueError("Native parallel-route regions differ from reviewed evidence")
    spine = dict(
        encounter_regions=[90, 41, 13, 0],
        stage_by_region=mapping,
        policy="Reviewed authentic three preliminary rooms on either native branch plus shared boss; exterior entry region105 is a noncombat lobby; branch selection is durable and precedes first spawn",
    )
    topology = topology_for(
        graph,
        spine,
        geometry,
        sources,
        flow["entry"],
        allow_nonadjacent=True,
        arrival_source_ids={2: 34749, 3: 34750, 4: 34744},
        allow_completed_entry_exit=True,
    )
    topology["branch_routes"] = branch_routes(graph, geometry)
    for room, branch_room in zip(
        topology["rooms"], topology["branch_routes"][0]["rooms"]
    ):
        room["anchor"] = branch_room["anchor"]
    topology["unresolved_native_elements"] = graph["unresolved"]
    bosses = next(
        r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
        if r["key"] == "native:73"
    )["boss_references"]
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    roster = progressive_family_roster(
        native,
        4,
        bosses,
        capacity=8,
        eligible_refs=eligible_family_refs(native, roles, bosses),
    )
    plan = base(native, route, roster["rooms"])["compiled_plan"]
    plan.update(
        progression_policy=roster["progression_policy"],
        policy_mode="user_authorized_progressive_native_parallel_branch_family_rooms",
    )
    # Normalize JSON object keys before computing frozen evidence hashes. Native
    # stage_by_region uses integer keys in memory; JSON persists string keys.
    plan, topology, route = json.loads(json.dumps([plan, topology, route]))
    config = prepare_configuration(
        copy.deepcopy(plan),
        copy.deepcopy(topology),
        copy.deepcopy(route),
        version=args.version,
        provenance=spine["policy"],
    )
    published = published_geometry(route["start_map_id"])
    combat = dict(
        map_id=route["start_map_id"],
        cells=list(published.cells),
        edges=list(published.edges),
    )
    augmented = copy.deepcopy(geometry)
    augmented["edges"] += [
        [p, d["destination_position"]]
        for d in topology["doors"]
        for p in d["native_approach_cells"]
    ]
    validations = []
    for branch in topology["branch_routes"]:
        variant = copy.deepcopy(config)
        for target, selected in zip(variant["topology"]["rooms"], branch["rooms"]):
            target.update(selected)
        placement = validate(
            variant, augmented, combat, enemy_formation, entry=flow["entry"]
        )
        if placement["status"] != "candidate_validated":
            raise ValueError("Native branch formation failed: " + json.dumps(placement))
        # Main topology cells retain lobby and both alternatives for movement;
        # branch records scope only spawning. Route witnesses use selected anchors.
        sequence_config = copy.deepcopy(config)
        for target, selected in zip(
            sequence_config["topology"]["rooms"], branch["rooms"]
        ):
            target["anchor"] = selected["anchor"]
            target["native_arrival"] = selected["native_arrival"]
        sequence_config["topology"]["rooms"][0]["native_arrival"] = flow["entry"]
        sequence = validate_hub_sequence(
            sequence_config, placement, allow_completed_entry_exit=True
        )
        validations.append(
            dict(
                branch_key=branch["key"],
                placement_validation=placement,
                sequence_validation=sequence,
            )
        )
    output = Path(f".runtime/local/palacio-zollo-native-cycle-v{args.version}-20261010")
    output.mkdir(exist_ok=True)
    for key, field in (
        ("plan", "compiled_plan"),
        ("topology", "topology"),
        ("route", "route"),
    ):
        if canonical_hash(config[field]) != config["evidence_hashes"][key]:
            raise ValueError(
                "Frozen configuration evidence changed during validation: " + key
            )
    serialized = json.dumps(config, indent=2) + "\n"
    if canonical_hash(json.loads(serialized)) != canonical_hash(config):
        raise ValueError("JSON serialization changes canonical configuration hash")
    target = output / "native_dungeon_73.json"
    target.write_text(serialized)
    import hashlib

    file_sha256 = hashlib.sha256(serialized.encode()).hexdigest()
    report = dict(
        scope="Source-only authentic parallel four-room routes; lobby has no spawn; no activation",
        records=[
            dict(
                key="native:73",
                status="offline_configuration_prepared",
                path=str(target),
                configuration_sha256=canonical_hash(config),
                configuration_canonical_sha256=canonical_hash(config),
                configuration_file_sha256=file_sha256,
                evidence_integrity_verified=True,
                rooms=4,
                branch_validations=validations,
                progression_policy=roster["progression_policy"],
                boss_references=bosses,
                completed_exit_witness="Native34746 returns stage4 boss to stage1 lobby; then native34747 returns to original exterior",
                source_only=True,
            )
        ],
    )
    path = Path(
        f"docs/reports/dungeons/PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V{args.version}-20261010.json"
    )
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
