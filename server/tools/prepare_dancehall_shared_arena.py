"""Freeze Dancehall's three documented encounters in its one native arena."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate, reachable
from extract_native_door_flow import shortest_path


def main():
    from wakfu_server import dungeon_shared_arena
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    root = Path(".runtime/local")
    native = next(
        r
        for r in json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
            "records"
        ]
        if r["key"] == "native:11"
    )
    flow = next(
        r
        for r in json.loads((root / "all-native-dungeon-flows.json").read_text())[
            "records"
        ]
        if r["key"] == "native:11"
    )
    geometry = json.loads(
        (root / "all-native-dungeon-exploration/exploration-549.json").read_text()
    )
    cells = reachable(geometry, flow["entry"])
    geometry = dict(
        geometry,
        cells=[list(c) for c in sorted(cells)],
        edges=[
            e
            for e in geometry["edges"]
            if tuple(e[0]) in cells and tuple(e[1]) in cells
        ],
    )
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    ordinary = sorted(set(pool) - {2469})
    evidence = dict(
        source_url="https://wakfu.wiki.gg/wiki/Dancehall_Arena",
        authority="One physical room with three dances: 7 ordinary;8 ordinary;7 ordinary plus BilbyQueen. Exact ordinary allocation is explicit local cyclic policy, not official composition.",
    )
    rooms = []
    for order, count in enumerate((7, 8, 7), 1):
        refs = [ordinary[(i + order - 1) % len(ordinary)] for i in range(count)] + (
            [2469] if order == 3 else []
        )
        monsters = [
            dict(
                name=pool[ref]["name_es"],
                ref_id=ref,
                count=1,
                role="boss" if ref == 2469 else "monster",
                native_min_level=pool[ref]["min_level"],
                native_max_level=pool[ref]["max_level"],
                guide_min_level=None,
                guide_max_level=None,
            )
            for ref in refs
        ]
        rooms.append(dict(order=order, monsters=monsters, diagnostics=[]))
    route = flow["route"]
    plan = dict(
        slug=route["key"],
        source_url=evidence["source_url"],
        source_sha256=canonical_hash(evidence),
        document_sha256=canonical_hash(rooms),
        definition_id=11,
        template_id=route["template_id"],
        asset_map_id=549,
        rooms=rooms,
        roster_ready=True,
        diagnostics=[],
        official=False,
        boss_references=[2469],
        policy_mode="reviewed_same_arena_three_dances_local_ordinary_rotation",
    )
    topology = dict(
        asset_map_id=549,
        policy=dungeon_shared_arena.POLICY,
        rooms=[
            dict(order=i, anchor=list(flow["entry"]), cells=geometry["cells"])
            for i in (1, 2, 3)
        ],
        doors=[],
        physical_doors=[],
        exploration_geometry=geometry,
        shared_arena_evidence=evidence,
    )
    transports = json.loads(
        (
            root
            / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    # Exit belongs to the same physical arena, while availability uses final completion.
    topology["physical_exit_objects"] = bind_exits(
        dict(topology, rooms=topology["rooms"][:1]), route, transports
    )
    published = published_geometry(549)
    combat = dict(map_id=549, cells=list(published.cells), edges=list(published.edges))
    for anchor in sorted(
        cells, key=lambda c: (sum((c[i] - flow["entry"][i]) ** 2 for i in range(2)), c)
    ):
        for room in topology["rooms"]:
            room["anchor"] = list(anchor)
        placement = validate(
            dict(topology=topology, compiled_plan=plan),
            geometry,
            combat,
            enemy_formation,
            entry=flow["entry"],
        )
        if placement["status"] == "candidate_validated":
            break
    else:
        raise ValueError("No safe shared arena formation")
    config = prepare_configuration(
        plan, topology, route, version=1, provenance=evidence["authority"]
    )
    witnesses = []
    for stage in placement["rooms"]:
        monsters = set(map(tuple, stage["monster_positions"]))
        witness = None
        for target in sorted(monsters):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                approach = (target[0] + dx, target[1] + dy, target[2])
                path = shortest_path(
                    geometry["edges"], flow["entry"], approach, monsters
                )
                if path:
                    witness = dict(
                        target=list(target), approach=list(approach), path=path
                    )
                    break
            if witness:
                break
        if not witness:
            raise ValueError("Shared encounter cannot be engaged")
        witnesses.append(dict(order=stage["order"], engagement_witness=witness))
    out = Path("docs/reports/dungeons/shared-arena-v1")
    out.mkdir(exist_ok=True)
    path = out / "native_dungeon_11.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    scores = [
        sum(m["count"] * m["native_min_level"] for m in room["monsters"])
        for room in rooms
    ]
    if not all(a < b for a, b in zip(scores, scores[1:])):
        raise ValueError("Local native-level difficulty proxy must increase")
    report = dict(
        records=[
            dict(
                key="native:11",
                route=route["key"],
                name=native["name_es"],
                status="offline_configuration_prepared",
                path=str(path),
                rooms=3,
                placement_validation=placement,
                sequence_validation=dict(
                    status="offline_shared_arena_sequence_validated", rooms=witnesses
                ),
                difficulty_proxy=dict(
                    metric="sum native minimum levels, not boss mechanics",
                    scores=scores,
                ),
                boss_mechanic_status="not_proved",
            )
        ]
    )
    Path("docs/reports/dungeons/DANCEHALL-SHARED-ARENA-20261010-V1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(scores)


if __name__ == "__main__":
    main()
