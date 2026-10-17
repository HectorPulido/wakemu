"""Typed offline reproduction of recipient snapshot producers and corrections.

The current producer has one recorded expectation. Matching that observation is
reproduction evidence, not a native-client oracle or live session admission.
Actor serialization bytes are explicit inputs with a declared authority label.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from .combat_reproduction import (
    source_identity,
    catalog_identity,
    controlled_environment,
    capture_clocks,
    digest,
    compare_expectation,
    ReproductionClock,
)
from .combat_reproduction_state import encode_state, decode_state, MAX_BYTES

SCHEMA = "wakemu-combat-recipient-reproduction-v2"
BOUNDARY = "offline-snapshot-producer-not-session-admission-or-client-rendering"


def capture_recipient_request(
    fight,
    shared,
    *,
    role,
    actor_payloads,
    payload_authority,
    deadline_ms=None,
    session_account_id=None,
    clocks=None,
    policies=None
):
    if role not in ("spectator", "owner"):
        raise ValueError("Unknown recipient reproduction role")
    if payload_authority not in ("native-runtime-serializer", "test-placeholder"):
        raise ValueError("Explicit actor payload authority is required")
    runtime = shared.runtime
    runtime_data = {
        key: getattr(runtime, key, None)
        for key in ("native_action_id", "awaiting_ack", "turn_deadline")
    }
    shared_data = {
        key: getattr(shared, key, None)
        for key in (
            "map_id",
            "instance_id",
            "join_context",
            "ack",
            "is_duel",
            "reconnect_remaining_turn_seconds",
            "reconnect_turn_end_packets",
        )
    }
    clocks = capture_clocks() if clocks is None else clocks
    policies = (
        {"WAKFU_NATIVE_AREA_CALLBACKS": "1", "WAKFU_NATIVE_GRANTED_CAST": "0"}
        if policies is None
        else policies
    )
    return dict(
        schema=SCHEMA,
        boundary=BOUNDARY,
        source=source_identity(),
        catalog={**catalog_identity(), "bundle_sha256": None},
        clocks=dict(clocks),
        policies=dict(policies),
        before=encode_state(
            dict(
                fight=fight,
                shared=shared_data,
                runtime=runtime_data,
                role=role,
                actor_payloads=actor_payloads,
                payload_authority=payload_authority,
                deadline_ms=deadline_ms,
                session_account_id=session_account_id,
            )
        ),
        expected=None,
    )


def _validate(case):
    if (
        type(case) is not dict
        or case.get("schema") != SCHEMA
        or case.get("boundary") != BOUNDARY
        or set(case)
        != {
            "schema",
            "boundary",
            "source",
            "catalog",
            "clocks",
            "policies",
            "before",
            "expected",
        }
    ):
        raise ValueError("Invalid recipient reproduction capsule")
    if len(json.dumps(case, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("Recipient capsule exceeds size bound")


def execute_recipient_case(case, *, allow_source_drift=False):
    _validate(case)
    source = source_identity()
    if source != case["source"] and not allow_source_drift:
        raise ValueError("Recipient reproduction source differs")
    if catalog_identity() != {
        key: case["catalog"][key] for key in ("revision", "inventory_sha256")
    }:
        raise ValueError("Recipient reproduction catalog differs")
    request = decode_state(case["before"])
    if set(request) != {
        "fight",
        "shared",
        "runtime",
        "role",
        "actor_payloads",
        "payload_authority",
        "deadline_ms",
        "session_account_id",
    }:
        raise ValueError("Incomplete recipient request graph")
    if request["role"] not in ("spectator", "owner"):
        raise ValueError("Unknown recipient role")
    if request["payload_authority"] not in (
        "native-runtime-serializer",
        "test-placeholder",
    ):
        raise ValueError("Unknown actor payload authority")
    shared = SimpleNamespace(**request["shared"])
    clock = ReproductionClock(case["clocks"])
    shared.runtime = SimpleNamespace(**request["runtime"], clock=clock)
    fight = request["fight"]
    before = encode_state(request)

    def actor_payload(fight, actor, *unused):
        pair = request["actor_payloads"][actor.id]
        if (
            type(pair) is not tuple
            or len(pair) != 2
            or any(type(value) is not bytes for value in pair)
        ):
            raise ValueError("Invalid captured actor payload")
        return pair

    packets, error = (), None
    with controlled_environment(case["clocks"], case["policies"]):
        try:
            if request["role"] == "spectator":
                from .combat_spectator_snapshot import current_snapshot

                packets = current_snapshot(
                    fight,
                    shared,
                    actor_payload=actor_payload,
                    deadline_ms=request["deadline_ms"],
                )
            else:
                from .combat_reconnect_snapshot import owned_snapshot

                packets = owned_snapshot(
                    fight,
                    shared,
                    SimpleNamespace(account_id=request["session_account_id"]),
                    actor_payload=actor_payload,
                )
        except ValueError as failure:
            error = dict(
                type=type(failure).__module__ + "." + type(failure).__name__,
                message=str(failure),
            )
    # Snapshot producers receive reconstructed namespaces. Copy their final
    # data fields back into the comparison graph so attribute mutations cannot
    # disappear merely because namespace construction copied a dictionary.
    if shared.runtime.clock is not clock:
        raise ValueError("Recipient snapshot producer replaced its diagnostic clock")
    request["runtime"] = {
        key: value for key, value in vars(shared.runtime).items() if key != "clock"
    }
    request["shared"] = {
        key: value for key, value in vars(shared).items() if key != "runtime"
    }
    after = encode_state(request)
    if after != before:
        raise ValueError("Recipient snapshot producer mutated its captured input graph")
    if source_identity() != source:
        raise ValueError("Source changed during recipient reproduction")
    result = encode_state(dict(state=after, packets=tuple(packets), error=error))
    return dict(
        result=result,
        sha256=digest(result),
        status="returned" if error is None else "raised",
        source_sha256=source["sha256"],
        source_matches=source == case["source"],
        catalog_matches=True,
        catalog_revision=case["catalog"]["revision"],
        input_unchanged=True,
        rng_boundary="snapshot-recipe-consumes-no-rng",
        payload_authority=request["payload_authority"],
    )


def record_recipient_expectation(case, result):
    _validate(case)
    case["expected"] = dict(result=result["result"], sha256=result["sha256"])


def compare_recipient_expectation(case, result):
    _validate(case)
    return compare_expectation(case, result)


def read_recipient_case(path):
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Recipient capsule exceeds size bound")
    case = json.loads(raw)
    _validate(case)
    return case
