"""Owner-thread turn driver for the stable, complete world bridge.

Candidate generation, query negotiation and this SDK live in ai-service.
The embedding world supplies its encounter and complete native authorities;
network sends and client ACK handling remain with the encounter owner.
"""
import time
import uuid
import math

from .native_oracle import NativeOracle
from ..bridge.world_bridge import NativeSession
from .native_deadline import bounded, check


def run_turn(
    runtime,
    *,
    characters,
    monsters,
    decks,
    excluded_decks,
    viewer_id,
    flags,
    transport,
    exporter,
    policy,
    policy_version,
    stats_serializer,
    max_actions=12,
    budget_seconds=10,
    clock=time.monotonic,
    outcome_features=None
):
    """Yield committed native deliveries, then resume from the current state.

    No per-action turn ACK is invented. Each action is freshly certified and
    staged before delivery. A failed query ends this NPC turn through the
    native barrier without adopting a forecast or spending its resources.
    """
    if (
        type(max_actions) is not int
        or max_actions < 1
        or type(budget_seconds) not in (int, float)
        or not math.isfinite(budget_seconds)
        or budget_seconds <= 0
    ):
        raise ValueError("Invalid native turn budget")
    fight = runtime.fight
    if fight.phase != "active" or fight.current is None or fight.current.controlled:
        raise ValueError("Native AI turn requires an active NPC")
    actor_id, turn_id = fight.current.id, fight.turn_id
    if not hasattr(runtime, "tactical_encounter_id"):
        runtime.tactical_encounter_id = (
            getattr(fight, "native_ai_fight_uuid", None) or uuid.uuid4().hex
        )
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks=excluded_decks,
        viewer_id=viewer_id,
        flags=flags,
        outcome_features=outcome_features,
    )
    deadline = clock() + budget_seconds
    catalog_manifest = None
    ending = dict(action={"type": "end_turn"}, reason="native_action_budget_exhausted")
    for _ in range(max_actions):
        fight = runtime.fight
        if runtime.awaiting_ack is not None or runtime.pending:
            return
        if (
            fight.phase != "active"
            or fight.current is None
            or fight.current.id != actor_id
            or fight.turn_id != turn_id
        ):
            return
        if clock() >= deadline:
            ending["reason"] = "native_turn_deadline_reached"
            break
        session = None
        stage = "session_preparation"
        try:
            with bounded(deadline, clock=clock):
                session = NativeSession(
                    oracle,
                    transport,
                    exporter,
                    policy=policy,
                    policy_version=policy_version,
                    fight_instance_id=runtime.tactical_encounter_id,
                    catalog_manifest=catalog_manifest,
                )
                catalog_manifest = session.catalog
                stage = "decision_search"
                decision = session.decide(certify=False)
                check()
                if hasattr(oracle, "coordination_for_action"):
                    try:
                        decision["coordinationDraft"] = oracle.coordination_for_action(
                            decision["action"]
                        )
                    except (ValueError, KeyError, AttributeError, TypeError) as error:
                        # Advisory evidence must neither authorize a cast nor
                        # prevent its separately certified native execution.
                        decision["coordinationUnknown"] = str(error)
                        decision["coordinationDraft"] = None
                check()
                stage = "source_guard"
                session.guard()
                stage = "native_commit"
                packets = oracle.commit(
                    decision["action"], stats_serializer=stats_serializer
                )
        except (ValueError, OSError, TypeError) as error:
            if session is not None and hasattr(session, "cancel"):
                try:
                    # Release a suspended coroutine even after the turn's
                    # deadline expired. A separate 250ms cleanup allowance
                    # cannot authorize another action or delay native fallback
                    # through the transport's usual retries.
                    with bounded(clock() + 0.25, clock=clock):
                        session.cancel()
                except (ValueError, OSError, TypeError):
                    pass
            ending = dict(
                action={"type": "end_turn"},
                reason="native_ai_query_or_commit_rejected",
                detail=str(error),
                error=type(error).__name__,
                stage=stage,
                elapsedMs=(clock() - (deadline - budget_seconds)) * 1000,
                turnBudgetMs=budget_seconds * 1000,
            )
            yield [], ending
            break
        yield packets, decision
        if decision["action"]["type"] == "end_turn":
            return
    fight = runtime.fight
    if (
        fight.phase == "active"
        and fight.current is not None
        and fight.current.id == actor_id
        and fight.turn_id == turn_id
        and runtime.awaiting_ack is None
        and not runtime.pending
    ):
        yield oracle.commit(
            {"type": "end_turn"}, stats_serializer=stats_serializer
        ), ending
