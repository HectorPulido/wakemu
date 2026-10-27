"""Measure real multi-owner native turns against the existing TCP AI service.

This private fixture measures native execution, not client acceptance or durable
Rift checkpoint publication. Inclusive timers overlap and must not be added.
"""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import inspect
from pathlib import Path
import json
import os
import time
from unittest.mock import patch

from benchmarks.benchmark_native_roster import fixture
from benchmarks.benchmark_native_tcp_profile import MeasuredTCPTransport
from wakfu_ai.bridge import world_bridge, world_sources
from wakfu_ai.bridge.world_entry import native_exporter
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native.native_profiles import encounter_profiles
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.native.native_turn import run_turn
from wakfu_server import native_catalog
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_runtime_messages import RuntimeMessages


def multiplayer_fixture():
    runtime, characters, monsters, decks, excluded, description = fixture(
        player_count=5,
        owner_accounts=(9001, 9001, 9001, 9002, 9003),
        monster_references=(5525,) * 7,
    )
    from wakfu_server.combat_server_spell import prepare_server_initialization

    for index, character in enumerate(characters.values()):
        runtime.fight, _ = prepare_server_initialization(
            character,
            monsters,
            runtime.fight,
            character["account_id"],
            decks[character["id"]],
            action_id=1,
            fight_start=(index == len(characters) - 1),
            player_characters=characters,
            deck_blobs=decks,
        )
    instance = 77
    for source in (*characters.values(), *monsters.values()):
        source["instance_id"] = instance
    runtime.fight.rift_monsters = deepcopy(monsters)
    runtime.fight.rift_wave_state = dict(
        instance_id=instance,
        wave=1,
        turn_budget=40,
        wave_actor_ids=list(monsters),
        current_actor_ids=list(monsters),
        pending_wave=None,
        staged_receipts=[],
    )
    provider = OwnedExpirationFactory(
        characters=characters,
        monsters=monsters,
        decks=decks,
        actor_id=next(iter(characters)),
        area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1",
    )
    runtime.expiration_runtime_factory = provider
    runtime.turn_start_provider = provider.turn_start
    runtime.turn_end_provider = provider.turn_end
    runtime.tactical_encounter_id = "private-multiplayer-native-baseline"
    return runtime, characters, monsters, decks, excluded, description


def registered_multiplayer_fixture():
    """Exercise actual Registry admissions, per-owner bootstrap and native Ready.

    Leases are private fixture identities. Durable Store admission is not claimed.
    """
    import struct
    from wakfu_server.combat_shared import Registry, Session, Transition
    from wakfu_server.combat_session_adapter import CombatSessionAdapter
    from wakfu_server.combat_heroes import player_actor
    from wakfu_server.combat_bootstrap import player_payload
    from wakfu_server.combat_actor import actor_effects, actual_monster_actor_stats
    from wakfu_server.combat_ready import prepare_ready
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.spells import default_deck

    runtime, characters, monsters, decks, excluded, description = fixture(
        player_count=3,
        owner_accounts=(9001,) * 3,
        monster_references=(5525,) * 7,
        ready=False,
    )
    sessions = [
        Session(account, actor, "private-" + str(account), 1134, 0)
        for account, actor in ((9001, 7001), (9002, 7004), (9003, 7005))
    ]
    registry = Registry(lambda candidate: candidate in sessions)

    def payload(fight, actor, owner):
        if actor.controlled:
            return player_payload(characters[actor.id], actor, fight.id, wp=6)
        source = monsters[actor.id]
        return (
            actual_monster_actor_stats(
                source,
                actor,
                fight.id,
                wp_current=source["wp"],
                wp_maximum=source["wp"],
                fight=fight,
            ),
            actor_effects(),
        )

    context = dict(
        description.join_context,
        actor_payload=payload,
        frozen_company_members=(7001, 7002, 7003, 7004, 7005),
    )
    shared = registry.register(runtime.fight, sessions[0], join_context=context)
    placement = set(description.arena["placement_cells"][0])
    occupied = {actor.position for actor in shared.fight.actors.values()}
    bootstrap = {}
    for session in sessions[1:]:
        position = sorted(placement - occupied)[0]
        occupied.add(position)
        character = dict(
            characters[7001],
            id=session.character_id,
            account_id=session.account_id,
            x=position[0],
            y=position[1],
            z=position[2],
        )
        characters[session.character_id] = character
        decks[session.character_id] = default_deck(character)
        excluded[session.character_id] = frozenset()
        actor = player_actor(character, 0)
        registry.join(
            session,
            struct.pack(">qB", 7001, 0),
            actor,
            actor_payload=payload,
            bootstrap_packets=CombatSessionAdapter.placement_bootstrap,
        )
        bootstrap[session.account_id] = [
            op
            for batch in registry.drain(shared.fight.id, session)
            for op, _ in batch.packets
        ]
    provider = OwnedExpirationFactory(
        characters=characters,
        monsters=monsters,
        decks=decks,
        actor_id=7001,
        area_callbacks=True,
    )
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=shared.fight.id
    )

    def initialize(preview, action_id):
        packets = []
        for index, character in enumerate(characters.values()):
            preview, owned = prepare_server_initialization(
                character,
                monsters,
                preview,
                character["account_id"],
                decks[character["id"]],
                action_id=action_id,
                fight_start=(index == len(characters) - 1),
                player_characters=characters,
                deck_blobs=decks,
            )
            packets.extend(owned)
        return preview, packets

    for session in sessions:

        def operation(fight, native):
            prepared, native, packets = prepare_ready(
                fight,
                session.account_id,
                True,
                initialize=initialize,
                stats_serializer=serializer,
                effects_serializer=actor_effects,
                runtime_stats_serializer=serializer,
                turn_start_provider=provider.turn_start,
                turn_end_provider=provider.turn_end,
                expiration_runtime_factory=provider,
            )
            return Transition(prepared, native, packets)

        registry.execute(
            shared.fight.id,
            session,
            session.character_id,
            operation,
            require_turn=False,
        )
    assert len(shared.fight.actors) == 12
    assert shared.fight.phase == "active"
    assert len(shared.participants) == 3
    assert shared.runtime.fight is shared.fight
    assert shared.fight.native_start_event_delivered
    return registry, shared, sessions, characters, monsters, decks, excluded, bootstrap


def registered_barrier_probe():
    """Require all three actual registry owners before releasing native pending."""
    import struct
    from wakfu_server.combat_shared import Transition

    (
        registry,
        shared,
        sessions,
        characters,
        monsters,
        decks,
        excluded,
        bootstrap,
    ) = registered_multiplayer_fixture()
    current = shared.fight.current
    assert not current.controlled
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=shared.fight.id
    )

    def end(fight, native):
        oracle = NativeOracle(
            native,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=sessions[0].character_id,
            flags=dict(native_start_events=True, native_area_callbacks=True),
        )
        packets = oracle.commit({"type": "end_turn"}, stats_serializer=serializer)
        return Transition(native.fight, native, packets)

    registry.execute_server(
        shared.fight.id, current.id, end, expected_sequence=shared.sequence
    )
    barrier = shared.runtime.awaiting_ack
    assert type(barrier) is int
    pending = tuple(shared.runtime.pending)
    results = []

    def release(fight, native, body):
        return Transition(fight, native, native.acknowledge_turn(body))

    for index, session in enumerate(sessions):
        results.append(
            registry.acknowledge(
                shared.fight.id, session, struct.pack(">i", barrier), release
            )
        )
        if index < len(sessions) - 1:
            assert shared.runtime.awaiting_ack == barrier
            assert tuple(shared.runtime.pending) == pending
    assert results == [False, False, True]
    assert shared.runtime.awaiting_ack is None
    return dict(
        actors=len(shared.fight.actors),
        owners=len(sessions),
        nativeAckResults=results,
        bootstrapOpcodes=bootstrap,
        currentId=shared.fight.current.id,
        privateLeases=True,
        durableStoreQualified=False,
    )


def measure(*, npc_turns=2, budget_seconds=20):
    source_files = {
        inspect.getfile(value)
        for value in (
            NativeOracle,
            RuntimeMessages,
            world_bridge.NativeSession,
            world_sources.bind_private_sources,
            fixture,
            multiplayer_fixture,
        )
    }

    def hashes():
        return {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in sorted(source_files)
        }

    source_before = hashes()
    started = time.perf_counter()
    runtime, characters, monsters, decks, excluded, description = multiplayer_fixture()
    construction_ms = (time.perf_counter() - started) * 1000
    exporter = native_exporter()
    transport = MeasuredTCPTransport("tcp://ai:8090", runtime.tactical_encounter_id)
    health = transport.request("/health", {})
    catalogue = transport.catalog(exporter)
    profiles = encounter_profiles(runtime, native_catalog._database(), monsters)
    stages = {}
    turns = []
    flags = dict(
        native_start_events=True,
        native_area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1",
    )

    def timed(name, original):
        def invoke(*args, **kwargs):
            wall, cpu = time.perf_counter(), time.thread_time()
            try:
                return original(*args, **kwargs)
            finally:
                row = stages.setdefault(
                    name, dict(calls=0, wallMs=0.0, threadCpuMs=0.0)
                )
                row["calls"] += 1
                row["wallMs"] += (time.perf_counter() - wall) * 1000
                row["threadCpuMs"] += (time.thread_time() - cpu) * 1000

        return invoke

    try:
        with ExitStack() as stack:
            try:
                from wakfu_ai.context import (
                    native_geometry_render_cache as geometry_render,
                )
            except ImportError:
                geometry_render = None
            if geometry_render is not None:
                original_render = geometry_render.rebase_fragment

                def measured_render(*args, **kwargs):
                    with geometry_render._LOCK:
                        previous_rows = tuple(
                            row[3] for row in geometry_render._CACHE.values()
                        )
                    result = original_render(*args, **kwargs)
                    hit = any(result[3] is rows for rows in previous_rows)
                    name = "geometry_render_hits" if hit else "geometry_render_misses"
                    stages.setdefault(name, dict(calls=0))["calls"] += 1
                    return result

                stack.enter_context(
                    patch.object(geometry_render, "rebase_fragment", measured_render)
                )
            for owner, attribute, name in (
                (NativeOracle, "__init__", "oracle_init"),
                (NativeOracle, "preview", "oracle_preview"),
                (NativeOracle, "commit", "oracle_commit"),
                (world_bridge, "fingerprint", "fingerprint"),
                (world_bridge, "deepcopy", "bridge_deepcopy"),
                (world_bridge, "encode_bytes", "native_graph_encode"),
                (world_bridge.NativeSession, "__init__", "session_init"),
                (world_bridge.NativeSession, "guard", "source_guard"),
                (RuntimeMessages, "__deepcopy__", "runtime_deepcopy"),
            ):
                stack.enter_context(
                    patch.object(
                        owner, attribute, timed(name, getattr(owner, attribute))
                    )
                )
            for index in range(npc_turns):
                current = runtime.fight.current
                if current.controlled:
                    raise AssertionError("Expected the next genuine NPC turn")
                profile = profiles.get(monsters[current.id]["ref"], profiles[None])
                wall, cpu = time.perf_counter(), time.thread_time()
                packets, decisions = [], []
                serializer = NativeStats(
                    characters=characters, monsters=monsters, fight_id=runtime.fight.id
                )
                for delivery, diagnostic in run_turn(
                    runtime,
                    characters=characters,
                    monsters=monsters,
                    decks=decks,
                    excluded_decks=excluded,
                    viewer_id=next(iter(characters)),
                    flags=flags,
                    transport=transport,
                    exporter=exporter,
                    policy=profile["policy"],
                    policy_version=profile["identity"],
                    stats_serializer=serializer,
                    budget_seconds=budget_seconds,
                ):
                    packets.extend(delivery)
                    decisions.append(diagnostic)
                row = dict(
                    index=index,
                    actorId=current.id,
                    wallMs=(time.perf_counter() - wall) * 1000,
                    threadCpuMs=(time.thread_time() - cpu) * 1000,
                    opcodes=dict(Counter(str(op) for op, _ in packets)),
                    packetSha256=hashlib.sha256(
                        b"".join(str(op).encode() + body for op, body in packets)
                    ).hexdigest(),
                    diagnostics=decisions,
                    awaitingAck=runtime.awaiting_ack,
                )
                turns.append(row)
                if runtime.awaiting_ack is None:
                    raise AssertionError("Native NPC turn did not arm a real ACK")
                import struct

                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                # Advance human turns only through their real owned native end.
                while runtime.fight.current.controlled:
                    owner = NativeOracle(
                        runtime,
                        characters=characters,
                        monsters=monsters,
                        decks=decks,
                        excluded_decks=excluded,
                        viewer_id=runtime.fight.current.id,
                        flags=flags,
                    )
                    owner.commit({"type": "end_turn"}, stats_serializer=serializer)
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        return dict(
            schema=1,
            sourceBefore=source_before,
            sourceAfter=hashes(),
            constructionMs=construction_ms,
            flags=flags,
            roster=dict(
                players=len(characters),
                accounts=len({c["account_id"] for c in characters.values()}),
                monsters=len(monsters),
            ),
            arenaCells=len(runtime.fight.walkable),
            stages=stages,
            turns=turns,
            rpc=transport.rpc,
            queries=dict(transport.query_counts),
            transportMetrics=transport.metrics,
            health=health,
            final=dict(
                phase=runtime.fight.phase,
                turn=runtime.fight.turn_id,
                actors={
                    str(a.id): dict(hp=a.hp, position=a.position, ap=a.ap, mp=a.mp)
                    for a in runtime.fight.actors.values()
                },
            ),
            limits=[
                "Private native fixture; no real client ACK acceptance",
                "No durable Rift wave/checkpoint publisher or reconnect/exit/create selection in this stage",
                "No responsiveness claim from native execution alone",
            ],
        )
    finally:
        transport.close()


if __name__ == "__main__":
    print(
        json.dumps(
            measure(npc_turns=int(os.environ.get("BENCHMARK_NPC_TURNS", "2"))),
            default=str,
        )
    )
