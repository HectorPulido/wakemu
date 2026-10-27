"""Accredit accumulated original Rift kills from durable terminal authority."""
from psycopg.pq import TransactionStatus


def load_locked(db, fight, character, eligible_character_ids):
    """Return original killed id/ref facts for the existing achievement service.

    The caller owns the settlement transaction and participant routing. Monetary
    reward context supplies its existing all-wave native identity validation;
    no reward is resolved, rolled or granted here. Achievement event receipts
    remain responsible for exactly-once progress on replay.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Rift achievement facts require an active transaction")
    state = getattr(fight, "rift_wave_state", None)
    if not isinstance(state, dict) or type(state.get("instance_id")) is not int:
        raise ValueError("Rift achievement facts require a trusted run identity")
    from wakfu_server.rift_runtime import _run
    from wakfu_server.rift_currency_rewards import reward_context
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.rift_wave_bindings import rosters as bound_rosters

    run = _run(db, state["instance_id"])
    if run["fight_id"] != fight.id or fight.phase != "finished":
        raise ValueError("Rift achievement facts require the terminal owned fight")
    receipt = db.execute(
        "SELECT outcome,result FROM rift_settlement_receipts "
        "WHERE instance_id=%s AND fight_id=%s",
        (run["instance_id"], fight.id),
    ).fetchone()
    if receipt is None:
        raise ValueError("Rift achievement facts require durable terminal settlement")
    outcome, result = receipt["outcome"], receipt["result"]
    if (
        outcome not in ("won", "lost", "closed")
        or run["status"] != outcome
        or not isinstance(result, dict)
        or result.get("outcome") != outcome
    ):
        raise ValueError("Rift achievement terminal authority differs")
    # Existing achievements credit winning participants only. Loss/closure
    # never invent a winner or translate partial kill counters into progress.
    player_team = assigned_roles(fight).player_team
    if outcome != "won":
        if fight.winner == player_team:
            raise ValueError("Rift achievement winner differs from settlement")
        return ()
    if (
        type(fight.winner) is not int
        or fight.winner != player_team
        or type(result.get("turn")) is not int
        or result["turn"] < run["policy"]["turn_budget"]
        or result.get("completed_waves") != run["completed_waves"]
        or result.get("defeated_monsters") != run["defeated_monsters"]
    ):
        raise ValueError("Rift achievement survival or progress is not accredited")
    rosters = bound_rosters(db, run, fight=fight)
    _, killed = reward_context(fight, character, run, rosters, eligible_character_ids)
    return tuple({"id": row["actor_id"], "ref": row["reference"]} for row in killed)
