"""Check control uncertainty using NativeOracle's board and a real WakIA RPC.

The two control spells are synthetic advisory inputs, not native spells. This
checks decision ranking only; it does not commit or validate their execution.
Run with wakia-native-probe.sh control.
"""
import json
import os
import uuid

from wakia_native_probe import fixture, load_bridge, readonly_providers


def main():
    readonly_providers()
    load_bridge(os.environ["WAKIA_PROBE_BRIDGE"])
    from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import build_snapshot
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import tcp_address
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
    snapshot = build_snapshot(oracle, budget_ms=1500)
    channel = FramedClient(*tcp_address(os.environ["WAKIA_PROBE_ENDPOINT"]), timeout=20)
    results = []
    try:
        for kind in ("remove_ap", "remove_mp"):
            for probability, conditional in ((25, False), (100, True)):
                for safe_id in (40, 41):
                    uncertain_id = 81 - safe_id
                    snapshot["requestId"] = uuid.uuid4().hex

                    def spell(identity, chance, has_condition):
                        return dict(
                            id=identity,
                            grade=1,
                            cost=3,
                            minRange=1,
                            maxRange=5,
                            removal=6,
                            rows=[
                                dict(
                                    kind=kind,
                                    amount=6,
                                    target="enemy",
                                    probability=chance,
                                    conditional=has_condition,
                                )
                            ],
                        )

                    snapshot["spells"] = [
                        spell(uncertain_id, probability, conditional),
                        spell(safe_id, 100, False),
                    ]
                    status, reply = channel.request("/jondo/decide", snapshot)
                    action = reply.get("action", {}) if isinstance(reply, dict) else {}
                    passed = (
                        status == 200
                        and action.get("type") == "cast"
                        and action.get("spellId") == safe_id
                    )
                    results.append(
                        dict(
                            kind=kind,
                            probability=probability,
                            conditional=conditional,
                            safeId=safe_id,
                            selected=action.get("spellId"),
                            passed=passed,
                        )
                    )
    finally:
        channel.close()
    result = dict(
        passed=all(row["passed"] for row in results),
        cases=results,
        scope="native in-memory board and synthetic advisory control spells; decision only",
    )
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
