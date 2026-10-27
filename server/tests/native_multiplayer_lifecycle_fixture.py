"""Reuse genuine native multi-owner Ready, paid lethal damage and ACK boundaries."""
from pathlib import Path
from types import SimpleNamespace
import sys


def _native_fixture_module():
    sdk = str(Path(__file__).resolve().parents[1] / "ai-service")
    previous = list(sys.path)
    try:
        if Path(sdk).is_dir() and sdk not in sys.path:
            sys.path.insert(0, sdk)
        from benchmarks import benchmark_multiplayer_native

        return benchmark_multiplayer_native
    finally:
        sys.path[:] = previous


def prepare_jamajam_encounter():
    import json, struct, time
    from unittest.mock import patch

    fixture_module = _native_fixture_module()
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.combat_shared import Transition

    started = time.monotonic()
    original_fixture = fixture_module.fixture

    def inputs(**options):
        options["monster_references"] = (1620, 5525, 5525, 5525, 5525, 5525, 5525)
        return original_fixture(**options)

    with patch.object(fixture_module, "fixture", inputs):
        (
            registry,
            shared,
            sessions,
            characters,
            monsters,
            decks,
            excluded,
            bootstrap,
        ) = fixture_module.registered_multiplayer_fixture()
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=shared.fight.id
    )
    flags = dict(native_start_events=True, native_area_callbacks=True)

    def oracle(runtime):
        return NativeOracle(
            runtime,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=sessions[0].character_id,
            flags=flags,
        )

    def end(preview, runtime):
        packets = oracle(runtime).commit(
            {"type": "end_turn"}, stats_serializer=serializer
        )
        return Transition(runtime.fight, runtime, packets)

    def ack():
        barrier = shared.runtime.awaiting_ack
        if barrier is None:
            return []

        def release(preview, runtime, body):
            return Transition(preview, runtime, runtime.acknowledge_turn(body))

        result = []
        for session in sessions:
            result.append(
                registry.acknowledge(
                    shared.fight.id, session, struct.pack(">i", barrier), release
                )
            )
        assert result == [False, False, True], result
        assert shared.runtime.awaiting_ack is None
        return result

    transitions = 0
    while not shared.fight.current.controlled:
        actor = shared.fight.current
        registry.execute_server(
            shared.fight.id, actor.id, end, expected_sequence=shared.sequence
        )
        ack()
        transitions += 1
        if transitions > 12:
            raise RuntimeError("Native NPC timeline did not reach a player")
    actor = shared.fight.current
    session = next(s for s in sessions if s.account_id == actor.owner_id)
    target = next(uid for uid, row in monsters.items() if row["ref"] == 1620)
    assert shared.fight.actors[target].hp == 1
    from collections import deque

    adjacency = {}
    for source, destination in shared.fight.edges:
        adjacency.setdefault(source, []).append(destination)
    occupied = {
        a.position
        for a in shared.fight.actors.values()
        if a.hp > 0 and a.id != actor.id
    }
    queue = deque([(actor.position, [])])
    seen = {actor.position}
    route = None
    goal = shared.fight.actors[target].position
    while queue:
        cell, path = queue.popleft()
        if abs(cell[0] - goal[0]) + abs(cell[1] - goal[1]) == 1 and cell[2] == goal[2]:
            route = path
            break
        if len(path) >= actor.mp:
            continue
        for destination in sorted(adjacency.get(cell, ())):
            if destination in seen or destination in occupied:
                continue
            seen.add(destination)
            queue.append((destination, path + [list(destination)]))
    if route is None:
        raise RuntimeError("No native directed route to Jamajam within movement budget")
    if route:

        def move(preview, runtime):
            packets = oracle(runtime).commit(
                dict(type="move", path=route), stats_serializer=serializer
            )
            return Transition(runtime.fight, runtime, packets)

        registry.execute(shared.fight.id, session, actor.id, move)
    actor = shared.fight.current
    observer = oracle(shared.runtime)
    selected = None
    attempts = []
    for spell, level in observer.owned_spells(shared.fight, actor.id).items():
        action = dict(
            type="cast",
            spellId=spell,
            level=level,
            target=list(shared.fight.actors[target].position),
            targetId=target,
        )
        try:
            forecast, packets, tx = observer.preview(
                shared.runtime, action, forecast=False
            )
        except (ValueError, TypeError, KeyError) as error:
            attempts.append(
                dict(spell=spell, error=type(error).__name__, detail=str(error))
            )
            continue
        if forecast.fight.actors[target].hp <= 0:
            selected = action
            break
    if selected is None:
        raise RuntimeError(
            json.dumps(
                dict(
                    reason="No currently legal paid lethal cast",
                    caster=actor.id,
                    position=actor.position,
                    targetPosition=shared.fight.actors[target].position,
                    attempts=attempts,
                )
            )
        )
    from wakfu_server.combat_qi_fight import current_registry

    target_actor = shared.fight.actors[target]
    target_slot = target_actor.native_obstacle_id
    assert target_slot in current_registry(shared.fight).ordered_U(
        *target_actor.position[:2]
    )
    return SimpleNamespace(
        registry=registry,
        shared=shared,
        sessions=sessions,
        characters=characters,
        monsters=monsters,
        selected=selected,
        serializer=serializer,
        oracle=oracle,
        end=end,
        ack=ack,
        actor_id=actor.id,
        target=target,
        target_slot=target_slot,
        started=started,
    )


def kill_jamajam_and_continue(encounter):
    import time
    from wakfu_server.combat_shared import Transition
    from wakfu_server.combat_qi_fight import current_registry

    registry, shared, sessions = (
        encounter.registry,
        encounter.shared,
        encounter.sessions,
    )
    actor = shared.fight.actors[encounter.actor_id]
    session = next(s for s in sessions if s.account_id == actor.owner_id)
    target, selected = encounter.target, encounter.selected
    oracle, serializer, ack, end = (
        encounter.oracle,
        encounter.serializer,
        encounter.ack,
        encounter.end,
    )
    characters, monsters, started = (
        encounter.characters,
        encounter.monsters,
        encounter.started,
    )
    before_ap = actor.ap
    before_retained = len(shared.fight.native_retained_records)

    for owner in sessions:
        registry.drain(shared.fight.id, owner)

    def cast(preview, runtime):
        packets = oracle(runtime).commit(selected, stats_serializer=serializer)
        return Transition(runtime.fight, runtime, packets)

    registry.execute(shared.fight.id, session, actor.id, cast)
    assert shared.fight.actors[target].hp <= 0
    corpse = shared.fight.actors[target]
    native_status = shared.fight.native_global_pv_collections["fighter_status"][
        str(target)
    ]
    death_queued = {
        owner.account_id: any(
            opcode == 12727
            for batch in shared.outboxes.get(owner.account_id, ())
            for opcode, _ in batch.packets
        )
        for owner in sessions
    }
    from wakfu_server.combat_hp_raw import hp_raw_current, hp_raw_present
    from wakfu_server.combat_global_pv_collections import global_fighter_guards
    import struct

    death_targets = {
        owner.account_id: [
            struct.unpack_from(">qB", payload, len(payload) - 9)
            for batch in shared.outboxes.get(owner.account_id, ())
            for opcode, payload in batch.packets
            if opcode == 12727
        ]
        for owner in sessions
    }
    assert native_status == "OUT_OF_PLAY", dict(
        target_id=target,
        actual_status=native_status,
        hp=corpse.hp,
        alive=corpse.hp > 0,
        obstacle_id=corpse.native_obstacle_id,
        original_obstacle_id=encounter.target_slot,
        death12727_queued=death_queued,
        death12727_targets=death_targets,
        raw_hp=hp_raw_current(corpse) if hp_raw_present(corpse) else None,
        native_guards=global_fighter_guards(shared.fight, target),
        target_is_registered_summon=target
        in getattr(shared.fight, "native_summon_registrations", {}),
        causal_events=[
            event
            for event in shared.fight.events
            if event.get("actor_id") == target or event.get("target_id") == target
        ][-8:],
    )
    # Native fighter state2 completes ordinary corpse QI ownership through
    # the reviewed producer; this is stricter than accepting arbitrary HP0.
    from wakfu_server.combat_ordinary_qi_retirement import retired_ordinary_qi_ids

    assert target in retired_ordinary_qi_ids(shared.fight)
    receipt = shared.fight.native_ordinary_qi_retirements[str(target)]
    assert receipt["qi_slot"] == encounter.target_slot
    assert corpse.native_obstacle_id == -1
    registry_snapshot = current_registry(shared.fight).serialized_slots()
    assert not any(
        row is not None and tuple(row["identity"]) == ("actor", target)
        for row in registry_snapshot
    )
    assert all(
        [state for identity, state in rows if identity == target] == [0, 2]
        for rows in death_targets.values()
    )
    paid_ap_spent = before_ap - shared.fight.actors[actor.id].ap
    assert paid_ap_spent > 0
    publications = {}
    for owner in sessions:
        publications[owner.account_id] = [
            op
            for batch in registry.drain(shared.fight.id, owner)
            for op, body in batch.packets
        ]
    assert all(12727 in opcodes for opcodes in publications.values()), publications
    ack()
    current = shared.fight.current
    if current.controlled:
        owner = next(s for s in sessions if s.account_id == current.owner_id)
        registry.execute(shared.fight.id, owner, current.id, end)
    else:
        registry.execute_server(
            shared.fight.id, current.id, end, expected_sequence=shared.sequence
        )
    results = ack()
    return dict(
        status="PASS",
        players=len(characters),
        owners=len(sessions),
        npcCount=len(monsters),
        targetReference=1620,
        nativeTargetInitialHp=1,
        paidCast=selected,
        apSpent=paid_ap_spent,
        retainedBefore=before_retained,
        retainedAfter=len(shared.fight.native_retained_records),
        deathPublishedToAccounts=list(publications),
        postKillAck=results,
        phase=shared.fight.phase,
        elapsedSeconds=time.monotonic() - started,
        limits="Private local native fixture; no network clients, durable player leases or historical Jamajam-disconnect attribution.",
    )
