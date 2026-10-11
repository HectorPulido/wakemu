"""Prepare source-only reviewed native endpoint candidates for classic13/155/84."""
import copy
import json
from pathlib import Path
from build_native_branch_spine import deepest_native_stage, shortest_path
from native_family_configuration_base import base
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from extract_dungeon_family_bosses import load_role_catalog
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as sequence


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.dungeon_physical_doors import POLICY

    load = lambda p: json.loads(Path(p).read_text())
    native = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    identity = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    formations = {
        r["key"]: r
        for r in load(
            "docs/reports/dungeons/THREE-BLOCKED-NATIVE-FORMATIONS-V1-20261010.json"
        )
    }
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    output = Path(".runtime/local/three-native-reviewed-candidates-v1-20261010")
    output.mkdir(exist_ok=True)
    rows = []
    for key in ["native:13", "native:155", "native:84"]:
        n = native[key]
        route = n["native_entry_routes"][0]
        evidence = formations[key]
        entry = evidence["entry"]
        mid = route["start_map_id"]
        row = dict(key=key, name=n["name_es"], route=route["key"])
        try:
            geometry = load(
                f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json"
            )
            doors = [
                o
                for o in n["native_objects"]
                if o["type"] == "Door" and o["map_id"] == mid
            ]
            if key == "native:84":
                topology = deepest_native_stage(geometry, doors, entry)
                if len(topology["rooms"]) != 2:
                    raise ValueError("Reviewed Negraspora requires two native arenas")
                selected = {1: [-62, -2, 0], 2: [-91, 0, 12]}
                for room in topology["rooms"]:
                    room["anchor"] = selected[room["order"]]
            else:
                anchor = {"native:13": [-79, -83, 1], "native:155": [-13, -13, 0]}[key]
                topology = dict(
                    asset_map_id=mid,
                    policy=POLICY,
                    official_room_order_verified=False,
                    progression_authority="Reviewed single encounter with literal native lobby access; generated family composition; no official mechanics claimed",
                    rooms=[dict(order=1, anchor=anchor, cells=geometry["cells"])],
                    doors=[],
                    physical_doors=[
                        dict(
                            source_id=o["id"],
                            position=[o[k] for k in ("x", "y", "z")],
                            source_room=1,
                            destination_room=1,
                            local_annex_gate=True,
                        )
                        for o in doors
                    ],
                    exploration_geometry=geometry,
                )
                topology["native_review_evidence"] = dict(
                    entry=entry,
                    initial_open_door_ids=[o["id"] for o in doors],
                    unsupported_legacy_transport_ids=[
                        u["source_id"] for u in evidence["native_graph"]["unresolved"]
                    ],
                )
            # Bind the known literal entry-side exterior; final stage returns by native walking.
            source_id = {"native:13": 18806, "native:155": 31858, "native:84": 21700}[
                key
            ]
            source = next(
                s for s in transports if s["map_id"] == mid and s["id"] == source_id
            )
            topology["physical_exit_objects"] = bind_exits(
                topology, route, [source], allow_physical_return=True
            )
            bosses = identity[key]["boss_references"]
            eligible = eligible_family_refs(n, roles, bosses)
            roster = progressive_family_roster(
                n, len(topology["rooms"]), bosses, capacity=8, eligible_refs=eligible
            )
            compiled = base(n, route, roster["rooms"])
            compiled["compiled_plan"]["progression_policy"] = roster[
                "progression_policy"
            ]
            config = prepare_configuration(
                compiled["compiled_plan"],
                topology,
                route,
                version=21,
                provenance="Manual native endpoint review; native species/role/levels; literal lobby and return walking; source-only",
            )
            p = published_geometry(mid)
            combat = dict(map_id=mid, cells=list(p.cells), edges=list(p.edges))
            placement = validate(config, geometry, combat, enemy_formation, entry=entry)
            if placement["status"] != "candidate_validated":
                raise ValueError(str(placement["reasons"]))
            stages = []
            if len(topology["rooms"]) > 1:
                for group in topology["local_mainspine_evidence"][
                    "mandatory_gate_groups"
                ]:
                    position = next(
                        d["position"]
                        for d in topology["physical_doors"]
                        if d["source_id"] == group[0]
                    )
                    stages.append(
                        dict(
                            directed_boundary_path=shortest_path(
                                geometry["edges"], entry, position
                            )
                        )
                    )
            traversal = sequence(config, dict(entry=entry, stages=stages), placement)
            path = output / (route["key"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=len(topology["rooms"]),
                boss_references=bosses,
                placement_validation=placement,
                sequence_validation=traversal,
                entry=entry,
            )
        except (ValueError, KeyError, StopIteration) as error:
            row.update(status="blocked", reason=str(error))
        rows.append(row)
    path = Path("docs/reports/dungeons/THREE-NATIVE-REVIEW-CANDIDATES-V1-20261010.json")
    path.write_text(
        json.dumps(
            dict(
                scope="Source-only native endpoint manual review; no activation",
                records=rows,
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            [
                dict(name=r["name"], status=r["status"], reason=r.get("reason"))
                for r in rows
            ]
        )
    )


if __name__ == "__main__":
    main()
