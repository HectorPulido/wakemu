"""Prepare La Pischina's four native trigger-separated encounter arenas.

No runtime writes or invented geometry. Native PositionTrigger cells form real
walk-graph cuts and are assigned to the destination stage. Existing mixed-flow
movement authorization enforces that frontier without fake Door state packets.
"""
from collections import defaultdict
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components
from extract_native_trigger_frontiers import extract as extract_trigger_frontiers
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog
from native_family_configuration_base import base
from prepare_milubo_mixed_configuration import validate_hybrid_sequence
from validate_dungeon_flow_rosters import validate


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.dungeon_native_flow import packets

    load = lambda p: json.loads(Path(p).read_text())
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:143"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:143"
    )
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-912.json"
    )
    objects = {o["id"]: o for o in native["native_objects"] if o["map_id"] == 912}
    positions = lambda o: tuple(int(o[k]) for k in ("x", "y", "z"))
    trigger_stages = {31447: (1, 2), 31448: (2, 3), 31449: (3, 4), 31450: (3, 4)}
    if any(objects[i]["type"] != "PositionTrigger" for i in trigger_stages):
        raise ValueError("Reviewed native PositionTrigger identity changed")
    triggers = [
        dict(
            source_id=i,
            position=list(positions(objects[i])),
            source_room=a,
            destination_room=b,
            native_object_type="PositionTrigger",
            authority="Literal native trigger cell separates native walking arenas; destination-stage movement frontier",
        )
        for i, (a, b) in trigger_stages.items()
    ]
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    gate_position = positions(objects[31487])
    blocked = {tuple(g["position"]) for g in triggers} | {gate_position}
    trigger_proof = extract_trigger_frontiers(
        geometry,
        [objects[i] for i in trigger_stages],
        flow["entry"],
        [15, -26, 20],
        blocked_cells=[gate_position],
        expected_rooms=4,
    )
    if [set(f["source_ids"]) for f in trigger_proof["frontiers"]] != [
        {31447},
        {31448},
        {31449, 31450},
    ]:
        raise ValueError(
            "Reusable native trigger frontier order contradicts reviewed Pischina flow"
        )
    labels, sizes = components(set(map(tuple, geometry["cells"])) - blocked, adjacency)
    arena_regions = [
        labels[p] for p in [(22, 38, 0), (24, 14, 1), (34, 6, 1), (52, -5, 1)]
    ]
    if len(set(arena_regions)) != 4 or [sizes[r] for r in arena_regions] != [
        220,
        183,
        231,
        270,
    ]:
        raise ValueError(
            "Native trigger cuts do not prove the reviewed four distinct arenas"
        )
    annex = labels[(54, -2, 0)]
    mapping = {r: i for i, r in enumerate(arena_regions, 1)}
    mapping[annex] = 3
    arrivals = [[22, 38, 0], [24, 15, 1], [33, 6, 1], [52, -4, 1]]
    rooms = []
    for order, region in enumerate(arena_regions, 1):
        arena = [p for p in sorted(labels) if labels[p] == region]
        n = len(arena)
        sx = sum(p[0] for p in arena)
        sy = sum(p[1] for p in arena)
        anchor = min(
            arena, key=lambda p: ((p[0] * n - sx) ** 2 + (p[1] * n - sy) ** 2, p)
        )
        room_cells = [
            list(p) for p in sorted(labels) if mapping.get(labels[p]) == order
        ]
        room_cells += [
            g["position"] for g in triggers if g["destination_room"] == order
        ]
        rooms.append(
            dict(
                order=order,
                anchor=list(anchor),
                native_arrival=arrivals[order - 1],
                cells=room_cells,
                encounter_component=region,
            )
        )
    exits = []
    for source in load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    ):
        if source["map_id"] != 912:
            continue
        order = mapping[labels[positions(source)]]
        for destination in source["destinations"]:
            exits.append(
                dict(
                    source_id=source["id"],
                    room_order=order,
                    destination_id=destination["destination_id"],
                    destination={k: destination[k] for k in ("map_id", "x", "y", "z")},
                    native_approach_cells=[list(positions(source))],
                )
            )
    topology = dict(
        asset_map_id=912,
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority="Four native PositionTrigger cell cuts ordered from actual native entry to native boss exit; explicit local encounter staging, unchanged native directed walk geometry",
        rooms=rooms,
        doors=[],
        physical_doors=[
            dict(
                source_id=31487,
                position=list(gate_position),
                source_room=3,
                destination_room=3,
                local_annex_gate=True,
            )
        ],
        position_trigger_gates=triggers,
        physical_exit_objects=exits,
        exploration_geometry=geometry,
        unresolved_native_physical_objects=[
            dict(
                source_id=i,
                position=list(positions(objects[i])),
                reason="No native walking edges at the decorative lower-layer Door position; not used as a mandatory frontier",
            )
            for i in (24202, 24203, 31444, 31445)
        ],
        optional_annex=dict(
            region=annex,
            native_cells=sizes[annex],
            mandatory_encounter=False,
            initial_actors=[],
        ),
    )
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    eligible = eligible_family_refs(native, roles, [4727])
    eligible.discard(4889)
    published = published_geometry(912)
    combat = dict(map_id=912, cells=list(published.cells), edges=list(published.edges))
    attempts = []
    for capacity in (8, 6, 4, 3, 2, 1):
        try:
            roster = progressive_family_roster(
                native,
                4,
                [4727],
                capacity=capacity,
                exclude=[4889],
                eligible_refs=eligible,
            )
            plan = base(native, flow["route"], roster["rooms"])["compiled_plan"]
            plan.update(
                progression_policy=roster["progression_policy"],
                policy_mode="user_authorized_progressive_native_trigger_family_rooms",
                roster_policy_evidence=dict(
                    boss_references=[4727],
                    excluded_conditional_guest_references=[4889],
                    initial_summons=False,
                    native_roles_required=True,
                    composition_authority="Explicit local progressive initial family composition; guide quantities unavailable",
                ),
            )
            proposal = copy.deepcopy(topology)
            for adjustment in range(25):
                config = prepare_configuration(
                    plan,
                    proposal,
                    flow["route"],
                    version=10,
                    provenance=topology["progression_authority"]
                    + "; native ordinary fish family only; boss4727 final; conditional guest4889 excluded",
                )
                placement = validate(
                    config, geometry, combat, enemy_formation, entry=flow["entry"]
                )
                if placement["status"] == "candidate_validated":
                    break
                for order in [r["order"] for r in placement["rooms"] if r["reasons"]]:
                    region = arena_regions[order - 1]
                    center = topology["rooms"][order - 1]["anchor"]
                    anchors = sorted(
                        [p for p in labels if labels[p] == region],
                        key=lambda p: (
                            sum((p[i] - center[i]) ** 2 for i in range(2)),
                            p,
                        ),
                    )
                    proposal["rooms"][order - 1]["anchor"] = list(
                        anchors[min(adjustment + 1, len(anchors) - 1)]
                    )
            else:
                raise ValueError(
                    "No bounded native formation: " + json.dumps(placement["reasons"])
                )
            sequence = validate_hybrid_sequence(config, placement)
            states = [
                dict(
                    unlocked_room=stage,
                    packet_count=len(
                        packets(
                            config["topology"],
                            map_id=912,
                            instance_id=1,
                            unlocked_room=stage,
                            completed=False,
                        )
                    ),
                )
                for stage in range(1, 5)
            ]
            packets(
                config["topology"],
                map_id=912,
                instance_id=1,
                unlocked_room=4,
                completed=True,
            )
            break
        except ValueError as error:
            attempts.append(dict(capacity=capacity, reason=str(error)))
    else:
        raise ValueError(
            "No verified four-room native trigger candidate: " + json.dumps(attempts)
        )
    output = Path(".runtime/local/pischina-native-trigger-v10-20261010")
    output.mkdir(exist_ok=True)
    path = output / "native_dungeon_143.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    target = Path(
        "docs/reports/dungeons/PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json"
    )
    target.write_text(
        json.dumps(
            dict(
                scope="Source-only four actual native trigger-cut arenas; no activation",
                records=[
                    dict(
                        key="native:143",
                        name="La Pischina",
                        route=flow["route"]["key"],
                        status="offline_configuration_prepared",
                        path=str(path),
                        rooms=4,
                        boss_references=[4727],
                        excluded_conditional_guest_references=[4889],
                        progression_policy=roster["progression_policy"],
                        native_encounter_component_sizes=[
                            sizes[r] for r in arena_regions
                        ],
                        placement_validation=placement,
                        sequence_validation=sequence,
                        native_object_state_checks=states,
                        attempts=attempts,
                        mechanics_limit="Trigger-derived local victory frontiers use authoritative room movement; native trigger scripts and optional annex mechanics are not certified",
                    )
                ],
            ),
            indent=2,
        )
        + "\n"
    )
    print(target)


if __name__ == "__main__":
    main()
