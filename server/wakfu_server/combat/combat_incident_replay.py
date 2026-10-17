"""Compare an observed runtime incident with an explicit offline provider recipe.

This qualifies only a particular operation outcome. Shared routing, bootstrap,
collective ACK and arbitrary live provider equivalence remain separate claims.
The incident is evidence, not executable code or an instruction to change rules.
"""
import hashlib
import json
import os
from pathlib import Path
import random
from copy import deepcopy

from .combat_incident_capture import SCHEMA
from .combat_reproduction import (
    SCHEMA as CASE_SCHEMA,
    execute_case,
    digest,
    compare_expectation,
    bind_catalog_bundle,
    verify_catalog_bundle,
    source_identity,
    catalog_identity,
    controlled_environment,
    ReproductionClock,
)
from .combat_reproduction_state import decode_state, encode_state, MAX_BYTES

RECIPE = "ordinary-server-runtime-v1"
LIVE_RECIPE = "observed-live-server-v1"
SHARED_SCHEMA = "wakemu-shared-combat-incident-v1"
NPC_SCHEMA = "wakemu-combat-npc-incident-v1"
NPC_RECIPE = "native-oracle-chosen-action-v1"
NPC_PUBLICATION_SCHEMA = "wakemu-combat-npc-publication-v1"
NPC_PUBLICATION_RECIPE = "native-npc-publication-v1"
SUPPORTED_ACTIONS = frozenset(
    {"player_spell", "player_weapon", "player_unarmed", "move", "end_turn"}
)


class IncidentReplayError(RuntimeError):
    """An incident lacks evidence needed to compare its actual execution."""


def read_incident(path):
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise IncidentReplayError("Incident exceeds size bound")
    try:
        receipt = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise IncidentReplayError("Incident is not valid bounded JSON") from error
    if type(receipt) is not dict or receipt.get("schema") not in (
        SCHEMA,
        SHARED_SCHEMA,
        NPC_SCHEMA,
        NPC_PUBLICATION_SCHEMA,
    ):
        raise IncidentReplayError("Unsupported incident schema or boundary")
    if receipt.get("before") is None or receipt.get("after") is None:
        raise IncidentReplayError("Incident state capture is incomplete")
    return receipt


def write_incident(path, receipt):
    raw = json.dumps(receipt, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_BYTES:
        raise IncidentReplayError("Incident exceeds size bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _catalog_case(receipt):
    return {
        "catalog": {
            **receipt["identity"]["catalog"],
            "bundle_sha256": receipt.get("catalog_bundle_sha256"),
        }
    }


def bind_incident_bundle(receipt, root):
    case = _catalog_case(receipt)
    bind_catalog_bundle(case, root)
    receipt["catalog_bundle_sha256"] = case["catalog"]["bundle_sha256"]
    return receipt


def verify_incident_bundle(receipt, root):
    verify_catalog_bundle(_catalog_case(receipt), root)


def replay_runtime_incident(
    receipt, *, provider_recipe, allow_source_drift=False, evidence_sink=None
):
    """Execute a captured request, without rebuilding a scene or live services.

    Selecting a recipe is explicit. Matching state and exact operation bytes is
    per-case evidence; it does not accredit all callbacks or final recipients.
    A mismatching observed-input tape is an infrastructure error, never an
    expected game rejection.
    """
    if receipt.get("schema") == NPC_PUBLICATION_SCHEMA:
        if evidence_sink is not None:
            raise IncidentReplayError(
                "Delivery sidecars currently require a shared player incident"
            )
        return replay_npc_publication_incident(
            receipt,
            provider_recipe=provider_recipe,
            allow_source_drift=allow_source_drift,
        )
    if receipt.get("schema") == NPC_SCHEMA:
        if evidence_sink is not None:
            raise IncidentReplayError("Shared evidence sink requires a shared incident")
        return replay_npc_incident(
            receipt,
            provider_recipe=provider_recipe,
            allow_source_drift=allow_source_drift,
        )
    if receipt.get("schema") == SHARED_SCHEMA:
        return replay_shared_incident(
            receipt,
            provider_recipe=provider_recipe,
            allow_source_drift=allow_source_drift,
            evidence_sink=evidence_sink,
        )
    if evidence_sink is not None:
        raise IncidentReplayError("Shared evidence sink requires a shared incident")
    if provider_recipe != RECIPE:
        raise IncidentReplayError("Unsupported explicit provider recipe")
    if (
        receipt.get("schema") != SCHEMA
        or receipt.get("delivery_boundary")
        != "operation_packets_before_shared_postprocessing"
    ):
        raise IncidentReplayError("Unsupported incident execution boundary")
    identity = receipt.get("identity")
    if type(identity) is not dict or set(identity) != {
        "source",
        "catalog",
        "dispatcher_sha256",
    }:
        raise IncidentReplayError("Missing incident source/catalog identity")
    server = Path(__file__).resolve().parents[2]
    dispatcher_matches = (
        hashlib.sha256((server / "local_game_server.py").read_bytes()).hexdigest()
        == identity["dispatcher_sha256"]
    )
    if not dispatcher_matches and not allow_source_drift:
        raise IncidentReplayError("Incident dispatcher source differs")
    before, after = decode_state(receipt["before"]), decode_state(receipt["after"])
    if set(before) != {
        "runtime",
        "action",
        "inputs",
        "session",
        "bootstrap",
        "recipients",
    } or set(after) != {"runtime", "packets"}:
        raise IncidentReplayError("Incomplete incident action boundary")
    action = before["action"]
    if type(action) is not dict or action.get("type") not in SUPPORTED_ACTIONS:
        raise IncidentReplayError("Incident action has no ordinary offline recipe")
    if before["inputs"].get("authority_recipe") != "observed-live-server-v1":
        raise IncidentReplayError("Incident authority boundary is unknown")
    observations = decode_state(receipt["observations"])
    inputs = dict(before["inputs"], authority_recipe=provider_recipe)
    # Diagnostic provider binding occurs before the tape. Gameplay then gets
    # each actual internal/external stream through replay_rng_argument.
    rng = random.Random(0)
    graph = encode_state({**before, "inputs": inputs, "rng_state": rng.getstate()})
    case = {
        "schema": CASE_SCHEMA,
        "source": identity["source"],
        "catalog": {**identity["catalog"], "bundle_sha256": None},
        "clocks": receipt.get("clocks"),
        "policies": receipt.get("policies"),
        "before": graph,
        "expected": None,
        "boundary": "isolated-runtime-action-not-live-session-recovery",
    }
    result = execute_case(
        case, allow_source_drift=allow_source_drift, observations=observations
    )
    outcome = decode_state(result["result"])
    actual = encode_state(
        {"runtime": outcome["runtime"], "packets": outcome["packets"]}
    )
    expected_view = {
        "state": receipt["after"],
        "error": receipt["error"],
        "raised": receipt["status"] == "raised",
    }
    actual_view = {
        "state": actual,
        "error": outcome["error"],
        "raised": result["status"] != "accepted",
    }
    # Runtime service implementations are represented separately by provider
    # identity. Compare their exact typed data graph, not callable objects.
    expected_view["state"] = {
        key: value for key, value in expected_view["state"].items() if key != "services"
    }
    actual_view["state"] = {
        key: value for key, value in actual_view["state"].items() if key != "services"
    }
    comparison = compare_expectation(
        {"expected": {"result": expected_view, "sha256": digest(expected_view)}},
        {"result": actual_view, "sha256": digest(actual_view)},
    )
    return {
        "incident_id": receipt["incident_id"],
        "operation_matches": comparison["matches"],
        "differences": comparison["differences"],
        "expected_sha256": digest(expected_view),
        "actual_sha256": digest(actual_view),
        "status": result["status"],
        "source_matches": result["source_matches"],
        "dispatcher_matches": dispatcher_matches,
        "catalog_matches": result["catalog_matches"],
        "provider_recipe": provider_recipe,
        "rng_ownership_known": outcome["input_replay"]["ownership_known"],
        "shared_delivery_qualified": False,
        "provider_equivalence": "observed-operation-outcome-only",
    }


def replay_npc_incident(receipt, *, provider_recipe, allow_source_drift=False):
    """Expose the chosen-action comparator through the common private CLI.

    The summary contains hashes, never the captured state or packet payloads.
    SDK source drift is intentionally unsupported by this recipe.
    """
    if provider_recipe != NPC_RECIPE:
        raise IncidentReplayError("Unsupported explicit NPC provider recipe")
    if allow_source_drift:
        raise IncidentReplayError(
            "NPC reproduction requires identical engine and SDK sources"
        )
    server = Path(__file__).resolve().parents[2]
    dispatcher_hash = hashlib.sha256(
        (server / "local_game_server.py").read_bytes()
    ).hexdigest()
    if receipt.get("identity", {}).get("dispatcher_sha256") != dispatcher_hash:
        raise IncidentReplayError("Incident dispatcher source differs")
    from .combat_npc_reproduction import after_state_projection, replay_npc_receipt

    result = replay_npc_receipt(receipt)
    expected = {
        "state": after_state_projection(receipt["after"]),
        "error": receipt["error"],
    }
    actual = {
        "state": after_state_projection(result["after"]),
        "error": result["error"],
    }
    comparison = compare_expectation(
        {"expected": {"result": expected, "sha256": digest(expected)}},
        {"result": actual, "sha256": digest(actual)},
    )
    return {
        "incident_id": receipt["incident_id"],
        "operation_matches": comparison["matches"],
        "differences": comparison["differences"],
        "expected_sha256": digest(expected),
        "actual_sha256": digest(actual),
        "status": "accepted" if result["error"] is None else "raised",
        "source_matches": True,
        "catalog_matches": True,
        "sdk_source_matches": True,
        "dispatcher_matches": True,
        "provider_recipe": provider_recipe,
        "shared_delivery_qualified": False,
        "state_comparison": "exact-domain-graph-with-immutable-scalar-values-v1",
        "boundary": result["boundary"],
    }


def replay_npc_publication_incident(
    receipt, *, provider_recipe, allow_source_drift=False
):
    """Summarize recomputed chosen attacks and actual Registry publication."""
    if provider_recipe != NPC_PUBLICATION_RECIPE or allow_source_drift:
        raise IncidentReplayError(
            "NPC publication requires its explicit recipe and identical sources"
        )
    server = Path(__file__).resolve().parents[2]
    dispatcher = hashlib.sha256(
        (server / "local_game_server.py").read_bytes()
    ).hexdigest()
    if receipt.get("identity", {}).get("dispatcher_sha256") != dispatcher:
        raise IncidentReplayError("Incident dispatcher source differs")
    from .combat_npc_publication import replay_npc_publication
    from .combat_npc_reproduction import after_state_projection

    result = replay_npc_publication(receipt)
    expected = {
        "state": after_state_projection(receipt["after"]),
        "error": receipt["error"],
        "return_value": receipt["return_value"],
        "return_recorded": receipt["return_recorded"],
        "transition": after_state_projection(receipt["transition"]),
    }
    actual = {
        "state": after_state_projection(result["after"]),
        "error": result["error"],
        "return_value": result["return_value"],
        "return_recorded": result["error"] is None,
        "transition": after_state_projection(result["transition"]),
    }
    comparison = compare_expectation(
        {"expected": {"result": expected, "sha256": digest(expected)}},
        {"result": actual, "sha256": digest(actual)},
    )
    return {
        "incident_id": receipt["incident_id"],
        "operation_matches": comparison["matches"],
        "mailbox_matches": comparison["matches"],
        "differences": comparison["differences"],
        "expected_sha256": digest(expected),
        "actual_sha256": digest(actual),
        "status": "returned" if result["error"] is None else "raised",
        "source_matches": True,
        "catalog_matches": True,
        "sdk_source_matches": True,
        "dispatcher_matches": True,
        "provider_recipe": provider_recipe,
        "shared_delivery_qualified": False,
        "bootstrap_qualified": False,
        "dispatch_qualified": False,
        "boundary": result["boundary"],
        "state_comparison": "exact-domain-graph-with-immutable-scalar-values-v1",
    }


def _shared_view(payload):
    return {
        **payload,
        "graph": {
            key: value for key, value in payload["graph"].items() if key != "services"
        },
    }


def replay_shared_incident(
    receipt, *, provider_recipe, allow_source_drift=False, evidence_sink=None
):
    """Run actual Registry guards, action, ACK and mailbox publication privately."""
    if evidence_sink is not None and not callable(evidence_sink):
        raise IncidentReplayError("Evidence sink must be a trusted local callable")
    if provider_recipe != LIVE_RECIPE:
        raise IncidentReplayError(
            "Shared incidents require the explicit live-server provider recipe"
        )
    if (
        receipt.get("schema") != SHARED_SCHEMA
        or receipt.get("delivery_boundary")
        != "registry_mailboxes_after_shared_postprocessing"
    ):
        raise IncidentReplayError("Unsupported shared incident boundary")
    identity = receipt.get("identity")
    if type(identity) is not dict or set(identity) != {
        "source",
        "catalog",
        "dispatcher_sha256",
    }:
        raise IncidentReplayError("Missing shared source/catalog identity")
    current_source = source_identity()
    source_matches = current_source == identity["source"]
    server = Path(__file__).resolve().parents[2]
    dispatcher_matches = (
        hashlib.sha256((server / "local_game_server.py").read_bytes()).hexdigest()
        == identity["dispatcher_sha256"]
    )
    if not allow_source_drift and not (source_matches and dispatcher_matches):
        raise IncidentReplayError("Shared incident sources differ")
    if catalog_identity() != identity["catalog"]:
        raise IncidentReplayError("Shared incident catalog differs")
    from .combat_shared_reproduction import (
        restore_shared_state,
        capture_shared_state,
        LeaseReplayMismatch,
        UnsupportedSharedReproduction,
    )
    from .combat_shared_incident_capture import suppress_shared_incidents
    from .combat_input_observation import replay_combat_inputs, InputReplayMismatch
    from .combat_live_reproduction import prepare_live_context
    from .combat_shared import Transition

    request = decode_state(receipt["request"])
    observations = decode_state(receipt["observations"])
    leases = decode_state(receipt["lease_observations"])
    operations = receipt.get("operations")
    if type(operations) is not list or len(operations) > 1:
        raise IncidentReplayError("Shared operation evidence is ambiguous")
    operation = decode_state(operations[0]) if operations else None
    if operation is not None:
        action = operation["action"]
        inputs = dict(
            operation["inputs"], live_provider_identity=operation["provider_identity"]
        )
    else:
        action = None
        inputs = {"live_provider_identity": receipt.get("provider_identity", {})}
    context = None
    clock = ReproductionClock(receipt["clocks"])

    def bind(runtime, shared):
        nonlocal context
        context = prepare_live_context(runtime, action, inputs, clock, observations)

    operation_packets = ()

    def execute(candidate, runtime):
        nonlocal operation_packets
        if action is None:
            raise IncidentReplayError(
                "Registry reached an operation without captured authority"
            )
        result = context.execute(runtime, action)
        operation_packets = tuple(result["packets"])
        return Transition(result["state"], runtime, operation_packets)

    def release(candidate, runtime, body):
        nonlocal operation_packets
        context.rebind_copy(runtime)
        operation_packets = tuple(runtime.acknowledge_turn(body))
        return Transition(runtime.fight, runtime, operation_packets)

    error = None
    returned = False
    value = None
    with controlled_environment(
        receipt["clocks"], receipt["policies"]
    ), suppress_shared_incidents():
        registry, shared, lease_tape = restore_shared_state(
            receipt["before"], leases, bind_runtime=bind
        )
        with replay_combat_inputs(observations) as input_tape:
            try:
                if request["type"] == "execute":
                    value = registry.execute(
                        shared.fight.id,
                        request["session"],
                        request["actor_id"],
                        execute,
                        expected_sequence=request["expected_sequence"],
                        require_turn=request["require_turn"],
                    )
                elif request["type"] == "shared_ack":
                    value = registry.acknowledge(
                        shared.fight.id, request["session"], request["body"], release
                    )
                else:
                    raise IncidentReplayError("Unsupported Registry request")
            except (
                InputReplayMismatch,
                LeaseReplayMismatch,
                UnsupportedSharedReproduction,
                IncidentReplayError,
            ):
                raise
            except Exception as failure:
                error = {
                    "type": type(failure).__module__ + "." + type(failure).__name__,
                    "message": str(failure),
                }
            else:
                returned = True
        lease_tape.assert_consumed()
        context.assert_complete()
        actual_after = capture_shared_state(shared, registry=registry)
    if source_identity() != current_source:
        raise IncidentReplayError("Shared incident sources changed during replay")
    expected = {
        "state": _shared_view(receipt["after"]),
        "error": receipt["error"],
        "return_value": receipt["return_value"],
        "return_recorded": receipt["return_recorded"],
        "operation_packets": receipt["operation_packets"],
    }
    actual = {
        "state": _shared_view(actual_after),
        "error": error,
        "return_value": value,
        "return_recorded": returned,
        "operation_packets": encode_state(operation_packets),
    }
    comparison = compare_expectation(
        {"expected": {"result": expected, "sha256": digest(expected)}},
        {"result": actual, "sha256": digest(actual)},
    )
    # A trusted verifier may inspect recomputed private mailboxes. Keep them
    # outside the public summary and detach them from the comparison graph.
    if evidence_sink is not None:
        evidence_sink(deepcopy(actual_after))
    return {
        "incident_id": receipt["incident_id"],
        "operation_matches": comparison["matches"],
        "mailbox_matches": comparison["matches"],
        "differences": comparison["differences"],
        "expected_sha256": digest(expected),
        "actual_sha256": digest(actual),
        "status": "returned" if returned else "raised",
        "source_matches": source_matches,
        "dispatcher_matches": dispatcher_matches,
        "catalog_matches": True,
        "provider_recipe": provider_recipe,
        "rng_ownership_known": input_tape.ownership_known,
        "shared_delivery_qualified": False,
        "bootstrap_qualified": False,
        "dispatch_qualified": False,
        "provider_equivalence": "observed-registry-and-mailbox-outcome-only",
    }
