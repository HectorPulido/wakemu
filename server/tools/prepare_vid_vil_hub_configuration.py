"""Prepare four native Vid Vil arenas, retaining the literal revisited hub."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_hybrid_native_dungeon_flow import extract
from prepare_hybrid_native_dungeons import topology_for
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog
from native_family_configuration_base import base
from validate_dungeon_flow_rosters import validate
from extract_milubo_mixed_flow import hybrid_path


def validate_hub_sequence(config, placement, *, allow_completed_entry_exit=False):
    """Prove every encounter and next source under destination-frontier gating."""
    topology = config["topology"]
    geometry = topology["exploration_geometry"]
    entry = topology["rooms"][0]["native_arrival"]
    witnesses = []
    for room, positioned in zip(topology["rooms"], placement["rooms"]):
        stage = room["order"]
        available = [
            d
            for d in topology["doors"]
            if max(d["source_room"], d["destination_room"]) <= stage
        ]
        previous = [
            d for d in available if max(d["source_room"], d["destination_room"]) < stage
        ]
        gates = list(topology.get("physical_doors", [])) + list(
            topology.get("position_trigger_gates", [])
        )
        blocked = [d["position"] for d in gates if d["destination_room"] > stage]
        ingress = hybrid_path(
            geometry["edges"], available, entry, room["anchor"], blocked=blocked
        )
        if ingress is None:
            raise ValueError("Actual native ingress cannot reach encounter")
        if (
            stage > 1
            and hybrid_path(
                geometry["edges"],
                previous,
                entry,
                room["anchor"],
                blocked=[
                    d["position"] for d in gates if d["destination_room"] >= stage
                ],
            )
            is not None
        ):
            raise ValueError("Encounter accessible before previous-stage victory")
        monsters = set(map(tuple, positioned["monster_positions"]))
        engagement = None
        for monster in sorted(monsters):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                target = [monster[0] + dx, monster[1] + dy, monster[2]]
                if target not in room["cells"]:
                    continue
                path = hybrid_path(
                    geometry["edges"],
                    available,
                    room["native_arrival"],
                    target,
                    blocked=list(monsters) + blocked,
                )
                if path is not None:
                    engagement = dict(target=list(monster), approach=target, path=path)
                    break
            if engagement:
                break
        if engagement is None:
            raise ValueError("Actual arrival cannot engage formation")
        next_bindings = [
            d
            for d in topology["doors"]
            if d["destination_room"] == stage + 1 and d["source_room"] <= stage
        ]
        targets = [p for d in next_bindings for p in d["native_approach_cells"]]
        targets += [
            a
            for a, b in geometry["edges"]
            for d in gates
            if d["source_room"] == stage
            and d["destination_room"] == stage + 1
            and b == d["position"]
            and a in room["cells"]
        ]
        if stage == len(topology["rooms"]):
            targets = [
                p
                for e in topology["physical_exit_objects"]
                if e["room_order"] == stage
                or (allow_completed_entry_exit and e["room_order"] == 1)
                for p in e["native_approach_cells"]
            ]
        paths = [
            path
            for target in targets
            if (
                path := hybrid_path(
                    geometry["edges"],
                    available,
                    room["anchor"],
                    target,
                    blocked=blocked,
                )
            )
            is not None
        ]
        if not paths:
            raise ValueError("No native path to next frontier or final exit")
        witnesses.append(
            dict(
                order=stage,
                ingress_path=ingress,
                engagement=engagement,
                next_source_paths=paths,
            )
        )
    return dict(status="offline_native_hub_sequence_validated", rooms=witnesses)


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
        if r["key"] == "native:115"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:115"
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
    mapping = {0: 1, 1: 2, 28: 3, 14: 4}
    if set(graph["reachable_regions"]) != set(mapping):
        raise ValueError(
            "Native reachable component set differs from reviewed four arenas"
        )
    spine = dict(
        encounter_regions=[0, 1, 28, 14],
        stage_by_region=mapping,
        native_visit_regions=[0, 1, 28, 1, 14],
        policy="Explicit local four-arena staging on literal native hub revisit; destination frontier and prior-stage receipt authorize forward travel",
    )
    topology = topology_for(
        graph, spine, geometry, sources, flow["entry"], allow_nonadjacent=True
    )
    expected = {
        26745: (1, 2),
        26746: (2, 1),
        26751: (2, 3),
        26750: (3, 2),
        26747: (2, 4),
        26748: (4, 2),
    }
    if {
        d["source_id"]: (d["source_room"], d["destination_room"])
        for d in topology["doors"]
    } != expected:
        raise ValueError("Literal native hub bindings differ from reviewed endpoints")
    if {e["source_id"] for e in topology["physical_exit_objects"]} != {26744, 26749}:
        raise ValueError("Literal native exterior exits differ from reviewed route")
    for room, anchor in zip(
        topology["rooms"], ([-7, 0, 0], [91, -70, 0], [265, -260, 0], [165, -144, 0])
    ):
        room["anchor"] = anchor
    topology["unresolved_native_elements"] = graph["unresolved"]
    bosses = next(
        r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
        if r["key"] == "native:115"
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
            policy_mode="user_authorized_progressive_native_hub_family_rooms",
        )
        for adjustment in range(25):
            proposal = copy.deepcopy(topology)
            for room in proposal["rooms"]:
                center = room["anchor"]
                alternatives = sorted(
                    map(tuple, room["cells"]),
                    key=lambda p: (sum((p[i] - center[i]) ** 2 for i in range(2)), p),
                )
                room["anchor"] = list(
                    alternatives[min(adjustment, len(alternatives) - 1)]
                )
            config = prepare_configuration(
                plan, proposal, route, version=11, provenance=spine["policy"]
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
        raise ValueError(
            "No native formation and hub sequence: " + json.dumps(attempts)
        )
    output = Path(".runtime/local/vid-vil-native-hub-v11-20261010")
    output.mkdir(exist_ok=True)
    target = output / "native_dungeon_115.json"
    target.write_text(json.dumps(config, indent=2) + "\n")
    report = dict(
        scope="Source-only four native arenas, no activation",
        records=[
            dict(
                key="native:115",
                status="offline_configuration_prepared",
                path=str(target),
                configuration_sha256=canonical_hash(config),
                rooms=4,
                native_visit_regions=spine["native_visit_regions"],
                boss_references=bosses,
                progression_policy=roster["progression_policy"],
                placement_validation=placement,
                sequence_validation=sequence,
                runtime_contract="Explicit nonadjacent native transport; forward gated by destination-1 durable victory and committed destination frontier; backward travel does not advance progress",
                source_only=True,
            )
        ],
    )
    path = Path("docs/reports/dungeons/VID-VIL-NATIVE-HUB-CANDIDATE-V11-20261010.json")
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
