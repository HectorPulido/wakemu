"""Exercise a native trap in an isolated in-memory local World encounter.

Catalog access is read-only. The bridge and two changed combat modules are
loaded from the invoking checkout; other runtime modules come from World.
The fixture does not create a player session or publish a fight.
"""
import copy
import importlib.util
import os
from pathlib import Path
import random
import statistics
import struct
import sys
import time

from wakia_native_probe import fixture, load_bridge, readonly_providers


def main():
    root = Path(os.environ["WAKIA_PROBE_DIR"])
    readonly_providers()
    load_bridge(root / "wakfu_ai")
    for name in ("combat_damage_source", "combat_damage_handler"):
        spec = importlib.util.spec_from_file_location(
            "wakfu_server." + name, root / (name + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

    import wakfu_server.monsters as monsters_module
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle

    original = monsters_module.owned_instance

    def monster(*args, **kwargs):
        return original(3856, 100, *args[2:], **kwargs)

    monsters_module.owned_instance = monster
    try:
        runtime, characters, monsters, decks, excluded, description = fixture(
            extra_ally=True
        )
    finally:
        monsters_module.owned_instance = original
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory

    provider = OwnedExpirationFactory(
        characters=characters,
        monsters=monsters,
        decks=decks,
        actor_id=7,
        fight_start=True,
        area_callbacks=True,
    )
    runtime.expiration_runtime_factory = provider
    runtime.turn_start_provider = provider.turn_start
    runtime.turn_end_provider = provider.turn_end
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks=excluded,
        viewer_id=description.pc.id,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    cell = (-9, -3, -1)
    source = runtime.fight
    source_state = tuple(
        (actor.id, actor.hp, actor.ap, actor.mp) for actor in source.actors.values()
    ), len(source.native_effect_areas)
    started = time.perf_counter()
    preview, packets, transaction = oracle.preview(
        runtime, dict(type="cast", spellId=5552, level=100, target=list(cell))
    )
    preview_ms = (time.perf_counter() - started) * 1000
    after_state = tuple(
        (actor.id, actor.hp, actor.ap, actor.mp) for actor in source.actors.values()
    ), len(source.native_effect_areas)
    if (
        runtime.fight is not source
        or after_state != source_state
        or preview.fight is source
    ):
        raise RuntimeError("Native preview changed the source fight")
    if not packets:
        raise RuntimeError("Native preview returned no cast packets")
    print(f"preview_ms={preview_ms:.2f} packets={len(packets)} source_unchanged=true")
    runtime = preview
    trap = next(
        (
            row
            for row in runtime.fight.native_effect_areas.values()
            if row.get("reference") == 1000
        ),
        None,
    )
    if trap is None:
        raise RuntimeError("Expected native TRAP1000 was not created")
    from wakfu_server.combat_effect_area_geometry import contains_area_actor

    ally = runtime.fight.actors[-8]
    if not contains_area_actor(trap, ally.position, ally.physical_radius):
        raise RuntimeError("Expected ally is outside the native trap geometry")
    runtime.end_server_turn(-7, runtime.fight.turn_id)
    if runtime.awaiting_ack is not None:
        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
    if runtime.fight.current.id != 7:
        raise RuntimeError("Expected player turn")

    prepared = runtime.fight
    samples = []
    for index in range(6):
        started = time.perf_counter()
        fight = copy.deepcopy(prepared)
        clone_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        factory, _ = oracle.factory(fight, 20, random.Random(1))
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        factory_ms = (time.perf_counter() - started) * 1000
        actor = fight.actors[7]
        hp, mp = actor.hp, actor.mp
        ally = fight.actors[-8]
        ally_hp = ally.hp
        activations, callback_times = [], []

        def step(current, moving, before, after):
            started = time.perf_counter()
            if index == 0:
                from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_trap_observation import (
                    compare_area_movement,
                )

                started_compare = time.perf_counter()
                comparison = compare_area_movement(
                    oracle,
                    current,
                    trap["uid"],
                    moving.id,
                    before,
                    after,
                    action_id=20,
                    rng_state=random.Random(1).getstate(),
                )
                expected = [
                    {
                        "actorId": 7,
                        "hp": -1,
                        "armor": 0,
                        "ap": 0,
                        "mp": -2,
                        "maxAp": 0,
                        "maxMp": -3,
                    }
                ]
                if (
                    comparison["complete"] is not False
                    or comparison["deltas"] != expected
                    or comparison["control"]["deltas"]
                ):
                    raise RuntimeError("Partial native trap comparison differed")
                print(
                    f"partial_comparison_ms={(time.perf_counter() - started_compare) * 1000:.2f} "
                    "active_hp=-1 active_mp=-2 active_max_mp=-3 control_changes=0"
                )
            activations.append(
                dispatcher.native_area_events.movement(
                    moving.id, from_cell=before, to_cell=after
                )
            )
            callback_times.append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        event = fight.move(3, 7, [cell], step_callback=step)
        movement_ms = (time.perf_counter() - started) * 1000
        if (
            hp - actor.hp != 1
            or ally.hp != ally_hp
            or event["cost"] != 1
            or activations != [((), (True,), ())]
        ):
            raise RuntimeError("Native trap activation or damage differed")
        samples.append((clone_ms, factory_ms, movement_ms, callback_times[0]))
        print(
            f"run={index} clone_ms={clone_ms:.2f} factory_ms={factory_ms:.2f} "
            f"movement_ms={movement_ms:.2f} activation_ms={callback_times[0]:.2f} "
            f"hp_loss={hp - actor.hp} ally_hp_loss={ally_hp - ally.hp} "
            f"mp_change={mp - actor.mp} path_cost={event['cost']}"
        )
    retained = [
        row
        for row in fight.native_retained_records.values()
        if row.get("generic_effect") == 171478 and row.get("target_id") == 7
    ]
    if len(retained) != 1 or actor.max_mp != 0:
        raise RuntimeError("Expected retained maximum-MP reduction")
    uid = retained[0]["uid"]
    effect = fight.owned_stat_effects.get(uid, {})
    if (
        effect.get("stat_id") != 3
        or effect.get("caster_id") != trap["uid"]
        or effect.get("timer") != {"actor_id": 7, "expiration_round": 1, "phase": "end"}
    ):
        raise RuntimeError("Unexpected retained reduction source or expiration")
    runtime.fight = fight
    from wakfu_server.combat_timeline_snapshot import current_wire_turn

    runtime.end_turn(3, 7, current_wire_turn(fight))
    if runtime.awaiting_ack is not None:
        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
    if (
        runtime.fight.actors[7].max_mp != 3
        or uid in runtime.fight.native_retained_records
        or uid in runtime.fight.owned_stat_effects
    ):
        raise RuntimeError("Maximum-MP reduction did not expire at turn end")
    print("maximum_mp=3->0->3 retained_expired_at_player_turn_end=true")
    warm = samples[1:]
    print(
        "warm_medians_ms "
        + " ".join(
            f"{name}={statistics.median(row[i] for row in warm):.2f}"
            for i, name in enumerate(("clone", "factory", "movement", "activation"))
        )
    )
    print(
        "Scope: synthetic encounter; paid movement and native area callback, "
        "not client or full World turn delivery."
    )


if __name__ == "__main__":
    main()
