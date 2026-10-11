"""Prepare the reviewed four-room Milubo dungeon without runtime writes."""
import copy
import json
from pathlib import Path
import sys
import struct

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_family_configuration_base import base
from extract_milubo_mixed_flow import hybrid_path
from extract_dungeon_family_bosses import load_role_catalog, role_allowed
from validate_dungeon_flow_rosters import validate

COUNTS = (
    {5113: 2, 5111: 2, 5112: 2},
    {5113: 2, 5111: 3, 5112: 2},
    {5113: 3, 5111: 3, 5112: 2},
    {5113: 3, 5111: 2, 5112: 2, 5114: 1},
)


def validate_hybrid_sequence(config, placement):
    """Check native arrivals, engagement, frontier closure and completed exit."""
    topology = config["topology"]
    geometry = topology["exploration_geometry"]
    entry = topology["rooms"][0]["native_arrival"]
    rooms = []
    gates = list(topology["physical_doors"]) + list(
        topology.get("position_trigger_gates", [])
    )
    for room, positioned in zip(topology["rooms"], placement["rooms"]):
        stage = room["order"]
        blocked = [d["position"] for d in gates if d["destination_room"] > stage]
        transports = [
            d
            for d in topology["doors"]
            if max(d["source_room"], d["destination_room"]) <= stage
        ]
        start = room["native_arrival"]
        monsters = set(map(tuple, positioned["monster_positions"]))
        engagement = None
        for monster in sorted(monsters):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                approach = [monster[0] + dx, monster[1] + dy, monster[2]]
                if tuple(approach) not in set(map(tuple, room["cells"])):
                    continue
                path = hybrid_path(
                    geometry["edges"],
                    transports,
                    start,
                    approach,
                    blocked=blocked + list(monsters),
                )
                if path is not None:
                    engagement = dict(
                        target=list(monster), approach=approach, path=path
                    )
                    break
            if engagement:
                break
        if engagement is None:
            raise ValueError(
                f"Room {stage} cannot engage its native formation from literal arrival"
            )
        ingress = hybrid_path(
            geometry["edges"], transports, entry, room["anchor"], blocked=blocked
        )
        if ingress is None:
            raise ValueError("Native ingress cannot reach actual encounter arena")
        previous_transports = [
            d
            for d in topology["doors"]
            if max(d["source_room"], d["destination_room"]) < stage
        ]
        closed = [d["position"] for d in gates if d["destination_room"] >= stage]
        if (
            stage > 1
            and hybrid_path(
                geometry["edges"],
                previous_transports,
                entry,
                room["anchor"],
                blocked=closed,
            )
            is not None
        ):
            raise ValueError("Encounter reachable before prior victory")
        exits = [
            e for e in topology["physical_exit_objects"] if e["room_order"] == stage
        ]
        forward = [
            d
            for d in topology["doors"]
            if d["source_room"] == stage and d["destination_room"] == stage + 1
        ]
        boundaries = [
            d
            for d in gates
            if d["source_room"] == stage and d["destination_room"] == stage + 1
        ]
        terminal_paths = []
        if stage == len(topology["rooms"]):
            targets = [p for e in exits for p in e["native_approach_cells"]]
        elif forward:
            targets = [p for d in forward for p in d["native_approach_cells"]]
        else:
            # The boundary itself is closed until victory; prove its approach
            # using native incoming walk edges while the physical gate is closed.
            targets = [
                a
                for a, b in geometry["edges"]
                if any(tuple(b) == tuple(d["position"]) for d in boundaries)
                and tuple(a) in set(map(tuple, room["cells"]))
            ]
        for target in targets:
            path = hybrid_path(
                geometry["edges"], transports, room["anchor"], target, blocked=blocked
            )
            if path is not None:
                terminal_paths.append(path)
        if not terminal_paths:
            raise ValueError(f"Room {stage} has no literal next gate/exit approach")
        rooms.append(
            dict(
                order=stage,
                native_arrival=start,
                ingress_path=ingress,
                engagement_witness=engagement,
                next_gate_or_exit_paths=terminal_paths,
            )
        )
    return dict(status="offline_native_mixed_sequence_validated", rooms=rooms)


def main():
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_native_flow import packets

    load = lambda p: json.loads(Path(p).read_text())
    evidence = load("docs/reports/dungeons/MILUBO-MIXED-NATIVE-FLOW-20261010.json")
    topology = evidence["topology"]
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:47"
    )
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    rooms = []
    scores = []
    for order, counts in enumerate(COUNTS, 1):
        monsters = []
        for ref, count in sorted(counts.items()):
            if not role_allowed(
                roles.get(ref), final_room=order == 4, allowed_boss_references=[5114]
            ):
                raise ValueError("Reviewed roster violates native role restrictions")
            m = pool[ref]
            monsters.append(
                dict(
                    name=m["name_es"],
                    ref_id=ref,
                    count=count,
                    role="boss" if ref == 5114 else "monster",
                    native_min_level=m["min_level"],
                    native_max_level=m["max_level"],
                    guide_min_level=None,
                    guide_max_level=None,
                )
            )
        rooms.append(dict(order=order, monsters=monsters))
        scores.append(sum(m["count"] * m["native_min_level"] for m in monsters))
    if scores != [424, 494, 562, 575]:
        raise ValueError("Reviewed native-minimum progression changed")
    compiled = base(native, evidence["route"], rooms)["compiled_plan"]
    compiled.update(
        policy_mode="reviewed_four_room_native_mixed_milubo",
        roster_policy_evidence=dict(
            boss_references=[5114],
            authority="Archived four guide room screenshots visually reviewed by root; native names/grades/roles matched exactly",
            initial_summons=False,
            quantities="Reviewed guide counts 6,7,8,8",
        ),
        progression_policy=dict(
            metric="sum(count * actual_spawn_level)",
            actual_spawn_level_policy="native_minimum",
            strict_increase=True,
            rooms=[
                dict(
                    order=i + 1,
                    quantity=sum(COUNTS[i].values()),
                    native_minimum_threat=score,
                )
                for i, score in enumerate(scores)
            ],
        ),
    )
    config = prepare_configuration(
        compiled,
        topology,
        evidence["route"],
        version=6,
        provenance="Reviewed four-room Milubo: native mixed physical gates and literal same-stage/adjacent-stage transports; exact guide initial family counts; final-only Luna Gigante; no initial summons; native minimum levels",
    )
    # Augmented edges are used only for offline reachability validation. Runtime
    # exploration retains the unchanged native walk edges and real transports.
    validation_geometry = copy.deepcopy(topology["exploration_geometry"])
    validation_geometry["edges"] += [
        [p, d["destination_position"]]
        for d in topology["doors"]
        for p in d["native_approach_cells"]
    ]
    p = published_geometry(1266)
    combat = dict(map_id=1266, cells=list(p.cells), edges=list(p.edges))
    placement = validate(
        config, validation_geometry, combat, enemy_formation, entry=[0, 0, 0]
    )
    if placement["status"] != "candidate_validated":
        raise ValueError(json.dumps(placement))
    sequence = validate_hybrid_sequence(config, placement)
    sources = [
        s
        for s in load(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        )
        if s["map_id"] == 1266
    ]
    state_checks = []
    for stage in range(1, 5):
        messages = packets(
            topology, map_id=1266, instance_id=1, unlocked_room=stage, completed=False
        )
        gates = {}
        for opcode, body in messages:
            identity = struct.unpack_from(">q", body)[0]
            if identity in (32205, 32212):
                state_id, visible, usable = struct.unpack_from(">hBB", body, 17)
                gates[identity] = dict(
                    state_id=state_id, visible=bool(visible), usable=bool(usable)
                )
        expected = {32205: stage < 2, 32212: stage < 4}
        if len(messages) != 12 or any(
            gates[identity]["visible"] != closed
            or gates[identity]["state_id"] != int(closed)
            for identity, closed in expected.items()
        ):
            raise ValueError("Native mixed gate hydration changed")
        state_checks.append(
            dict(
                unlocked_room=stage,
                packet_count=len(messages),
                physical_gate_states=gates,
            )
        )
    packets(topology, map_id=1266, instance_id=1, unlocked_room=4, completed=True)
    output = Path(".runtime/local/milubo-four-room-mixed-v6-20261010")
    output.mkdir(exist_ok=True)
    path = output / "native_dungeon_47.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    report = dict(
        scope="Source-only four-room candidate, no runtime activation",
        records=[
            dict(
                key="native:47",
                route="native_dungeon_47",
                name="Mazmorra Milubo",
                status="offline_configuration_prepared",
                path=str(path),
                rooms=4,
                boss_references=[5114],
                room_quantities=[6, 7, 8, 8],
                native_minimum_threat=scores,
                placement_validation=placement,
                sequence_validation=sequence,
                native_object_state_checks=state_checks,
                source_only=True,
                requires_server_deployment=True,
            )
        ],
    )
    target = Path(
        "docs/reports/dungeons/MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json"
    )
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
