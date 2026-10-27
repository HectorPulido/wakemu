"""Transactional scenario result facts; independent of original monster kills."""
from .combat_encounter_objective import (
    SceneTerminalEventReceipt,
    observe_native_terminal,
    verify_scene_terminal_intent,
)


def objective_result_payload(receipt):
    """Expose an exact policy/objective binding for existing objective filters."""
    if not isinstance(receipt, SceneTerminalEventReceipt):
        raise ValueError("Scenario objective fact requires its typed receipt")
    return dict(
        kind="scenario_objective_completed",
        fight_id=receipt.fight_id,
        map_id=receipt.map_id,
        reference=receipt.boss_reference,
        objective_key=receipt.objective_key,
        outcome_policy=receipt.policy,
        outcome_version=receipt.version,
        result=receipt.result,
        score=receipt.score,
        table=receipt.table,
        terminal_root=receipt.terminal_root,
        terminal_kind=receipt.terminal_kind,
        scene_contract_policy=receipt.scene_contract_policy,
        admission_digest=receipt.admission_digest,
    )


def enqueue_objective_results(db, fight):
    """Run after score finalization in the existing settlement transaction.

    The durable objective repository supplies exact event replay conflict and
    per-owner outbox semantics in both local and external objectives modes.
    No quest ID, kill fact, reward or victory is fabricated by this adapter.
    """
    if getattr(fight, "native_encounter_objective_policy", None) is None:
        return ()
    observe_native_terminal(fight)
    journal = getattr(fight, "native_encounter_objective_results", {})
    if not journal:
        return ()
    profile = fight.boss_score_profile
    status = db.execute(
        "SELECT f.status,r.snapshot FROM combat_fights f "
        "JOIN boss_score_terminal_receipts r ON r.fight_id=f.id WHERE f.id=%s",
        (fight.id,),
    ).fetchone()
    if (
        status is None
        or status["status"] != "finished"
        or fight.phase != "finished"
        or fight.winner != profile["player_team"]
        or status["snapshot"].get("winning_team") != fight.winner
    ):
        raise ValueError("Scenario result fact lacks durable terminal authority")
    from wakfu_server.objectives.repository import enqueue

    deliveries = []
    for record in journal.values():
        receipt = verify_scene_terminal_intent(
            fight, SceneTerminalEventReceipt.from_record(record)
        )
        payload = objective_result_payload(receipt)
        for identity in profile["player_ids"]:
            actor = fight.actors[identity]
            if getattr(actor, "pve_withdrawn", False) or not fight._in_play(actor):
                continue
            if type(actor.owner_id) is not int or actor.owner_id <= 0:
                raise ValueError("Scenario result recipient lost its owned account")
            participant = db.execute(
                "SELECT p.team,EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
                "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
                "FROM combat_fight_participants p "
                "WHERE p.fight_id=%s AND p.character_id=%s AND p.account_id=%s",
                (fight.id, identity, actor.owner_id),
            ).fetchone()
            if (
                participant is None
                or participant["team"] != fight.winner
                or participant["withdrawn"]
            ):
                raise ValueError("Scenario result recipient lacks durable admission")
            key = f"scenario-result:{fight.id}:{receipt.policy}"
            result = enqueue(db, actor.owner_id, identity, key, payload)
            deliveries.append(
                dict(
                    account_id=actor.owner_id,
                    character_id=identity,
                    event_key=key,
                    result=result,
                )
            )
    return tuple(deliveries)
