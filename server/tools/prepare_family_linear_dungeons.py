"""Prepare user-authorized local family encounters on proved native linear flows.

No runtime writes. Official quantities are deliberately not inferred. Boss
identity remains evidence-driven; geometry, entry, exit and six-player placement
retain the existing validators.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def family_roster(native, room_count, boss, *, quantity=8, exclude=()):
    """Use one final boss and deterministic same-dungeon family additions."""
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    if boss not in pool or type(boss) is not int:
        raise ValueError("Identified boss is outside the native dungeon family")
    if not 1 <= quantity <= 121 or not 1 <= room_count <= 100:
        raise ValueError("Invalid local encounter capacity or room count")
    regular = sorted(set(pool) - {boss} - set(exclude))
    if not regular and room_count > 1:
        raise ValueError("No resolved non-boss family for preliminary rooms")
    rooms = []
    for order in range(1, room_count + 1):
        refs = (
            [
                regular[(order - 1 + i) % len(regular)]
                for i in range(quantity - (order == room_count))
            ]
            if regular
            else []
        )
        if order == room_count:
            refs.append(boss)
        monsters = []
        for ref in sorted(set(refs)):
            m = pool[ref]
            if not 0 < m["min_level"] <= m["max_level"]:
                raise ValueError("Native species grade bounds unavailable")
            monsters.append(
                dict(
                    name=m["name_es"],
                    ref_id=ref,
                    count=refs.count(ref),
                    role="boss" if ref == boss else "monster",
                    native_min_level=m["min_level"],
                    native_max_level=m["max_level"],
                    guide_min_level=None,
                    guide_max_level=None,
                )
            )
        rooms.append(dict(order=order, monsters=monsters, policy_applied=True))
    return dict(
        rooms=rooms,
        official=False,
        policy_mode="user_authorized_local_family_encounters",
        boss_references=[boss],
        species_pool_provenance="native dungeon raw_cno; evidence-reviewed boss; explicit local quantities",
    )


def progressive_family_roster(
    native, room_count, boss_refs, *, capacity=8, exclude=(), eligible_refs=None
):
    """Build strictly increasing native-minimum threat, with final bosses only.

    ``eligible_refs`` must come from native role metadata, never display names.
    Capacity is the common formation ceiling for every stage, so reducing a
    cramped final room also reduces earlier encounters.
    """
    if eligible_refs is None:
        raise ValueError("Native role eligibility evidence is required")
    if type(room_count) is not int or not 1 <= room_count <= 100:
        raise ValueError("Invalid room count")
    if type(capacity) is not int or not 1 <= capacity <= 121:
        raise ValueError("Invalid common formation capacity")
    bosses = set(boss_refs)
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    if not bosses or not bosses.issubset(pool) or not bosses.issubset(eligible_refs):
        raise ValueError("Final boss lacks native identity or eligible role evidence")
    if capacity < len(bosses):
        raise ValueError("Final bosses exceed common formation capacity")
    regular = sorted(
        set(pool) & set(eligible_refs) - bosses - set(exclude),
        key=lambda ref: (pool[ref]["min_level"], ref),
    )
    if not regular and room_count > 1:
        raise ValueError("No eligible ordinary family for preliminary encounters")
    rooms, metrics = [], []
    for order in range(1, room_count + 1):
        quantity = max(1, math.ceil(capacity * order / room_count))
        final = order == room_count
        quantity = max(quantity, len(bosses) if final else 1)
        ordinary_count = quantity - (len(bosses) if final else 0)
        if ordinary_count and not regular:
            ordinary_count = 0
        # Progress through increasingly strong ordinary native species. Counts
        # remain the primary progression when the family's native levels match.
        top = max(1, math.ceil(len(regular) * order / room_count)) if regular else 0
        selected = regular[:top]
        refs = [selected[-1 - (i % len(selected))] for i in range(ordinary_count)]
        if final:
            refs.extend(sorted(bosses))
        monsters = []
        for ref in sorted(set(refs)):
            m = pool[ref]
            if not 0 < m["min_level"] <= m["max_level"]:
                raise ValueError("Native species grade bounds unavailable")
            monsters.append(
                dict(
                    name=m["name_es"],
                    ref_id=ref,
                    count=refs.count(ref),
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
                "Strict native-minimum threat progression cannot fit common formation capacity"
            )
        metrics.append(
            dict(order=order, quantity=len(refs), native_minimum_threat=threat)
        )
        rooms.append(dict(order=order, monsters=monsters, policy_applied=True))
    return dict(
        rooms=rooms,
        official=False,
        policy_mode="user_authorized_progressive_native_family_encounters",
        boss_references=sorted(bosses),
        species_pool_provenance="Native dungeon family; native-role-filtered ordinary species; final-only identified bosses",
        progression_policy=dict(
            metric="sum(count * actual_spawn_level)",
            interpretation="Deterministic composition progression proxy; not certification of boss mechanics or overall fight difficulty",
            actual_spawn_level_policy="native_minimum",
            strict_increase=True,
            common_formation_capacity=capacity,
            prohibited_roles=["dominant", "archmonster", "unknown"],
            rooms=metrics,
        ),
    )


def eligible_family_refs(native, role_catalog, boss_refs):
    """Require literal native role metadata for every eligible family actor."""
    from extract_dungeon_family_bosses import role_allowed

    return {
        m["ref_id"]
        for m in native["native_species_pool"]
        if role_allowed(
            role_catalog.get(m["ref_id"]),
            final_room=True,
            allowed_boss_references=boss_refs,
        )
    }


def audit_configuration_progression(config, catalog):
    """Pure release audit of actual fixed native levels and prohibited roles."""
    from extract_dungeon_family_bosses import native_role

    violations, metrics = [], []
    plan = config.get("compiled_plan", {})
    rooms = plan.get("rooms", [])
    topology_orders = [r["order"] for r in config.get("topology", {}).get("rooms", [])]
    if [r.get("order") for r in rooms] != topology_orders or not rooms:
        violations.append("combat_room_topology_mismatch")
    if config.get("level_policy", {}).get("mode") != "native_minimum":
        violations.append("actual_spawn_level_policy_not_proved")
    selected = set(
        plan.get("roster_policy_evidence", {}).get(
            "boss_references", plan.get("boss_references", [])
        )
    )
    observed_bosses = {}
    final = max(topology_orders, default=0)
    previous = None
    for room in rooms:
        order, threat, quantity = room.get("order"), 0, 0
        if not room.get("monsters"):
            violations.append(f"room_{order}:missing_combat_roster")
        for monster in room.get("monsters", []):
            ref, count = monster.get("ref_id"), monster.get("count")
            native = catalog.get(ref)
            role = native_role(native)
            if role in ("unknown", "dominant", "archmonster"):
                violations.append(f"room_{order}:prohibited_native_role:{ref}:{role}")
            if type(count) is not int or count <= 0:
                violations.append(f"room_{order}:invalid_quantity:{ref}")
                continue
            if not native or type(native.get("min_level")) is not int:
                violations.append(f"room_{order}:native_level_unavailable:{ref}")
                continue
            if (monster.get("native_min_level"), monster.get("native_max_level")) != (
                native["min_level"],
                native["max_level"],
            ):
                violations.append(f"room_{order}:native_grade_bounds_changed:{ref}")
            if role == "boss":
                if order != final:
                    violations.append(f"room_{order}:boss_before_final:{ref}")
                if ref not in selected:
                    violations.append(f"room_{order}:unselected_native_boss:{ref}")
                observed_bosses[ref] = observed_bosses.get(ref, 0) + count
            elif monster.get("role") == "boss":
                violations.append(f"room_{order}:declared_boss_not_native_boss:{ref}")
            quantity += count
            threat += count * native["min_level"]
        metrics.append(
            dict(order=order, quantity=quantity, actual_spawn_level_sum=threat)
        )
        if room.get("monsters"):
            if previous is not None and threat <= previous:
                violations.append(
                    f"room_{order}:composition_strength_not_strictly_increasing"
                )
            previous = threat
    if not selected or set(observed_bosses) != selected:
        violations.append("identified_final_boss_set_not_present")
    if any(count != 1 for count in observed_bosses.values()):
        violations.append("final_native_boss_not_singleton")
    if (
        config.get("topology", {}).get("local_final_arena_policy")
        or config.get("topology", {}).get("local_final_region_evidence")
        or plan.get("final_arena_only")
    ):
        violations.append("simplified_final_arena_not_full_flow")
    return dict(
        status="passed" if not violations else "blocked",
        violations=violations,
        metric="sum(count * actual_spawn_level)",
        actual_spawn_level_policy="native_minimum",
        interpretation="Composition progression proxy; boss mechanics and overall difficulty not certified",
        rooms=metrics,
    )


def progressive_configuration(
    config, native, boss_refs, catalog, *, capacity=8, exclude=(), version=None
):
    """Create a fresh immutable candidate while retaining literal native topology."""
    from native_family_configuration_base import base
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )

    roster = progressive_family_roster(
        native,
        len(config["topology"]["rooms"]),
        boss_refs,
        capacity=capacity,
        exclude=exclude,
        eligible_refs=eligible_family_refs(native, catalog, boss_refs),
    )
    compiled = base(native, config["route"], roster["rooms"])["compiled_plan"]
    compiled["roster_policy_evidence"] = {
        k: roster[k]
        for k in (
            "policy_mode",
            "official",
            "boss_references",
            "species_pool_provenance",
        )
    }
    compiled["progression_policy"] = roster["progression_policy"]
    compiled["document_sha256"] = canonical_hash(compiled["rooms"])
    result = prepare_configuration(
        compiled,
        copy.deepcopy(config["topology"]),
        config["route"],
        version=version if version is not None else config["version"] + 1,
        provenance="User-authorized strictly increasing native-minimum composition proxy; native-role-filtered ordinary family; final-only actual bosses",
    )
    audit = audit_configuration_progression(result, catalog)
    if audit["status"] != "passed":
        raise ValueError(
            "Progressive policy audit failed: " + json.dumps(audit["violations"])
        )
    return result


def teleport_sequence(config, placement):
    """Prove engagement and each literal forward approach inside its own room."""
    from extract_native_door_flow import shortest_path

    topology = config["topology"]
    observations = []
    for room, positioned in zip(topology["rooms"], placement["rooms"]):
        cells = set(map(tuple, room["cells"]))
        edges = [
            e
            for e in topology["exploration_geometry"]["edges"]
            if tuple(e[0]) in cells and tuple(e[1]) in cells
        ]
        start = room["native_arrival"]
        monsters = set(map(tuple, positioned["monster_positions"]))
        engagement = None
        for target in sorted(monsters):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                approach = (target[0] + dx, target[1] + dy, target[2])
                path = shortest_path(edges, start, approach, monsters)
                if path:
                    engagement = dict(
                        target=list(target), approach=list(approach), path=path
                    )
                    break
            if engagement:
                break
        if engagement is None:
            raise ValueError(f"Room {room['order']} cannot engage from native arrival")
        if room["order"] < len(topology["rooms"]):
            ends = [
                d
                for d in topology["doors"]
                if d["source_room"] == room["order"]
                and d["destination_room"] == room["order"] + 1
            ]
        else:
            ends = [
                e
                for e in topology["physical_exit_objects"]
                if e["room_order"] == room["order"]
            ]
        paths = [
            shortest_path(edges, start, p)
            for end in ends
            for p in end["native_approach_cells"]
        ]
        if not any(paths) and not (
            room["order"] == len(topology["rooms"])
            and topology.get("completed_exit_witness")
        ):
            raise ValueError(
                f"Room {room['order']} has no directed path to next transport or exit"
            )
        observations.append(
            dict(
                order=room["order"],
                engagement_witness=engagement,
                transport_paths=[p for p in paths if p],
            )
        )
    return dict(
        status="offline_exploration_sequence_validated",
        rooms=observations,
        completed_exit_witness=topology.get("completed_exit_witness"),
    )


def main():
    from build_physical_dungeon_configuration import build as physical_build
    from build_native_teleport_configuration import build as teleport_build
    from prepare_native_physical_candidates import bind_exits
    from validate_dungeon_flow_rosters import validate
    from validate_prepared_physical_flows import validate as sequence
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boss-evidence", type=Path, action="append", default=[])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".runtime/local/family-linear-candidates-20261010"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/reports/dungeons/FAMILY-LINEAR-CANDIDATES-20261010.json"),
    )
    args = parser.parse_args()
    load = lambda p: json.loads(Path(p).read_text())
    native = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    active = {
        r["route"]
        for r in load(
            "docs/reports/dungeons/MAXIMUM-ACTIVATION-READBACK-20261010.json"
        )["records"]
    }
    flows = (
        load(".runtime/local/all-native-dungeon-flows.json")["records"]
        + load("docs/reports/dungeons/AUTOMATIC-TELEPORT-FLOW.json")["records"]
    )
    bases = {
        r["route"]["key"]: r
        for r in load(
            ".runtime/local/methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
        )["configurations"]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    identities = {}
    for path in [
        Path("docs/reports/dungeons/EXACT-BOSS-IDENTITY-EVIDENCE-20261010.json"),
        *args.boss_evidence,
    ]:
        for row in load(path)["records"]:
            if len(row.get("boss_references", [])) == 1:
                identities[row["key"]] = row
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for flow in flows:
        route = flow["route"]["key"]
        n = native[flow["key"]]
        if route in active or flow["status"] not in (
            "physical_linear_chain_proved",
            "native_teleport_linear_chain_proved",
        ):
            continue
        if (
            n["native"]["type"]
            not in (
                "DUNGEON_2_ROOMS",
                "DUNGEON_3_ROOMS",
                "DUNGEON_4_ROOMS",
                "DUNGEON_3_PLAYERS",
            )
            or "néo" in n["native"]["name_fr"].lower()
        ):
            continue
        row = dict(
            key=n["key"], name=n["name_es"], route=route, flow_status=flow["status"]
        )
        try:
            evidence = identities.get(n["key"], {})
            bosses = set(evidence.get("boss_references", [])) or {
                m["ref_id"]
                for g in n["guides"]
                for r in g["rooms"]
                for m in r["monsters"]
                if m.get("role") == "boss" and m.get("ref_id")
            }
            if len(bosses) != 1:
                raise ValueError(
                    "Exactly one actual family boss still needs identity evidence"
                )
            boss = next(iter(bosses))
            topology = load(flow["candidate_topology_path"])
            geometry = load(
                f'.runtime/local/all-native-dungeon-exploration/exploration-{flow["route"]["start_map_id"]}.json'
            )
            prepared = published_geometry(topology["asset_map_id"])
            combat = dict(
                map_id=prepared.map_id,
                cells=list(prepared.cells),
                edges=list(prepared.edges),
            )
            exclude = evidence.get("excluded_nonfamily_references", [])
            failures = []
            for quantity in (8, 6, 4, 3, 2, 1):
                roster = family_roster(
                    n, len(topology["rooms"]), boss, quantity=quantity, exclude=exclude
                )
                if route in bases:
                    base = bases[route]
                else:
                    from native_family_configuration_base import base as native_base

                    base = native_base(n, flow["route"], roster["rooms"])
                if flow["status"] == "physical_linear_chain_proved":
                    exits = bind_exits(
                        copy.deepcopy(topology), base["route"], transports
                    )
                    config = physical_build(
                        base,
                        geometry,
                        roster,
                        [
                            o
                            for o in n["native_objects"]
                            if o["type"] == "Door"
                            and o["map_id"] == topology["asset_map_id"]
                        ],
                        flow["entry"],
                        flow["directed_physical_flows"][0]["exit"],
                        exits,
                        4,
                    )
                else:
                    config = teleport_build(
                        base, topology, roster, transports, version=4
                    )
                placement = validate(
                    config,
                    config["topology"]["exploration_geometry"],
                    combat,
                    enemy_formation,
                    entry=flow["entry"],
                )
                if placement["status"] == "candidate_validated":
                    try:
                        traversal = (
                            sequence(
                                config, flow["directed_physical_flows"][0], placement
                            )
                            if flow["status"] == "physical_linear_chain_proved"
                            else teleport_sequence(config, placement)
                        )
                    except ValueError as error:
                        failures.append(dict(quantity=quantity, reasons=[str(error)]))
                        continue
                    break
                failures.append(dict(quantity=quantity, reasons=placement["reasons"]))
            else:
                raise ValueError(
                    "No six-player native formation: " + json.dumps(failures)
                )
            row.update(
                boss_references=[boss],
                boss_identity_evidence=evidence or "existing reviewed guide boss role",
                placement_validation=placement,
                local_quantity=quantity,
                formation_reductions=failures,
            )
            row["sequence_validation"] = traversal
            path = args.output_dir / (route + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=len(topology["rooms"]),
                boss_mechanics="not certified",
                scope="user-authorized family approximation; not official composition",
            )
        except (ValueError, KeyError, StopIteration) as error:
            row.update(status="blocked", reason=str(error) or type(error).__name__)
        records.append(row)
    args.report.write_text(
        json.dumps(
            dict(
                scope="Source-only local family preparation; no runtime writes",
                records=records,
            ),
            indent=2,
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
        )
    )


if __name__ == "__main__":
    main()
