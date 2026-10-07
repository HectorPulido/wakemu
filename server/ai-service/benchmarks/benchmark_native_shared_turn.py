#!/usr/bin/env python3
"""Measure a full native HTTP turn through the real shared-fight Registry.

Diagnostic only. It provisions the complete SDK/catalogue before the clock,
uses the complete native arena, and deliberately leaves the real client ACK
barrier armed when the turn finishes.
"""
import json
from pathlib import Path
import tempfile
import threading
import time

from wakfu_ai.context.catalog_bootstrap import provision
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.native.native_turn import run_turn
from wakfu_ai.http.server import BoundedHTTPServer, Handler
from wakfu_ai.http import server as ai_service
from wakfu_ai.bridge.world_bridge import ContextTransport


def _counts(packets):
    result = {}
    for packet in packets:
        if isinstance(packet, (tuple, list)) and packet:
            key = str(packet[0])
            result[key] = result.get(key, 0) + 1
    return result


def main():
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    from wakfu_server.combat_shared import Registry, Session
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.bridge.world_bridge import CompleteContextExporter
    from wakfu_ai.bridge.world_shared import run_shared_turn
    from benchmarks.benchmark_native_turn_http import _fixture
    from wakfu_ai.bridge.world_entry import native_exporter
    from wakfu_ai.planning.team_blackboard import observe, confirm

    repo = Path(__file__).resolve().parents[2]
    runtime_root = repo.parent / ".runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    prewarm_runtime_catalogs()
    prewarm_seconds = time.monotonic() - started
    exporter = native_exporter()
    inventory_started = time.monotonic()
    exporter.inventory()
    inventory_seconds = time.monotonic() - inventory_started

    with tempfile.TemporaryDirectory(
        prefix="native-shared-turn-", dir=runtime_root
    ) as store_path:
        store = ContextStore(store_path)
        provision_started = time.monotonic()
        provision_result = provision(exporter.roots, store)
        provision_seconds = time.monotonic() - provision_started

        old_store = ai_service._CONTEXT_STORE
        ai_service._CONTEXT_STORE = store
        listener = BoundedHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=listener.serve_forever, daemon=True)
        worker.start()
        try:
            runtime, characters, monsters, decks, excluded, fixture = _fixture()
            # Seed a restored confirmed outcome through the same blackboard
            # writer used after local send or shared Registry publication.
            # This verifies the next AI query receives a valid team focus.
            runtime.tactical_encounter_id = "benchmark-confirmed-previous-outcome"
            previous = observe(runtime.fight)
            fixture.pc.hp -= 5
            fixture.character["hp"] = fixture.pc.hp
            runtime.fight.sequence += 1
            confirm(runtime, previous, [dict(action={"type": "cast", "spellId": 7962})])
            session = Session(9, 7, "benchmark", 1134, 0)
            registry = Registry(lambda current: current == session)
            shared = registry.register(runtime.fight, session, runtime=runtime)
            adapter = type("SharedAdapter", (), {"registry": registry})()
            stats = NativeStats(
                characters=characters, monsters=monsters, fight_id=runtime.fight.id
            )
            transport = ContextTransport(
                "http://%s:%s" % listener.server_address, timeout=30
            )
            record = {
                "budgetSeconds": 5,
                "configuredDefaultBudgetSeconds": 5,
                "arenaCells": len(runtime.fight.walkable),
                "arenaEdges": len(runtime.fight.edges),
                "preparations": [],
                "decisions": [],
                "commits": [],
                "http": {},
                "sharedSequenceBefore": shared.sequence,
                "restoredConfirmedTeamContext": runtime.fight.native_ai_team_context[
                    "1"
                ],
            }
            active = {"record": record, "turnStarted": time.monotonic()}

            original_init = __import__("world_bridge").NativeSession.__init__
            original_decide = __import__("world_bridge").NativeSession.decide
            original_envelope = __import__("world_bridge").NativeSession.envelope
            original_guard = __import__("world_bridge").NativeSession.guard
            original_commit = NativeOracle.commit
            original_request = transport.request

            def observed_init(native_session, *args, **kwargs):
                t0 = time.monotonic()
                result = original_init(native_session, *args, **kwargs)
                record["preparations"].append(
                    {
                        "elapsedStart": t0 - active["turnStarted"],
                        "seconds": time.monotonic() - t0,
                        "catalogManifestSupplied": kwargs.get("catalog_manifest")
                        is not None,
                    }
                )
                return result

            def observed_decide(native_session, *args, **kwargs):
                row = {"elapsedStart": time.monotonic() - active["turnStarted"]}
                t0 = time.monotonic()
                try:
                    result = original_decide(native_session, *args, **kwargs)
                    row["decision"] = result
                    return result
                except Exception as error:
                    row["error"] = type(error).__name__ + ": " + str(error)
                    raise
                finally:
                    row["seconds"] = time.monotonic() - t0
                    record["decisions"].append(row)

            def observed_envelope(native_session):
                started_envelope = time.monotonic()
                envelope = original_envelope(native_session)
                record.setdefault("envelopeTeamContexts", []).append(
                    envelope["teamContext"]
                )
                root = envelope.get("root", {})
                topology = root.get("topologyDistances")
                record.setdefault("topologyMeasurements", []).append(
                    {
                        "seconds": time.monotonic() - started_envelope,
                        "cellCount": root.get("topologyCellCount"),
                        "distances": topology,
                        "actorsMeasured": len(topology)
                        if isinstance(topology, dict)
                        else None,
                        "unknown": topology is None,
                    }
                )
                return envelope

            def observed_guard(native_session):
                record["sourceGuardChecks"] = record.get("sourceGuardChecks", 0) + 1
                try:
                    return original_guard(native_session)
                except Exception as error:
                    record.setdefault("sourceGuardFailures", []).append(
                        type(error).__name__ + ": " + str(error)
                    )
                    raise

            def observed_commit(oracle, action, *, stats_serializer):
                row = {
                    "elapsedSeconds": time.monotonic() - active["turnStarted"],
                    "action": action,
                    "awaitingAckBefore": oracle.runtime.awaiting_ack,
                    "pendingBefore": len(oracle.runtime.pending),
                }
                t0 = time.monotonic()
                try:
                    packets = original_commit(
                        oracle, action, stats_serializer=stats_serializer
                    )
                    counts = _counts(packets)
                    row.update(
                        opcodeCounts=counts,
                        packetCount=len(packets),
                        fifo13420=counts.get("13420", 0),
                        outbound13510=counts.get("13510", 0),
                        awaitingAckAfter=oracle.runtime.awaiting_ack,
                        pendingAfter=len(oracle.runtime.pending),
                        actors={
                            str(key): {
                                "hp": actor.hp,
                                "ap": actor.ap,
                                "mp": actor.mp,
                                "position": list(actor.position),
                            }
                            for key, actor in oracle.runtime.fight.actors.items()
                        },
                    )
                    return packets
                finally:
                    row["commitSeconds"] = time.monotonic() - t0
                    record["commits"].append(row)

            def observed_request(endpoint, payload):
                row = record["http"].setdefault(endpoint, {"calls": 0, "seconds": 0.0})
                row["calls"] += 1
                if endpoint == "/v3/decide":
                    record.setdefault("serviceTeamContexts", []).append(
                        payload.get("teamContext")
                    )
                t0 = time.monotonic()
                try:
                    return original_request(endpoint, payload)
                finally:
                    row["seconds"] += time.monotonic() - t0

            from wakfu_ai.bridge.world_bridge import NativeSession

            NativeSession.__init__ = observed_init
            NativeSession.decide = observed_decide
            NativeSession.envelope = observed_envelope
            NativeSession.guard = observed_guard
            NativeOracle.commit = observed_commit
            transport.request = observed_request
            try:
                active["turnStarted"] = time.monotonic()

                def runner(candidate):
                    yield from run_turn(
                        candidate,
                        characters=characters,
                        monsters=monsters,
                        decks=decks,
                        excluded_decks=excluded,
                        viewer_id=7,
                        flags={},
                        transport=transport,
                        exporter=exporter,
                        policy={},
                        policy_version="native-shared-benchmark",
                        stats_serializer=stats,
                    )

                deliveries = list(run_shared_turn(runtime, adapter, session, runner))
                record["totalSeconds"] = time.monotonic() - active["turnStarted"]
                record["diagnostics"] = [diagnostic for _, diagnostic in deliveries]
                record["sharedSequenceAfter"] = shared.sequence
                record["sharedFightIdentityRetained"] = (
                    shared.runtime.fight is shared.fight
                )
                record["sharedAwaitingAck"] = shared.runtime.awaiting_ack
                record["sharedPendingCount"] = len(shared.runtime.pending)
                record["ackBarrierTurn"] = shared.ack.turn
                record["ackParticipants"] = len(shared.ack.expected)
                batches = registry.drain(runtime.fight.id, session)
                packets = [packet for batch in batches for packet in batch.packets]
                record["outboxBatches"] = len(batches)
                record["outboxSequence"] = [batch.sequence for batch in batches]
                record["outboxPacketCount"] = len(packets)
                record["outboxOpcodes"] = _counts(packets)
                record["outboxHasTurnEnd"] = "12502" in _counts(packets)
                record["clientAckSimulated"] = False
                record["sourceGuardIntact"] = bool(
                    record.get("sourceGuardChecks")
                ) and not record.get("sourceGuardFailures")
                record["serviceSawConfirmedFocus"] = any(
                    isinstance(context, dict) and context.get("focusId") == 7
                    for context in record.get("serviceTeamContexts", [])
                )
                record["sourceRootAwaitingAck"] = runtime.awaiting_ack
                record["sourceRootHp"] = fixture.pc.hp
            finally:
                NativeSession.__init__ = original_init
                NativeSession.decide = original_decide
                NativeSession.envelope = original_envelope
                NativeSession.guard = original_guard
                NativeOracle.commit = original_commit

        finally:
            listener.shutdown()
            listener.server_close()
            worker.join()
            ai_service._CONTEXT_STORE = old_store

    result = {
        "prewarmSecondsOutsideTurn": prewarm_seconds,
        "exporterInventoryWarmSecondsOutsideTurn": inventory_seconds,
        "completeCatalogProvisionSecondsOutsideTurn": provision_seconds,
        "provision": provision_result,
        "measurement": record,
    }
    artifact = runtime_root / "native-shared-turn-http-budget5.json"
    artifact.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
