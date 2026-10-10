"""Build frozen physical-door configuration from native exploration and reviewed roster."""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components
from extract_native_door_flow import extract
from collections import defaultdict


def topology_for(geometry, doors, entry, exit_position, exit_objects):
    from wakfu_server.dungeon_physical_doors import POLICY

    flow = extract(geometry, doors, entry, exit_position)
    if flow["status"] != "physical_linear_chain_proved":
        raise ValueError("Native physical door flow is not linear and directed")
    positions = {d["id"]: tuple(d[k] for k in ("x", "y", "z")) for d in doors}
    blocked = {positions[i] for i in flow["door_chain"]}
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    cells = set(map(tuple, geometry["cells"])) - blocked
    labels, sizes = components(cells, adjacency)
    chain = []
    region = labels[tuple(entry)]
    chain.append(region)
    for identity in flow["door_chain"]:
        neighbors = {labels[n] for n in adjacency[positions[identity]] if n in labels}
        forward = neighbors - {region}
        if len(forward) != 1:
            raise ValueError("Physical door region is ambiguous")
        region = forward.pop()
        chain.append(region)
    rooms = []
    for order, region in enumerate(chain, 1):
        selected = sorted(c for c, label in labels.items() if label == region)
        count = len(selected)
        sx = sum(p[0] for p in selected)
        sy = sum(p[1] for p in selected)
        anchor = min(
            selected,
            key=lambda p: ((p[0] * count - sx) ** 2 + (p[1] * count - sy) ** 2, p),
        )
        rooms.append(
            dict(order=order, anchor=list(anchor), cells=[list(c) for c in selected])
        )
    return dict(
        asset_map_id=geometry["map_id"],
        policy=POLICY,
        official_room_order_verified=False,
        progression_authority="Explicit DEV ordered native physical gates unlocked by durable room victory",
        rooms=rooms,
        doors=[],
        physical_doors=[
            dict(
                source_id=identity,
                position=list(positions[identity]),
                source_room=i + 1,
                destination_room=i + 2,
            )
            for i, identity in enumerate(flow["door_chain"])
        ],
        physical_exit_objects=exit_objects,
        exploration_geometry={
            k: geometry[k]
            for k in (
                "map_id",
                "profile",
                "client_sha256",
                "topology_sha256",
                "cells",
                "edges",
            )
        },
    )


def build(base, geometry, roster, doors, entry, exit_position, exit_objects, version):
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )

    plan = copy.deepcopy(base["compiled_plan"])
    plan["rooms"] = [
        dict(order=r["order"], monsters=r["monsters"], diagnostics=[])
        for r in roster["rooms"]
    ]
    plan["roster_policy_evidence"] = {
        k: roster[k]
        for k in (
            "policy_mode",
            "official",
            "boss_references",
            "species_pool_provenance",
        )
        if k in roster
    }
    plan["policy_mode"] = "explicit_dev_native_physical_rooms"
    plan["official"] = False
    plan["document_sha256"] = canonical_hash(
        dict(rooms=plan["rooms"], policy=plan["policy_mode"])
    )
    plan["diagnostics"] = []
    plan["roster_ready"] = True
    topology = topology_for(geometry, doors, entry, exit_position, exit_objects)
    return prepare_configuration(
        plan,
        topology,
        base["route"],
        version=version,
        provenance="Explicit DEV native exploration profile 6/0/4; directed physical gates; final-room singleton boss; room-victory unlock policy",
    )


def migration(config):
    text = json.dumps(config, separators=(",", ":"), ensure_ascii=False)
    return (
        """-- Frozen native physical-door dungeon, source-only until normal migration deployment.
DO $migration$
DECLARE config jsonb := $configuration$"""
        + text
        + """$configuration$::jsonb;
route text := config->'route'->>'key';
version integer := (config->>'version')::integer;
config_key text := 'dungeon_runtime_config:' || route || ':v' || version;
BEGIN
    IF EXISTS(SELECT 1 FROM settings WHERE name=config_key AND value<>config) THEN
        RAISE EXCEPTION 'Immutable dungeon configuration version conflicts';
    END IF;
    INSERT INTO settings(name,value) VALUES(config_key,config) ON CONFLICT(name) DO NOTHING;
    INSERT INTO dungeon_context_policy_versions(route_key,policy_version,template_id,definition_id,
        max_level,min_level,difficulty_level,is_difficulty_available,can_increase_difficulty,
        is_competitive_cancelled,allowed_ids,provenance)
    VALUES(route,version,(config->'route'->>'template_id')::integer,
        (config->'route'->>'definition_id')::integer,0,0,2,false,false,false,'{}',config->>'provenance')
    ON CONFLICT(route_key,policy_version) DO NOTHING;
    INSERT INTO dungeon_context_active_policies(route_key,policy_version) VALUES(route,version)
    ON CONFLICT(route_key) DO UPDATE SET policy_version=EXCLUDED.policy_version;
    INSERT INTO settings(name,value) VALUES('dungeon_runtime_active:'||route,
        jsonb_build_object('version',version,'key',config_key))
    ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value;
END $migration$;
"""
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())
    row = next(
        r for r in inventory["records"] if r["native"] and r["native"]["id"] == 27
    )
    configs = json.loads(
        Path(
            ".runtime/local/methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
        ).read_text()
    )["configurations"]
    base = next(c for c in configs if c["slug"] == "le-tofulailler")
    config = build(
        base,
        json.loads(args.geometry.read_text()),
        json.loads(args.roster.read_text()),
        [o for o in row["native_objects"] if o["type"] == "Door"],
        [14, -25, 0],
        [33, -5, -12],
        [dict(source_id=26871, room_order=1), dict(source_id=26872, room_order=3)],
        3,
    )
    args.output.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    args.migration.write_text(migration(config))
    print(
        json.dumps(
            dict(
                version=config["version"],
                rooms=len(config["topology"]["rooms"]),
                anchors=[r["anchor"] for r in config["topology"]["rooms"]],
            )
        )
    )
