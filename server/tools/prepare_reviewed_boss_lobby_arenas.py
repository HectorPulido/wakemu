"""Prepare reviewed single encounters behind initially open native lobby gates."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_open_boss_dungeons import prepare
from validate_dungeon_flow_rosters import reachable, validate
from validate_prepared_physical_flows import validate as validate_sequence


def build(native, flow, geometry, transports, combat, formation, evidence):
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )

    pool = native["native_species_pool"]
    if sorted(m["ref_id"] for m in pool) != sorted(evidence["boss_references"]):
        raise ValueError("Reviewed one-encounter roster differs from native pool")
    entry = tuple(flow["entry"])
    lobby = set(map(tuple, flow["first_encounter_reachable_cells"]))
    cells = reachable(geometry, entry)
    doors = [o for o in native["native_objects"] if o["type"] == "Door"]
    positions = {tuple(int(d[k]) for k in ("x", "y", "z")) for d in doors}
    arena = cells - lobby - positions
    if not arena or not lobby or entry not in lobby:
        raise ValueError("No distinct native lobby and arena")
    roster = [
        dict(
            name=m["name_es"],
            ref_id=m["ref_id"],
            count=1,
            role="boss",
            native_min_level=m["min_level"],
            native_max_level=m["max_level"],
            guide_min_level=None,
            guide_max_level=None,
        )
        for m in pool
    ]
    route = flow["route"]
    plan = dict(
        slug=route["key"],
        source_url=evidence["source_url"],
        source_sha256=canonical_hash(evidence),
        document_sha256=canonical_hash(roster),
        definition_id=route["definition_id"],
        template_id=route["template_id"],
        asset_map_id=route["start_map_id"],
        rooms=[],
        roster_ready=True,
        diagnostics=[],
    )
    base = dict(compiled_plan=plan, route=route, version=1)
    opened = copy.deepcopy(flow)
    opened.update(
        status="open_geometry_no_separator",
        first_encounter_reachable_cells=[list(c) for c in sorted(cells)],
    )
    config, _, _ = prepare(
        native,
        opened,
        base,
        geometry,
        transports,
        combat,
        formation,
        reviewed_roster=roster,
    )
    topology = config["topology"]
    topology[
        "progression_authority"
    ] = "Reviewed one encounter; native lobby gates initially open under explicit local access policy; no invented preliminary fights"
    topology["physical_doors"] = [
        dict(
            source_id=d["id"],
            position=[int(d[k]) for k in ("x", "y", "z")],
            source_room=1,
            destination_room=1,
            access_authority="Initially open lobby access; same encounter stage",
        )
        for d in doors
    ]
    topology["reviewed_encounter_evidence"] = evidence
    topology["lobby_cells"] = [list(c) for c in sorted(lobby)]
    # Keep combat itself in the arena, never in the narrow entrance/exit lobby.
    for anchor in sorted(
        arena, key=lambda c: (sum((c[i] - entry[i]) ** 2 for i in range(2)), c)
    ):
        topology["rooms"][0]["anchor"] = list(anchor)
        placement = validate(
            dict(topology=topology, compiled_plan=config["compiled_plan"]),
            topology["exploration_geometry"],
            combat,
            formation,
            entry=entry,
        )
        if placement["status"] == "candidate_validated" and all(
            tuple(p) in arena for p in placement["rooms"][0]["monster_positions"]
        ):
            break
    else:
        raise ValueError("No complete arena-only formation and six player placements")
    config = prepare_configuration(
        config["compiled_plan"],
        topology,
        route,
        version=2,
        provenance="Reviewed native single boss encounter; lobby gates initially open; exact roster quantities; directed engagement and native exit verified; boss mechanics unverified",
    )
    sequence = validate_sequence(config, dict(entry=list(entry)), placement)
    return config, placement, sequence


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    root = Path(".runtime/local")
    inv = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    flows = json.loads((root / "all-native-dungeon-flows.json").read_text())["records"]
    transports = json.loads(
        (
            root
            / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    evidence = {
        79: dict(
            boss_references=[2708, 2709, 2710, 2714],
            source_url="https://wakfu.guide/donjons/96-110/#repaire-des-super-vilains",
            authority="Guide explicitly describes one combat against four named bosses, matching native pool; one of each",
            mechanics_unverified=[
                "Merkator survivor scaling and ally boosts",
                "Megathon bubble imprisonment and counter posture",
                "Kralaman teleport and back-hit debuff",
                "Lardevil death triggers and charge glyphs",
            ],
        ),
        196: dict(
            boss_references=[5589],
            source_url="https://www.youtube.com/watch?v=xDRZuyI6Drk",
            authority="Official WAKFU 1.84 trailer names Toross Mordal in three-player Necromonde; installed native dungeon pool contains only reference5589; one initial boss explicit local policy",
            mechanics_unverified=[
                "Toross phases, effects and encounter scripts",
                "Optional native stele modifiers",
            ],
        ),
    }
    output = Path("docs/reports/dungeons/reviewed-boss-lobby-arenas-v1")
    output.mkdir(exist_ok=True)
    records = []
    for identity, proof in evidence.items():
        native = next(r for r in inv if r["key"] == f"native:{identity}")
        flow = next(r for r in flows if r["key"] == native["key"])
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
        row = dict(
            key=native["key"],
            route=flow["route"]["key"],
            name=native["name_es"],
            reviewed_evidence=proof,
        )
        try:
            config, placement, sequence = build(
                native, flow, geometry, transports, combat, enemy_formation, proof
            )
            path = output / (flow["route"]["key"] + ".json")
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=1,
                placement_validation=placement,
                sequence_validation=sequence,
                boss_mechanic_status="not_proved",
            )
        except ValueError as error:
            row.update(status="blocked", reason=str(error))
        records.append(row)
    Path(
        "docs/reports/dungeons/REVIEWED-BOSS-LOBBY-ARENAS-20261010-V1.json"
    ).write_text(
        json.dumps(
            dict(
                scope="Source-only reviewed arena candidates; no runtime writes",
                records=records,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print([(r["name"], r["status"], r.get("reason")) for r in records])


if __name__ == "__main__":
    main()
