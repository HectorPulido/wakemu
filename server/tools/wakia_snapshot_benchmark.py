#!/usr/bin/env python3
"""Measure a private native fixture's WakIA snapshot and running Host decision.

Run inside the local World container with PYTHONPATH=/app:/app/tools. The fight
is never registered or committed. PostgreSQL is read-only and Redis writes are
blocked by wakia_native_probe. This uses installed images, not checkout code.
"""
import json
import statistics
import time
import uuid

from wakia_native_probe import fixture, readonly_providers


def main():
    readonly_providers()
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import build_snapshot
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.transport.framed import FramedClient

    runtime, characters, monsters, decks, excluded, description = fixture()
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks=excluded,
        viewer_id=description.pc.id,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    channel = FramedClient("wakia", 8091, timeout=20)
    samples = []
    try:
        for iteration in range(5):
            # Change the private native identity before snapshotting, so the
            # exported source and its fingerprint remain consistent.
            runtime.tactical_encounter_id = uuid.uuid4().hex
            start = time.monotonic()
            snapshot = build_snapshot(oracle, budget_ms=2000)
            snapshot_ms = (time.monotonic() - start) * 1000
            # The new private fight ID prevents a prior sample's plan from
            # being reused. A second unchanged request records what the Host
            # actually does without pretending an action was committed.
            decisions = []
            for mode in ("fresh", "unchanged"):
                start = time.monotonic()
                status, response = channel.request("/wakia/decide", snapshot)
                roundtrip_ms = (time.monotonic() - start) * 1000
                if status != 200 or not isinstance(response, dict):
                    raise RuntimeError(f"WakIA decision failed with status {status}")
                timing = response.get("serviceTiming") or {}
                action = response.get("action") or {}
                decisions.append(
                    dict(
                        requestMode=mode,
                        planReused=response.get("planReused"),
                        hostRoundtripMs=round(roundtrip_ms, 3),
                        hostParseMs=timing.get("parseMs"),
                        hostPlanningMs=timing.get("planningMs"),
                        hostTotalMs=timing.get("totalMs"),
                        actionType=action.get("type"),
                    )
                )
            samples.append(
                dict(
                    cold=iteration == 0,
                    snapshotMs=round(snapshot_ms, 3),
                    decisions=decisions,
                    cells=len(snapshot["board"]["cells"]),
                    actors=len(snapshot["board"]["actors"]),
                    spells=len(snapshot["spells"]),
                )
            )
    finally:
        channel.close()
    warm = samples[1:]
    print(
        json.dumps(
            dict(
                scope="private native fight; running World bridge and WakIA Host; no native action commit or client",
                measurements="snapshot includes projection; Host roundtrip includes encoding/network/Host response; Host timings are service-reported",
                limitations="installed images; catalog already available; no Python decision comparison; no complete turn or ACK",
                warmSnapshotMedianMs=round(
                    statistics.median(s["snapshotMs"] for s in warm), 3
                ),
                warmFreshHostRoundtripMedianMs=round(
                    statistics.median(
                        s["decisions"][0]["hostRoundtripMs"] for s in warm
                    ),
                    3,
                ),
                warmUnchangedHostRoundtripMedianMs=round(
                    statistics.median(
                        s["decisions"][1]["hostRoundtripMs"] for s in warm
                    ),
                    3,
                ),
                samples=samples,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
