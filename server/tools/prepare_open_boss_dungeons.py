"""Prepare singleton native ultimate-boss arenas without inventing door progression.

Read-only preparation. Native ULTIMATE_BOSS plus a singleton species pool is
identity authority; one initial boss is an explicit local encounter policy.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate, reachable
from validate_prepared_physical_flows import validate as validate_sequence


def prepare(
    native, flow, base, geometry, transports, combat, formation, *, reviewed_roster=None
):
    from wakfu_server.dungeon_physical_doors import POLICY
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )

    if reviewed_roster is None and (
        native["native"]["type"] != "ULTIMATE_BOSS"
        or len(native["native_species_pool"]) != 1
    ):
        raise ValueError(
            "Requires native ultimate-boss type and exactly one native species"
        )
    if flow["status"] != "open_geometry_no_separator" or flow.get(
        "native_internal_teleports"
    ):
        raise ValueError("Requires open arena without unproved internal transports")
    if any(len(g["rooms"]) > 1 for g in native.get("guides", [])):
        raise ValueError(
            "Reviewed guide has preliminary encounters; singleton arena cannot erase them"
        )
    boss = native["native_species_pool"][0]
    cells = set(map(tuple, flow["first_encounter_reachable_cells"]))
    entry = tuple(flow["entry"])
    if entry not in cells or not cells:
        raise ValueError("Native entry is outside the reachable encounter component")
    # Retain only proven first-encounter terrain and its directed edges.
    geometry = copy.deepcopy(geometry)
    geometry["cells"] = [list(c) for c in sorted(cells)]
    geometry["edges"] = [
        e for e in geometry["edges"] if tuple(e[0]) in cells and tuple(e[1]) in cells
    ]
    if reachable(geometry, entry) != cells:
        raise ValueError(
            "Encounter component is not directed-reachable from native arrival"
        )
    topology = dict(
        asset_map_id=geometry["map_id"],
        policy=POLICY,
        official_room_order_verified=False,
        progression_authority=(
            "Explicit local singleton native ultimate-boss arena"
            if reviewed_roster is None
            else "Reviewed single encounter; known quantities preserved; unknown boss quantity defaults to one"
        ),
        rooms=[dict(order=1, anchor=list(entry), cells=geometry["cells"])],
        doors=[],
        physical_doors=[],
        exploration_geometry=geometry,
    )
    try:
        exits = bind_exits(topology, flow["route"], transports)
    except ValueError:
        # Multiple independently valid native exits are safe aliases only when
        # every one has the exact same exterior destination.
        aliases = []
        for source in transports:
            try:
                aliases.extend(bind_exits(topology, flow["route"], [source]))
            except ValueError:
                continue
        destinations = {
            tuple(e["destination"][k] for k in ("map_id", "x", "y", "z"))
            for e in aliases
        }
        if len(aliases) < 2 or len(destinations) != 1:
            raise ValueError("No unique native exterior destination from arena")
        exits = [min(aliases, key=lambda e: e["source_id"])]
        topology["equivalent_native_exit_aliases"] = aliases
    topology["physical_exit_objects"] = exits
    plan = copy.deepcopy(base["compiled_plan"])
    monster = dict(
        name=boss["name_es"],
        ref_id=boss["ref_id"],
        count=1,
        role="boss",
        native_min_level=boss["min_level"],
        native_max_level=boss["max_level"],
        guide_min_level=None,
        guide_max_level=None,
    )
    monsters = reviewed_roster if reviewed_roster is not None else [monster]
    bosses = [m["ref_id"] for m in monsters if m["role"] == "boss"]
    plan.update(
        rooms=[dict(order=1, monsters=monsters, diagnostics=[])],
        policy_mode=(
            "explicit_local_singleton_native_ultimate_boss"
            if reviewed_roster is None
            else "explicit_local_reviewed_single_encounter"
        ),
        official=False,
        roster_ready=True,
        diagnostics=[],
        boss_references=bosses,
        roster_policy_evidence=dict(
            boss_references=bosses,
            species_pool_provenance=(
                "Installed native ULTIMATE_BOSS singleton species pool"
                if reviewed_roster is None
                else "Reviewed one-encounter guide joined to installed native species pool"
            ),
        ),
    )
    plan["document_sha256"] = canonical_hash(plan["rooms"])
    # Search deterministic native anchors; validate complete formation and six players.
    failures = []
    for anchor in sorted(
        cells, key=lambda c: (sum((c[i] - entry[i]) ** 2 for i in range(2)), c)
    ):
        topology["rooms"][0]["anchor"] = list(anchor)
        placement = validate(
            dict(topology=topology, compiled_plan=plan),
            geometry,
            combat,
            formation,
            entry=entry,
        )
        if placement["status"] == "candidate_validated":
            break
        failures.append(placement.get("reasons", []))
    else:
        raise ValueError(
            "No same-component boss formation with six player slots: "
            + str(failures[:3])
        )
    config = prepare_configuration(
        plan,
        topology,
        base["route"],
        version=base["version"] + 1,
        provenance=(
            "Native singleton ultimate-boss identity; local one-boss encounter; directed entry/engagement/native exterior exit proved; boss mechanics unverified"
            if reviewed_roster is None
            else "Reviewed single encounter preserving all resolved species and known counts; unknown boss count uses local singleton policy; directed entry/engagement/native exit proved; mechanics unverified"
        ),
    )
    sequence = validate_sequence(config, dict(entry=list(entry)), placement)
    return config, placement, sequence


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    root = Path(".runtime/local")
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    flows = json.loads((root / "all-native-dungeon-flows.json").read_text())["records"]
    bases = json.loads(
        (
            root / "methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
        ).read_text()
    )["configurations"]
    transports = json.loads(
        (
            root
            / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    output = root / "open-boss-configurations"
    output.mkdir(exist_ok=True)
    records = []
    for flow in flows:
        if flow["status"] != "open_geometry_no_separator":
            continue
        row = dict(key=flow["key"], route=flow["route"]["key"], name=flow["name"])
        try:
            native = next(n for n in inventory if n["key"] == flow["key"])
            if native["native"]["type"] != "ULTIMATE_BOSS":
                raise ValueError(
                    "Open multi-species/arcade arena needs reviewed initial encounter and progression"
                )
            base = next((b for b in bases if b["route"]["key"] == row["route"]), None)
            if base is None:
                raise ValueError("Missing compiled route configuration")
            mid = flow["route"]["start_map_id"]
            geometry = json.loads(
                (
                    root / f"all-native-dungeon-exploration/exploration-{mid}.json"
                ).read_text()
            )
            published = published_geometry(mid)
            combat = dict(
                map_id=mid, cells=list(published.cells), edges=list(published.edges)
            )
            config, placement, sequence = prepare(
                native, flow, base, geometry, transports, combat, enemy_formation
            )
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=1,
                placement_validation=placement,
                sequence_validation=sequence,
                boss_mechanic_status="not_proved",
                encounter_quantity_authority="Explicit local singleton boss policy",
            )
        except (ValueError, KeyError, StopIteration, FileNotFoundError) as error:
            row.update(status="blocked", reason=str(error) or type(error).__name__)
        records.append(row)
    Path("docs/reports/dungeons/OPEN-BOSS-CANDIDATES.json").write_text(
        json.dumps(dict(records=records), indent=2) + "\n"
    )
    print(
        json.dumps(
            [(r["name"], r["status"], r.get("reason")) for r in records],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
