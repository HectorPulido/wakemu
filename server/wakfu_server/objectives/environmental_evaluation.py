"""Declared race/competition evaluators over the shared durable fact ledger.

No original mission or tie formula is inferred. Each enabled profile must bind
an immutable evaluator and source authority before admission.
"""
from . import environmental_runtime as rules


def attach_policy(db, profile):
    if profile["mode"] in ("race", "competitive"):
        profile["evaluation"] = db.execute(
            "SELECT * FROM environmental_profile_evaluation WHERE profile_key=%s AND version=%s",
            (profile["profile_key"], profile["version"]),
        ).fetchone()
        rules.validate_evaluation(profile["mode"], profile["evaluation"])
    return profile


def race_finish(db, event, profile, participant, score, now_ms):
    from . import environmental_storage as storage

    policy = profile["evaluation"]
    rules.validate_evaluation("race", policy)
    prior = db.execute(
        "SELECT count(*) AS n FROM environmental_event_rankings WHERE instance_id=%s",
        (event["instance_id"],),
    ).fetchone()["n"]
    position = prior + 1
    if position > policy["winner_count"]:
        raise ValueError("Environmental race continued beyond its winner limit")
    db.execute(
        "INSERT INTO environmental_event_rankings VALUES(%s,%s,%s,%s,%s,true,%s)",
        (
            event["instance_id"],
            participant["character_id"],
            position,
            position,
            score,
            now_ms,
        ),
    )
    storage._entitle(db, event, participant, now_ms)
    if position == policy["winner_count"]:
        event = db.execute(
            "UPDATE environmental_event_instances SET state='completed',terminal_at_ms=%s "
            "WHERE instance_id=%s RETURNING *",
            (now_ms, event["instance_id"]),
        ).fetchone()
        storage._queue_cleanup(db, event, now_ms)
    return event


def competitive_ranking(db, event, profile):
    """Project the frozen final-eligibility policy without settling rewards.

    This declared Wakemu live projection reuses final eligibility; it is not
    recovered original-server arithmetic. Characters that have
    not yet qualified retain the native unknown rank rather than an award rank.
    """
    from . import environmental_storage as storage

    objectives = storage._objectives(db, profile)
    participants = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s ORDER BY character_id",
        (event["instance_id"],),
    ).fetchall()
    eligible = []
    for participant in participants:
        progress = storage._progress(db, event, participant["character_id"])
        score = sum(progress.values())
        rules.integer(score, "competitive score")
        if (
            participant["eligible"]
            and score >= profile["minimum_contribution"]
            and rules.complete(objectives, progress)
        ):
            eligible.append(dict(participant, score=score))
    return rules.competitive_order(eligible, profile["evaluation"])


def competition_finish(db, event, profile, now_ms):
    """Called once at expiration, under the common scope/event lock.

    Event deadline fences facts. Actual entitlement/companion snapshot time is
    this durable finalization, including an offline catch-up; never backdated.
    """
    from . import environmental_storage as storage

    ranking = competitive_ranking(db, event, profile)
    policy = db.execute(
        "SELECT eligibility_contract FROM environmental_profile_ranked_reward_policy "
        "WHERE profile_key=%s AND version=%s",
        (profile["profile_key"], profile["version"]),
    ).fetchone()
    if policy is not None and policy["eligibility_contract"] == "all_eligible":
        # The original list can include a consolation XP band. The declared
        # policy awards it to eligible contributors outside the leading ranks.
        ranking = [dict(row, rewarded=True) for row in ranking]
    if ranking:
        event = db.execute(
            "UPDATE environmental_event_instances SET state='completed',terminal_at_ms=%s "
            "WHERE instance_id=%s RETURNING *",
            (now_ms, event["instance_id"]),
        ).fetchone()
    for row in ranking:
        db.execute(
            "INSERT INTO environmental_event_rankings VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                event["instance_id"],
                row["character_id"],
                row["position"],
                row["display_rank"],
                row["score"],
                row["rewarded"],
                now_ms,
            ),
        )
        if row["rewarded"]:
            storage._entitle(db, event, row, now_ms)
    return event
