"""Prepare reviewed Steamers hub and Lampionaute noncombat transit routes."""
import argparse
import copy
import hashlib
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

POLICIES = {
    188: dict(
        arenas=[4, 8, 12, 19],
        mapping={10: 1, 4: 1, 8: 2, 12: 3, 19: 4},
        incoming={2: 33624, 3: 33625, 4: 33634},
        description="Reviewed four Steamers encounters reached through noncombat lobby hub10; optional native physical annex terrain retained in its arena stage; nonadjacent transports explicitly victory gated",
    ),
    149: dict(
        arenas=[24, 16, 5, 2],
        mapping={24: 1, 21: 2, 18: 2, 16: 2, 6: 3, 8: 3, 5: 3, 2: 4},
        incoming={2: 17303, 3: 17311, 4: 17319},
        description="Reviewed four Lampionaute combat encounters; literal note and painting/training alternative regions are noncombat same-stage transit, not extra encounters; native foreign exterior retained",
    ),
}


def prepare_candidate(identity, version):
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda p: json.loads(Path(p).read_text())
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == f"native:{identity}"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == native["key"]
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
    policy = POLICIES[identity]
    mapping = dict(policy["mapping"])
    pending = set(graph["reachable_regions"]) - set(mapping)
    while pending:
        changed = False
        for region in sorted(pending):
            neighboring = {
                mapping[l["source_region"]]
                for l in graph["links"]
                if l["destination_region"] == region
                and l["source_region"] in mapping
                and l["kind"].startswith("physical")
            }
            neighboring |= {
                mapping[l["destination_region"]]
                for l in graph["links"]
                if l["source_region"] == region
                and l["destination_region"] in mapping
                and l["kind"].startswith("physical")
            }
            if len(neighboring) > 1:
                raise ValueError("Native annex has contradictory stage attachments")
            if neighboring:
                mapping[region] = next(iter(neighboring))
                pending.remove(region)
                changed = True
                break
        if not changed:
            raise ValueError("Native reachable annex has no exact physical attachment")
    # topology_for preserves all literal external destinations. A foreign exit
    # is retained only under the separately reviewed native exit contract.
    if identity == 149:
        for e in graph["exits"]:
            if (
                e["source_id"],
                e["destination_id"],
                e["destination_map_id"],
                e["destination_position"],
            ) not in (
                (17381, 3987, 1211, [8368, 8352, 0]),
                (17382, 3987, 1211, [8368, 8352, 0]),
            ):
                raise ValueError("Native Lampionaute foreign exterior evidence changed")
    spine = dict(
        encounter_regions=policy["arenas"],
        stage_by_region=mapping,
        policy=policy["description"],
    )
    topology = topology_for(
        graph,
        spine,
        geometry,
        sources,
        flow["entry"],
        allow_nonadjacent=True,
        arrival_source_ids=policy["incoming"],
        allow_foreign_exit=identity == 149,
    )
    topology["unresolved_native_elements"] = graph["unresolved"]
    if identity == 149:
        topology["native_foreign_exterior_policy"] = {
            "reason": "Reviewed literal native Lampionaute entrance and completion exits share exterior1211 although selected historical exterior entry route is235",
            "bindings": [
                dict(
                    source_id=identity,
                    source_sha256=canonical_hash(
                        next(
                            s
                            for s in sources
                            if s["map_id"] == geometry["map_id"] and s["id"] == identity
                        )
                    ),
                    destination_id=3987,
                    destination=dict(map_id=1211, x=8368, y=8352, z=0),
                )
                for identity in (17381, 17382)
            ],
        }
    bosses = next(
        r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
        if r["key"] == native["key"]
    )["boss_references"]
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    eligible = eligible_family_refs(native, roles, bosses)
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
    attempts = []
    for capacity in (8, 6, 4):
        roster = progressive_family_roster(
            native, 4, bosses, capacity=capacity, eligible_refs=eligible
        )
        plan = base(native, route, roster["rooms"])["compiled_plan"]
        plan.update(
            progression_policy=roster["progression_policy"],
            policy_mode="user_authorized_progressive_reviewed_native_hub_transit_family_rooms",
        )
        for adjustment in range(25):
            proposal = copy.deepcopy(topology)
            for room in proposal["rooms"]:
                arena_cells = next(
                    r["cells"]
                    for r in graph["components"]
                    if r["region"] == room["encounter_component"]
                )
                center = room["anchor"]
                alternatives = sorted(
                    arena_cells,
                    key=lambda p: (sum((p[i] - center[i]) ** 2 for i in range(2)), p),
                )
                room["anchor"] = alternatives[min(adjustment, len(alternatives) - 1)]
            normalized_plan, proposal, normalized_route = json.loads(
                json.dumps([plan, proposal, route])
            )
            config = prepare_configuration(
                normalized_plan,
                proposal,
                normalized_route,
                version=version,
                provenance=policy["description"],
            )
            placement = validate(
                config, augmented, combat, enemy_formation, entry=flow["entry"]
            )
            if placement["status"] != "candidate_validated":
                continue
            try:
                sequence = validate_hub_sequence(config, placement)
            except ValueError as error:
                attempts.append(str(error))
                continue
            break
        else:
            continue
        break
    else:
        raise ValueError("No native formation/sequence: " + json.dumps(attempts))
    for key, field in (
        ("plan", "compiled_plan"),
        ("topology", "topology"),
        ("route", "route"),
    ):
        if canonical_hash(config[field]) != config["evidence_hashes"][key]:
            raise ValueError("Frozen evidence mismatch: " + key)
    serialized = json.dumps(config, indent=2) + "\n"
    if canonical_hash(json.loads(serialized)) != canonical_hash(config):
        raise ValueError("JSON persistence changes canonical evidence")
    output = Path(f".runtime/local/reviewed-hub-transit-v{version}-20261010")
    output.mkdir(exist_ok=True)
    target = output / f"native_dungeon_{identity}.json"
    target.write_text(serialized)
    return dict(
        key=native["key"],
        route=route["key"],
        status="offline_configuration_prepared",
        path=str(target),
        rooms=4,
        boss_references=bosses,
        configuration_sha256=canonical_hash(config),
        configuration_canonical_sha256=canonical_hash(config),
        configuration_file_sha256=hashlib.sha256(serialized.encode()).hexdigest(),
        progression_policy=roster["progression_policy"],
        placement_validation=placement,
        sequence_validation=sequence,
        unresolved_native_elements=graph["unresolved"],
        requires_server_deployment=True,
        source_only=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=int, nargs="+", default=[188, 149])
    parser.add_argument("--version", type=int, default=16)
    args = parser.parse_args()
    records = []
    for identity in args.targets:
        try:
            records.append(prepare_candidate(identity, args.version))
        except ValueError as error:
            records.append(
                dict(key=f"native:{identity}", status="blocked", reason=str(error))
            )
    report = Path(
        f"docs/reports/dungeons/REVIEWED-HUB-TRANSIT-CANDIDATES-V{args.version}-20261010.json"
    )
    report.write_text(
        json.dumps(
            dict(
                scope="Source-only reviewed noncombat hub/transit vs four combat stages; literal native geometry and endpoints",
                records=records,
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(records, default=str)[:1200])


if __name__ == "__main__":
    main()
