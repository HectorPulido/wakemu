"""Profile private full native turns against the existing separate TCP AI.

Run in one catalog-warmed, read-only World process. No live Registry, socket,
player, or database state is adopted. Cold means no continuation hint; both
modes retain current planner optimizations and warmed native/catalog caches.
The inclusive stage timers overlap and must not be added together.
"""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import statistics
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from benchmarks.benchmark_native_fixture import fixture
from wakfu_ai.bridge import world_bridge
from wakfu_ai.bridge.world_entry import native_exporter
from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_ai.native import native_turn
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.transport.endpoint import tcp_address
from wakfu_ai.transport.framed_context import FramedContextTransport
from wakfu_ai.transport import framed, framed_context


_PROFILE_SAMPLES = []


def _json_default(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    raise TypeError(f"Unsupported profile JSON value: {type(value).__name__}")


def distribution(values):
    ordered = sorted(values)
    result = dict(
        samples=len(values),
        p50=statistics.median(values),
        min=min(values),
        max=max(values),
    )
    if len(values) >= 20:
        result["p95"] = ordered[math.ceil(len(values) * 0.95) - 1]
        result[
            "p95Qualification"
        ] = "empirical nearest rank; diagnostic corpus, not SLA"
    else:
        result["p95Qualification"] = "omitted: fewer than 20 samples"
    return result


class MeasuredTCPTransport(FramedContextTransport):
    def __init__(self, url, instance):
        host, port = tcp_address(url)
        super().__init__(host, port, timeout=120)
        self.instance = instance
        self.rpc = []
        self.roots = {}
        self.decisions = []
        self.query_counts = Counter()
        self.warm_starts = []

    def request(self, endpoint, payload):
        # Context bundling wraps the actual native request. Measure the wire
        # operation once, and validate identities on the unwrapped exchange.
        native = (
            payload.get("request", {})
            if endpoint == "/v3/context/continue"
            else payload
        )
        if endpoint in ("/v3/decide", "/v3/context/continue") and "protocol" in native:
            if native["fightInstanceId"] != self.instance:
                raise AssertionError("Foreign fixture initialization")
            self.roots[native["requestId"]] = (native["sourceKey"], native["rootState"])
            self.warm_starts.append(deepcopy(native.get("warmStart")))
        started = time.perf_counter()
        row = dict(endpoint=endpoint)
        try:
            reply = super().request(endpoint, payload)
            if endpoint in ("/v3/decide", "/v3/context/continue"):
                # The production continuation endpoint currently returns the
                # normal QuerySessions reply directly, not an invented envelope.
                identity = (
                    reply.get("decision", {})
                    if reply.get("status") == "decided"
                    else reply
                )
                expected = self.roots.get(native.get("requestId"))
                if expected is None or (
                    identity.get("requestId"),
                    identity.get("sourceKey"),
                ) != (native["requestId"], expected[0]):
                    raise AssertionError("Foreign TCP native reply")
                if reply.get("status") == "decided":
                    if identity.get("rootState") != expected[1]:
                        raise AssertionError("Foreign TCP native decision root")
                    self.decisions.append(deepcopy(identity))
                else:
                    for query in reply.get("queries", []):
                        name = query["operation"]
                        if name == "preview":
                            name += ":" + query["action"]["type"]
                        self.query_counts[name] += 1
            return reply
        except BaseException as error:
            row["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            row["ms"] = (time.perf_counter() - started) * 1000
            self.rpc.append(row)


def _sample(exporter, *, url, mode, pair, budget_seconds, seed_fixture):
    from wakfu_server.combat_shared import Registry, Session
    from wakfu_server.combat_resource_pa_notifications import set_resource_current
    from wakfu_ai.context.native_fingerprint import fingerprint

    runtime, characters, monsters, decks, excluded, actors = deepcopy(seed_fixture)
    set_resource_current(runtime.fight, actors.npc, 3, 1)
    instance = "private-tcp-profile-" + uuid.uuid4().hex
    runtime.tactical_encounter_id = instance
    from wakfu_ai.native.native_profiles import encounter_profiles
    from wakfu_server import native_catalog

    profile_started = time.perf_counter()
    profiles = encounter_profiles(runtime, native_catalog._database(), monsters)
    profile = profiles.get(actors.monster["ref"], profiles[None])
    profile_ms = (time.perf_counter() - profile_started) * 1000
    configured_turn_ms = profile["policy"].get("limits", {}).get("turnMs", 10000)
    if type(configured_turn_ms) is not int or not 1 <= configured_turn_ms <= 60000:
        raise ValueError("Invalid actual database profile turn deadline")
    first_turn = actors.npc.turn_count == 1
    # world_entry has both the outer actor allowance and the profile deadline.
    production_budget = min(
        (20 if first_turn else 10),
        max(configured_turn_ms, 20000 if first_turn else 0) / 1000,
    )
    effective_budget = production_budget if budget_seconds is None else budget_seconds
    flags = dict(
        native_area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "0") == "1",
        native_start_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
        native_environment={
            key: value
            for key, value in os.environ.items()
            if key.startswith("WAKFU_NATIVE_")
        },
    )
    member = Session(9, 7, instance, 1134, 0)
    registry = Registry(lambda candidate: candidate == member)
    shared = registry.register(runtime.fight, member, runtime=runtime)
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=runtime.fight.id
    )
    transport = MeasuredTCPTransport(url, instance)
    before = fingerprint(runtime)
    hp_before = actors.pc.hp
    resource_before = dict(
        ap=actors.npc.ap, mp=actors.npc.mp, wp=actors.npc.effect_stats[4]
    )
    stages = {}
    diagnostics = []
    error = None

    def measured(name, function):
        def invoke(*args, **kwargs):
            started = time.perf_counter()
            failed = False
            try:
                return function(*args, **kwargs)
            except BaseException:
                failed = True
                raise
            finally:
                row = stages.setdefault(
                    name, dict(calls=0, failures=0, inclusiveMs=0.0)
                )
                row["calls"] += 1
                row["failures"] += int(failed)
                row["inclusiveMs"] += (time.perf_counter() - started) * 1000

        return invoke

    original_envelope = world_bridge.NativeSession.envelope

    def envelope(session):
        result = original_envelope(session)
        if mode == "cold":
            result.pop("warmStart", None)
        return result

    def runner(candidate):
        return native_turn.run_turn(
            candidate,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=7,
            flags=flags,
            transport=transport,
            exporter=exporter,
            policy=profile["policy"],
            policy_version=profile["identity"],
            stats_serializer=serializer,
            budget_seconds=effective_budget,
        )

    cpu_started, started = time.process_time(), time.perf_counter()
    try:
        with ExitStack() as stack:
            for owner, attribute, name in (
                (world_bridge.NativeSession, "__init__", "session_preparation"),
                (world_bridge.NativeSession, "guard", "source_guards"),
                (NativeOracle, "__init__", "oracle_preparation"),
                (NativeOracle, "preview", "native_previews"),
                (NativeOracle, "commit", "native_commit"),
                (Registry, "execute_server", "registry_publication"),
                (world_bridge, "encode_bytes", "native_graph_encoding"),
                (world_bridge, "_json_bytes", "bridge_json_encoding"),
                (framed_context, "_json_bytes", "transport_metric_json_encoding"),
                (framed, "encode_frame", "tcp_frame_encoding"),
                (world_bridge.gzip, "compress", "gzip_compression"),
            ):
                stack.enter_context(
                    patch.object(
                        owner, attribute, measured(name, getattr(owner, attribute))
                    )
                )
            stack.enter_context(
                patch.object(
                    world_bridge.NativeSession,
                    "envelope",
                    measured("envelope", envelope),
                )
            )
            driver = run_shared_turn(
                runtime, SimpleNamespace(registry=registry), member, runner
            )
            try:
                for _, diagnostic in driver:
                    diagnostics.append(deepcopy(diagnostic))
            finally:
                driver.close()
    except Exception as caught:
        error = type(caught).__name__ + ": " + str(caught)
    elapsed_ms = (time.perf_counter() - started) * 1000
    cpu_ms = (time.process_time() - cpu_started) * 1000
    actor, target = shared.fight.actors[actors.npc.id], shared.fight.actors[7]
    batches = registry.drain(runtime.fight.id, member)
    packets = [packet for batch in batches for packet in batch.packets]
    actions = [row.get("action") for row in diagnostics]
    result = dict(
        mode=mode,
        pair=pair,
        fullTurnWallMs=elapsed_ms,
        sdkProcessCpuMs=cpu_ms,
        error=error,
        stages=stages,
        rpc=transport.rpc,
        transportMetrics=deepcopy(transport.metrics),
        profile=dict(
            identity=profile["identity"],
            policy=profile["policy"],
            snapshotReadMsOutsideTurn=profile_ms,
        ),
        flags=dict(
            native_area_callbacks=flags["native_area_callbacks"],
            native_start_events=flags["native_start_events"],
            native_environmentKeys=sorted(flags["native_environment"]),
            native_environmentSha256=hashlib.sha256(
                world_bridge._json_bytes(flags["native_environment"])
            ).hexdigest(),
        ),
        effectiveBudgetSeconds=effective_budget,
        productionBudgetSeconds=production_budget,
        budgetOverrideSeconds=budget_seconds,
        fixtureOverrides=dict(npcMP=1),
        queries=dict(transport.query_counts),
        searchCount=len(transport.roots),
        initialPositions=dict(
            npc=list(actors.npc.position), target=list(actors.pc.position)
        ),
        selectedDecisions=transport.decisions,
        diagnostics=diagnostics,
        actions=actions,
        warmStarts=transport.warm_starts,
        arenaCells=len(runtime.fight.walkable),
        gameplay=dict(
            damage=hp_before - target.hp,
            targetHp=target.hp,
            netResourceChangeAfterTurnBoundary={
                key: value - resource_before[key]
                for key, value in dict(
                    ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4]
                ).items()
            },
            position=list(actor.position),
            phase=shared.fight.phase,
            currentId=shared.fight.current.id if shared.fight.current else None,
        ),
        publication=dict(
            sequence=shared.sequence,
            batches=len(batches),
            packets=len(packets),
            opcodes=dict(Counter(str(opcode) for opcode, _ in packets)),
            sourceRuntimeUnchanged=fingerprint(runtime) == before,
            realAckArmed=shared.runtime.awaiting_ack is not None,
            clientAckReceived=bool(shared.ack.received),
            sameFightRuntime=shared.runtime.fight is shared.fight,
        ),
        fallbackReasons=[row.get("reason") for row in diagnostics if row.get("reason")],
    )
    transport.close()
    return result


def run_profile(*, url="tcp://ai:8090", pairs=3, budget_seconds=None, output=None):
    if type(pairs) is not int or not 1 <= pairs <= 20:
        raise ValueError("pairs must be 1..20")
    if budget_seconds is not None and (
        not math.isfinite(budget_seconds) or not 0 < budget_seconds <= 120
    ):
        raise ValueError("budget_seconds must be finite and <=120")
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    import wakfu_server

    started = time.perf_counter()
    prewarm_runtime_catalogs()
    prewarm_ms = (time.perf_counter() - started) * 1000
    exporter = native_exporter()
    host, port = tcp_address(url)
    preflight = FramedContextTransport(host, port, timeout=120)
    started = time.perf_counter()
    try:
        health = preflight.request("/health", {})
        catalog = preflight.catalog(exporter)
    finally:
        preflight.close()
    catalog_ms = (time.perf_counter() - started) * 1000
    sources = {}
    for module in (wakfu_server, world_bridge, native_turn):
        path = Path(inspect.getfile(module)).resolve()
        sources[module.__name__] = dict(
            path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )
    from wakfu_server import combat_terrain

    original_arena = combat_terrain.local_arena

    def fixed_arena(*args, **kwargs):
        return original_arena(*args, **dict(kwargs, relocate_monsters=False))

    # Placement relocation normally chooses a legal spawn. For an A/B corpus
    # choose the requested native cells once, then clone the complete runtime
    # and authority maps so both modes start from identical combat/RNG state.
    with patch.object(combat_terrain, "local_arena", fixed_arena):
        seed_fixture = fixture(npc_position=(-6, -7, -1))
    global _PROFILE_SAMPLES
    samples = []
    _PROFILE_SAMPLES = samples
    for pair in range(pairs):
        for mode in ("cold", "warm") if pair % 2 == 0 else ("warm", "cold"):
            row = _sample(
                exporter,
                url=url,
                mode=mode,
                pair=pair,
                budget_seconds=budget_seconds,
                seed_fixture=seed_fixture,
            )
            samples.append(row)
            print(
                "TCP_NATIVE_SAMPLE " + json.dumps(row, default=_json_default),
                flush=True,
            )
    result = dict(
        kind="private-native-full-turn-real-tcp",
        url=url,
        sources=sources,
        health=health,
        catalog=catalog,
        prewarmMsOutsideTurns=prewarm_ms,
        catalogMsOutsideTurns=catalog_ms,
        budgetSeconds=budget_seconds,
        budgetQualification="None uses actual SQL profile and world_entry actor allowance; numeric value is an explicit harness override",
        coldDefinition="current planner without warmStart; all other optimizations retained",
        stageAccounting="inclusive overlapping timers; do not sum",
        excludes=[
            "client animation and ACK arrival",
            "live World queue contention",
            "cold native catalog startup",
        ],
        samples=samples,
        summary={
            mode: distribution(
                [row["fullTurnWallMs"] for row in samples if row["mode"] == mode]
            )
            for mode in ("cold", "warm")
        },
        comparisons=[
            dict(
                pair=pair,
                equivalentActions=next(
                    row
                    for row in samples
                    if row["pair"] == pair and row["mode"] == "cold"
                )["actions"]
                == next(
                    row
                    for row in samples
                    if row["pair"] == pair and row["mode"] == "warm"
                )["actions"],
                equivalentGameplay=next(
                    row
                    for row in samples
                    if row["pair"] == pair and row["mode"] == "cold"
                )["gameplay"]
                == next(
                    row
                    for row in samples
                    if row["pair"] == pair and row["mode"] == "warm"
                )["gameplay"],
            )
            for pair in range(pairs)
        ],
    )
    # The control process also serializes the return value. Keep original
    # samples above for diagnosis, while exposing a strictly JSON-safe result.
    result = json.loads(json.dumps(result, default=_json_default))
    if output is not None:
        Path(output).write_text(json.dumps(result, indent=2) + "\n")
    return result


def probe_catalog_inventory(*, budget_seconds=10):
    """Profile only the identified opaque inventory stage in the same heap.

    cProfile adds overhead: this diagnoses attribution, not production speed.
    It does not start a turn, transport request, or load another native catalog.
    """
    import cProfile
    import gc
    import io
    import pstats
    import traceback
    from wakfu_ai.native.native_deadline import bounded

    exporter = native_exporter()
    profiler = cProfile.Profile()
    events, starts = [], {}

    def observe_gc(phase, info):
        generation = info["generation"]
        if phase == "start":
            starts[generation] = (time.perf_counter(), traceback.format_stack(limit=8))
        else:
            prior = starts.pop(generation, None)
            if prior is not None:
                events.append(
                    dict(
                        generation=generation,
                        ms=(time.perf_counter() - prior[0]) * 1000,
                        collected=info["collected"],
                        uncollectable=info["uncollectable"],
                        triggerStack=prior[1],
                    )
                )

    error = None
    count = None
    gc_before = gc.get_count()
    started, cpu_started = time.perf_counter(), time.process_time()
    gc.callbacks.append(observe_gc)
    profiler.enable()
    try:
        with bounded(time.monotonic() + budget_seconds):
            manifest, _ = exporter.inventory()
            count = len(manifest["entries"])
    except Exception as caught:
        error = type(caught).__name__ + ": " + str(caught)
    finally:
        profiler.disable()
        gc.callbacks.remove(observe_gc)
    text = io.StringIO()
    pstats.Stats(profiler, stream=text).sort_stats("cumulative").print_stats(45)
    return dict(
        kind="catalog-inventory-attribution-only",
        profilerOverhead=True,
        wallMs=(time.perf_counter() - started) * 1000,
        processCpuMs=(time.process_time() - cpu_started) * 1000,
        budgetSeconds=budget_seconds,
        error=error,
        entries=count,
        gcBefore=gc_before,
        gcAfter=gc.get_count(),
        gcEvents=sorted(events, key=lambda row: row["ms"], reverse=True)[:20],
        profile=text.getvalue(),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="tcp://ai:8090")
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Explicit override; omit to use real first-turn/profile allowance",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    measurement = run_profile(
        url=args.url, pairs=args.pairs, budget_seconds=args.budget, output=args.output
    )
    print(
        json.dumps(dict(summary=measurement["summary"], output=str(args.output))),
        flush=True,
    )
