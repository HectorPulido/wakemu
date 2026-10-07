#!/usr/bin/env python3
"""Compare complete native turn negotiation with empty/preloaded AI stores.

Diagnostic only: one ephemeral localhost AI listener, real HTTP transport,
full native arena/catalogue, independent encounters, and no client ACK replay.
"""
import base64
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


def _fixture():
    from benchmarks.benchmark_native_fixture import fixture

    return fixture()


def main():
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    from wakfu_server.paths import DATA_ROOT
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.bridge.world_bridge import NativeSession
    from wakfu_ai.bridge.world_entry import native_exporter

    root = Path(__file__).resolve().parents[2]
    runtime_root = root.parent / ".runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    prewarm_started = time.monotonic()
    prewarm_runtime_catalogs()
    prewarm_seconds = time.monotonic() - prewarm_started

    exporter = native_exporter()
    inventory_started = time.monotonic()
    exporter.inventory()  # Warm only the exporter hash cache, outside each turn clock.
    exporter_inventory_seconds = time.monotonic() - inventory_started

    # Provision the complete source set once, outside both preloaded turn clocks.
    with tempfile.TemporaryDirectory(
        prefix="native-turn-preloaded-", dir=runtime_root
    ) as preloaded_path, tempfile.TemporaryDirectory(
        prefix="native-turn-empty-", dir=runtime_root
    ) as empty_path:
        preloaded_store = ContextStore(preloaded_path)
        provision_started = time.monotonic()
        provision_result = provision(exporter.roots, preloaded_store)
        provision_seconds = time.monotonic() - provision_started

        old_store = ai_service._CONTEXT_STORE
        listener = BoundedHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=listener.serve_forever, daemon=True)
        worker.start()
        measurements = []
        active = {"record": None}
        transport_url = "http://%s:%s" % listener.server_address

        original_init = NativeSession.__init__
        original_decide = NativeSession.decide
        original_commit = NativeOracle.commit

        def observed_init(session, *args, **kwargs):
            record = active["record"]
            started = time.monotonic()
            supplied = kwargs.get("catalog_manifest")
            try:
                return original_init(session, *args, **kwargs)
            finally:
                record["preparations"].append(
                    {
                        "startedAtTurnSeconds": time.monotonic()
                        - record["turnStarted"],
                        "seconds": time.monotonic() - started,
                        "catalogManifestSupplied": supplied is not None,
                        "catalogManifest": getattr(session, "catalog", None),
                    }
                )

        def observed_decide(session, *args, **kwargs):
            record = active["record"]
            row = {
                "catalogManifest": session.catalog,
                "startedAtTurnSeconds": time.monotonic() - record["turnStarted"],
            }
            started = time.monotonic()
            try:
                decision = original_decide(session, *args, **kwargs)
                row["decision"] = decision
                return decision
            except Exception as error:
                row["error"] = type(error).__name__ + ": " + str(error)
                raise
            finally:
                row["seconds"] = time.monotonic() - started
                record["sessions"].append(row)

        def observed_commit(oracle, action, *, stats_serializer):
            record = active["record"]
            started = time.monotonic()
            row = {
                "action": action,
                "elapsedAtCommitSeconds": time.monotonic() - record["turnStarted"],
                "actionIdBefore": oracle.runtime.action_id,
                "awaitingAckBefore": oracle.runtime.awaiting_ack,
                "pendingBefore": len(oracle.runtime.pending),
            }
            try:
                packets = original_commit(
                    oracle, action, stats_serializer=stats_serializer
                )
                opcodes = _counts(packets)
                row.update(
                    packetCount=len(packets),
                    opcodeCounts=opcodes,
                    fifo13420=opcodes.get("13420", 0),
                    outbound13510=opcodes.get("13510", 0),
                    awaitingAckAfter=oracle.runtime.awaiting_ack,
                    pendingAfter=len(oracle.runtime.pending),
                    actionIdAfter=oracle.runtime.action_id,
                    actorsAfter={
                        str(identity): {
                            "hp": actor.hp,
                            "ap": actor.ap,
                            "mp": actor.mp,
                            "wp": actor.effect_stats.get(4),
                            "position": list(actor.position),
                        }
                        for identity, actor in oracle.runtime.fight.actors.items()
                    },
                )
                return packets
            except Exception as error:
                row["error"] = type(error).__name__ + ": " + str(error)
                raise
            finally:
                row["seconds"] = time.monotonic() - started
                record["commits"].append(row)

        NativeSession.__init__ = observed_init
        NativeSession.decide = observed_decide
        NativeOracle.commit = observed_commit
        try:
            scenarios = [
                ("empty_store_budget3", ContextStore(empty_path), 3),
                ("preloaded_store_budget3", preloaded_store, 3),
                ("preloaded_store_budget5", preloaded_store, 5),
            ]
            for name, store, budget in scenarios:
                ai_service._CONTEXT_STORE = store
                runtime, characters, monsters, decks, excluded, fixture = _fixture()
                stats = NativeStats(
                    characters=characters, monsters=monsters, fight_id=runtime.fight.id
                )
                record = {
                    "name": name,
                    "budgetSeconds": budget,
                    "arenaCells": len(runtime.fight.walkable),
                    "arenaEdges": len(runtime.fight.edges),
                    "preparations": [],
                    "sessions": [],
                    "commits": [],
                    "deliveries": [],
                    "requests": {},
                }
                active["record"] = record
                transport = ContextTransport(transport_url, timeout=30)
                original_request = transport.request

                def observed_request(
                    endpoint, payload, *, _request=original_request, _record=record
                ):
                    row = _record["requests"].setdefault(
                        endpoint,
                        {
                            "calls": 0,
                            "seconds": 0.0,
                            "rawBlockBytes": 0,
                            "requestBytes": 0,
                        },
                    )
                    encoded = json.dumps(
                        payload, separators=(",", ":"), allow_nan=False
                    ).encode()
                    row["requestBytes"] += len(encoded)
                    if endpoint == "/v3/context/block":
                        row["rawBlockBytes"] += len(
                            base64.b64decode(payload["data"], validate=True)
                        )
                    row["calls"] += 1
                    started = time.monotonic()
                    try:
                        return _request(endpoint, payload)
                    finally:
                        row["seconds"] += time.monotonic() - started

                transport.request = observed_request

                record["turnStarted"] = time.monotonic()
                generator = run_turn(
                    runtime,
                    characters=characters,
                    monsters=monsters,
                    decks=decks,
                    excluded_decks=excluded,
                    viewer_id=7,
                    flags={},
                    transport=transport,
                    exporter=exporter,
                    policy={},
                    policy_version="native-turn-budget-comparison",
                    stats_serializer=stats,
                    budget_seconds=budget,
                )
                while True:
                    try:
                        packets, diagnostic = next(generator)
                    except StopIteration:
                        break
                    opcodes = _counts(packets)
                    record["deliveries"].append(
                        {
                            "elapsedSeconds": time.monotonic() - record["turnStarted"],
                            "diagnostic": diagnostic,
                            "packetCount": len(packets),
                            "opcodeCounts": opcodes,
                            "fifo13420": opcodes.get("13420", 0),
                            "outbound13510": opcodes.get("13510", 0),
                            "awaitingAck": runtime.awaiting_ack,
                            "pendingCount": len(runtime.pending),
                            "currentActor": runtime.fight.current.id
                            if runtime.fight.current
                            else None,
                            "actionId": runtime.action_id,
                        }
                    )
                record["totalTurnSeconds"] = time.monotonic() - record["turnStarted"]
                record["finalAwaitingAck"] = runtime.awaiting_ack
                record["finalPendingCount"] = len(runtime.pending)
                record["finalCurrentActor"] = (
                    runtime.fight.current.id if runtime.fight.current else None
                )
                for index, session in enumerate(record["sessions"]):
                    prep = (
                        record["preparations"][index]
                        if index < len(record["preparations"])
                        else {"seconds": 0}
                    )
                    session["preparationSeconds"] = prep["seconds"]
                    session["preparationStartedAtTurnSeconds"] = prep.get(
                        "startedAtTurnSeconds", 0
                    )
                    session["negotiationSeconds"] = prep["seconds"] + session["seconds"]
                    session["exceedsTurnBudget"] = (
                        prep.get("startedAtTurnSeconds", 0)
                        + session["negotiationSeconds"]
                        > budget
                    )
                preparation_overruns = any(
                    prep.get("startedAtTurnSeconds", 0) + prep["seconds"] > budget
                    for prep in record["preparations"]
                )
                record["budgetExceededDuringNegotiation"] = preparation_overruns or any(
                    session["exceedsTurnBudget"] for session in record["sessions"]
                )
                record["lateCandidateCommits"] = [
                    commit
                    for commit in record["commits"]
                    if commit["action"].get("type") != "end_turn"
                    and commit["elapsedAtCommitSeconds"] > budget
                ]
                record["fallbackEndTurnCommits"] = [
                    commit
                    for commit in record["commits"]
                    if commit["action"].get("type") == "end_turn"
                ]
                measurements.append(record)
        finally:
            NativeSession.__init__ = original_init
            NativeSession.decide = original_decide
            NativeOracle.commit = original_commit
            listener.shutdown()
            listener.server_close()
            worker.join()
            ai_service._CONTEXT_STORE = old_store

    result = {
        "prewarmSeconds": prewarm_seconds,
        "exporterInventoryWarmSeconds": exporter_inventory_seconds,
        "provisionSecondsOutsideTurnClock": provision_seconds,
        "provision": provision_result,
        "catalogSource": str(DATA_ROOT),
        "results": measurements,
    }
    artifact = runtime_root / "native-turn-http-budget-comparison.json"
    result["artifact"] = str(artifact)
    artifact.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
