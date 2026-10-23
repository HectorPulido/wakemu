"""Explicit Wakemu rewards from committed ecology and organized PvP facts.

These constants are normalized immutable SQL policy, not original formulas.
Player action callers own the transaction; no reads initialize progression.
"""
from . import national_progression as national

POLICY = "wakemu-national-v1"


def _policy(db, key=POLICY):
    row = db.execute(
        "SELECT * FROM wakemu_national_earning_policies WHERE policy_key=%s", (key,)
    ).fetchone()
    if row is None:
        raise ValueError("Missing Wakemu national earning policy")
    return row


def _owner(db, character_id):
    national._transaction(db)
    row = db.execute(
        "SELECT c.account_id,c.id,COALESCE(n.nation_id,0) AS nation_id FROM characters c "
        "LEFT JOIN character_chat_nations n ON n.character_id=c.id "
        "WHERE c.id=%s AND c.deleted_at IS NULL FOR UPDATE OF c",
        (character_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing national earning owner")
    return row


def _activate(db, owner):
    # A legacy player starts an explicitly new Wakemu epoch on a real action.
    # Existing native imports and constructor state are never overwritten.
    db.execute(
        "INSERT INTO character_national_authority(character_id,account_id,version,rank_id,provenance) "
        "VALUES(%s,%s,%s,0,'wakemu_policy_epoch') ON CONFLICT(character_id) DO NOTHING",
        (owner["id"], owner["account_id"], national.VERSION),
    )


def ecology(db, character_id, operation):
    """Called only by genuine live flora/birth/removal producers, never repair."""
    owner = _owner(db, character_id)
    if owner["nation_id"] == 0:
        return False
    source = db.execute(
        "SELECT * FROM personal_ecology_receipts WHERE character_id=%s AND operation=%s",
        (character_id, operation),
    ).fetchone()
    if source is None:
        raise ValueError("Missing committed ecological earning evidence")
    evidence = source["evidence"]
    if (
        evidence.get("managed_equilibrium") is not True
        or evidence.get("kind") not in ("plant", "monster")
        or evidence.get("action") not in ("plant", "remove")
        or type(evidence.get("distance_before")) is not int
        or type(evidence.get("distance_after")) is not int
    ):
        return False
    before_distance, after_distance = (
        evidence["distance_before"],
        evidence["distance_after"],
    )
    if before_distance == after_distance:
        return False
    digest = national._digest(
        {"operation": operation, "evidence": evidence, "revision": source["revision"]}
    )
    prior = db.execute(
        "SELECT source_digest FROM character_national_earning_receipts WHERE character_id=%s "
        "AND source_kind='ecology' AND source_key=%s",
        (character_id, operation),
    ).fetchone()
    if prior is not None:
        if prior["source_digest"] != digest:
            raise ValueError("National ecology source changed on replay")
        return False
    policy = _policy(db)
    _activate(db, owner)
    score = db.execute(
        "SELECT score FROM character_national_crime_scores WHERE character_id=%s AND nation_id=%s",
        (character_id, owner["nation_id"]),
    ).fetchone()
    before = 0 if score is None else score["score"]
    delta = (
        policy["ecology_gain"]
        if after_distance < before_distance
        else policy["ecology_loss"]
    )
    # Preserve imported values outside the custom cap; never clamp them away.
    after = min(
        max(before + delta, min(before, policy["citizenship_min"])),
        max(before, policy["citizenship_max"]),
    )
    db.execute(
        "INSERT INTO character_national_crime_scores VALUES(%s,%s,%s,%s) "
        "ON CONFLICT(character_id,nation_id) DO UPDATE SET score=EXCLUDED.score",
        (character_id, owner["account_id"], owner["nation_id"], after),
    )
    _receipt(
        db, owner, "ecology", operation, policy, digest, before, after, delta, None
    )
    return True


def _receipt(db, owner, kind, key, policy, digest, before, after, delta, period):
    db.execute(
        "INSERT INTO character_national_earning_receipts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            owner["id"],
            owner["account_id"],
            kind,
            str(key),
            policy["policy_key"],
            owner["nation_id"],
            digest,
            before,
            after,
            delta,
            period,
        ),
    )
    db.execute(
        "UPDATE character_national_authority SET revision=revision+1 WHERE character_id=%s",
        (owner["id"],),
    )
    db.execute("SELECT pg_notify('wakemu_objectives_updates',%s)", (str(owner["id"]),))


def neutralize(db, character_id, item_ref):
    """Called inside the real scroll transaction; never creates missing history."""
    owner = _owner(db, character_id)
    policy = db.execute(
        "SELECT * FROM wakemu_national_neutrality_rules WHERE item_ref=%s", (item_ref,)
    ).fetchone()
    if policy is None:
        raise ValueError("Missing qualified national neutrality rule")
    if policy["clear_citizenship"]:
        db.execute(
            "DELETE FROM character_national_crime_scores WHERE character_id=%s",
            (character_id,),
        )
    if policy["clear_merit"]:
        db.execute(
            "DELETE FROM character_national_merit WHERE character_id=%s",
            (character_id,),
        )
        db.execute(
            "UPDATE character_national_authority SET rank_id=0 WHERE character_id=%s",
            (character_id,),
        )
    db.execute(
        "UPDATE character_national_authority SET revision=revision+1 WHERE character_id=%s",
        (character_id,),
    )


def hourly_pvp(db, event_id, *, fight=None):
    """Only a completed, native-roster-verified durable hourly defeat earns merit."""
    from wakfu_server.objectives import pvp

    national._transaction(db)
    event = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE id=%s FOR UPDATE", (event_id,)
    ).fetchone()
    if event is None or event["status"] != "completed" or not event["rewards_reserved"]:
        raise ValueError("National merit requires a completed hourly result")
    outcome = db.execute(
        "SELECT o.*,f.status AS fight_status FROM friendly_duel_outcomes o "
        "JOIN combat_fights f ON f.id=o.fight_id AND f.fight_kind='duel' WHERE o.fight_id=%s",
        (event["fight_id"],),
    ).fetchone()
    roster = db.execute(
        "SELECT character_id,account_id,team,level FROM objectives_pvp_fight_roster "
        "WHERE event_id=%s ORDER BY team,character_id",
        (event_id,),
    ).fetchall()
    if (
        outcome is None
        or outcome["fight_status"] != "finished"
        or outcome["reason"] != "defeat"
        or outcome["winner_character_id"] != event["winner_character_id"]
        or {outcome["winner_character_id"], outcome["loser_character_id"]}
        != {event["first_character_id"], event["second_character_id"]}
        or not pvp._valid_roster(event, roster)
        or roster != pvp._native_roster(db, event["fight_id"], fight)
    ):
        raise ValueError(
            "National merit lacks the original valid hourly roster/outcome"
        )
    policy = _policy(db, event["national_policy_key"])
    # Settlement already owns participant locks; retain the shared ID order.
    owners = [
        _owner(db, cid)
        for cid in sorted((event["first_character_id"], event["second_character_id"]))
    ]
    changed = []
    for owner in owners:
        if owner["nation_id"] == 0:
            continue
        digest = national._digest(
            {
                "event": event_id,
                "fight_id": event["fight_id"],
                "roster": roster,
                "winner": outcome["winner_character_id"],
                "policy": policy["policy_key"],
            }
        )
        prior = db.execute(
            "SELECT source_digest FROM character_national_earning_receipts WHERE "
            "character_id=%s AND source_kind='hourly_pvp' AND source_key=%s",
            (owner["id"], str(event_id)),
        ).fetchone()
        if prior is not None:
            if prior["source_digest"] != digest:
                raise ValueError("National hourly source changed on replay")
            continue
        _activate(db, owner)
        state = db.execute(
            "SELECT * FROM character_national_authority WHERE character_id=%s",
            (owner["id"],),
        ).fetchone()
        ranks = national._ranks(db, state["version"])
        merit = db.execute(
            "SELECT merit FROM character_national_merit WHERE character_id=%s",
            (owner["id"],),
        ).fetchone()
        # Native imported ranks have no known exact merit. The new custom epoch
        # starts at that rank's verified lower bound, explicitly stored as such.
        before = dict(ranks)[state["rank_id"]] if merit is None else merit["merit"]
        delta = (
            policy["merit_win"]
            if owner["id"] == outcome["winner_character_id"]
            else policy["merit_loss"]
        )
        after = max(0, min(policy["merit_max"], before + delta))
        rank = max(identity for identity, threshold in ranks if threshold <= after)
        db.execute(
            "INSERT INTO character_national_merit VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT(character_id) DO UPDATE SET merit=EXCLUDED.merit,policy_key=EXCLUDED.policy_key",
            (
                owner["id"],
                owner["account_id"],
                policy["policy_key"],
                after,
                state["rank_id"],
            ),
        )
        db.execute(
            "UPDATE character_national_authority SET rank_id=%s WHERE character_id=%s",
            (rank, owner["id"]),
        )
        _receipt(
            db,
            owner,
            "hourly_pvp",
            event_id,
            policy,
            digest,
            before,
            after,
            delta,
            event["period_key"],
        )
        changed.append(owner["id"])
    return tuple(changed)
