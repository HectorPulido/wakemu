"""Prepare four Riktus encounters using literal activation-cell frontiers.

The local mandatory route uses the western preliminary arena. The authentic
eastern alternative remains accessible transit terrain with no extra encounter.
Durable east/west encounter choice is not implemented by this preparation.
"""
from collections import defaultdict
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decode_native_interactive_activation_cells import decode
from extract_dungeon_topology import components
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog
from native_family_configuration_base import base
from validate_dungeon_flow_rosters import validate
from prepare_vid_vil_hub_configuration import validate_hub_sequence


def topology_for(native, geometry, objects, sources, entry):
    owned = {o["id"]: o for o in objects if o["map_id"] == 301}
    trigger = owned[31790]
    if trigger["type"] != "PositionTrigger" or decode(trigger) != [
        [-3, -67, 0],
        [-8, -59, 0],
        [9, -59, 0],
    ]:
        raise ValueError("Native Riktus activation-cell membership changed")
    doors = [o for o in owned.values() if o["type"] == "Door"]
    position = lambda obj: tuple(int(obj[key]) for key in ("x", "y", "z"))
    blocked = {position(o) for o in doors} | {(-3, -67, 0)}
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    labels, sizes = components(set(map(tuple, geometry["cells"])) - blocked, adjacency)
    expected = {0: 1080, 4: 221, 7: 844, 33: 198, 52: 198}
    if {
        region: size for region, size in enumerate(sizes) if size > 100
    } != expected or labels[tuple(entry)] != 7:
        raise ValueError("Native Riktus activation cuts differ from reviewed arenas")
    mapping = {7: 1, 4: 2, 52: 2, 0: 3, 33: 4}
    arenas = [7, 4, 0, 33]
    physical = []
    for door in doors:
        memberships = {labels[p] for p in adjacency[position(door)] if p in labels}
        stages = {mapping[r] for r in memberships}
        physical.append(
            dict(
                source_id=door["id"],
                position=list(position(door)),
                source_room=min(stages),
                destination_room=max(stages),
            )
        )
    arrivals = [list(entry)]
    for source_id, region in ((13937, 4), (13939, 0), (13942, 33)):
        candidates = [
            b
            for a, b in geometry["edges"]
            if tuple(a) == position(owned[source_id]) and labels.get(tuple(b)) == region
        ]
        if not candidates:
            raise ValueError("Reviewed west-route gate has no native directed arrival")
        arrivals.append(min(candidates))
    rooms = []
    for order, region in enumerate(arenas, 1):
        arena = [p for p, label in labels.items() if label == region]
        count, sx, sy = len(arena), sum(p[0] for p in arena), sum(p[1] for p in arena)
        anchor = min(
            arena,
            key=lambda p: ((p[0] * count - sx) ** 2 + (p[1] * count - sy) ** 2, p),
        )
        cells = [list(p) for p in sorted(labels) if mapping.get(labels[p]) == order]
        if order == 4:
            cells.append([-3, -67, 0])
        rooms.append(
            dict(
                order=order,
                anchor=list(anchor),
                native_arrival=arrivals[order - 1],
                cells=cells,
                encounter_component=region,
            )
        )
    exits = []
    for source in sources:
        if source["map_id"] != 301:
            continue
        center = position(source)
        approaches = {
            tuple(p[key] for key in ("x", "y", "z"))
            for p in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(center)
        approaches = {p for p in approaches if p in labels and labels[p] in mapping}
        orders = {mapping[labels[p]] for p in approaches}
        if len(orders) != 1:
            raise ValueError("Native Riktus exit approaches do not bind a unique stage")
        order = next(iter(orders))
        for destination in source["destinations"]:
            if (
                destination["map_id"] != 1207
                or destination.get("criterion", "").strip()
                or destination.get("cyX", 0)
                or destination.get("cyZ", -1) >= 0
            ):
                raise ValueError("Native Riktus exterior is not the reviewed free exit")
            exits.append(
                dict(
                    source_id=source["id"],
                    room_order=order,
                    destination_id=destination["destination_id"],
                    destination={
                        key: destination[key] for key in ("map_id", "x", "y", "z")
                    },
                    native_approach_cells=[list(p) for p in sorted(approaches)],
                )
            )
    return dict(
        asset_map_id=301,
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority="Explicit local four-encounter west route on native physical and activation-cell cuts; eastern preliminary region remains optional transit without extra encounter; no durable east/west encounter choice",
        rooms=rooms,
        doors=[],
        physical_doors=physical,
        position_trigger_gates=[
            dict(
                source_id=31790,
                position=[-3, -67, 0],
                source_room=3,
                destination_room=4,
                native_object_type="PositionTrigger",
                authority="Literal bEH-decoded Re.bkT activation cell; no polygon or collision inference",
            )
        ],
        physical_exit_objects=exits,
        exploration_geometry=geometry,
        native_activation_evidence=dict(
            source_id=31790,
            center=list(position(trigger)),
            activation_cells=decode(trigger),
            interpretation="Exact native trigger membership; not polygon vertices",
        ),
        optional_native_east_route=dict(
            region=52,
            cells=sizes[52],
            generated_encounter=False,
            preserved_native_gate_ids=[13938, 13940],
        ),
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
        if r["key"] == "native:139"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:139"
    )
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-301.json"
    )
    topology = topology_for(
        native,
        geometry,
        load(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-map-objects.json"
        ),
        load(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ),
        flow["entry"],
    )
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    combat_source = published_geometry(301)
    combat = dict(
        map_id=301, cells=list(combat_source.cells), edges=list(combat_source.edges)
    )
    attempts = []
    for capacity in (8, 6, 4):
        roster = progressive_family_roster(
            native,
            4,
            [4538],
            capacity=capacity,
            eligible_refs=eligible_family_refs(native, roles, [4538]),
        )
        plan = base(native, flow["route"], roster["rooms"])["compiled_plan"]
        plan.update(
            progression_policy=roster["progression_policy"],
            policy_mode="user_authorized_progressive_native_west_activation_route",
        )
        for adjustment in range(40):
            proposal = copy.deepcopy(topology)
            for room in proposal["rooms"]:
                center = room["anchor"]
                region = room["encounter_component"]
                # Keep initial actors in the selected western arena, never the
                # preserved optional eastern branch sharing its progress stage.
                available = (
                    room["cells"]
                    if region != 4
                    else [p for p in room["cells"] if p[0] < -10]
                )
                choices = sorted(
                    available,
                    key=lambda p: (sum((p[i] - center[i]) ** 2 for i in range(2)), p),
                )
                room["anchor"] = choices[min(adjustment, len(choices) - 1)]
            frozen_plan, proposal, route = json.loads(
                json.dumps([plan, proposal, flow["route"]])
            )
            config = prepare_configuration(
                frozen_plan,
                proposal,
                route,
                version=18,
                provenance=topology["progression_authority"],
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
        raise ValueError("No validated Riktus west route: " + json.dumps(attempts))
    output = Path(".runtime/local/riktus-elite-native-west-v18-20261010")
    output.mkdir(exist_ok=True)
    path = output / "native_dungeon_139.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    report = dict(
        scope="Source-only fixed-west local encounter policy; all native terrain and gates preserved",
        records=[
            dict(
                key="native:139",
                name=native["name_es"],
                route=route["key"],
                status="offline_configuration_prepared",
                path=str(path),
                configuration_sha256=canonical_hash(config),
                rooms=4,
                boss_references=[4538],
                progression_policy=roster["progression_policy"],
                placement_validation=placement,
                sequence_validation=sequence,
                native_activation_evidence=topology["native_activation_evidence"],
                optional_native_east_route=topology["optional_native_east_route"],
                attempts=attempts,
                source_only=True,
            )
        ],
    )
    target = Path(
        "docs/reports/dungeons/RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json"
    )
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
