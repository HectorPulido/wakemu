"""Separate Jondo turn adapter; native World alone publishes game actions."""
import json
import math
import os
import time
import uuid
import logging
from contextlib import contextmanager

from ..native.native_oracle import NativeOracle
from ..native.native_stats import NativeStats
from ..native.native_store import load_authorities
from ..native.native_control import effective_server_controlled
from ..native.native_deadline import bounded, check
from ..transport.framed import FramedClient
from ..transport.endpoint import tcp_address
from .jondo_snapshot import build_snapshot


_LOG = logging.getLogger(__name__)


@contextmanager
def _slow_native_stage(stage, actor_id, turn_id, spell_id=None):
    """Observe atomic work without retaining native state or an ACK interval."""
    wall, cpu = time.monotonic(), time.process_time()
    try:
        yield
    finally:
        elapsed = time.monotonic() - wall
        cpu_elapsed = time.process_time() - cpu
        if elapsed >= 1.0:
            try:
                _LOG.warning(
                    "Slow native AI stage=%s actor=%s turn=%s spell=%s wall_ms=%.3f cpu_ms=%.3f",
                    stage,
                    actor_id,
                    turn_id,
                    spell_id if type(spell_id) is int else None,
                    elapsed * 1000,
                    cpu_elapsed * 1000,
                )
            except Exception:
                # A diagnostic sink must not replace a native result/error.
                pass


def action_key(action):
    return json.dumps(action, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _service_timing(reply):
    timing = reply.get("serviceTiming")
    if (
        not isinstance(timing, dict)
        or timing.get("scope") != "received_frame_to_completed_decision"
    ):
        return None
    result = {}
    for name in ("parseMs", "queueWaitMs", "planningMs", "totalMs"):
        value = timing.get(name)
        if type(value) not in (int, float):
            return None
        try:
            value = float(value)
        except OverflowError:
            return None
        if not math.isfinite(value) or value < 0:
            return None
        result[name] = value
    return dict(result, scope="received_frame_to_completed_decision")


def checked_actions(reply, request):
    if (
        not isinstance(reply, dict)
        or type(reply.get("protocol")) is not int
        or reply.get("protocol") != 1
        or reply.get("requestId") != request["requestId"]
        or reply.get("source") != request["source"]
    ):
        raise ValueError("Jondo decision belongs to a foreign native source")
    actions = [reply.get("action")]
    alternatives = reply.get("alternatives", [])
    if not isinstance(alternatives, list) or len(alternatives) > 32:
        raise ValueError("Invalid Jondo alternative actions")
    actions.extend(alternatives)
    seen = set()
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Invalid Jondo chosen action")
        key = action_key(action)
        if key not in seen:
            seen.add(key)
            yield action


def run_prepared_turn(
    runtime,
    oracle,
    serializer,
    transport,
    *,
    deadline,
    max_actions=12,
    max_rejections=8
):
    """Certify only chosen actions; a rejected choice never spends resources."""
    fight = runtime.fight
    actor_id, turn_id = fight.current.id, fight.turn_id

    def current_position():
        current = runtime.fight.current
        if current is not None and current.id == actor_id:
            position = getattr(current, "position", None)
            if position is not None:
                return tuple(position)
        return None

    # A successful cast changes the tactical situation and permits returning
    # through earlier cells (for example attack, then flee through a portal).
    # Movement alone must not repeatedly undo its own destination choices.
    position = current_position()
    movement_destinations = {position} if position is not None else set()
    turn_actions = []
    for _ in range(max_actions):
        fight = runtime.fight
        if (
            fight.phase != "active"
            or fight.current is None
            or (fight.current.id, fight.turn_id) != (actor_id, turn_id)
            or runtime.awaiting_ack is not None
            or runtime.pending
        ):
            return
        if time.monotonic() >= deadline:
            break
        rejected, failures = [], []
        committed = False
        prepared = None
        decision_started = time.monotonic()
        decision_phases = dict(snapshot=0.0, plannerRpc=0.0, nativeCommit=0.0)
        decision_attempts, busy_retries = 0, 0
        # Re-query the same unchanged source with rejection feedback before
        # giving up. A legal alternative must not disappear behind one invalid
        # Jondo suggestion caused by advisory Dofus/Wakfu differences.
        for retry in range(3):
            fight = runtime.fight
            if (
                fight is None
                or fight.phase != "active"
                or fight.current is None
                or (fight.current.id, fight.turn_id) != (actor_id, turn_id)
                or runtime.awaiting_ack is not None
                or runtime.pending
            ):
                return
            with bounded(deadline):
                check()
                snapshot_started = time.monotonic()
                budget_ms = max(
                    1, min(2000, int((deadline - time.monotonic()) * 1000) - 100)
                )
                if (
                    prepared is not None
                    and oracle.state_identity(runtime)
                    != prepared["source"]["nativeIdentity"]
                ):
                    # Another transition invalidates both cached facts and
                    # legality failures belonging to the previous source.
                    prepared = None
                    rejected, failures = [], []
                if prepared is None:
                    prepared = build_snapshot(
                        oracle, excluded_actions=rejected, budget_ms=budget_ms
                    )
                check()
                budget_ms = max(
                    1, min(2000, int((deadline - time.monotonic()) * 1000) - 100)
                )
                # Keep prepared facts private to this unchanged-source retry
                # group. Every RPC still owns fresh custody and feedback data.
                request = dict(
                    prepared,
                    requestId=uuid.uuid4().hex,
                    source=dict(prepared["source"]),
                    excludedActions=list(rejected),
                    limits=dict(prepared.get("limits", {}), budgetMs=budget_ms),
                    native=dict(
                        prepared.get("native", {}),
                        turnActions=[dict(row) for row in turn_actions],
                    ),
                )
                snapshot_ms = (time.monotonic() - snapshot_started) * 1000
                decision_phases["snapshot"] += snapshot_ms
                rpc_started = time.monotonic()
                decision_attempts += 1
                try:
                    status, reply = transport.request(
                        "/jondo/decide", request, deadline=deadline
                    )
                finally:
                    rpc_ms = (time.monotonic() - rpc_started) * 1000
                    decision_phases["plannerRpc"] += rpc_ms
            if status != 200:
                if status == 503 and retry < 2:
                    with _slow_native_stage(
                        "identity_busy_reply", actor_id, turn_id
                    ), bounded(deadline):
                        if (
                            oracle.state_identity(runtime)
                            != request["source"]["nativeIdentity"]
                        ):
                            raise ValueError(
                                "Native source changed during Jondo decision"
                            )
                    fight = runtime.fight
                    if (
                        fight is None
                        or fight.phase != "active"
                        or fight.current is None
                        or (fight.current.id, fight.turn_id) != (actor_id, turn_id)
                        or runtime.awaiting_ack is not None
                        or runtime.pending
                    ):
                        return
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Native AI turn deadline reached")
                    # Capacity errors can clear while another owner finishes.
                    # Keep the same source and existing attempt/deadline budget;
                    # no rejected native effect or payment is replayed here.
                    busy_retries += 1
                    time.sleep(min(0.025, remaining))
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Native AI turn deadline reached")
                    with bounded(deadline):
                        if (
                            oracle.state_identity(runtime)
                            != request["source"]["nativeIdentity"]
                        ):
                            raise ValueError(
                                "Native source changed during Jondo capacity retry"
                            )
                    continue
                raise ValueError("Jondo service rejected compact snapshot")
            with _slow_native_stage("identity_reply", actor_id, turn_id), bounded(
                deadline
            ):
                if (
                    oracle.state_identity(runtime)
                    != request["source"]["nativeIdentity"]
                ):
                    raise ValueError("Native source changed during Jondo decision")
            candidates = list(checked_actions(reply, request))
            # An end-turn suggestion is used after this reply's concrete
            # alternatives have had their own native validation opportunity.
            if rejected:
                candidates.sort(key=lambda action: action.get("type") == "end_turn")
            for action in candidates:
                key = action_key(action)
                if key in rejected:
                    continue
                if action.get("type") == "end_turn" and rejected and retry < 2:
                    continue
                with _slow_native_stage(
                    "identity_candidate", actor_id, turn_id, action.get("spellId")
                ), bounded(deadline):
                    before = oracle.state_identity(runtime)
                try:
                    destination = None
                    if action.get("type") == "move" and action.get("path"):
                        destination = tuple(action["path"][-1])
                    elif action.get("type") == "portal_travel" and action.get(
                        "destination"
                    ):
                        destination = tuple(action["destination"])
                    if destination is not None and destination in movement_destinations:
                        raise ValueError(
                            "Movement revisits a destination without an intervening cast"
                        )
                    # commit() prepares the chosen action on its private native
                    # transaction, validates it and stages all packets before
                    # adoption. No advisory forecast is ever adopted here.
                    commit_started = time.monotonic()
                    try:
                        with _slow_native_stage(
                            "native_commit", actor_id, turn_id, action.get("spellId")
                        ), bounded(deadline):
                            commit_kwargs = dict(stats_serializer=serializer)
                            if action.get("type") == "end_turn":
                                from .jondo_facing import defensive_facing

                                evidence = defensive_facing(request)
                                if evidence is not None:
                                    commit_kwargs["defensive_facing"] = evidence
                            packets = oracle.commit(action, **commit_kwargs)
                    finally:
                        commit_ms = (time.monotonic() - commit_started) * 1000
                        decision_phases["nativeCommit"] += commit_ms
                except (ValueError, TypeError) as error:
                    with _slow_native_stage(
                        "identity_rejection", actor_id, turn_id, action.get("spellId")
                    ), bounded(deadline):
                        if oracle.state_identity(runtime) != before:
                            raise ValueError(
                                "Rejected Jondo action mutated native state"
                            ) from error
                    rejected.append(key)
                    failures.append(
                        dict(
                            action=action, error=type(error).__name__, detail=str(error)
                        )
                    )
                    if len(rejected) >= max_rejections:
                        break
                    continue
                position = current_position()
                observed = dict(type=action["type"])
                if action.get("type") == "cast":
                    observed["spellId"] = action["spellId"]
                if type(action.get("targetId")) is int:
                    observed["targetId"] = action["targetId"]
                if isinstance(action.get("target"), (tuple, list)):
                    observed["target"] = list(action["target"])
                elif destination is not None and position is not None:
                    observed["target"] = list(position)
                turn_actions.append(observed)
                if action.get("type") == "cast":
                    movement_destinations = (
                        {position} if position is not None else set()
                    )
                elif position is not None:
                    movement_destinations.add(position)
                yield packets, dict(
                    protocol=1,
                    planner="jondo",
                    requestId=request["requestId"],
                    source=request["source"],
                    action=action,
                    rejectedActions=failures,
                    phaseElapsedMs=dict(
                        snapshot=snapshot_ms, plannerRpc=rpc_ms, nativeCommit=commit_ms
                    ),
                    decisionPhaseElapsedMs=dict(decision_phases),
                    decisionAttempts=decision_attempts,
                    busyRetries=busy_retries,
                    decisionElapsedMs=(time.monotonic() - decision_started) * 1000,
                    jondoElapsedMs=reply.get("elapsedMs"),
                    jondoServiceTiming=_service_timing(reply),
                    jondoPlanReused=reply.get("planReused", False),
                    strategyId=reply.get("strategyId", "normal-jondo"),
                    strategyMode=reply.get("strategyMode", "normal"),
                    strategyReason=reply.get("strategyReason"),
                )
                committed = True
                if action.get("type") == "end_turn":
                    return
                break
            if committed or len(rejected) >= max_rejections:
                break
        if not committed:
            break
    fight = runtime.fight
    if (
        fight.phase == "active"
        and fight.current is not None
        and (fight.current.id, fight.turn_id) == (actor_id, turn_id)
        and runtime.awaiting_ack is None
        and not runtime.pending
    ):
        # The native turn barrier remains available after a network/decision
        # allowance. It preserves existing client ACK and FIFO publication.
        with _slow_native_stage("native_turn_barrier", actor_id, turn_id):
            barrier_packets = runtime.end_server_turn(actor_id, turn_id)
        yield barrier_packets, dict(
            action={"type": "end_turn"},
            planner="jondo",
            reason="jondo_native_turn_barrier",
        )


def run_npc_turn(
    runtime,
    *,
    store=None,
    viewer_character=None,
    monsters=None,
    stats_serializer=None,
    shared_adapter=None,
    session=None,
    world_context=None
):
    """Use the existing owner/Registry interface without the legacy planner."""
    if world_context is not None:
        from .world_host import execute

        yield from execute(runtime, world_context, run_npc_turn)
        return
    if session is not None:
        if shared_adapter is None:
            raise ValueError("Shared Jondo AI requires its encounter coordinator")
        from .world_shared import run_shared_turn

        yield from run_shared_turn(
            runtime,
            shared_adapter,
            session,
            lambda candidate: run_npc_turn(
                candidate,
                store=store,
                viewer_character=viewer_character,
                monsters=monsters,
                stats_serializer=stats_serializer,
            ),
        )
        return
    if (
        runtime.fight is None
        or runtime.fight.current is None
        or runtime.fight.phase != "active"
        or runtime.awaiting_ack is not None
        or runtime.pending
    ):
        return
    from wakfu_server.combat_automatic_npc_turn import requires_automatic_npc_turn_end

    actor_id, turn_id = runtime.fight.current.id, runtime.fight.turn_id
    if requires_automatic_npc_turn_end(runtime.fight, runtime.fight.current):
        yield runtime.end_automatic_npc_turn(actor_id, turn_id), dict(
            action={"type": "end_turn"},
            planner="jondo",
            reason="ordinary_root_without_action_controller",
        )
        return
    if not effective_server_controlled(runtime.fight, runtime.fight.current):
        return
    from psycopg import Error as DatabaseError

    transport = None
    try:
        entered = time.monotonic()
        preparation = getattr(runtime, "native_ai_preparation_started_at", entered)
        if type(preparation) not in (int, float) or not math.isfinite(preparation):
            raise ValueError("Invalid Jondo owner preparation clock")
        started = min(entered, preparation)
        deadline = started + (20 if runtime.fight.current.turn_count == 1 else 10)
        with bounded(deadline):
            authorities = load_authorities(
                runtime, store, monsters, viewer_id=viewer_character["id"]
            )
            if not hasattr(runtime, "tactical_encounter_id"):
                runtime.tactical_encounter_id = (
                    getattr(runtime.fight, "native_ai_fight_uuid", None)
                    or uuid.uuid4().hex
                )
            flags = dict(
                native_area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "0")
                == "1",
                native_start_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1")
                == "1",
                native_environment={
                    key: value
                    for key, value in os.environ.items()
                    if key.startswith("WAKFU_NATIVE_")
                },
            )
            oracle = NativeOracle(
                runtime,
                characters=authorities["characters"],
                monsters=authorities["monsters"],
                decks=authorities["decks"],
                excluded_decks=authorities["excluded_decks"],
                viewer_id=viewer_character["id"],
                flags=flags,
            )
            serializer = NativeStats(
                characters=authorities["characters"],
                monsters=authorities["monsters"],
                fight_id=runtime.fight.id,
                registrations=authorities["registrations"],
                map_id=viewer_character["map_id"],
            )
            from .backend_selection import pinned_endpoint

            endpoint = pinned_endpoint(runtime, expected_backend="jondo")
            if not endpoint.startswith("tcp://"):
                raise ValueError("Jondo AI requires explicit TCP framing")
            host, port = tcp_address(endpoint)
            transport = FramedClient(host, port, timeout=20)
        # Candidate work uses short bounded scopes inside the driver. Do not
        # retain an AI deadline across yielded FIFO delivery or the final native
        # turn barrier, matching the existing World action driver's contract.
        yield from run_prepared_turn(
            runtime, oracle, serializer, transport, deadline=deadline
        )
    except (ValueError, TypeError, OSError, DatabaseError) as error:
        fight = runtime.fight
        if (
            fight.phase == "active"
            and fight.current is not None
            and (fight.current.id, fight.turn_id) == (actor_id, turn_id)
            and runtime.awaiting_ack is None
            and not runtime.pending
        ):
            yield runtime.end_server_turn(actor_id, turn_id), dict(
                action={"type": "end_turn"},
                planner="jondo",
                reason="jondo_native_bridge_rejected",
                error=type(error).__name__,
                detail=str(error),
            )
    finally:
        if transport is not None:
            transport.close()
