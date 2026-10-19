"""Publish AI commits through the existing shared fight authority and ACKs."""
from ..native.native_control import effective_server_controlled
from wakfu_server.combat_automatic_npc_turn import requires_automatic_npc_turn_end

import time
import gzip
import uuid
from copy import deepcopy
from contextlib import nullcontext
import os

from ..context.native_context import encode_bytes
from ..planning.team_blackboard import observe, confirm
from .world_bridge import turn_catalogue_scope


class _NoPublication(Exception):
    """Abort Registry adoption when the runner produced no public outcome."""


def run_shared_turn(
    runtime,
    adapter,
    session,
    runner,
    *,
    prepare_candidate=None,
    expected_turn=None,
    expected_sequence=None,
    started_at=None,
):
    with turn_catalogue_scope():
        yield from _run_shared_turn(
            runtime,
            adapter,
            session,
            runner,
            prepare_candidate=prepare_candidate,
            expected_turn=expected_turn,
            expected_sequence=expected_sequence,
            started_at=started_at,
        )


def _run_shared_turn(
    runtime,
    adapter,
    session,
    runner,
    *,
    prepare_candidate=None,
    expected_turn=None,
    expected_sequence=None,
    started_at=None,
):
    from wakfu_server.combat_shared import Transition

    registry = adapter.registry
    shared = registry.lookup(runtime.fight.id)
    preparation_started = time.monotonic()
    if started_at is not None:
        preparation_started = min(preparation_started, started_at)
    with shared.lock:
        registry._member(shared, session)
        current = shared.fight.current
        if (
            shared.runtime is None
            or current is None
            or not (
                effective_server_controlled(shared.fight, current)
                or requires_automatic_npc_turn_end(shared.fight, current)
            )
            or shared.runtime.awaiting_ack is not None
            or shared.runtime.pending
            or getattr(shared, "native_ai_turn_claim", None) is not None
            or expected_turn is not None
            and (current.id, shared.fight.turn_id) != expected_turn
            or expected_sequence is not None
            and shared.sequence != expected_sequence
        ):
            return
        actor_id, turn_id = current.id, shared.fight.turn_id
        claim = (actor_id, turn_id, uuid.uuid4().hex)
        shared.native_ai_turn_claim = claim

    def end_native_turn(candidate, native):
        if native is None or native.fight is not candidate:
            raise ValueError("Shared native encounter/runtime identity differs")
        if prepare_candidate is not None:
            prepare_candidate(native, session)
        return Transition(
            native.fight,
            native,
            tuple(
                native.end_automatic_npc_turn(actor_id, turn_id)
                if requires_automatic_npc_turn_end(candidate, candidate.current)
                else native.end_server_turn(actor_id, turn_id)
            ),
        )

    try:
        for action_index in range(13):
            with shared.lock:
                registry._member(shared, session)
                current = shared.fight.current
                if (
                    getattr(shared, "native_ai_turn_claim", None) != claim
                    or shared.fight.phase != "active"
                    or current is None
                    or current.id != actor_id
                    or shared.fight.turn_id != turn_id
                    or shared.runtime.awaiting_ack is not None
                    or shared.runtime.pending
                ):
                    return
                before = observe(shared.fight)
                sequence = shared.sequence
                candidate, native = deepcopy((shared.fight, shared.runtime))
                if native is None or native.fight is not candidate:
                    raise ValueError("Shared native encounter/runtime identity differs")
                if prepare_candidate is not None:
                    prepare_candidate(native, session)
                # Freeze all coordinator data while its authority is locked.
                # Native locks are capabilities encoded by the graph codec;
                # they must not be copied as ordinary mutable domain data.
                stage_started = time.monotonic()
                metadata = dict(vars(shared))
                metadata["fight"] = dict(nativeReference="runtime.fight")
                metadata["runtime"] = dict(nativeReference="runtime")
                metadata["lock"] = dict(
                    module=type(shared.lock).__module__,
                    name=type(shared.lock).__qualname__,
                    ownerThread=True,
                )
                native.native_ai_shared_context = gzip.compress(
                    encode_bytes(metadata), compresslevel=1, mtime=0
                )
                native.native_ai_preparation_started_at = preparation_started
                shared_preparation_ms = (time.monotonic() - stage_started) * 1000
            diagnostics = []
            transition = None
            failure = None
            try:
                automatic_end = requires_automatic_npc_turn_end(
                    native.fight, native.fight.current
                )
                if action_index == 12 or automatic_end:
                    fallback_context = nullcontext()
                    if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR"):
                        try:
                            from wakfu_server.combat_npc_publication import (
                                npc_fallback_scope,
                            )

                            fallback_context = npc_fallback_scope(
                                native, actor_id, turn_id
                            )
                        except Exception:
                            pass
                    with fallback_context as fallback_incident:
                        packets = (
                            native.end_automatic_npc_turn(actor_id, turn_id)
                            if automatic_end
                            else native.end_server_turn(actor_id, turn_id)
                        )
                        if fallback_incident is not None:
                            fallback_incident.packets(packets)
                    diagnostics.append(
                        dict(
                            action={"type": "end_turn"},
                            reason="ordinary_root_without_action_controller"
                            if automatic_end
                            else "native_action_budget_exhausted",
                            sharedPreparationMs=shared_preparation_ms,
                        )
                    )
                    transition = Transition(native.fight, native, tuple(packets))
                else:
                    iterator = iter(runner(native))
                    try:
                        for packets, diagnostic in iterator:
                            diagnostics.append(
                                dict(
                                    diagnostic,
                                    sharedPreparationMs=shared_preparation_ms,
                                )
                            )
                            if packets:
                                transition = Transition(
                                    native.fight, native, tuple(packets)
                                )
                                break
                    finally:
                        close = getattr(iterator, "close", None)
                        if callable(close):
                            close()
                    if transition is None:
                        raise _NoPublication()
            except _NoPublication:
                # A current owned NPC cannot wait forever for an action that
                # was never published. Discard this private result and run the
                # same fresh native end boundary as any rejected continuation.
                failure = ValueError("Native continuation produced no publication")
            except (ValueError, OSError, TypeError) as error:
                failure = error
            # Expensive queries and network I/O never hold the encounter lock.
            # A concurrent native transition invalidates this private result;
            # subsequent work still shares the original absolute deadline.
            with shared.lock:
                registry._member(shared, session)
                current = shared.fight.current
                if (
                    getattr(shared, "native_ai_turn_claim", None) != claim
                    or shared.fight.phase != "active"
                    or current is None
                    or current.id != actor_id
                    or shared.fight.turn_id != turn_id
                    or shared.runtime.awaiting_ack is not None
                    or shared.runtime.pending
                ):
                    return
                if shared.sequence != sequence:
                    continue
                if failure is None:
                    registry.execute_server(
                        shared.fight.id,
                        actor_id,
                        lambda candidate, runtime: transition,
                        expected_sequence=sequence,
                        incident_runtime=transition.runtime,
                        incident_packets=transition.packets,
                        incident_session=session,
                        incident_recipe="live-server-end-turn"
                        if action_index == 12 or automatic_end
                        else "chosen-native-commit",
                        incident_turn_id=turn_id,
                    )
                else:
                    # Discard the failed private pair. Earlier published actions
                    # remain authoritative; stage the native barrier afresh.
                    diagnostics = [
                        dict(
                            action={"type": "end_turn"},
                            reason="shared_native_action_rejected",
                            detail=str(failure),
                            error=type(failure).__name__,
                        )
                    ]

                    registry.execute_server(
                        shared.fight.id,
                        actor_id,
                        end_native_turn,
                        expected_sequence=sequence,
                        incident_session=session,
                        incident_recipe="live-server-end-turn",
                        incident_turn_id=turn_id,
                    )
                if shared.runtime.awaiting_ack is not None:
                    registry.arm_ack(shared.fight.id, shared.runtime.awaiting_ack)
                confirm(shared.runtime, before, diagnostics)
            for diagnostic in diagnostics:
                yield [], dict(
                    diagnostic, shared=True, actorId=actor_id, turnId=turn_id
                )
    except GeneratorExit:
        # The consumer can disconnect after receiving a move. Preserve that
        # publication and queue the native barrier for remaining participants.
        with shared.lock:
            current = shared.fight.current
            if (
                getattr(shared, "native_ai_turn_claim", None) == claim
                and shared.fight.phase == "active"
                and current is not None
                and current.id == actor_id
                and shared.fight.turn_id == turn_id
                and shared.runtime.awaiting_ack is None
                and not shared.runtime.pending
            ):
                registry.execute_server(
                    shared.fight.id,
                    actor_id,
                    end_native_turn,
                    expected_sequence=shared.sequence,
                    incident_session=session,
                    incident_recipe="live-server-end-turn",
                    incident_turn_id=turn_id,
                )
                if shared.runtime.awaiting_ack is not None:
                    registry.arm_ack(shared.fight.id, shared.runtime.awaiting_ack)
        raise
    finally:
        with shared.lock:
            if getattr(shared, "native_ai_turn_claim", None) == claim:
                del shared.native_ai_turn_claim
