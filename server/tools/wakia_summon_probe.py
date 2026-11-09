"""Emit a native two-snapshot summon scenario for the local WakIA Host probe.

The encounter and summon trigger are synthetic; all combat state, UID
allocation, summon construction, turn boundaries, and spell projections use
the installed World engine. No player session or shared fight is created.
PostgreSQL is forced read-only and Redis writes are rejected in this process.
"""
import json
import os
import random
import struct

from wakia_native_probe import fixture, load_bridge, readonly_providers


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    readonly_providers()
    load_bridge(os.environ["WAKIA_PROBE_BRIDGE"])
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import build_snapshot
    from wakfu_server.combat_summon import prepare_summon, summon_specification
    from wakfu_server.combat_summon_codec import summon_application
    from wakfu_server.combat_summon_creation import NativeSummonBuilder
    from wakfu_server.combat_summon_initialization import summon_initializer
    from wakfu_server.combat_timeline_snapshot import current_wire_turn

    runtime, characters, monsters, decks, excluded, description = fixture()
    fight = runtime.fight
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks=excluded,
        viewer_id=description.pc.id,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    factory, adapter = oracle.factory(fight, 2, random.Random(1))
    specification = summon_specification(
        {"effect_class": 307},
        {"parameters": [3786, 20, 0, 3, 1]},
        evaluation_level=20,
        container_present=True,
        caster_level=10,
        caster_team=1,
        caster_direction=3,
        native_minimum_level=1,
    )
    occupied = {tuple(actor.position[:2]) for actor in fight.actors.values()}
    candidates = sorted(
        (
            position
            for position in fight.walkable
            if position[2] == description.pc.position[2]
            and tuple(position[:2]) not in occupied
        ),
        key=lambda position: (
            sum(abs(position[i] - description.pc.position[i]) for i in range(2)),
            position,
        ),
    )
    require(bool(candidates), "Synthetic arena has no free summon cell")
    runner_uid = fight.allocate_effect_uid()
    allocated = []

    def allocate(preview):
        identity = preview.allocate_effect_uid()
        while identity in preview.actors:
            identity = preview.allocate_effect_uid()
        allocated.append(identity)
        return identity

    timing = bytes.fromhex(
        "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
    )

    def encode(preview, selected, registration, cell):
        actor = preview.actors[registration.actor_id]
        return (
            summon_application(
                preview.id,
                99,
                uid=runner_uid,
                base_uid=None,
                effect_reference=123,
                caster_id=-7,
                cell=actor.position,
                specification=selected,
                actor_id=actor.id,
                obstacle_index=actor.native_obstacle_id,
                properties=tuple(sorted(registration.fight_properties)),
                timing_payload=timing,
            ),
        )

    preview, packets = prepare_summon(
        fight,
        specification,
        caster_id=-7,
        cell=candidates[0],
        authority=adapter.actor_authority,
        allocate_actor_uid=allocate,
        build_native_actor=NativeSummonBuilder(
            adapter.actor_authority, initialize_states=summon_initializer(factory, [])
        ),
        encode_application=encode,
    )
    require(bool(packets) and len(allocated) == 1, "Native summon preparation failed")
    summon_id = allocated[0]
    runtime.fight = preview

    def acknowledge():
        if runtime.awaiting_ack is not None:
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))

    runtime.end_server_turn(-7, runtime.fight.turn_id)
    acknowledge()
    require(
        runtime.fight.current.id == summon_id, "Summon did not receive its native turn"
    )
    summon_snapshot = build_snapshot(oracle, budget_ms=1000)
    require(
        any(
            row["id"] == 5228 and not row.get("unknownProjection")
            for row in summon_snapshot["spells"]
        ),
        "Native summon spell 5228 was not projected",
    )
    runtime.end_server_turn(summon_id, runtime.fight.turn_id)
    acknowledge()
    require(runtime.fight.current.id == 7, "Expected synthetic player turn")
    runtime.end_turn(3, 7, current_wire_turn(runtime.fight))
    acknowledge()
    require(runtime.fight.current.id == -7, "Expected synthetic summoner turn")
    snapshot = build_snapshot(oracle, budget_ms=1000)
    require(
        any(
            book["actorId"] == summon_id
            and any(spell["id"] == 5228 for spell in book["spells"])
            for book in snapshot["native"]["estimatedSummonBooks"]
        ),
        "Summoner snapshot did not retain the owned-spell estimate",
    )
    print(json.dumps(snapshot, separators=(",", ":")))


if __name__ == "__main__":
    main()
