"""Freeze authentic optional Kokolost actors separately from generated rosters.

Proof only: this does not add an optional-encounter runtime controller, council
voting or rewards, and does not change the four mandatory encounter stages.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_hybrid_native_dungeon_flow import extract
from extract_milubo_mixed_flow import hybrid_path


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.dungeon_runtime_config import canonical_hash

    load = lambda p: json.loads(Path(p).read_text())
    native = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:141"
    )
    flow = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:141"
    )
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-295.json"
    )
    sources = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    graph = extract(geometry, native["native_objects"], sources, flow["entry"], 1135)
    catalog = load(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )["monsters"]
    names = load(".runtime/local/methodwakfu-dungeons/native-monster-names-fr.json")[
        "monsters"
    ]
    pool = {m["ref"]: m for m in catalog}
    fr = {m["ref"]: m for m in names}
    allowlist = []
    for ref, name, count in [
        (1751, "Vieux Binson", 1),
        (1753, "Viandredi", 1),
        (4728, "Grokoko", 2),
    ]:
        m = pool[ref]
        if m["family_id"] != 356 or (
            ref in (1751, 1753) and fr[ref]["name_fr"] != name
        ):
            raise ValueError("Optional guide/native identity evidence changed")
        allowlist.append(
            dict(
                ref_id=ref,
                name_fr=fr[ref]["name_fr"],
                name_es=m["name"],
                count=count,
                family_id=m["family_id"],
                native_world_properties=m["raw_visual_arrays"]["csc"],
                native_min_level=m["min_level"],
                native_max_level=m["max_level"],
                native_record_sha256=canonical_hash(m),
                optional=True,
                authority="Reviewed optional guide roster and exact native French name within Kokolost family356; explicit user exception for authentic documented optional encounters",
            )
        )
    branch_regions = {
        l["source_region"]
        for l in graph["links"]
        if l["kind"] == "physical_gate" and l["source_id"] == 13348
    }
    branch = next(
        c
        for c in graph["components"]
        if c["region"] in branch_regions and len(c["cells"]) == 141
    )
    if len(branch["cells"]) != 141:
        raise ValueError(
            "Reviewed optional branch region no longer matches native terrain"
        )
    cells = set(map(tuple, branch["cells"]))
    n = len(cells)
    sx = sum(p[0] for p in cells)
    sy = sum(p[1] for p in cells)
    anchors = sorted(
        cells, key=lambda p: ((p[0] * n - sx) ** 2 + (p[1] * n - sy) ** 2, p)
    )
    published = published_geometry(295)
    section = dict(
        map_id=295,
        cells=[list(p) for p in published.cells if tuple(p) in cells],
        edges=[
            (a, b)
            for a, b in published.edges
            if tuple(a) in cells and tuple(b) in cells
        ],
    )
    for anchor in anchors:
        try:
            positions = list(enemy_formation(section, anchor, 4, player_slots=6))
            break
        except ValueError:
            continue
    else:
        raise ValueError("No native optional formation with six player slots")
    main = load(
        ".runtime/local/hybrid-native-full-room-v7-20261010/native_dungeon_141.json"
    )["topology"]
    available = [
        d for d in main["doors"] if max(d["source_room"], d["destination_room"]) <= 3
    ]
    blocked = [
        d["position"] for d in main["physical_doors"] if d["destination_room"] > 3
    ]
    path = hybrid_path(
        geometry["edges"],
        available,
        main["rooms"][2]["anchor"],
        anchor,
        blocked=blocked,
    )
    if path is None:
        raise ValueError(
            "Optional branch not natively reachable from third encounter stage"
        )
    proof = dict(
        schema_version=1,
        version=9,
        key="native:141",
        optional=True,
        mandatory_room_count=4,
        status="identity_geometry_proved_runtime_optional_controller_missing",
        source_url="https://methodwakfu.com/pvm/donjons/kokokolantha/",
        name_matching_note="Guide heading names Viandredi exactly; one composition paragraph spells Viendredi. Native family356 resolves1753. Same-name family1147 copies5741/5742 are excluded.",
        allowlist=allowlist,
        location=dict(
            map_id=295,
            region=branch["region"],
            cells=branch["cells"],
            anchor=list(anchor),
            entrance_gate_id=13348,
            entrance_gate_position=[-21, -86, 0],
            council_component=10,
            mimic_alternative_gate_id=13347,
            mimic_alternative_region=8,
        ),
        formation=dict(player_slots=6, monster_positions=positions),
        native_access_path=path,
        guide_access=dict(
            optional=True, council_minimum_votes=3, mutually_exclusive_mimic_branch=True
        ),
        pending=[
            "Separate optional encounter identity and durable victory without advancing mandatory room progress",
            "Council voting and mutually exclusive branch choice, or explicitly authorized local access policy",
            "Optional encounter rewards and cleanup",
            "Do not insert these actors in generated main family rosters",
        ],
        runtime_changes=False,
    )
    target = Path(
        "docs/reports/dungeons/KOKOLOST-AUTHENTIC-OPTIONAL-PROOF-V9-20261010.json"
    )
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
