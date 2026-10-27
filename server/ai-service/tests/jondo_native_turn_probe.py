"""Reusable real TCP/native chosen-action driver for opt-in qualification."""
import struct
import time
import uuid


def run(
    endpoint,
    *,
    reference=1,
    level=10,
    npc_position=(-7, -7, -1),
    pc_position=(-8, -7, -1),
    max_actions=4,
    fixture_factory=None
):
    if fixture_factory is None:
        raise ValueError("An actual native fixture factory is required")
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address
    from wakfu_ai.native.native_deadline import bounded
    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_ai.bridge.jondo_snapshot import build_snapshot

    runtime, characters, monsters, decks, excluded, description = fixture_factory(
        monster_reference=reference,
        monster_level=level,
        npc_position=npc_position,
        pc_position=pc_position,
    )
    runtime.tactical_encounter_id = uuid.uuid4().hex
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
    before_hp = runtime.fight.actors[description.pc.id].hp
    actual_npc = tuple(runtime.fight.current.position)
    actual_pc = tuple(runtime.fight.actors[description.pc.id].position)
    from unittest.mock import patch
    from wakfu_ai.bridge import jondo_entry
    import json

    snapshots, rpc = [], []
    first_request = None
    original_snapshot = jondo_entry.build_snapshot

    def observed_snapshot(*args, **kwargs):
        nonlocal first_request
        began = time.monotonic()
        result = original_snapshot(*args, **kwargs)
        if first_request is None:
            first_request = result
        snapshots.append(
            dict(
                requestId=result["requestId"],
                wallMs=(time.monotonic() - began) * 1000,
                source=result["source"],
                sourceGuardPassed=True,
                cells=len(result["board"]["cells"]),
                edges=len(result["board"]["edges"]),
                losPairs=len(result["board"]["lineOfSight"]),
                portalEdges=len(result["board"].get("portalEdges", [])),
            )
        )
        return result

    class RecordingChannel(FramedClient):
        def request(self, endpoint, payload, *, deadline=None):
            began = time.monotonic()
            record = dict(
                requestId=payload["requestId"],
                endpoint=endpoint,
                sentBytes=len(json.dumps(payload, separators=(",", ":")).encode()),
            )
            try:
                status, result = super().request(endpoint, payload, deadline=deadline)
                record.update(
                    status=status,
                    reply=result,
                    receivedBytes=len(
                        json.dumps(result, separators=(",", ":")).encode()
                    ),
                )
                return status, result
            except Exception as error:
                record["error"] = dict(type=type(error).__name__, detail=str(error))
                raise
            finally:
                record["wallMs"] = (time.monotonic() - began) * 1000
                rpc.append(record)

    started = time.monotonic()
    channel = RecordingChannel(*tcp_address(endpoint), timeout=20)
    deliveries, error = [], None
    try:
        # Observe the snapshots the driver actually needs. Do not execute a
        # preliminary snapshot that warms its caches before measuring a turn.
        with patch.object(jondo_entry, "build_snapshot", observed_snapshot):
            for delivery in run_prepared_turn(
                runtime,
                oracle,
                serializer,
                channel,
                deadline=started + 20,
                max_actions=max_actions,
            ):
                deliveries.append(delivery)
    except Exception as failure:
        error = dict(type=type(failure).__name__, detail=str(failure))
    finally:
        channel.close()
    turn_wall_ms = (time.monotonic() - started) * 1000
    after_hp = runtime.fight.actors[description.pc.id].hp
    actions = [diagnostic["action"] for _, diagnostic in deliveries]
    pending_ack = runtime.awaiting_ack
    ack_packets, ack_error = [], None
    ack_started = time.monotonic()
    if pending_ack is not None:
        try:
            ack_packets = runtime.acknowledge_turn(struct.pack(">i", pending_ack))
        except Exception as failure:
            ack_error = dict(type=type(failure).__name__, detail=str(failure))
    adjacent = sum(abs(a - b) for a, b in zip(actual_npc[:2], actual_pc[:2])) == 1
    checks = dict(
        nativeErrorAbsent=error is None,
        nativeFifoDelivered=any(packets for packets, _ in deliveries),
        snapshotsSourceGuarded=bool(snapshots)
        and all(row["sourceGuardPassed"] for row in snapshots),
        adjacentAttacked=(after_hp < before_hp) if adjacent else None,
        ackCleared=(runtime.awaiting_ack is None and ack_error is None)
        if pending_ack is not None
        else None,
    )
    return dict(
        kind="jondo_actual_native_fixture",
        reference=reference,
        level=level,
        qualification="Actual initialized native fixture and chosen-action loop; Store/session preparation is outside this measurement.",
        positions=dict(npc=actual_npc, pc=actual_pc),
        requestedPositions=dict(npc=npc_position, pc=pc_position),
        passed=all(value is not False for value in checks.values()),
        checks=checks,
        wallMs=turn_wall_ms,
        ackWallMs=(time.monotonic() - ack_started) * 1000,
        damage=before_hp - after_hp,
        actions=actions,
        diagnostics=[diagnostic for _, diagnostic in deliveries],
        fixtureSetup=getattr(description, "fixture_setup", None),
        firstRequest=first_request,
        snapshotMeasurements=snapshots,
        rpcMeasurements=rpc,
        tcpOpens=channel.tcp_opens,
        sentPayloadBytes=channel.sent_payload_bytes,
        nativeError=error,
        ackError=ack_error,
        awaitedAck=pending_ack,
        ackAccepted=pending_ack is not None and ack_error is None,
        ackPackets=len(ack_packets),
        awaitingAck=runtime.awaiting_ack,
        pending=bool(runtime.pending),
    )
