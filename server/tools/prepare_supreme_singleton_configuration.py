"""Stage a reviewed singleton repair; never install or activate configurations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def prepare(base, native, *, version, source_url, authority):
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )

    if not source_url or not authority.strip():
        raise ValueError("Reviewed composition evidence is required")
    if type(version) is not int or version <= base["version"]:
        raise ValueError("Replacement requires a fresh later version")
    for field, value in (
        ("plan", base["compiled_plan"]),
        ("topology", base["topology"]),
        ("route", base["route"]),
    ):
        if canonical_hash(value) != base["evidence_hashes"][field]:
            raise ValueError("Frozen baseline evidence differs: " + field)
    plan = copy.deepcopy(base["compiled_plan"])
    topology = copy.deepcopy(base["topology"])
    reference = native["ref"]
    if (
        type(reference) is not int
        or 49 not in native["raw_visual_arrays"]["csc"]
        or plan.get("policy_mode") != "generated_native_species_policy"
        or not plan.get("generated_fields")
        or topology.get("policy") != "local_accessible_anchor_policy"
        or topology.get("doors")
        or topology.get("physical_doors")
        or topology.get("branch_routes")
        or topology.get("exploration_geometry")
    ):
        raise ValueError(
            "Repair requires an explicit generated singleton ultimate arena"
        )
    monsters = [m for room in plan["rooms"] for m in room["monsters"]]
    if not monsters or any(m["ref_id"] != reference for m in monsters):
        raise ValueError("Mixed species cannot be discarded by singleton repair")
    bosses = [
        (room, m)
        for room in plan["rooms"]
        for m in room["monsters"]
        if m["role"] == "boss"
    ]
    if len(bosses) != 1 or bosses[0][1]["count"] != 1:
        raise ValueError("A single existing native boss is required")
    room, boss = bosses[0]
    if (boss["native_min_level"], boss["native_max_level"]) != (
        native["min_level"],
        native["max_level"],
    ):
        raise ValueError("Native boss grade authority differs")
    selected = [r for r in topology["rooms"] if r["order"] == room["order"]]
    if len(selected) != 1 or not topology.get("completion_destination"):
        raise ValueError("Existing boss terrain and exterior return are required")
    previous_rooms = copy.deepcopy(plan["rooms"])
    plan.update(
        rooms=[dict(order=1, monsters=[copy.deepcopy(boss)], diagnostics=[])],
        policy_mode="reviewed_local_singleton_ultimate_composition",
        official=False,
        reviewed_official=False,
        boss_references=[reference],
        diagnostics=[],
        roster_ready=True,
        local_policy="One reviewed native boss in its existing final arena; no generated filler encounters.",
    )
    plan.pop("generated_fields", None)
    plan["roster_policy_evidence"] = dict(
        source_url=source_url,
        authority=authority,
        baseline_version=base["version"],
        baseline_plan_hash=base["evidence_hashes"]["plan"],
        previous_rooms_sha256=canonical_hash(previous_rooms),
        boss_references=[reference],
        placement_authority="Existing local final-room native cells and anchor; not recovered official placement",
    )
    plan["document_sha256"] = canonical_hash(plan["rooms"])
    selected = copy.deepcopy(selected[0])
    selected["order"] = 1
    topology.update(
        rooms=[selected],
        auto_edges=[],
        room_count_source="reviewed_local_singleton_composition",
        room_count_official=False,
        official_room_order_verified=False,
    )
    provenance = (
        "Reviewed Wakemu singleton ultimate-boss composition repair; "
        "existing final-room native cells/anchor and exterior return preserved; "
        "generated filler copies removed; original encounter setup and mechanics separately qualified"
    )
    return prepare_configuration(
        plan, topology, base["route"], version=version, provenance=provenance
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--native-index", type=Path, required=True)
    parser.add_argument("--reference", type=int, required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.baseline.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.baseline_sha256:
        raise ValueError("Baseline file hash differs")
    records = json.loads(args.native_index.read_text())["native_records"]
    native = [r["payload"] for r in records if r["record_key"] == str(args.reference)]
    if len(native) != 1:
        raise ValueError("Native reference is absent or ambiguous")
    result = prepare(
        json.loads(raw),
        native[0],
        version=args.version,
        source_url=args.source_url,
        authority=args.authority,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                route=result["route"]["key"],
                version=result["version"],
                status="staged_not_installed",
                output=str(args.output),
            )
        )
    )


if __name__ == "__main__":
    main()
