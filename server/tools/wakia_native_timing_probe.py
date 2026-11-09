"""Measure isolated synthetic turns against the running local WakIA service.

The World process is not restarted and no synthetic fight is published. The
checkout bridge runs in a separate process with read-only catalog providers;
the running planner image may differ from the checkout. Timings exclude client
and shared World publication, and should not be treated as production percentiles.
"""
import json
import os
import statistics
import struct
import time

from wakia_native_probe import fixture, load_bridge, readonly_providers


def summarize(values):
    values = sorted(values)
    if not values:
        return None
    # Nearest-rank p95; with eight turns this equals the maximum observation.
    index = (95 * len(values) + 99) // 100 - 1
    return dict(
        median=round(statistics.median(values), 2),
        p95=round(values[index], 2),
        samples=len(values),
    )


def main():
    readonly_providers()
    load_bridge(os.environ["WAKIA_PROBE_DIR"] + "/wakfu_ai")
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
    from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.wakia_bridge.wakfu_ai.transport.framed import FramedClient

    results = []
    for sample in range(9):
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
        serializer = NativeStats(
            characters=characters,
            monsters=monsters,
            fight_id=runtime.fight.id,
            map_id=description.character["map_id"],
        )
        initial_hp = description.pc.hp
        channel = FramedClient(*tcp_address("tcp://wakia:8091"), timeout=30)
        started = time.monotonic()
        try:
            deliveries = list(
                run_prepared_turn(
                    runtime,
                    oracle,
                    serializer,
                    channel,
                    deadline=started + 30,
                    max_actions=4,
                )
            )
            pending = runtime.awaiting_ack
            ack_started = time.monotonic()
            if pending is not None:
                runtime.acknowledge_turn(struct.pack(">i", pending))
            ack_ms = (time.monotonic() - ack_started) * 1000
        finally:
            channel.close()
        diagnostics = [item for _, item in deliveries]
        actions = [item.get("action", {}).get("type") for item in diagnostics]
        if (
            not all(kind in actions for kind in ("move", "cast", "end_turn"))
            or pending is None
            or runtime.awaiting_ack is not None
            or runtime.fight.actors[7].hp >= initial_hp
        ):
            raise RuntimeError("Synthetic turn, damage or ACK verification failed")
        phases = [item.get("phaseElapsedMs", {}) for item in diagnostics]
        value = dict(
            turnMs=round((time.monotonic() - started) * 1000, 2),
            ackMs=round(ack_ms, 2),
            snapshotMs=round(sum(row.get("snapshot", 0) for row in phases), 2),
            rpcMs=round(sum(row.get("plannerRpc", 0) for row in phases), 2),
            commitMs=round(sum(row.get("nativeCommit", 0) for row in phases), 2),
            actions=actions,
        )
        results.append(value)
        print(json.dumps(dict(sample=sample, cold=sample == 0, **value)), flush=True)
    warm = results[1:]
    print(
        json.dumps(
            dict(
                warm={
                    key: summarize([row[key] for row in warm])
                    for key in ("turnMs", "snapshotMs", "rpcMs", "commitMs", "ackMs")
                },
                scope="isolated synthetic turns; 8 samples; p95 is the observed maximum; "
                "excludes client and shared World publication; planner is the running local image",
            )
        )
    )


if __name__ == "__main__":
    main()
