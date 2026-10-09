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
    entered_at = clock()
    preparation_started = getattr(
        runtime, "native_ai_preparation_started_at", entered_at
    )
    if type(preparation_started) not in (int, float) or not math.isfinite(
        preparation_started
    ):
        raise ValueError("Invalid native owner preparation start")
    # A fresh action driver must retain the original encounter-owned turn
    # allowance. Future timestamps cannot extend it beyond the current entry.
    started_at = min(entered_at, preparation_started)
    deadline = started_at + budget_seconds
    stage_elapsed_ms = {}

    def record_stage(name, stage_started):
        stage_elapsed_ms[name] = stage_elapsed_ms.get(name, 0.0) + max(
            0.0, (clock() - stage_started) * 1000
        )

    def end_turn_packets(oracle):
        if oracle is not None:
            try:
                return oracle.commit(
                    {"type": "end_turn"}, stats_serializer=stats_serializer
                )
            except TimeoutError:
                # The action deadline may already be exhausted. End-turn is
                # the safety barrier, not another AI action; let the live
                # encounter owner advance it even when oracle checks time out.
                pass
        # Oracle construction itself can fail. The live runtime still owns
        # the turn barrier, so complete it directly without adopting a plan.
        return runtime.end_server_turn(actor_id, turn_id)

    oracle = None
    initialization_failed = False
    catalog_manifest = None
    ending = dict(action={"type": "end_turn"}, reason="native_action_budget_exhausted")
    stage = "oracle_create"
    stage_started = clock()
    try:
        with bounded(deadline, clock=clock):
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
            check()
    except (ValueError, OSError, TypeError) as error:
        initialization_failed = True
        record_stage("oracle_create", stage_started)
        ending = dict(
            action={"type": "end_turn"},
            reason="native_ai_query_or_commit_rejected",
            detail=str(error),
            error=type(error).__name__,
            stage="oracle_create",
            elapsedMs=max(0.0, (clock() - started_at) * 1000),
            turnBudgetMs=budget_seconds * 1000,
            stageElapsedMs=dict(stage_elapsed_ms),
        )
        yield [], ending
    else:
        record_stage("oracle_create", stage_started)
    for _ in range(max_actions):
        if initialization_failed or oracle is None:
            break
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
        stage = "catalog_session"
        try:
            with bounded(deadline, clock=clock):
                stage_started = clock()
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
                record_stage("catalog_session", stage_started)
                stage = "search"
                stage_started = clock()
                decision = session.decide(certify=False)
                check()
                record_stage("search", stage_started)
                stage = "coordination"
                stage_started = clock()
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
                record_stage("coordination", stage_started)
                stage = "source_guard"
                stage_started = clock()
                session.guard()
                record_stage("source_guard", stage_started)
                stage = "commit"
                stage_started = clock()
                packets = oracle.commit(
                    decision["action"], stats_serializer=stats_serializer
                )
                record_stage("commit", stage_started)
                decision["stageElapsedMs"] = dict(stage_elapsed_ms)
                decision["elapsedMs"] = max(0.0, (clock() - started_at) * 1000)
                decision["turnBudgetMs"] = budget_seconds * 1000
        except (ValueError, OSError, TypeError) as error:
            if stage in {"catalog_session", "search", "source_guard", "commit"}:
                record_stage(stage, stage_started)
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
                elapsedMs=max(0.0, (clock() - started_at) * 1000),
                turnBudgetMs=budget_seconds * 1000,
                stageElapsedMs=dict(stage_elapsed_ms),
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
        stage_started = clock()
        packets = end_turn_packets(oracle)
        record_stage("commit", stage_started)
        ending["stageElapsedMs"] = dict(stage_elapsed_ms)
        ending["elapsedMs"] = max(0.0, (clock() - started_at) * 1000)
        ending["turnBudgetMs"] = budget_seconds * 1000
        yield packets, ending
