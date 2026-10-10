"""Freeze an automatically proved native teleport chain and resolved DEV roster."""
import copy


def build(base, topology, roster, transports, *, version):
    from prepare_native_physical_candidates import bind_exits
    from wakfu_server import dungeon_native_flow, dungeon_object_states
    from wakfu_server.dungeon_runtime_config import (
        canonical_hash,
        prepare_configuration,
    )

    topology = copy.deepcopy(topology)
    if topology.get("policy") != dungeon_native_flow.TELEPORT_POLICY:
        raise ValueError("Only proved native teleport topology is supported")
    if topology.get("physical_doors"):
        raise ValueError("Mixed physical and teleport gates require separate proof")
    topology["physical_exit_objects"] = bind_exits(topology, base["route"], transports)
    plan = copy.deepcopy(base["compiled_plan"])
    plan["rooms"] = [
        dict(order=r["order"], monsters=copy.deepcopy(r["monsters"]), diagnostics=[])
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
    plan.update(
        policy_mode="explicit_dev_native_teleport_rooms",
        official=False,
        diagnostics=[],
        roster_ready=True,
    )
    plan["document_sha256"] = canonical_hash(
        dict(rooms=plan["rooms"], policy=plan["policy_mode"])
    )
    candidate = prepare_configuration(
        plan,
        topology,
        base["route"],
        version=version,
        provenance="Explicit DEV ordered native teleport rooms; literal approach and arrival cells; durable room-victory unlocks; nonofficial composition",
    )
    # Verify every published object stage against the literal supplied catalog.
    sources = [s for s in transports if s["map_id"] == topology["asset_map_id"]]
    for stage in range(1, len(topology["rooms"]) + 1):
        dungeon_object_states.packets(
            topology,
            sources,
            map_id=topology["asset_map_id"],
            instance_id=1,
            unlocked_room=stage,
            completed=False,
        )
    dungeon_object_states.packets(
        topology,
        sources,
        map_id=topology["asset_map_id"],
        instance_id=1,
        unlocked_room=len(topology["rooms"]),
        completed=True,
    )
    return candidate
