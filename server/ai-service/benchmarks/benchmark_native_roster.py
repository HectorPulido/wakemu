#!/usr/bin/env python3
"""Build complete native multi-owner PvE rosters for private AI benchmarks.

The fixture uses the same official placement, actor, snapshot, QI, and timeline
constructors as the world. It does not register synthetic socket leases or
claim that private ACK progression represents client acceptance.
"""
from collections import defaultdict, deque
import argparse
import hashlib
import gzip
import json
import os
import time
from types import SimpleNamespace
from pathlib import Path


def _connected_monster_positions(map_id, origin, count):
    """Choose deterministic reachable map cells using only exported edges."""
    from wakfu_server.combat_terrain import map_geometry

    geometry = map_geometry(map_id)
    forward = defaultdict(list)
    for source, destination in geometry["edges"]:
        forward[tuple(source)].append(tuple(destination))
    distance = {tuple(origin): 0}
    queue = deque([tuple(origin)])
    while queue:
        source = queue.popleft()
        for destination in forward[source]:
            if destination not in distance:
                distance[destination] = distance[source] + 1
                queue.append(destination)

    cells = [tuple(cell) for cell in geometry["cells"]]
    selected = []
    for minimum_distance in range(4, 32):
        for cell in cells:
            if distance.get(cell) != minimum_distance:
                continue
            if any(
                max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) <= 1
                for other in selected
            ):
                continue
            selected.append(cell)
            if len(selected) == count:
                return tuple(selected)
    raise ValueError("Map has too few separated reachable monster positions")


def fixture(
    *,
    map_id=1134,
    pc_position=(-8, -7, -1),
    monster_references=(5462, 5462, 5462, 5462, 5462, 5525),
    monster_level=1,
    fight_id=41001,
    first_character_id=7001,
    first_account_id=9001,
    first_monster_id=-2001,
    player_count=6,
    owner_accounts=None,
    ready=True,
):
    """Return a bounded native multi-owner encounter and all owned sources.

    Five reference 5462 actors exercise generic walking without an implied
    attack. The final reference 5525 owns catalogued native spell 7962 at level
    one; its cast is still accepted only if the native oracle certifies it.
    """
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import placement_messages, player_payload
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_qi_snapshot import NativeQISnapshot
    from wakfu_server.combat_qi_surface_catalog import native_qi_surface_provenance
    from wakfu_server.combat_actor import actor_effects, monster_actor_stats
    from wakfu_server.monsters import native_abilities, owned_instance
    from wakfu_server.spells import default_deck

    if (
        not 1 <= len(monster_references) <= 12
        or type(player_count) is not int
        or not 1 <= player_count <= 6
        or (owner_accounts is not None and len(owner_accounts) != player_count)
        or type(map_id) is not int
        or type(monster_level) is not int
        or len(pc_position) != 3
        or any(type(value) is not int for value in pc_position)
    ):
        raise ValueError(
            "The native roster fixture requires bounded rosters and a valid origin"
        )

    monster_positions = _connected_monster_positions(
        map_id, pc_position, len(monster_references)
    )
    monsters = {
        first_monster_id
        - index: owned_instance(
            reference,
            monster_level,
            first_monster_id - index,
            map_id=map_id,
            x=position[0],
            y=position[1],
            z=position[2],
            team=1,
            instance_id=0,
        )
        for index, (reference, position) in enumerate(
            zip(monster_references, monster_positions)
        )
    }
    arena = local_arena(
        map_id,
        0,
        tuple(pc_position),
        monster_positions,
        relocate_monsters=(len(monster_references) == 6),
    )
    pc_slots = set(arena["placement_cells"][0])
    if tuple(pc_position) not in pc_slots or len(pc_slots) < player_count:
        raise ValueError("Official placement did not supply the requested player slots")
    pc_positions = (
        tuple(pc_position),
        *sorted(pc_slots - {tuple(pc_position)})[: player_count - 1],
    )
    if len(set(pc_positions + tuple(monster_positions))) != player_count + len(
        monster_references
    ):
        raise ValueError("Official placement produced overlapping roster coordinates")

    characters = {}
    actors = []
    for index, position in enumerate(pc_positions):
        character_id = first_character_id + index
        account_id = (
            first_account_id + index
            if owner_accounts is None
            else owner_accounts[index]
        )
        character = {
            "id": character_id,
            "account_id": account_id,
            "breed": 15,
            "level": 1,
            "active_build_index": 0,
            "map_id": map_id,
            "instance_id": 0,
            "x": position[0],
            "y": position[1],
            "z": position[2],
            "hp": 60,
            "max_hp": 60,
            "builds": {},
            "inventory_items": [],
        }
        characters[character_id] = character
        actor = Actor(
            character_id,
            0,
            position,
            character["hp"],
            6,
            3,
            0,
            1,
            account_id,
            True,
            max_hp=character["max_hp"],
            direction=0,
        )
        initialize_fresh_player_cosmetics(actor, character)
        actors.append(actor)

    npc_actors = [
        Actor(
            monster["id"],
            1,
            (monster["x"], monster["y"], monster["z"]),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
            max_hp=monster["max_hp"],
            direction=3,
        )
        for monster in monsters.values()
    ]
    actors.extend(npc_actors)
    fight = Fight(
        fight_id,
        actors,
        arena["validated_cells"],
        arena["placement_cells"],
        arena["valid_edges"],
    )
    initialize_global_pv_collections(fight, tuple(fight.actors))

    qi_names = ("x", "y", "width", "height", "cell_masks")
    qi_snapshot = NativeQISnapshot({name: arena[name] for name in qi_names})
    fight.native_qi_snapshot = {
        "x": qi_snapshot.x,
        "y": qi_snapshot.y,
        "width": qi_snapshot.width,
        "height": qi_snapshot.height,
        "cell_masks": list(qi_snapshot.masks),
    }
    freeze_terrain(fight)
    provenance = arena.get("native_qi_surface_provenance")
    if provenance != native_qi_surface_provenance(map_id):
        raise ValueError("Official arena QI surface provenance changed")
    fight.native_qi_surface_provenance = dict(provenance)
    fight.native_obstacle_cells = (
        frozenset() if arena.get("team_values") == [] else None
    )

    wp_resources = {actor_id: (6, 6) for actor_id in characters}
    wp_resources.update(
        {
            monster_id: (monster["wp"], monster["wp"])
            for monster_id, monster in monsters.items()
        }
    )
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters=monsters,
        wp_resources=wp_resources,
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
    )

    payloads = {
        character_id: player_payload(
            characters[character_id], fight.actors[character_id], fight_id, wp=6
        )
        for character_id in characters
    }
    payloads.update(
        {
            monster_id: (
                monster_actor_stats(
                    monster,
                    fight_id,
                    direction=3,
                    obstacle_id=fight.actors[monster_id].native_obstacle_id,
                ),
                actor_effects(),
            )
            for monster_id, monster in monsters.items()
        }
    )
    placement_packets = placement_messages(
        fight,
        arena,
        payloads,
        terrain_effect_id=46,
        terrain_instance_id=-300,
        leaders={0: next(iter(characters)), 1: next(iter(monsters))},
    )
    if ready:
        for account_id in dict.fromkeys(
            character["account_id"] for character in characters.values()
        ):
            fight.ready(account_id)

    runtime = RuntimeMessages(fight)
    decks = {
        identity: default_deck(character) for identity, character in characters.items()
    }
    excluded_decks = {identity: frozenset() for identity in characters}
    abilities = {
        str(monster["id"]): native_abilities(monster["ref"], monster["level"])
        for monster in monsters.values()
    }
    description = SimpleNamespace(
        map_id=map_id,
        arena=arena,
        pc_ids=tuple(characters),
        monster_ids=tuple(monsters),
        pc_positions=pc_positions,
        monster_positions=monster_positions,
        abilities=abilities,
        placement_packets=placement_packets,
        join_context={
            "arena": arena,
            "terrain_effect_id": 46,
            "terrain_instance_id": -300,
            "leaders": {0: next(iter(characters)), 1: next(iter(monsters))},
            "duration_ms": 60000,
            "monsters": monsters,
            "roster": {
                "owners": [
                    character["account_id"] for character in characters.values()
                ],
                "characters": list(characters),
                "monsters": list(monsters),
            },
            "benchmarkFutureField": {"kept": True, "schema": 1},
        },
        completeRoster=True,
        rosterSource="explicit benchmark characters and owned_instance monsters initialized by official native constructors; not live Store leases",
        privateAckHarnessOnly=True,
        sharedRegistryAdmission="not_used",
    )
    from wakfu_ai.context.native_context import encode_bytes

    # Carry complete synthetic join metadata, including an unknown future
    # field, through the normal complete-state graph. This is benchmark data,
    # not a fabricated SharedFight/Registry lease.
    raw_context = encode_bytes({"join_context": description.join_context})
    runtime.native_ai_shared_context = gzip.compress(
        raw_context, compresslevel=1, mtime=0
    )
    description.join_context_raw_bytes = len(raw_context)
    description.join_context_compressed_bytes = len(runtime.native_ai_shared_context)
    return runtime, characters, monsters, decks, excluded_decks, description


def fresh_private_turn_ack(runtime):
    """Consume only the native turn barrier in a benchmark-private runtime."""
    import struct

    turn = runtime.awaiting_ack
    if type(turn) is not int:
        raise ValueError("Private benchmark expected a pending native turn ACK")
    return runtime.acknowledge_turn(struct.pack(">i", turn))


def _opcode_counts(packets):
    counts = {}
    for packet in packets:
        if isinstance(packet, (tuple, list)) and packet:
            key = str(packet[0])
            counts[key] = counts.get(key, 0) + 1
    return counts


def _source_hashes():
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "ai-service/benchmarks/benchmark_native_roster.py",
        root / "ai-service/wakfu_ai/native/native_turn.py",
        root / "ai-service/wakfu_ai/native/native_oracle.py",
        root / "ai-service/wakfu_ai/native/native_stats.py",
        root / "ai-service/wakfu_ai/bridge/world_bridge.py",
        root / "ai-service/wakfu_ai/bridge/world_entry.py",
        root / "ai-service/wakfu_ai/context/native_context.py",
        root / "ai-service/wakfu_ai/http/server.py",
        root / "wakfu_server/combat/combat_state.py",
        root / "wakfu_server/combat/combat_qi_fight.py",
        root / "wakfu_server/combat/combat_actor_snapshot.py",
        root / "wakfu_server/combat/combat_terrain.py",
        root / "wakfu_server/combat/combat_shared.py",
        root / "wakfu_server/combat/combat_runtime_messages.py",
    )
    result = {}
    for path in paths:
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def _construction_record(runtime, characters, monsters, description):
    from wakfu_ai.context.native_context import NativeGraph

    fight = runtime.fight
    compressed_graph = NativeGraph(runtime.native_ai_shared_context)
    raw_graph = NativeGraph(gzip.decompress(runtime.native_ai_shared_context))
    return {
        "mapId": description.map_id,
        "fightId": fight.id,
        "phase": fight.phase,
        "rosterSource": description.rosterSource,
        "roster": {
            "characters": list(characters),
            "monsterActorIds": list(monsters),
            "actorCount": len(fight.actors),
            "teamCounts": {
                str(team): sum(actor.team == team for actor in fight.actors.values())
                for team in (0, 1)
            },
            "owners": [character["account_id"] for character in characters.values()],
        },
        "arena": {
            "cells": len(fight.walkable),
            "directedEdges": len(fight.edges),
            "placementSlots": {
                str(team): len(cells) for team, cells in fight.placement.items()
            },
            "qiSlots": sum(slot is not None for slot in fight.native_qi_slots),
        },
        "initialOrder": list(fight.order),
        "initialCurrentActor": fight.current.id,
        "monsterReferences": {
            str(identity): monster["ref"] for identity, monster in monsters.items()
        },
        "nativeAbilities": description.abilities,
        "nativeAiSpellDependency": (
            "5525 owns level-1 native spell 7962; execution is reported only if the"
            " full oracle accepts and commits it"
        ),
        "genericWalkerDependency": "reference 5462 has no native abilities; movement only",
        "placementPacketCount": len(description.placement_packets),
        "placementOpcodes": _opcode_counts(description.placement_packets),
        "privateAckHarnessOnly": True,
        "clientAckSimulated": False,
        "clientAcceptanceClaim": False,
        "sharedRegistryAdmission": description.sharedRegistryAdmission,
        "completeJoinContextKeys": sorted(description.join_context),
        "completeJoinContextBytes": len(runtime.native_ai_shared_context),
        "rawDecodedJoinContextBytes": description.join_context_raw_bytes,
        "compressedJoinContextBytes": description.join_context_compressed_bytes,
        "completeJoinContextSha256": hashlib.sha256(
            runtime.native_ai_shared_context
        ).hexdigest(),
        "completeJoinContextRoundTrip": compressed_graph.data == raw_graph.data,
        "futureJoinContextFieldPreserved": description.join_context[
            "benchmarkFutureField"
        ],
    }


def _run_encounter(
    runtime,
    characters,
    monsters,
    decks,
    excluded,
    description,
    transport,
    exporter,
    *,
    budget_seconds,
    rounds,
    record=None,
    progress=None,
    max_npc_turns=None,
):
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.native.native_turn import run_turn
    from wakfu_ai.bridge.world_bridge import NativeSession

    record = record or _construction_record(runtime, characters, monsters, description)
    record.update(
        turns=[], decisions=[], commits=[], sourceGuardChecks=0, sourceGuardFailures=[]
    )
    stats = NativeStats(
        characters=characters, monsters=monsters, fight_id=runtime.fight.id
    )
    original_guard = NativeSession.guard
    active = {"round": None, "actorId": None}
    request_rows = []
    record["transport"] = request_rows
    original_request = transport.request

    def observed_request(endpoint, payload):
        started = time.monotonic()
        try:
            reply = original_request(endpoint, payload)
            if endpoint == "/v3/decide" and isinstance(reply, dict):
                exchange = {
                    "round": active["round"],
                    "actorId": active["actorId"],
                    "requestId": payload.get("requestId"),
                    "replyStatus": reply.get("status"),
                    "elapsedSeconds": time.monotonic() - started,
                    "backendPreparation": reply.get("backendPreparation"),
                    "queryOperations": [
                        {
                            "id": query.get("id"),
                            "operation": query.get("operation"),
                            "action": query.get("action"),
                            "actors": query.get("actors"),
                            "depth": query.get("depth"),
                        }
                        for query in reply.get("queries", [])
                        if isinstance(query, dict)
                    ]
                    if isinstance(reply.get("queries", []), list)
                    else [],
                    "queryResponse": {
                        key: payload["response"].get(key)
                        for key in ("id", "supported", "unknownDependencies")
                        if isinstance(payload.get("response"), dict)
                        and key in payload["response"]
                    },
                    "decision": reply.get("decision"),
                }
                if exchange["replyStatus"] == "decided":
                    record["decisions"].append(exchange)
                request_rows.append(exchange)
            return reply
        finally:
            if endpoint != "/v3/decide":
                request_rows.append(
                    {
                        "round": active["round"],
                        "actorId": active["actorId"],
                        "endpoint": endpoint,
                        "elapsedSeconds": time.monotonic() - started,
                    }
                )

    def observed_guard(session):
        try:
            result = original_guard(session)
            record["sourceGuardChecks"] += 1
            return result
        except Exception as error:
            record["sourceGuardFailures"].append(
                type(error).__name__ + ": " + str(error)
            )
            raise

    transport.request = observed_request
    NativeSession.guard = observed_guard
    try:
        initial_native_round = runtime.fight.native_timeline_round
        target_native_round = initial_native_round + rounds
        record["initialNativeRound"] = initial_native_round
        record["targetNativeRoundExclusive"] = target_native_round
        maximum_activations = max(24, len(runtime.fight.actors) * rounds * 3)
        activation = 0
        while (
            runtime.fight.phase == "active"
            and runtime.fight.native_timeline_round < target_native_round
            and activation < maximum_activations
            and (
                max_npc_turns is None
                or sum(not row["controlled"] for row in record["turns"]) < max_npc_turns
            )
        ):
            actor = runtime.fight.current
            if actor is None:
                break
            activation += 1
            round_number = runtime.fight.native_timeline_round
            active.update(round=round_number, actorId=actor.id)
            before_state = {
                "hp": actor.hp,
                "ap": actor.ap,
                "mp": actor.mp,
                "position": list(actor.position),
                "turnId": runtime.fight.turn_id,
                "turnCount": actor.turn_count,
            }
            all_actors_before = {
                identity: {
                    "hp": value.hp,
                    "ap": value.ap,
                    "mp": value.mp,
                    "position": list(value.position),
                }
                for identity, value in runtime.fight.actors.items()
            }
            if actor.controlled:
                if progress is not None:
                    progress(
                        record,
                        dict(
                            phase="owner_turn_started",
                            mapId=description.map_id,
                            round=round_number,
                            actorId=actor.id,
                        ),
                    )
                started = time.monotonic()
                packets = runtime.end_turn(actor.owner_id, actor.id, actor.turn_count)
                ack_turn = runtime.awaiting_ack
                ack_packets = []
                if ack_turn is not None:
                    ack_packets = fresh_private_turn_ack(runtime)
                record["turns"].append(
                    {
                        "round": round_number,
                        "actorId": actor.id,
                        "controlled": True,
                        "action": {"type": "owner_skip_harness"},
                        "elapsedSeconds": time.monotonic() - started,
                        "packets": len(packets),
                        "opcodes": _opcode_counts(packets),
                        "privateTurnAckConsumed": ack_turn is not None,
                        "privateAckTurn": ack_turn,
                        "privateAckReleasedPackets": len(ack_packets),
                        "privateAckReleasedOpcodes": _opcode_counts(ack_packets),
                        "before": before_state,
                        "afterActorId": runtime.fight.current.id
                        if runtime.fight.current
                        else None,
                    }
                )
                if progress is not None:
                    progress(
                        record,
                        dict(
                            phase="owner_turn_completed",
                            mapId=description.map_id,
                            round=round_number,
                            actorId=actor.id,
                        ),
                    )
                continue

            turn_started = time.monotonic()
            if progress is not None:
                progress(
                    record,
                    dict(
                        phase="npc_turn_started",
                        mapId=description.map_id,
                        round=round_number,
                        actorId=actor.id,
                        reference=monsters[actor.id]["ref"],
                    ),
                )
            turn_events = []
            runtime.native_ai_preparation_started_at = turn_started
            for packets, diagnostic in run_turn(
                runtime,
                characters=characters,
                monsters=monsters,
                decks=decks,
                excluded_decks=excluded,
                viewer_id=next(iter(characters)),
                flags=dict(
                    native_area_callbacks=os.environ.get(
                        "WAKFU_NATIVE_AREA_CALLBACKS", "0"
                    )
                    == "1",
                    native_start_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1")
                    == "1",
                    native_environment={
                        key: value
                        for key, value in os.environ.items()
                        if key.startswith("WAKFU_NATIVE_")
                    },
                ),
                transport=transport,
                exporter=exporter,
                policy={},
                policy_version="native-6v6-private-benchmark",
                stats_serializer=stats,
                budget_seconds=budget_seconds,
            ):
                action = diagnostic.get("action", {})
                event = {
                    "action": action,
                    "reason": diagnostic.get("reason"),
                    "stage": diagnostic.get("stage"),
                    "elapsedMs": diagnostic.get("elapsedMs"),
                    "turnBudgetMs": diagnostic.get("turnBudgetMs"),
                    "stageElapsedMs": diagnostic.get("stageElapsedMs"),
                    "backendPreparation": diagnostic.get("backendPreparation"),
                    "transportMetrics": json.loads(json.dumps(transport.metrics)),
                    "requestId": diagnostic.get("requestId"),
                    "fightInstanceId": diagnostic.get("fightInstanceId"),
                    "sourceRevision": diagnostic.get("sourceRevision"),
                    "policyVersion": diagnostic.get("policyVersion"),
                    "producerTrace": diagnostic.get("producerTrace"),
                    "packets": len(packets),
                    "opcodes": _opcode_counts(packets),
                }
                turn_events.append(event)
                if action.get("type") != "end_turn" and packets:
                    record["commits"].append(
                        {
                            "round": round_number,
                            "actorId": actor.id,
                            "action": action,
                            "packetCount": len(packets),
                            "opcodes": _opcode_counts(packets),
                            "actionCounter": runtime.fight.sequence,
                            "awaitingAck": runtime.awaiting_ack,
                            "pendingPackets": len(runtime.pending),
                            "actorAfter": {
                                "hp": runtime.fight.actors[actor.id].hp,
                                "ap": runtime.fight.actors[actor.id].ap,
                                "mp": runtime.fight.actors[actor.id].mp,
                                "position": list(
                                    runtime.fight.actors[actor.id].position
                                ),
                            },
                        }
                    )
            if runtime.awaiting_ack is not None:
                ack_turn = runtime.awaiting_ack
                ack_packets = fresh_private_turn_ack(runtime)
                ack_consumed = True
            else:
                ack_turn = None
                ack_packets = []
                ack_consumed = False
            all_actors_after = {
                identity: {
                    "hp": value.hp,
                    "ap": value.ap,
                    "mp": value.mp,
                    "position": list(value.position),
                }
                for identity, value in runtime.fight.actors.items()
            }
            actor_changes = {
                str(identity): {"before": all_actors_before[identity], "after": state}
                for identity, state in all_actors_after.items()
                if all_actors_before.get(identity) != state
            }
            record["turns"].append(
                {
                    "round": round_number,
                    "actorId": actor.id,
                    "controlled": False,
                    "reference": monsters[actor.id]["ref"],
                    "nativeAbilities": description.abilities[str(actor.id)],
                    "turnId": before_state["turnId"],
                    "before": before_state,
                    "elapsedSeconds": time.monotonic() - turn_started,
                    "ownerDeadlineSeconds": budget_seconds,
                    "events": turn_events,
                    "privateAckTurn": ack_turn,
                    "privateTurnAckConsumed": ack_consumed,
                    "privateAckReleasedPackets": len(ack_packets),
                    "privateAckReleasedOpcodes": _opcode_counts(ack_packets),
                    "actorChanges": actor_changes,
                    "awaitingAckAfterHarness": runtime.awaiting_ack,
                    "afterActorId": runtime.fight.current.id
                    if runtime.fight.current
                    else None,
                    "afterRound": runtime.fight.native_timeline_round,
                }
            )
            if progress is not None:
                progress(
                    record,
                    dict(
                        phase="npc_turn_completed",
                        mapId=description.map_id,
                        round=round_number,
                        actorId=actor.id,
                        elapsedSeconds=record["turns"][-1]["elapsedSeconds"],
                        actionCount=len(turn_events),
                        ackConsumed=ack_consumed,
                    ),
                )
        record["fightPhaseAfter"] = runtime.fight.phase
        record["npcTurnsCompleted"] = sum(
            not turn["controlled"] for turn in record["turns"]
        )
        record["npcTurnsExpected"] = len(monsters) * rounds
        record["requestedRoundsCompleted"] = (
            record["npcTurnsCompleted"] == record["npcTurnsExpected"]
            or runtime.fight.phase != "active"
        )
        record["npcTurnLimit"] = max_npc_turns
        record["requestedWorkloadCompleted"] = (
            record["requestedRoundsCompleted"]
            if max_npc_turns is None
            else record["npcTurnsCompleted"]
            == min(max_npc_turns, record["npcTurnsExpected"])
            or runtime.fight.phase != "active"
        )
        if not record["requestedWorkloadCompleted"]:
            raise RuntimeError(
                f"Expected {record['npcTurnsExpected']} NPC turns across {rounds} completed "
                f"native timeline rounds; observed {record['npcTurnsCompleted']} with "
                f"phase={runtime.fight.phase!r}, nativeRound={runtime.fight.native_timeline_round}"
            )
        record["fightInstanceId"] = getattr(runtime, "tactical_encounter_id", None)
        record["finalRound"] = runtime.fight.native_timeline_round
        record["finalActorId"] = (
            runtime.fight.current.id if runtime.fight.current else None
        )
        record["awaitingAckAtEnd"] = runtime.awaiting_ack
        record["privateAckHarnessOnly"] = True
        record["clientAckSimulated"] = False
        record["clientAcceptanceClaim"] = False
        record[
            "sharedRegistryAdmission"
        ] = "not_used; complete 12-actor roster is initialized natively before the private oracle run"
        record["sourceGuardIntact"] = (
            record["sourceGuardChecks"] >= len(record["commits"])
            and not record["sourceGuardFailures"]
        )
    finally:
        transport.request = original_request
        NativeSession.guard = original_guard
    record["transport"] = request_rows
    return record


def _main(
    fixture_only=False,
    budget_seconds=10,
    rounds=2,
    map_id="both",
    cold_catalog=False,
    max_npc_turns=None,
):
    positions = {
        1134: (-8, -7, -1),
        527: (-217, -35, 0),
    }
    map_ids = (1134, 527) if map_id == "both" else (map_id,)
    encounters = []
    for selected in map_ids:
        print(
            json.dumps({"progress": "fixture_construction_started", "mapId": selected}),
            flush=True,
        )
        encounter = fixture(map_id=selected, pc_position=positions[selected])
        encounters.append(encounter)
        print(
            json.dumps(
                {"progress": "fixture_construction_completed", "mapId": selected}
            ),
            flush=True,
        )
    constructions = [
        _construction_record(runtime, characters, monsters, description)
        for runtime, characters, monsters, _, _, description in encounters
    ]
    if fixture_only:
        print(json.dumps({"constructions": constructions}, indent=2, sort_keys=True))
        return

    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    from wakfu_ai.bridge.world_bridge import ContextTransport
    from wakfu_ai.bridge.world_entry import native_exporter

    repository = Path(__file__).resolve().parents[2]
    runtime_root = Path(
        os.environ.get(
            "E18_BENCHMARK_OUTPUT_DIR",
            "/data" if Path("/data").is_dir() else str(repository / ".runtime"),
        )
    )
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_metadata = {
        "worldImage": os.environ.get("E18_WORLD_IMAGE"),
        "worldStartedAt": os.environ.get("E18_WORLD_STARTED_AT"),
        "engineContainerMode": os.environ.get("E18_ENGINE_CONTAINER_MODE", "world"),
        "liveWorldAtStart": os.environ.get("E18_LIVE_WORLD_AT_START"),
        "aiImage": os.environ.get("E18_AI_IMAGE"),
        "aiStartedAt": os.environ.get("E18_AI_STARTED_AT"),
        "sourceHashesBefore": _source_hashes(),
        "sourceHashesAfter": None,
        "worldIdentityDrift": None,
        "worldIdentityCheck": "external docker monitor writes drift evidence; this process has no Docker API",
        "progress": {"phase": "initializing"},
    }
    partial_path = runtime_root / "native-6v6-roster-turns.progress.json"
    final_path = runtime_root / "native-6v6-roster-turns.json"
    record = {
        **run_metadata,
        "budgetSeconds": budget_seconds,
        "roundsRequested": rounds,
        "encounters": [],
        "allTransport": [],
    }

    def write_progress(encounter_record=None, event=None):
        if event is not None:
            record["progress"] = event
        record["partialEncounter"] = encounter_record
        temporary = partial_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, partial_path)
        print(json.dumps({"progress": record["progress"]}, sort_keys=True), flush=True)

    write_progress(event={"phase": "native_prewarm_started"})
    warm_started = time.monotonic()
    prewarm_runtime_catalogs()
    prewarm_seconds = time.monotonic() - warm_started
    write_progress(
        event={"phase": "native_prewarm_completed", "seconds": prewarm_seconds}
    )
    exporter = native_exporter()
    write_progress(event={"phase": "exporter_inventory_started"})
    inventory_started = time.monotonic()
    manifest = None
    if not cold_catalog:
        manifest, _ = exporter.inventory()
    inventory_seconds = time.monotonic() - inventory_started
    write_progress(
        event={"phase": "exporter_inventory_completed", "seconds": inventory_seconds}
    )
    parser_url = getattr(_main, "backend_url", "http://ai:8090")
    transport = ContextTransport(parser_url, timeout=30)
    record.update(
        {
            "backendUrl": parser_url,
            "prewarmSecondsOutsideOwnerTurns": prewarm_seconds,
            "exporterInventorySecondsOutsideOwnerTurns": inventory_seconds,
            "coldCatalog": cold_catalog,
            "maxNpcTurns": max_npc_turns,
            "exporterManifestEntryCount": len(manifest["entries"])
            if manifest
            else None,
            "exporterManifestSha256": hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if manifest
            else None,
            "catalogSource": "full native exporter manifest; backend is the running AI service",
            "sourceHashes": _source_hashes(),
        }
    )
    for runtime, characters, monsters, decks, excluded, description in encounters:
        encounter_record = _construction_record(
            runtime, characters, monsters, description
        )
        record["encounters"].append(encounter_record)
        encounter = _run_encounter(
            runtime,
            characters,
            monsters,
            decks,
            excluded,
            description,
            transport,
            exporter,
            budget_seconds=budget_seconds,
            rounds=rounds,
            record=encounter_record,
            progress=write_progress,
            max_npc_turns=max_npc_turns,
        )
        encounter["transportStartIndex"] = len(record["allTransport"])
        record["allTransport"].extend(encounter.pop("transport"))
        record["partialEncounter"] = None
        write_progress(
            event={"phase": "encounter_completed", "mapId": description.map_id}
        )

    record["sourceHashesAfter"] = _source_hashes()
    record["sourceHashStable"] = (
        record["sourceHashesBefore"] == record["sourceHashesAfter"]
    )
    record["progress"] = {"phase": "completed"}
    final_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    partial_path.unlink(missing_ok=True)
    print(json.dumps(record, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-only", action="store_true")
    parser.add_argument(
        "--cold-catalog",
        action="store_true",
        help="Include the first exporter inventory in the measured turn",
    )
    parser.add_argument(
        "--max-npc-turns",
        type=int,
        help="Stop after this many private NPC turns per encounter",
    )
    parser.add_argument("--budget-seconds", type=float, default=10)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--url", default="http://ai:8090")
    parser.add_argument("--map-id", choices=("both", "527", "1134"), default="both")
    arguments = parser.parse_args()
    if arguments.rounds < 2:
        parser.error("--rounds must include the first and following round")
    if arguments.max_npc_turns is not None and arguments.max_npc_turns < 1:
        parser.error("--max-npc-turns must be positive")
    _main.backend_url = arguments.url
    _main(
        fixture_only=arguments.fixture_only,
        budget_seconds=arguments.budget_seconds,
        rounds=arguments.rounds,
        map_id="both" if arguments.map_id == "both" else int(arguments.map_id),
        cold_catalog=arguments.cold_catalog,
        max_npc_turns=arguments.max_npc_turns,
    )


if __name__ == "__main__":
    main()
