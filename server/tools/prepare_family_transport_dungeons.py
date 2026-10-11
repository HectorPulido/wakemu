"""Prepare bounded local family encounters on literal native transport evidence.

No runtime writes. Unreachable optional transports and mutually exclusive Neo
alternatives can be excluded, but reachable missing endpoints remain blockers.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_family_configuration_base import base
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
    teleport_sequence,
)
from extract_dungeon_family_bosses import load_role_catalog
from prepare_open_boss_dungeons import prepare as prepare_arena
from extract_native_teleport_flow import extract, topology_for
from build_native_teleport_configuration import build
from validate_dungeon_flow_rosters import validate


def native_spines(flow):
    """Enumerate deterministic simple paths; side branches remain unconfigured."""
    paths = []

    def visit(chain, stages):
        paths.append(
            dict(
                flow,
                status="native_teleport_linear_chain_proved",
                region_chain=chain,
                stages=stages,
            )
        )
        current = (
            flow["entry"]
            if not stages
            else stages[-1]["alternatives"][0]["transport"]["destination_position"]
        )
        for link in sorted(
            flow["native_links"],
            key=lambda l: (l["destination_region"], l["source_id"]),
        ):
            if (
                link["source_region"] != chain[-1]
                or link["destination_region"] in chain
            ):
                continue
            if (
                link["requires_item"]
                or link["requires_kamas"]
                or link["instance_template"] >= 0
                or link["criterion"].strip() not in ("", "not IsNeoServer()")
            ):
                continue
            # Directed reachability is revalidated by the full stage validator.
            stage = dict(
                source_region=chain[-1],
                destination_region=link["destination_region"],
                alternatives=[dict(transport=link)],
            )
            visit(chain + [link["destination_region"]], stages + [stage])

    visit([flow["region_chain"][0]], [])
    return sorted(
        [p for p in paths if len(p["region_chain"]) > 1],
        key=lambda p: (-len(p["region_chain"]), p["region_chain"]),
    )


def classic_sources(transports, map_id):
    """Exclude only exact native mutually exclusive Neo-server alternatives."""
    sources = []
    for original in transports:
        if original["map_id"] != map_id:
            continue
        source = copy.deepcopy(original)
        source["destinations"] = [
            d
            for d in source["destinations"]
            if d.get("criterion", "").strip() != "IsNeoServer()"
        ]
        if source["destinations"]:
            sources.append(source)
    return sources


def optional_outside_component(sources, cells):
    """Prove that every same-map source is outside the selected entry terrain."""
    selected = set(map(tuple, cells))
    omitted = []
    for source in sources:
        internal = [
            d for d in source["destinations"] if d["map_id"] == source["map_id"]
        ]
        if not internal:
            continue
        approaches = {
            tuple(p[k] for k in ("x", "y", "z"))
            for p in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(tuple(source[k] for k in ("x", "y", "z")))
        if approaches & selected:
            raise ValueError(
                f"Reachable internal transport {source['id']} cannot be erased by local arena policy"
            )
        omitted.append(source["id"])
    return sorted(omitted)


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda p: json.loads(Path(p).read_text())
    inventory = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    bosses = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    physical = {
        r["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    flows = load("docs/reports/dungeons/AUTOMATIC-TELEPORT-FLOW.json")["records"]
    all_sources = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    output = Path(".runtime/local/family-transport-progressive-v2-20261010")
    output.mkdir(exist_ok=True)
    role_catalog = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    records = []
    # Transport records are authoritative for all twelve ordinary internal cases.
    for original in flows:
        key = original["key"]
        native = inventory[key]
        if key not in bosses or native["native"]["type"] not in (
            "DUNGEON_2_ROOMS",
            "DUNGEON_3_ROOMS",
            "DUNGEON_4_ROOMS",
            "DUNGEON_3_PLAYERS",
        ):
            continue
        if original["status"] not in (
            "unresolved_native_transport_endpoints",
            "transports_within_same_physical_region",
            "branched_native_transport_graph",
        ):
            continue
        row = dict(
            key=key,
            name=native["name_es"],
            route=original["route"]["key"],
            original_status=original["status"],
        )
        try:
            evidence = bosses[key]
            identified = evidence["boss_references"]
            eligible = eligible_family_refs(native, role_catalog, identified)
            if not identified:
                raise ValueError("Identified native family boss required")
            mid = original["map_id"]
            geometry = load(
                f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json"
            )
            sources = classic_sources(all_sources, mid)
            objects = [o for o in native["native_objects"] if o["map_id"] == mid]
            internal = [
                dict(
                    s, destinations=[d for d in s["destinations"] if d["map_id"] == mid]
                )
                for s in sources
            ]
            internal = [s for s in internal if s["destinations"]]
            revised = extract(geometry, objects, original["entry"], internal)
            p = published_geometry(mid)
            combat = dict(map_id=mid, cells=list(p.cells), edges=list(p.edges))
            failures = []
            if revised[
                "status"
            ] == "physical_sequence_with_unverified_criteria" and all(
                l["criterion"].strip() in ("", "not IsNeoServer()")
                for l in revised["native_links"]
            ):
                revised["status"] = "native_teleport_linear_chain_proved"
            if revised["status"] in (
                "native_teleport_linear_chain_proved",
                "branched_native_transport_graph",
            ):
                spine_failures = []
                spine_options = (
                    native_spines(revised)
                    if revised["status"] == "branched_native_transport_graph"
                    else [revised]
                )
                for spine in spine_options:
                    try:
                        candidate_topology = topology_for(
                            geometry, objects, original["entry"], internal, spine
                        )
                        from prepare_native_physical_candidates import bind_exits

                        bind_exits(candidate_topology, original["route"], sources)
                        topology = candidate_topology
                        row["local_spine_regions"] = spine["region_chain"]
                        row["excluded_optional_native_links"] = [
                            l
                            for l in revised["native_links"]
                            if l["source_region"] not in spine["region_chain"]
                            or l["destination_region"] not in spine["region_chain"]
                            or abs(
                                spine["region_chain"].index(l["source_region"])
                                - spine["region_chain"].index(l["destination_region"])
                            )
                            != 1
                        ]
                        break
                    except ValueError as error:
                        spine_failures.append(str(error))
                else:
                    raise ValueError(
                        "No native spine has completed-run exit: "
                        + json.dumps(sorted(set(spine_failures)))
                    )
                for quantity in (8, 6, 4, 3, 2, 1):
                    try:
                        roster = progressive_family_roster(
                            native,
                            len(topology["rooms"]),
                            identified,
                            capacity=quantity,
                            exclude=evidence.get("excluded_nonfamily_references", []),
                            eligible_refs=eligible,
                        )
                        compiled = base(native, original["route"], roster["rooms"])
                        compiled["compiled_plan"]["progression_policy"] = roster[
                            "progression_policy"
                        ]
                        config = build(compiled, topology, roster, sources, version=5)
                        placement = validate(
                            config,
                            config["topology"]["exploration_geometry"],
                            combat,
                            enemy_formation,
                            entry=original["entry"],
                        )
                        if placement["status"] != "candidate_validated":
                            raise ValueError(str(placement["reasons"]))
                        traversal = teleport_sequence(config, placement)
                        break
                    except ValueError as error:
                        failures.append(dict(quantity=quantity, reason=str(error)))
                else:
                    raise ValueError(
                        "No validated native linear configuration: "
                        + json.dumps(failures)
                    )
                row[
                    "local_policy"
                ] = "Local native transport spine; exact IsNeoServer alternatives excluded; optional side branches excluded; family encounters approximate"
            elif revised["status"] == "transports_within_same_physical_region":
                flow = copy.deepcopy(physical[key])
                omitted = optional_outside_component(
                    sources, flow["first_encounter_reachable_cells"]
                )
                flow.update(
                    status="open_geometry_no_separator", native_internal_teleports=[]
                )
                arena_native = copy.deepcopy(native)
                arena_native["guides"] = []
                for quantity in (8, 6, 4, 3, 2, 1):
                    try:
                        roster = progressive_family_roster(
                            native,
                            1,
                            identified,
                            capacity=quantity,
                            exclude=evidence.get("excluded_nonfamily_references", []),
                            eligible_refs=eligible,
                        )
                        compiled = base(native, original["route"], roster["rooms"])
                        compiled["compiled_plan"]["progression_policy"] = roster[
                            "progression_policy"
                        ]
                        compiled["version"] = 4
                        config, placement, traversal = prepare_arena(
                            arena_native,
                            flow,
                            compiled,
                            geometry,
                            sources,
                            combat,
                            enemy_formation,
                            reviewed_roster=roster["rooms"][0]["monsters"],
                        )
                        break
                    except ValueError as error:
                        failures.append(dict(quantity=quantity, reason=str(error)))
                else:
                    raise ValueError(
                        "No validated native entry-component arena: "
                        + json.dumps(failures)
                    )
                row.update(
                    local_policy="One local family encounter on proved entry component; optional disconnected internal transports are not dungeon stages; official room count not claimed",
                    excluded_unreachable_transport_ids=omitted,
                )
            else:
                row["native_transport_evidence"] = revised
                raise ValueError(
                    "Literal transport graph needs ordered reachable stages and native completed-run exit: "
                    + revised["status"]
                )
            config["compiled_plan"]["roster_policy_evidence"] = evidence
            config["compiled_plan"][
                "policy_mode"
            ] = "user_authorized_native_family_transport_encounters"
            config["provenance"] = row["local_policy"]
            from wakfu_server.dungeon_runtime_config import canonical_hash

            config["evidence_hashes"]["plan"] = canonical_hash(config["compiled_plan"])
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                progression_policy=roster["progression_policy"],
                collapsed_single_encounter=len(config["topology"]["rooms"]) == 1,
                path=str(path),
                rooms=len(config["topology"]["rooms"]),
                boss_references=identified,
                local_quantity=quantity,
                formation_reductions=failures,
                placement_validation=placement,
                sequence_validation=traversal,
            )
        except (ValueError, KeyError, FileNotFoundError) as error:
            row.update(status="blocked", reason=str(error))
        records.append(row)
    for mixed in load(
        "docs/reports/dungeons/MIXED-NATIVE-TRANSPORT-AUDIT-20261010.json"
    )["records"]:
        if mixed["key"] in ("native:145", "native:136", "native:151"):
            records.append(
                dict(
                    mixed,
                    status="blocked",
                    reason="Mixed physical gates and native transport endpoints need supported exact room bindings; local family roster cannot repair traversal",
                )
            )
    target = Path("docs/reports/dungeons/FAMILY-TRANSPORT-PROGRESSIVE-V2-20261010.json")
    target.write_text(
        json.dumps(
            dict(
                scope="Source-only; literal transport evidence; local family encounters; no runtime activation",
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
