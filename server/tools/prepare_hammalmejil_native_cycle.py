"""Prepare three Hammalmejil encounters on its literal native walking cycle."""
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


def reviewed_cycle(graph):
    """Keep every literal gate; the native return opens at the final frontier."""
    expected = {19112: {3, 12}, 19109: {5, 12}, 19110: {3, 5}}
    actual = {}
    for link in graph["links"]:
        if link["kind"] == "physical_gate":
            actual.setdefault(link["source_id"], set()).update(
                (link["source_region"], link["destination_region"])
            )
    if actual != expected or graph["entry_region"] != 12:
        raise ValueError("Native Hammalmejil cycle differs from reviewed endpoints")
    if set(graph["reachable_regions"]) != {3, 5, 12}:
        raise ValueError("Native Hammalmejil reachable arenas differ from review")
    return dict(
        encounter_regions=[12, 5, 3],
        stage_by_region={12: 1, 5: 2, 3: 3},
        native_visit_regions=[12, 5, 3, 12],
        policy="Explicit local three-encounter staging on the literal native walking cycle; clockwise encounter order is local policy, not verified official placement; native return gate opens at final frontier",
    )


def main():
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
        if r["key"] == "native:68"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:68"
    )
    route = flow["route"]
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-548.json"
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
    spine = reviewed_cycle(graph)
    topology = topology_for(
        graph,
        spine,
        geometry,
        sources,
        flow["entry"],
        allow_nonadjacent=True,
        allow_completed_entry_exit=True,
        arrival_source_ids={2: 19109, 3: 19110},
    )
    topology["unresolved_native_elements"] = graph["unresolved"]
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    published = published_geometry(548)
    combat = dict(map_id=548, cells=list(published.cells), edges=list(published.edges))
    attempts = []
    for capacity in (8, 6, 4):
        roster = progressive_family_roster(
            native,
            3,
            [2464],
            capacity=capacity,
            eligible_refs=eligible_family_refs(native, roles, [2464]),
        )
        plan = base(native, route, roster["rooms"])["compiled_plan"]
        plan.update(
            progression_policy=roster["progression_policy"],
            policy_mode="user_authorized_progressive_native_walking_cycle",
        )
        for adjustment in range(25):
            proposal = copy.deepcopy(topology)
            for room in proposal["rooms"]:
                center = room["anchor"]
                choices = sorted(
                    room["cells"],
                    key=lambda p: (sum((p[i] - center[i]) ** 2 for i in range(2)), p),
                )
                room["anchor"] = choices[min(adjustment, len(choices) - 1)]
            frozen_plan, proposal, frozen_route = json.loads(
                json.dumps([plan, proposal, route])
            )
            config = prepare_configuration(
                frozen_plan,
                proposal,
                frozen_route,
                version=17,
                provenance=spine["policy"],
            )
            placement = validate(
                config, geometry, combat, enemy_formation, entry=flow["entry"]
            )
            if placement["status"] != "candidate_validated":
                attempts.append(
                    dict(
                        capacity=capacity,
                        adjustment=adjustment,
                        reasons=placement["reasons"],
                    )
                )
                continue
            try:
                sequence = validate_hub_sequence(
                    config, placement, allow_completed_entry_exit=True
                )
            except ValueError as error:
                attempts.append(
                    dict(capacity=capacity, adjustment=adjustment, reason=str(error))
                )
                continue
            break
        else:
            continue
        break
    else:
        raise ValueError("No validated native cycle: " + json.dumps(attempts))
    output = Path(".runtime/local/hammalmejil-native-cycle-v17-20261010")
    output.mkdir(exist_ok=True)
    path = output / "native_dungeon_68.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    report = dict(
        scope="Source-only native walking cycle; no runtime activation",
        records=[
            dict(
                key="native:68",
                name=native["name_es"],
                route=route["key"],
                status="offline_configuration_prepared",
                path=str(path),
                configuration_sha256=canonical_hash(config),
                rooms=3,
                boss_references=[2464],
                native_visit_regions=spine["native_visit_regions"],
                progression_policy=roster["progression_policy"],
                placement_validation=placement,
                sequence_validation=sequence,
                attempts=attempts,
                local_policy=spine["policy"],
                source_only=True,
            )
        ],
    )
    target = Path(
        "docs/reports/dungeons/HAMMALMEJIL-NATIVE-CYCLE-CANDIDATE-V17-20261010.json"
    )
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
