"""Prepare real multistage family encounters using combined native topology.

Source-only versioned preparation. No native walk edges or destinations change.
Optional disabled sources require exact native hashes and an explicit reason.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_hybrid_native_dungeon_flow import extract, main_spine
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog, role_allowed
from native_family_configuration_base import base
from prepare_milubo_mixed_configuration import validate_hybrid_sequence
from validate_dungeon_flow_rosters import validate

TARGETS = (124, 141, 63, 150, 145, 136, 151)
DISABLED = {
    49: {
        14676: "Classic native transport source is in a component unreachable from the selected dungeon entry",
        14675: "Classic native return source is in a component unreachable from the selected dungeon entry",
        16172: "Classic native return source is in an unreachable optional component",
    },
    63: {
        20084: "Optional secret requires a native item criterion; outside the mandatory three-room dungeon route",
        20082: "Return from the disabled optional item-gated secret; outside the mandatory dungeon route",
    },
    150: {
        31459: "Alternate foreign exterior exit map1210 is outside the reviewed map1137 entry-return contract"
    },
    136: {
        35990: "Alternative mine entry shortcut is outside the reviewed four-room exterior route; preserve shared boss progression",
        35991: "Alternative mine return shortcut is outside the reviewed exterior route; nonadjacent-stage travel not authorized",
    },
    151: {
        24166: "Native source is in a one-way component unreachable from the reviewed mandatory dungeon route"
    },
}
REVIEWED = {
    141: (
        {4730: 2, 4729: 2, 4728: 2},
        {4730: 2, 4729: 3, 4728: 2},
        {4730: 3, 4729: 3, 4728: 2},
        {4731: 1, 4730: 3, 4729: 2, 4728: 2},
    ),
    151: (
        {4911: 3, 4909: 2, 4912: 2},
        {4911: 2, 4909: 3, 4912: 3},
        {4913: 1, 4911: 2, 4909: 3, 4912: 2},
    ),
    136: (
        {4511: 2, 4510: 1, 4512: 3},
        {4511: 2, 4510: 2, 4512: 3},
        {4511: 3, 4510: 2, 4512: 3},
        {4512: 3, 4511: 2, 4510: 2, 4519: 1},
    ),
}


def reviewed_roster(native, counts, bosses, roles):
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    rooms = []
    metrics = []
    for order, refs in enumerate(counts, 1):
        monsters = []
        for ref, count in sorted(refs.items()):
            if not role_allowed(
                roles.get(ref),
                final_room=order == len(counts),
                allowed_boss_references=bosses,
            ):
                raise ValueError("Reviewed native role is forbidden")
            m = pool[ref]
            monsters.append(
                dict(
                    name=m["name_es"],
                    ref_id=ref,
                    count=count,
                    role="boss" if ref in bosses else "monster",
                    native_min_level=m["min_level"],
                    native_max_level=m["max_level"],
                    guide_min_level=None,
                    guide_max_level=None,
                )
            )
        threat = sum(m["count"] * m["native_min_level"] for m in monsters)
        if metrics and threat <= metrics[-1]["native_minimum_threat"]:
            raise ValueError(
                "Reviewed composition does not increase actual native-minimum threat"
            )
        metrics.append(
            dict(order=order, quantity=sum(refs.values()), native_minimum_threat=threat)
        )
        rooms.append(dict(order=order, monsters=monsters))
    return dict(
        rooms=rooms,
        progression_policy=dict(
            metric="sum(count * actual_spawn_level)",
            actual_spawn_level_policy="native_minimum",
            strict_increase=True,
            rooms=metrics,
        ),
        reviewed_guide=True,
    )


def topology_for(
    graph,
    spine,
    geometry,
    sources,
    entry,
    *,
    allow_nonadjacent=False,
    arrival_source_ids=None,
    allow_completed_entry_exit=False,
    allow_foreign_exit=False,
):
    from wakfu_server.dungeon_runtime_config import canonical_hash

    mapping = spine["stage_by_region"]
    components = {r["region"]: r["cells"] for r in graph["components"]}
    sources = {s["id"]: s for s in sources}
    rooms = []
    for stage, arena in enumerate(spine["encounter_regions"], 1):
        arena_cells = list(map(tuple, components[arena]))
        n = len(arena_cells)
        sx = sum(p[0] for p in arena_cells)
        sy = sum(p[1] for p in arena_cells)
        anchor = min(
            arena_cells, key=lambda p: ((p[0] * n - sx) ** 2 + (p[1] * n - sy) ** 2, p)
        )
        incoming = [
            l
            for l in graph["links"]
            if (
                mapping.get(l["source_region"]) == stage - 1
                or (
                    allow_nonadjacent and mapping.get(l["source_region"], stage) < stage
                )
            )
            and mapping.get(l["destination_region"]) == stage
        ]
        if arrival_source_ids and stage in arrival_source_ids:
            incoming = [
                l for l in incoming if l["source_id"] == arrival_source_ids[stage]
            ]
        if stage == 1:
            arrival = list(entry)
        elif len(incoming) != 1:
            raise ValueError("Mixed stage has no unique literal forward gate/transport")
        elif incoming[0]["kind"] == "native_transport":
            arrival = incoming[0]["destination_position"]
        else:
            gate = incoming[0]
            target_cells = set(map(tuple, components[gate["destination_region"]]))
            candidates = [
                b
                for a, b in geometry["edges"]
                if tuple(a) == tuple(gate["position"]) and tuple(b) in target_cells
            ]
            if not candidates:
                raise ValueError(
                    "Native physical gate has no directed far-side arrival"
                )
            arrival = min(candidates)
        rooms.append(
            dict(
                order=stage,
                anchor=list(anchor),
                native_arrival=list(arrival),
                cells=[
                    p
                    for region in sorted(mapping)
                    if mapping[region] == stage
                    for p in components[region]
                ],
                encounter_component=arena,
            )
        )
    physical = []
    doors = []
    seen = set()
    for link in graph["links"]:
        a = mapping.get(link["source_region"])
        b = mapping.get(link["destination_region"])
        if a is None or b is None:
            continue
        if abs(a - b) > 1 and not allow_nonadjacent:
            raise ValueError("Native link would skip encounter stages")
        if link["kind"].startswith("physical"):
            if link["source_id"] in seen:
                continue
            seen.add(link["source_id"])
            physical.append(
                dict(
                    source_id=link["source_id"],
                    position=link["position"],
                    source_room=min(a, b),
                    destination_room=max(a, b),
                    local_annex_gate=a == b,
                )
            )
        else:
            doors.append(
                dict(
                    source_id=link["source_id"],
                    source_room=a,
                    destination_room=b,
                    destination_id=link["destination_id"],
                    source_position=link["source_position"],
                    native_approach_cells=link["native_approach_cells"],
                    destination_position=link["destination_position"],
                    same_stage=a == b,
                )
            )
    for binding in doors:
        if abs(binding["source_room"] - binding["destination_room"]) > 1:
            binding["progression_gate_room"] = (
                max(binding["source_room"], binding["destination_room"]) - 1
            )
    exits = [
        dict(
            source_id=e["source_id"],
            room_order=mapping[e["source_region"]],
            destination_id=e["destination_id"],
            destination=dict(
                map_id=e["destination_map_id"],
                **dict(zip(("x", "y", "z"), e["destination_position"])),
            ),
            native_approach_cells=e["native_approach_cells"],
        )
        for e in graph["exits"]
        if (e["matches_entry_exterior"] or allow_foreign_exit)
        and e["source_region"] in mapping
    ]
    if len([e for e in exits if e["room_order"] == 1]) != 1 or (
        not allow_completed_entry_exit
        and len([e for e in exits if e["room_order"] == len(rooms)]) != 1
    ):
        raise ValueError("Mixed route needs unique exact native entry and final exits")
    return dict(
        asset_map_id=geometry["map_id"],
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority=spine["policy"],
        rooms=rooms,
        doors=doors,
        physical_doors=physical,
        physical_exit_objects=exits,
        exploration_geometry=geometry,
        local_spine_evidence=spine,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=int, nargs="+", default=list(TARGETS))
    parser.add_argument("--version", type=int, default=7)
    args = parser.parse_args()
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_native_flow import packets

    load = lambda p: json.loads(Path(p).read_text())
    inventory = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    flows = {
        r["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    bosses = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    output = Path(f".runtime/local/hybrid-native-full-room-v{args.version}-20261010")
    output.mkdir(exist_ok=True)
    records = []
    for identity in args.targets:
        key = f"native:{identity}"
        native = inventory[key]
        flow = flows[key]
        route = flow["route"]
        mid = route["start_map_id"]
        row = dict(key=key, name=native["name_es"], route=route["key"])
        attempts = []
        try:
            geometry = load(
                f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json"
            )
            sources = [s for s in transports if s["map_id"] == mid]
            disabled = DISABLED.get(identity, {})
            graph = extract(
                geometry,
                native["native_objects"],
                [s for s in sources if s["id"] not in disabled],
                flow["entry"],
                route["entry_map_id"],
            )
            count = {"DUNGEON_3_ROOMS": 3, "DUNGEON_4_ROOMS": 4, "DUNGEON_2_ROOMS": 2}[
                native["native"]["type"]
            ]
            spine = main_spine(graph, count)
            topology = topology_for(graph, spine, geometry, sources, flow["entry"])
            topology["unresolved_native_elements"] = graph["unresolved"]
            topology["disabled_native_sources"] = [
                dict(
                    source_id=source["id"],
                    reason=disabled[source["id"]],
                    source_sha256=canonical_hash(source),
                )
                for source in sources
                if source["id"] in disabled
            ]
            identified = bosses[key]["boss_references"]
            eligible = eligible_family_refs(native, roles, identified)
            published = published_geometry(mid)
            combat = dict(
                map_id=mid, cells=list(published.cells), edges=list(published.edges)
            )
            quantities = (8,) if identity in REVIEWED else (8, 6, 4, 3, 2, 1)
            for capacity in quantities:
                try:
                    roster = (
                        reviewed_roster(native, REVIEWED[identity], identified, roles)
                        if identity in REVIEWED
                        else progressive_family_roster(
                            native,
                            count,
                            identified,
                            capacity=capacity,
                            exclude=bosses[key].get(
                                "excluded_nonfamily_references", []
                            ),
                            eligible_refs=eligible,
                        )
                    )
                    plan = base(native, route, roster["rooms"])["compiled_plan"]
                    plan.update(
                        progression_policy=roster["progression_policy"],
                        policy_mode="reviewed_guide_native_mixed_rooms"
                        if identity in REVIEWED
                        else "user_authorized_progressive_native_mixed_family_rooms",
                        roster_policy_evidence=dict(
                            boss_references=identified,
                            reviewed_guide=identity in REVIEWED,
                            local_final_adjustment="Conohos final encounter adds one ordinary 4512 to preserve requested increasing composition; original guide final has seven actors"
                            if identity == 136
                            else None,
                            initial_summons=False,
                            native_roles_required=True,
                        ),
                    )
                    # Deterministic centroid anchors, with bounded native alternatives
                    # in the actual encounter component when a formation crosses an edge.
                    proposal = copy.deepcopy(topology)
                    validation_geometry = copy.deepcopy(geometry)
                    validation_geometry["edges"] += [
                        [p, d["destination_position"]]
                        for d in proposal["doors"]
                        for p in d["native_approach_cells"]
                    ]
                    for adjustment in range(25):
                        config = prepare_configuration(
                            plan,
                            proposal,
                            route,
                            version=args.version,
                            provenance=spine["policy"]
                            + "; exact guide composition where independently reviewed, otherwise explicit progressive local family; no dominant/archmonster/initial summons",
                        )
                        placement = validate(
                            config,
                            validation_geometry,
                            combat,
                            enemy_formation,
                            entry=flow["entry"],
                        )
                        if placement["status"] == "candidate_validated":
                            break
                        bad = [
                            r["order"]
                            for r in placement["rooms"]
                            if r.get("reasons")
                            or r.get("status") not in (None, "candidate_validated")
                        ]
                        if not bad:
                            bad = list(range(1, count + 1))
                        for order in bad:
                            room = proposal["rooms"][order - 1]
                            region = room["encounter_component"]
                            center = topology["rooms"][order - 1]["anchor"]
                            available = [
                                tuple(p)
                                for r in graph["components"]
                                if r["region"] == region
                                for p in r["cells"]
                            ]
                            alternatives = sorted(
                                available,
                                key=lambda p: (
                                    sum((p[i] - center[i]) ** 2 for i in range(2)),
                                    p,
                                ),
                            )
                            room["anchor"] = list(
                                alternatives[min(adjustment + 1, len(alternatives) - 1)]
                            )
                    else:
                        raise ValueError(
                            "No bounded native formation anchors: "
                            + json.dumps(placement["reasons"])
                        )
                    sequence = validate_hybrid_sequence(config, placement)
                    hydration = [
                        dict(
                            stage=stage,
                            packet_count=len(
                                packets(
                                    config["topology"],
                                    map_id=mid,
                                    instance_id=1,
                                    unlocked_room=stage,
                                    completed=False,
                                )
                            ),
                        )
                        for stage in range(1, count + 1)
                    ]
                    packets(
                        config["topology"],
                        map_id=mid,
                        instance_id=1,
                        unlocked_room=count,
                        completed=True,
                    )
                    break
                except ValueError as error:
                    attempts.append(dict(capacity=capacity, reason=str(error)))
            else:
                raise ValueError(
                    "No validated full-room mixed candidate: " + json.dumps(attempts)
                )
            path = output / (route["key"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=count,
                boss_references=identified,
                progression_policy=roster["progression_policy"],
                placement_validation=placement,
                sequence_validation=sequence,
                object_state_checks=hydration,
                disabled_native_sources=topology["disabled_native_sources"],
                unresolved_native_elements=graph["unresolved"],
                requires_server_deployment=True,
                attempts=attempts,
            )
        except (ValueError, KeyError) as error:
            row.update(status="blocked", reason=str(error), attempts=attempts)
        records.append(row)
    report = Path(
        f"docs/reports/dungeons/HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V{args.version}-20261010.json"
    )
    report.write_text(
        json.dumps(
            dict(
                scope="Source-only actual native room counts; combined literal gates/transports; no runtime writes",
                records=records,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(
        json.dumps(
            [
                dict(name=r["name"], status=r["status"], reason=r.get("reason"))
                for r in records
            ],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
