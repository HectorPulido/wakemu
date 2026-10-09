#!/usr/bin/env python3
"""Native concurrent turns against an existing AI service; no client ACK replay.

Run inside world with PYTHONPATH=/app:/app/ai-service. Encounters deliberately
reuse numeric fight/actor IDs, but have distinct UUIDs and future runtime data.
Only private Registry instances are modified, never real fights or sockets.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import resource
import sys
import threading
import time
import uuid

from benchmarks.benchmark_native_fixture import fixture
from wakfu_ai.context.native_fingerprint import fingerprint
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.native.native_turn import run_turn
from wakfu_ai.bridge.world_bridge import ContextTransport
from wakfu_ai.bridge.world_shared import run_shared_turn


def quantiles(values):
    ordered = sorted(values)
    return {
        "samples": len(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "p50": ordered[math.ceil(len(ordered) * 0.50) - 1],
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
    }


class MeasuredTransport(ContextTransport):
    def __init__(self, url, instance_id):
        super().__init__(url, timeout=30)
        self.instance_id = instance_id
        self.http = {}
        self.searches = {}
        self.decisions = []
        self.stages = []
        self.turn_started = None

    def catalog(self, exporter):
        started = time.monotonic()
        try:
            return super().catalog(exporter)
        finally:
            self.stages.append(
                dict(
                    stage="catalog_inventory_and_verification",
                    elapsedStart=started - self.turn_started,
                    seconds=time.monotonic() - started,
                )
            )

    def instance_bytes(self, payload):
        started = time.monotonic()
        try:
            return super().instance_bytes(payload)
        finally:
            self.stages.append(
                dict(
                    stage="complete_context_compression_and_http",
                    rawBytes=len(payload),
                    elapsedStart=started - self.turn_started,
                    seconds=time.monotonic() - started,
                )
            )

    def request(self, endpoint, payload):
        record = self.http.setdefault(endpoint, dict(calls=0, seconds=0.0, failures=[]))
        record["calls"] += 1
        if endpoint == "/v3/decide" and "protocol" in payload:
            if payload["fightInstanceId"] != self.instance_id:
                raise AssertionError("Foreign native encounter initialization")
            self.searches[payload["requestId"]] = payload["sourceKey"]
            self.stages.append(
                dict(
                    stage="search_initial_http",
                    elapsedStart=time.monotonic() - self.turn_started,
                )
            )
        started = time.monotonic()
        try:
            reply = super().request(endpoint, payload)
            if endpoint == "/v3/decide":
                if "protocol" in payload and "backendPreparation" in reply:
                    self.stages.append(
                        dict(
                            stage="backend_initial_preparation",
                            measurements=reply["backendPreparation"],
                            elapsedStart=started - self.turn_started,
                        )
                    )
                expected = self.searches[payload["requestId"]]
                identity = (
                    reply.get("decision", {})
                    if reply.get("status") == "decided"
                    else reply
                )
                if (
                    identity.get("requestId") != payload["requestId"]
                    or identity.get("sourceKey") != expected
                ):
                    raise AssertionError("Foreign native search response")
                if reply.get("status") == "decided":
                    self.decisions.append(identity)
            return reply
        except Exception as error:
            record["failures"].append(
                dict(type=type(error).__name__, detail=str(error))
            )
            raise
        finally:
            record["seconds"] += time.monotonic() - started


def encounter(url, index, *, npc_position=(-7, -7, -1)):
    from wakfu_server.combat_shared import Registry, Session
    from wakfu_server.combat_snapshot_wire import snapshot_characteristics

    runtime, characters, monsters, decks, excluded, actors = fixture(
        npc_position=npc_position, pc_hp=60 - index % 5
    )
    # Validate native wire resources before any timed search. Distinct HP
    # must be installed in the fresh snapshot, never patched after install.
    for actor in runtime.fight.actors.values():
        snapshot_characteristics(actor)
    instance = uuid.uuid4().hex
    runtime.tactical_encounter_id = instance
    runtime.future_concurrency_marker = dict(
        instance=instance, index=index, payload=b"all-context"
    )
    session = Session(9, 7, "concurrent-native-benchmark", 1134, 0)
    registry = Registry(lambda candidate: candidate == session)
    shared = registry.register(runtime.fight, session, runtime=runtime)
    return dict(
        runtime=runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded=excluded,
        actors=actors,
        instance=instance,
        session=session,
        registry=registry,
        shared=shared,
        fixture_native_verified=True,
        transport=MeasuredTransport(url, instance),
    )


def measure_turn(case, exporter, barrier, budget):
    runtime, registry, shared = case["runtime"], case["registry"], case["shared"]
    session, transport = case["session"], case["transport"]
    before = fingerprint(runtime)
    before_hp = runtime.fight.actors[7].hp
    stats = NativeStats(
        characters=case["characters"],
        monsters=case["monsters"],
        fight_id=runtime.fight.id,
    )
    adapter = type("Adapter", (), {"registry": registry})()
    barrier.wait(timeout=30)
    started = time.monotonic()
    transport.turn_started = started

    def runner(candidate):
        yield from run_turn(
            candidate,
            characters=case["characters"],
            monsters=case["monsters"],
            decks=case["decks"],
            excluded_decks=case["excluded"],
            viewer_id=7,
            flags={},
            transport=transport,
            exporter=exporter,
            policy=case.get("policy", {}),
            policy_version="native-concurrent-benchmark",
            stats_serializer=stats,
            budget_seconds=budget,
        )

    diagnostics = [
        diagnostic
        for _, diagnostic in run_shared_turn(runtime, adapter, session, runner)
    ]
    elapsed = time.monotonic() - started
    batches = registry.drain(runtime.fight.id, session)
    packets = [packet for batch in batches for packet in batch.packets]
    opcodes = {}
    for opcode, _ in packets:
        opcodes[str(opcode)] = opcodes.get(str(opcode), 0) + 1
    invariants = dict(
        fixtureNativeCharacteristicsVerified=case["fixture_native_verified"],
        sourceUnchanged=fingerprint(runtime) == before,
        encounterUnchanged=shared.runtime.tactical_encounter_id == case["instance"],
        futureMarkerUnchanged=shared.runtime.future_concurrency_marker
        == runtime.future_concurrency_marker,
        runtimeFightIdentity=shared.runtime.fight is shared.fight,
        publishedOnce=shared.sequence == 1 and len(batches) == 1,
        nativeEndPublished="12502" in opcodes,
        realAckArmed=shared.runtime.awaiting_ack is not None
        and shared.ack.turn == shared.runtime.awaiting_ack,
        noClientAckReceived=not shared.ack.received,
    )
    return dict(
        instanceId=case["instance"],
        fightId=runtime.fight.id,
        actorIds=sorted(runtime.fight.actors),
        arenaCells=len(runtime.fight.walkable),
        arenaEdges=len(runtime.fight.edges),
        seconds=elapsed,
        sourceHp=before_hp,
        publishedHp=shared.fight.actors[7].hp,
        damage=before_hp - shared.fight.actors[7].hp,
        packetCount=len(packets),
        opcodeCounts=opcodes,
        invariants=invariants,
        diagnostics=diagnostics,
        http=transport.http,
        searches=transport.searches,
        searchCount=len(transport.searches),
        selectedDecisions=transport.decisions,
        committedActions=[
            row["action"]
            for row in diagnostics
            if row.get("action", {}).get("type") != "end_turn"
        ],
        fallbackReasons=[row["reason"] for row in diagnostics if row.get("reason")],
        stages=transport.stages,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--budget", type=float, default=10)
    parser.add_argument(
        "--cold",
        action="store_true",
        help="Do not prewarm native catalogs or provision context before measured turns",
    )
    parser.add_argument(
        "--cold-catalog",
        action="store_true",
        help="Keep world startup native prewarm, but include context provisioning in turns",
    )
    parser.add_argument(
        "--parts", action="store_true", help="Exercise complete fragment transport"
    )
    parser.add_argument(
        "--search-fraction",
        type=float,
        help="Override the generic fraction of remaining turn allocated to each decision",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--npc-position", type=int, nargs=3, default=[-7, -7, -1])
    args = parser.parse_args()
    if (
        not 1 <= args.repeats <= 20
        or any(not 1 <= value <= 8 for value in args.concurrency)
        or not math.isfinite(args.budget)
        or args.budget <= 0
    ):
        parser.error("Invalid native benchmark workload")
    if args.search_fraction is not None and (
        not math.isfinite(args.search_fraction) or not 0 < args.search_fraction <= 1
    ):
        parser.error("Invalid native search fraction")
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    from wakfu_ai.bridge.world_entry import native_exporter

    print(
        json.dumps(dict(stage="native_catalog_prewarm", status="started")), flush=True
    )
    started = time.monotonic()
    if not args.cold:
        prewarm_runtime_catalogs()
    prewarm_seconds = time.monotonic() - started
    print(
        json.dumps(
            dict(
                stage="native_catalog_prewarm",
                status="completed",
                seconds=prewarm_seconds,
            )
        ),
        flush=True,
    )
    exporter = native_exporter()
    try:
        print(
            json.dumps(
                dict(stage="complete_catalog_transfer_and_seal", status="started")
            ),
            flush=True,
        )
        started = time.monotonic()
        catalog = (
            None
            if args.cold or args.cold_catalog
            else ContextTransport(args.url, timeout=30).catalog(exporter)
        )
        catalog_seconds = time.monotonic() - started
        print(
            json.dumps(
                dict(
                    stage="complete_catalog_transfer_and_seal",
                    status="completed",
                    seconds=catalog_seconds,
                    manifest=catalog,
                )
            ),
            flush=True,
        )
        cohorts = []
        for concurrency in args.concurrency:
            for repeat in range(args.repeats):
                cases = [
                    encounter(
                        args.url,
                        repeat * 8 + index,
                        npc_position=tuple(args.npc_position),
                    )
                    for index in range(concurrency)
                ]
                for case in cases:
                    case["transport"].native_graph_parts = args.parts
                    if args.search_fraction is not None:
                        case["policy"] = {"searchTimeFraction": args.search_fraction}
                barrier = threading.Barrier(concurrency)
                cpu_started, wall_started = time.process_time(), time.monotonic()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = [
                        pool.submit(measure_turn, case, exporter, barrier, args.budget)
                        for case in cases
                    ]
                    measurements = [future.result() for future in futures]
                searches = [
                    identity
                    for result in measurements
                    for identity in result["searches"]
                ]
                cohorts.append(
                    dict(
                        concurrency=concurrency,
                        repeat=repeat,
                        wallSeconds=time.monotonic() - wall_started,
                        sdkProcessCpuSeconds=time.process_time() - cpu_started,
                        searchesStarted=len(searches),
                        searchIdsUnique=len(set(searches)) == len(searches)
                        if searches
                        else None,
                        measurements=measurements,
                    )
                )
                print(
                    json.dumps(
                        dict(
                            progress=dict(
                                concurrency=concurrency,
                                repeat=repeat,
                                attacks=sum(
                                    result["damage"] > 0 for result in measurements
                                ),
                                seconds=[result["seconds"] for result in measurements],
                            )
                        )
                    ),
                    flush=True,
                )
        summaries = []
        for concurrency in args.concurrency:
            results = [
                result
                for cohort in cohorts
                if cohort["concurrency"] == concurrency
                for result in cohort["measurements"]
            ]
            summaries.append(
                dict(
                    concurrency=concurrency,
                    seconds=quantiles([r["seconds"] for r in results]),
                    attacks=sum(r["damage"] > 0 for r in results),
                    total=len(results),
                    searchesStarted=sum(r["searchCount"] for r in results),
                    committedNonEndActions=sum(
                        len(r["committedActions"]) for r in results
                    ),
                    selectedEndTurns=sum(
                        decision["action"]["type"] == "end_turn"
                        for r in results
                        for decision in r["selectedDecisions"]
                    ),
                    fallbackReasons=dict(
                        Counter(
                            reason for r in results for reason in r["fallbackReasons"]
                        )
                    ),
                    invariantFailures=[
                        dict(instance=r["instanceId"], name=name)
                        for r in results
                        for name, valid in r["invariants"].items()
                        if not valid
                    ],
                )
            )
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result = dict(
            measuredAt=datetime.now(timezone.utc).isoformat(),
            aiUrl=args.url,
            mode="existing_ai_http_private_native_registries",
            budgetSeconds=args.budget,
            initialNpcPosition=args.npc_position,
            coldStart=args.cold,
            coldCatalog=args.cold or args.cold_catalog,
            nativeGraphParts=args.parts,
            searchTimeFraction=args.search_fraction,
            prewarmSecondsOutsideTurns=prewarm_seconds,
            catalogSecondsOutsideTurns=catalog_seconds,
            catalogManifest=catalog,
            sdkProcessPeakRssBytes=rss if sys.platform == "darwin" else rss * 1024,
            percentiles="empirical_nearest_rank_small_corpus_not_sla",
            cohorts=cohorts,
            summaries=summaries,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(dict(output=str(args.output), summaries=summaries), indent=2),
            flush=True,
        )
        if any(summary["invariantFailures"] for summary in summaries) or any(
            c["searchIdsUnique"] is False for c in cohorts
        ):
            raise SystemExit("Native concurrency invariant failed")
    finally:
        exporter.close()


if __name__ == "__main__":
    main()
