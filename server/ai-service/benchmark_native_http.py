#!/usr/bin/env python3
"""Measure real HTTP negotiation with the full native arena and catalogues.

Run with PYTHONPATH=server:server/ai-service and the native test environment.
This starts an ephemeral localhost HTTP listener, never a game service.
"""
import json
from pathlib import Path
import tempfile
import threading
import time
import sys
import urllib.error

from context_store import ContextStore
from native_context import encode
from native_oracle import NativeOracle
from server import BoundedHTTPServer, Handler
import server as service
from world_bridge import CompleteContextExporter, ContextTransport, NativeSession


def main():
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.spells import default_deck
    from tests.test_combat_npc_attack import NativeNpcAttackTests

    prewarm_runtime_catalogs()
    print("Native catalogs ready", file=sys.stderr, flush=True)
    fixture = NativeNpcAttackTests()
    fixture.setUp()
    fight = fixture.fight
    fixture.monster.update(id=fixture.npc.id, map_id=1134)
    fixture.pc.position, fixture.npc.position = (-8, -7, -1), (-7, -7, -1)
    terrain = local_arena(1134, fight.id, fixture.pc.position, fixture.npc.position)
    fight.walkable, fight.edges = terrain["validated_cells"], terrain["valid_edges"]
    freeze_terrain(fight)
    fight.order, fight.turn_index = [fixture.npc.id, fixture.pc.id], 0
    fixture.npc.turn_count = 1
    runtime = RuntimeMessages(fight)
    oracle = NativeOracle(
        runtime,
        characters={7: fixture.character},
        monsters={fixture.npc.id: fixture.monster},
        decks={7: default_deck(fixture.character)},
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags={},
    )
    before = encode(runtime)
    root = Path(__file__).resolve().parent.parent
    exporter = CompleteContextExporter(
        {"catalog": DATA_ROOT, "engine": root / "wakfu_server"}
    )
    with tempfile.TemporaryDirectory(prefix="wakfu-native-http-") as temporary:
        service._CONTEXT_STORE = ContextStore(temporary)
        listener = BoundedHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=listener.serve_forever, daemon=True)
        worker.start()
        try:
            transport = ContextTransport(
                "http://%s:%s" % listener.server_address, timeout=30
            )
            timings = {}
            phases = {}

            def observed_phase(name, operation):
                def invoke(*args, **kwargs):
                    started = time.monotonic()
                    try:
                        return operation(*args, **kwargs)
                    finally:
                        entry = phases.setdefault(name, {"calls": 0, "seconds": 0})
                        entry["calls"] += 1
                        entry["seconds"] += time.monotonic() - started

                return invoke

            oracle.preview = observed_phase("nativePreview", oracle.preview)
            original_request = transport.request

            def observed_request(endpoint, payload):
                started = time.monotonic()
                try:
                    return original_request(endpoint, payload)
                except urllib.error.HTTPError as error:
                    print(error.read().decode(), file=sys.stderr, flush=True)
                    raise
                finally:
                    entry = timings.setdefault(endpoint, {"calls": 0, "seconds": 0})
                    entry["calls"] += 1
                    entry["seconds"] += time.monotonic() - started

            transport.request = observed_request
            results = []
            catalog_manifest = None
            for label in ("cold", "warm", "normal", "normal_cached"):
                print("Starting " + label, file=sys.stderr, flush=True)
                timings.clear()
                phases.clear()
                started = time.monotonic()
                policy = (
                    {}
                    if label.startswith("normal")
                    else {
                        "limits": {"depth": 1, "beam": 4, "nodes": 48, "budgetMs": 5000}
                    }
                )
                session = NativeSession(
                    oracle,
                    transport,
                    exporter,
                    policy=policy,
                    policy_version="http-benchmark",
                    fight_instance_id="native-http-benchmark",
                    catalog_manifest=catalog_manifest
                    if label == "normal_cached"
                    else None,
                )
                catalog_manifest = session.catalog
                for method in ("guard", "query", "register"):
                    setattr(
                        session,
                        method,
                        observed_phase(method, getattr(session, method)),
                    )
                prepared = time.monotonic()
                decision = session.decide(max_queries=8192)
                assert (
                    encode(runtime) == before
                ), "HTTP forecasts mutated the live source"
                results.append(
                    {
                        "run": label,
                        "prepareSeconds": prepared - started,
                        "decisionSeconds": time.monotonic() - prepared,
                        "action": decision["action"],
                        "endpoints": dict(timings),
                        "phases": dict(phases),
                    }
                )
                print(
                    json.dumps(results[-1], sort_keys=True), file=sys.stderr, flush=True
                )
            print(
                json.dumps(
                    {"results": results, "validatedCells": len(fight.walkable)},
                    sort_keys=True,
                )
            )
        finally:
            listener.shutdown()
            listener.server_close()
            worker.join()


if __name__ == "__main__":
    main()
