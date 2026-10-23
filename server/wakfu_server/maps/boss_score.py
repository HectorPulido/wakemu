"""Local boss scoring: validated damage before minimum-HP clamping.

Only a successful server damage executor may supply damage/attribution. Calls
share its database transaction; rollback removes receipts and no memory counter
is authoritative. This adapts documented boss challenges, not native parity.
"""
from psycopg.types.json import Jsonb
from psycopg.pq import TransactionStatus

POLICY = "wakemu-boss-validated-damage-v1"


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid boss score " + name)
    return value


def _transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Boss score requires the damage transaction")


def freeze(db, fight_id, *, monsters, player_ids, player_team=0, persist=True):
    """Pin configured boss actors and owned participant actor IDs before play."""
    _transaction(db)
    _integer(fight_id, "fight", 1)
    if type(player_team) is not int or player_team not in (0, 1):
        raise ValueError("Invalid boss score player team")
    row = db.execute(
        "SELECT value FROM settings WHERE name='boss_score_policy'"
    ).fetchone()
    if row is None:
        return None
    policy = row["value"]
    if policy.get("policy") != POLICY or policy.get("schema_version") != 1:
        raise ValueError("Invalid boss score policy")
    bosses = {
        str(identity): dict(
            reference=monster["ref"],
            round_limit=_integer(
                policy["profiles"][str(monster["ref"])]["round_limit"], "round limit", 1
            ),
        )
        for identity, monster in monsters.items()
        if str(monster["ref"]) in policy["profiles"]
        and type(monster.get("team")) is int
        and monster["team"] in (0, 1)
        and monster["team"] != player_team
    }
    if len(bosses) != 1:
        # Mixed or duplicate boss challenge roles need their own profile.
        return None
    if len({row["round_limit"] for row in bosses.values()}) != 1:
        raise ValueError("Boss encounter has incompatible termination profiles")
    for boss in bosses.values():
        early = policy["profiles"][str(boss["reference"])].get(
            "allow_early_boss_defeat", False
        )
        if type(early) is not bool:
            raise ValueError("Invalid early boss defeat flag")
        boss["allow_early_boss_defeat"] = early
    players = sorted({_integer(identity, "player", 1) for identity in player_ids})
    participants = db.execute(
        "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND team=%s",
        (fight_id, player_team),
    ).fetchall()
    if not set(players) <= {r["character_id"] for r in participants}:
        raise ValueError("Boss score participants lack durable ownership")
    if not players:
        raise ValueError("Boss score lacks owned participants")
    snapshot = dict(
        policy=POLICY,
        bosses=bosses,
        player_ids=players,
        round_limit=next(iter(bosses.values()))["round_limit"],
        player_team=player_team,
        includes_armor=True,
        includes_owned_summons=True,
        allow_early_boss_defeat=next(iter(bosses.values()))["allow_early_boss_defeat"],
    )
    if not persist:
        return snapshot
    return freeze_snapshot(db, fight_id, snapshot)


def prepare_snapshot(db, fight_id, **options):
    """Read configured authority without publishing a failed readiness preview."""
    return freeze(db, fight_id, persist=False, **options)


def freeze_snapshot(db, fight_id, snapshot):
    """Publish the previously prepared profile alongside checkpoint CAS."""
    _transaction(db)
    from wakfu_server.combat_boss_score_policy import RUSHU_SCORE

    if snapshot.get("encounter_controller") == RUSHU_SCORE.name:
        if "outgoing_level_policy" in snapshot:
            from wakfu_server.combat_boss_party_level_policy import (
                validate_level_profile,
            )

            validate_level_profile(snapshot)
        else:
            # Preserve an identical already-frozen historical receipt only.
            # Fresh profiles must carry authenticated party-level authority;
            # the outgoing damage policy never supplies a silent 1.0 fallback.
            previous = db.execute(
                "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s FOR UPDATE",
                (fight_id,),
            ).fetchone()
            if previous is None or previous["snapshot"] != snapshot:
                raise ValueError(
                    "New Rushu score profile lacks frozen party-level authority"
                )
    db.execute(
        "INSERT INTO boss_score_encounters(fight_id,snapshot) VALUES(%s,%s) ON CONFLICT DO NOTHING",
        (fight_id, Jsonb(snapshot)),
    )
    saved = db.execute(
        "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s FOR UPDATE",
        (fight_id,),
    ).fetchone()["snapshot"]
    if saved != snapshot:
        raise ValueError("Boss score encounter authority changed")
    return saved


def record_damage(
    db,
    fight_id,
    *,
    event_id,
    source_id,
    target_id,
    owner_actor_id,
    post_mitigation_damage,
    armor_absorbed,
    round_number,
    source_is_registered_summon=False
):
    """Executor-only hook, after successful execution inside its commit TX.

    post_mitigation_damage excludes armor absorption; armor_absorbed adds that
    validated component back. Both precede minimum-HP clamping. owner_actor_id
    must come from actual registered summon authority, never a client request.
    event_id identifies one runner/target delivery across retries.
    """
    _transaction(db)
    if any(
        type(value) is not int or value == 0
        for value in (source_id, target_id, owner_actor_id)
    ):
        raise ValueError("Invalid boss score actor identity")
    if type(source_is_registered_summon) is not bool:
        raise ValueError("Invalid boss score summon authority")
    if not isinstance(event_id, str) or not event_id or len(event_id) > 200:
        raise ValueError("Invalid boss score event identity")
    row = db.execute(
        "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s FOR UPDATE",
        (fight_id,),
    ).fetchone()
    if row is None:
        return False
    snapshot = row["snapshot"]
    round_number = _integer(round_number, "damage round", 1)
    if round_number > snapshot["round_limit"]:
        return False
    if (
        str(target_id) not in snapshot["bosses"]
        or owner_actor_id not in snapshot["player_ids"]
    ):
        return False
    if source_id != owner_actor_id and source_is_registered_summon is not True:
        return False
    damage = _integer(post_mitigation_damage, "damage")
    armor = _integer(armor_absorbed, "armor")
    payload = dict(
        source_id=source_id,
        target_id=target_id,
        owner_actor_id=owner_actor_id,
        damage=damage,
        armor=armor,
        round_number=round_number,
        registered_summon=source_is_registered_summon,
    )
    previous = db.execute(
        "SELECT snapshot FROM boss_score_damage_receipts WHERE fight_id=%s AND event_id=%s",
        (fight_id, event_id),
    ).fetchone()
    if previous is not None:
        if previous["snapshot"] != payload:
            raise ValueError("Boss score event replay changed")
        return True
    if db.execute(
        "SELECT 1 FROM boss_score_terminal_receipts WHERE fight_id=%s", (fight_id,)
    ).fetchone():
        raise ValueError("Boss score is finalized")
    db.execute(
        "INSERT INTO boss_score_damage_receipts(fight_id,event_id,snapshot,amount) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (fight_id, event_id, Jsonb(payload), damage + armor),
    )
    saved = db.execute(
        "SELECT snapshot FROM boss_score_damage_receipts WHERE fight_id=%s AND event_id=%s",
        (fight_id, event_id),
    ).fetchone()["snapshot"]
    if saved != payload:
        raise ValueError("Boss score event replay changed")
    return True


def finalize(
    db,
    fight_id,
    *,
    completed_rounds,
    survived,
    winning_team,
    boss_defeated=False,
    terminal_authority=None
):
    """Freeze a terminal result; never changes the fight winner or turn loop."""
    _transaction(db)
    rounds = _integer(completed_rounds, "completed rounds")
    if type(boss_defeated) is not bool:
        raise ValueError("Invalid terminal boss defeat authority")
    if type(survived) is not bool:
        raise ValueError("Invalid boss score survival")
    row = db.execute(
        "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s FOR UPDATE",
        (fight_id,),
    ).fetchone()
    if row is None:
        return None
    status = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
    ).fetchone()
    if status is None or status["status"] != "finished":
        raise ValueError("Boss score requires a durable terminal fight")
    previous = db.execute(
        "SELECT snapshot FROM boss_score_terminal_receipts WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if previous:
        return previous["snapshot"]
    if winning_team is not None and (
        type(winning_team) is not int or winning_team not in (0, 1)
    ):
        raise ValueError("Invalid boss score winner")
    authority = row["snapshot"]
    completion = rounds >= authority["round_limit"] or (
        authority.get("allow_early_boss_defeat") is True and boss_defeated
    )
    eligible = survived and winning_team == authority["player_team"] and completion
    score = (
        int(
            db.execute(
                "SELECT COALESCE(sum(amount),0) AS score FROM boss_score_damage_receipts WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["score"]
        )
        if eligible
        else 0
    )
    from wakfu_server.combat_boss_score_policy import (
        OGREST_SCORE,
        native_score_policy,
        score_drop_rate_bp,
    )

    native_policy = native_score_policy(authority)
    if native_policy is not None:
        minimum = _integer(
            authority["minimum_score"],
            "native score minimum",
            native_policy.minimum_score,
        )
        if native_policy == OGREST_SCORE:
            if winning_team == authority["player_team"]:
                terminal = terminal_authority
                if (
                    not isinstance(terminal, dict)
                    or terminal.get("policy") != OGREST_SCORE.name
                    or terminal.get("result") != "victory"
                    or str(terminal.get("boss_id")) not in authority["bosses"]
                    or terminal.get("actor_id") not in authority["player_ids"]
                    or terminal.get("table") not in (19, 20)
                    or terminal.get("source") != "actual_owned_player_turn_end"
                    or terminal.get("area_reference") != 1255
                    or terminal.get("score") != score
                ):
                    raise ValueError(
                        "Ogrest result requires its actual earned terminal exit"
                    )
            elif terminal_authority is not None:
                raise ValueError("Defeated Ogrest team cannot claim exit authority")
            if score < max(minimum, native_policy.loot_minimum_score):
                eligible = (
                    False  # A genuine low-score exit still retains its raw score.
                )
        elif not boss_defeated or score < minimum:
            eligible = False
            score = 0
    result = dict(
        policy=POLICY,
        score=score,
        eligible=eligible,
        completed_rounds=rounds,
        survived=survived,
        winning_team=winning_team,
        boss_defeated=boss_defeated,
    )
    if native_policy == OGREST_SCORE and terminal_authority is not None:
        result["native_terminal_authority"] = dict(terminal_authority)
    if native_policy is not None:
        result["encounter_controller"] = native_policy.name
        if eligible and native_policy.drop_score_step:
            result["boss_score_drop_rate_bp"] = score_drop_rate_bp(native_policy, score)
            result["boss_score_drop_source"] = native_policy.drop_source
    db.execute(
        "INSERT INTO boss_score_terminal_receipts(fight_id,snapshot,score) VALUES(%s,%s,%s)",
        (fight_id, Jsonb(result), score),
    )
    return result


def drop_context(db, fight_id):
    """Only an eligible immutable terminal receipt authorizes score drops."""
    if (
        db.execute("SELECT 1 FROM settings WHERE name='boss_score_policy'").fetchone()
        is None
    ):
        return {}
    row = db.execute(
        "SELECT snapshot,score FROM boss_score_terminal_receipts WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if row is None or row["snapshot"].get("eligible") is not True:
        return {}
    score = _integer(row["score"], "terminal score")
    if score != row["snapshot"].get("score"):
        raise ValueError("Boss score receipt disagrees with terminal authority")
    context = {"score": score}
    terminal = row["snapshot"]
    if "boss_score_drop_rate_bp" in terminal:
        from wakfu_server.combat_boss_score_policy import NOX_SCORE, score_drop_rate_bp

        rate = terminal["boss_score_drop_rate_bp"]
        if (
            terminal.get("encounter_controller") != NOX_SCORE.name
            or terminal.get("boss_score_drop_source") != NOX_SCORE.drop_source
            or type(rate) is not int
            or rate != score_drop_rate_bp(NOX_SCORE, score)
        ):
            raise ValueError("Boss score drop multiplier lost terminal authority")
        context["boss_score_drop_rate_bp"] = rate
    from wakfu_server.combat_boss_score_policy import NOX_SCORE

    if terminal.get("encounter_controller") == NOX_SCORE.name:
        from wakfu_server.combat_nox_complex_loot_policy import terminal_drop_context

        permission = terminal_drop_context(db, terminal)
        if permission is not None:
            context["nox_complex_loot"] = permission
    return context
