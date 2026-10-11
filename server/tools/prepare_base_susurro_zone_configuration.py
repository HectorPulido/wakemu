"""Prepare four native Base Susurro arenas using decoded activation-set frontier."""
import copy
import json
from collections import defaultdict
from pathlib import Path
from decode_native_interactive_activation_cells import decode
from extract_dungeon_topology import components
from native_family_configuration_base import base
from extract_dungeon_family_bosses import load_role_catalog
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from prepare_milubo_mixed_configuration import validate_hybrid_sequence
from validate_dungeon_flow_rosters import validate


def main():
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_native_flow import packets

    load = lambda p: json.loads(Path(p).read_text())
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:53"
    )
    route = native["native_entry_routes"][0]
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-448.json"
    )
    raw = next(
        o
        for o in load(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-map-objects.json"
        )
        if o["map_id"] == 448 and o["id"] == 16538
    )
    activation = decode(raw)
    if set(map(tuple, activation)) != {
        (-2, -43, 8),
        (-1, -43, 8),
        (0, -43, 8),
        (1, -43, 8),
        (2, -43, 8),
        (-1, -42, 8),
        (0, -42, 8),
        (1, -42, 8),
        (3, -43, 8),
    }:
        raise ValueError("Reviewed ZoneTrigger activation set changed")
    objects = {o["id"]: o for o in native["native_objects"]}
    physical = []
    for identity, source, destination in [
        (16262, 1, 2),
        (16508, 1, 2),
        (16263, 3, 4),
        (16509, 3, 4),
    ]:
        obj = objects[identity]
        physical.append(
            dict(
                source_id=identity,
                position=[int(obj[k]) for k in ("x", "y", "z")],
                source_room=source,
                destination_room=destination,
            )
        )
    triggers = [
        dict(
            source_id=16538,
            position=p,
            source_room=2,
            destination_room=3,
            native_object_type="ZoneTrigger",
            native_activation_cells=activation,
            authority="Exact native Re.bkT activation-set point; local victory movement frontier, not collision polygon",
        )
        for p in activation
    ]
    blocked = {tuple(d["position"]) for d in physical + triggers}
    adj = defaultdict(set)
    for a, b in geometry["edges"]:
        adj[tuple(a)].add(tuple(b))
        adj[tuple(b)].add(tuple(a))
    labels, sizes = components(set(map(tuple, geometry["cells"])) - blocked, adj)
    anchors = [[0, -13, 8], [0, -32, 8], [-1, -52, 8], [-1, -85, 8]]
    regions = [labels[tuple(a)] for a in anchors]
    if [sizes[r] for r in regions] != [438, 63, 333, 374]:
        raise ValueError("Four reviewed native arenas changed")
    mapping = {r: i + 1 for i, r in enumerate(regions)}
    # Native islands cut off by the full activation set remain destination-owned.
    for point in activation:
        for neighbor in adj[tuple(point)]:
            if neighbor in labels and labels[neighbor] not in mapping:
                mapping[labels[neighbor]] = 3
    rooms = []
    arrivals = [[0, 0, 0], [0, -22, 8], [-2, -43, 8], [0, -60, 8]]
    for order, anchor in enumerate(anchors, 1):
        cells = [list(c) for c in sorted(labels) if mapping.get(labels[c], 1) == order]
        cells.extend(
            g["position"] for g in physical + triggers if g["destination_room"] == order
        )
        rooms.append(
            dict(
                order=order,
                anchor=anchor,
                native_arrival=arrivals[order - 1],
                cells=cells,
                encounter_component=regions[order - 1],
            )
        )
    exits = []
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    for identity, order in [(16258, 1), (16259, 4)]:
        source = next(
            t for t in transports if t["map_id"] == 448 and t["id"] == identity
        )
        for destination in source["destinations"]:
            exits.append(
                dict(
                    source_id=identity,
                    room_order=order,
                    destination_id=destination["destination_id"],
                    destination={k: destination[k] for k in ("map_id", "x", "y", "z")},
                    native_approach_cells=[[int(source[k]) for k in ("x", "y", "z")]],
                )
            )
    topology = dict(
        asset_map_id=448,
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority="Four native arenas separated by four exact Door cells and decoded ZoneTrigger16538 activation-set frontier; explicit local progressive family encounters",
        rooms=rooms,
        doors=[],
        physical_doors=physical,
        position_trigger_gates=triggers,
        physical_exit_objects=exits,
        exploration_geometry=geometry,
        native_activation_evidence=dict(
            source_id=16538,
            activation_cells=activation,
            decoder="decode_native_interactive_activation_cells.decode",
            native_class="bEH / Re.bkT",
            semantics="Exact activation membership; local movement authorization, no native scripted mechanics claim",
        ),
    )
    if set(map(tuple, geometry["cells"])) != {
        tuple(c) for room in rooms for c in room["cells"]
    }:
        raise ValueError("Native cells were omitted")
    bosses = next(
        r["boss_references"]
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
        if r["key"] == "native:53"
    )
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    eligible = eligible_family_refs(native, roles, bosses)
    roster = progressive_family_roster(
        native, 4, bosses, capacity=8, eligible_refs=eligible
    )
    plan = base(native, route, roster["rooms"])["compiled_plan"]
    plan["progression_policy"] = roster["progression_policy"]
    p = published_geometry(448)
    combat = dict(map_id=448, cells=list(p.cells), edges=list(p.edges))
    for room, roster_room in zip(rooms, roster["rooms"]):
        cells = set(map(tuple, room["cells"]))
        section = dict(
            combat,
            cells=[c for c in combat["cells"] if tuple(c) in cells],
            edges=[
                e
                for e in combat["edges"]
                if tuple(e[0]) in cells and tuple(e[1]) in cells
            ],
        )
        quantity = sum(m["count"] for m in roster_room["monsters"])
        center = room["anchor"]
        for anchor in sorted(
            (c for c in labels if labels[c] == room["encounter_component"]),
            key=lambda c: sum((c[i] - center[i]) ** 2 for i in range(3)),
        ):
            try:
                enemy_formation(section, anchor, quantity, player_slots=6)
            except ValueError:
                continue
            room["anchor"] = list(anchor)
            break
        else:
            raise ValueError("No full-stage formation at order " + str(room["order"]))
    config = prepare_configuration(
        plan, topology, route, version=22, provenance=topology["progression_authority"]
    )
    placement = validate(config, geometry, combat, enemy_formation, entry=[0, 0, 0])
    if placement["status"] != "candidate_validated":
        raise ValueError(str(placement))
    traversal = validate_hybrid_sequence(config, placement)
    for stage in range(1, 5):
        packets(
            topology, map_id=448, instance_id=1, unlocked_room=stage, completed=False
        )
    output = Path(".runtime/local/base-susurro-zone-v22-20261010")
    output.mkdir(exist_ok=True)
    path = output / "native_dungeon_53.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    report = Path("docs/reports/dungeons/BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json")
    report.write_text(
        json.dumps(
            dict(
                scope="Source-only four native arenas; decoded activation points; no activation",
                records=[
                    dict(
                        key="native:53",
                        name=native["name_es"],
                        route=route["key"],
                        status="offline_configuration_prepared",
                        path=str(path),
                        rooms=4,
                        boss_references=bosses,
                        activation_cells=activation,
                        native_encounter_component_sizes=[438, 63, 333, 374],
                        placement_validation=placement,
                        sequence_validation=traversal,
                        progression_policy=roster["progression_policy"],
                    )
                ],
            ),
            indent=2,
        )
        + "\n"
    )
    print(report)


if __name__ == "__main__":
    main()
