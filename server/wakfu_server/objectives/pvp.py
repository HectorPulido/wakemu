"""Hourly selected-account matchups over authoritative consenting native duels."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb

TIMEZONE = "America/Bogota"
POLICIES = {"participation": "content-v1.daily", "winner": "content-v1.dungeon"}


def hour(at=None):
    if at is not None and at.tzinfo is None:
        raise ValueError("PvP hour requires a timezone-aware timestamp")
    local = (at or datetime.now(timezone.utc)).astimezone(ZoneInfo(TIMEZONE))
    start = local.replace(minute=0, second=0, microsecond=0)
    return (
        start.strftime("%Y-%m-%dT%H"),
        start.astimezone(timezone.utc),
        (start + timedelta(hours=1)).astimezone(timezone.utc),
    )


def validate_level_policy(policy):
    if type(policy) is not dict:
        raise ValueError("Invalid PvP level policy")
    kind = policy.get("type")
    field = {
        "relative": "maximum_percent",
        "absolute": "maximum_difference",
        "bracket": "size",
    }.get(kind)
    if (
        field is None
        or set(policy) != {"type", field}
        or type(policy[field]) is not int
    ):
        raise ValueError("Invalid PvP level policy")
    minimum = 0 if kind == "absolute" else 1
    maximum = 100 if kind == "relative" else MAX_CHARACTER_LEVEL
    if not minimum <= policy[field] <= maximum:
        raise ValueError("PvP level policy is out of range")
    return policy


def compatible_levels(policy, first, second):
    validate_level_policy(policy)
    if any(
        type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL
        for level in (first, second)
    ):
        return False
    if policy["type"] == "relative":
        return (
            abs(first - second) * 100 <= min(first, second) * policy["maximum_percent"]
        )
    if policy["type"] == "absolute":
        return abs(first - second) <= policy["maximum_difference"]
    return (first - 1) // policy["size"] == (second - 1) // policy["size"]


def level_policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='objectives_pvp_level_policy'"
    ).fetchone()
    if row is None:
        raise ValueError("PvP level policy is unavailable")
    return validate_level_policy(row["value"])


def _valid_roster(event, roster):
    teams = {}
    for row in roster:
        if row["team"] not in (0, 1) or type(row["level"]) is not int:
            return False
        teams.setdefault(row["team"], []).append(row)
    if set(teams) != {0, 1} or len(teams[0]) != len(teams[1]) or not teams[0]:
        return False
    owners = [{row["account_id"] for row in teams[team]} for team in (0, 1)]
    if any(len(owner) != 1 for owner in owners) or owners[0] == owners[1]:
        return False
    if owners[0] | owners[1] != {event["first_account_id"], event["second_account_id"]}:
        return False
    leaders = {
        event["first_character_id"]: event["first_account_id"],
        event["second_character_id"]: event["second_account_id"],
    }
    if any(
        not any(
            row["character_id"] == identity and row["account_id"] == owner
            for row in roster
        )
        for identity, owner in leaders.items()
    ):
        return False
    levels = [sorted(row["level"] for row in teams[team]) for team in (0, 1)]
    return all(compatible_levels(event["level_policy"], a, b) for a, b in zip(*levels))


def _native_roster(db, fight_id, fight=None):
    """Bind eligibility to actual native actor levels, including modulation."""
    rows = db.execute(
        "SELECT character_id,account_id,team FROM combat_fight_participants WHERE fight_id=%s ORDER BY team,character_id",
        (fight_id,),
    ).fetchall()
    if fight is not None:
        if fight.id != fight_id:
            raise ValueError("PvP fight identity mismatch")
        actors = {
            str(identity): actor.__dict__ for identity, actor in fight.actors.items()
        }
    else:
        checkpoint = db.execute(
            "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
        ).fetchone()
        if checkpoint is None:
            return None
        actors = checkpoint["snapshot"].get("actors", {})
    roster = []
    for row in rows:
        actor = actors.get(str(row["character_id"]))
        if (
            not isinstance(actor, dict)
            or actor.get("controlled") is not True
            or actor.get("owner_id") != row["account_id"]
            or actor.get("team") != row["team"]
            or type(actor.get("effective_level")) is not int
        ):
            return None
        roster.append({**dict(row), "level": actor["effective_level"]})
    return roster


def _effective_player(player):
    from wakfu_server.builds import effective_sheet_level

    actor = dict(player)
    index = player["selected_build_index"]
    sheet = player["selected_build_sheet"]
    actor["builds"] = {} if sheet is None else {index: {"sheet": bytes(sheet).hex()}}
    return {**dict(player), "level": effective_sheet_level(actor, index)}


def _selected_accounts(db, account_ids):
    """Live account ownership follows its actual selected actor, not a web tab."""
    rows = db.execute(
        "SELECT s.account_id,s.character_id,s.generation,c.*,selection.active_index AS selected_build_index,"
        "build.sheet AS selected_build_sheet,EXISTS(SELECT 1 FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.account_id=s.account_id "
        "AND f.status IN ('placement','active')) AS fighting "
        "FROM sessions s JOIN characters c ON c.id=s.character_id AND c.account_id=s.account_id "
        "JOIN character_build_selection selection ON selection.character_id=c.id "
        "LEFT JOIN character_builds build ON build.character_id=c.id AND build.build_index=selection.active_index "
        "WHERE s.account_id=ANY(%s::bigint[]) AND s.expires_at>CURRENT_TIMESTAMP AND c.deleted_at IS NULL",
        (list(account_ids),),
    ).fetchall()
    return {row["account_id"]: _effective_player(row) for row in rows}


def _notify(db):
    db.execute("SELECT pg_notify('wakemu_objectives_updates','all')")


def _frozen_policies(db):
    result = {}
    for kind, key in POLICIES.items():
        row = db.execute(
            "SELECT key,policy,revision FROM objectives_reward_policies WHERE key=%s",
            (key,),
        ).fetchone()
        if row is None:
            raise ValueError("Hourly PvP reward policy unavailable: " + key)
        result[kind] = dict(row)
    from .points import weights

    configured = weights(db)
    result["points"] = {
        "participation": configured["hourly_pvp_participation"],
        "winner": configured["hourly_pvp_win"],
    }
    return result


def tick(db, now=None):
    """Create only the current hour; recover durable outcomes, never fake wins."""
    now = now or datetime.now(timezone.utc)
    if not db.execute(
        "SELECT pg_try_advisory_xact_lock(747117410) AS locked"
    ).fetchone()["locked"]:
        return None
    # Hooks normally bind immediately. The worker can repair a lost handoff from
    # the accepted native invitation and its durable timestamps after restart.
    candidates = db.execute(
        "SELECT i.fight_id,i.challenger_account_id,i.challenger_character_id,i.target_account_id,i.target_character_id "
        "FROM friendly_duel_invitations i JOIN objectives_pvp_events e ON e.status='open' "
        "AND i.responded_at>=e.created_at AND i.responded_at<e.ends_at "
        "AND ((i.challenger_account_id=e.first_account_id AND i.target_account_id=e.second_account_id) "
        "OR (i.target_account_id=e.first_account_id AND i.challenger_account_id=e.second_account_id)) "
        "WHERE i.status='accepted' ORDER BY i.responded_at,i.fight_id"
    ).fetchall()
    for row in candidates:
        mark_fight_started(
            db,
            row["fight_id"],
            row["challenger_account_id"],
            row["challenger_character_id"],
            row["target_account_id"],
            row["target_character_id"],
        )
    for row in db.execute(
        "SELECT o.* FROM objectives_pvp_events e JOIN friendly_duel_outcomes o USING(fight_id) WHERE e.status='in_fight' ORDER BY e.id"
    ).fetchall():
        record_result(
            db,
            row["fight_id"],
            row["winner_character_id"],
            row["loser_character_id"],
            row["reason"],
        )
    expired = db.execute(
        "UPDATE objectives_pvp_events SET status='expired' WHERE (status='open' AND ends_at<=%s) "
        "OR (status='in_fight' AND NOT EXISTS(SELECT 1 FROM combat_fights f WHERE f.id=objectives_pvp_events.fight_id AND f.status IN ('placement','active'))) RETURNING id",
        (now,),
    ).fetchall()
    if expired:
        _notify(db)
    active = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE status IN ('open','in_fight') ORDER BY starts_at LIMIT 1"
    ).fetchone()
    if active:
        return active
    key, start, end = hour(now)
    existing = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE period_key=%s", (key,)
    ).fetchone()
    if existing:
        return existing
    players = db.execute(
        "SELECT s.account_id,s.character_id,s.generation,c.*,selection.active_index AS selected_build_index,"
        "build.sheet AS selected_build_sheet FROM sessions s JOIN characters c "
        "ON c.id=s.character_id AND c.account_id=s.account_id "
        "JOIN character_build_selection selection ON selection.character_id=c.id "
        "LEFT JOIN character_builds build ON build.character_id=c.id AND build.build_index=selection.active_index "
        "WHERE s.expires_at>%s AND c.deleted_at IS NULL "
        "AND c.instance_id=0 AND c.level BETWEEN 1 AND %s "
        "AND NOT EXISTS(SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.account_id=s.account_id AND f.status IN ('placement','active')) "
        "AND NOT EXISTS(SELECT 1 FROM objectives_pvp_events e WHERE e.status='in_fight' "
        "AND s.account_id IN(e.first_account_id,e.second_account_id)) "
        "ORDER BY md5(%s||':'||s.account_id::text),s.account_id",
        (now, MAX_CHARACTER_LEVEL, key),
    ).fetchall()
    players = [_effective_player(player) for player in players]
    players = [
        player for player in players if 1 <= player["level"] <= MAX_CHARACTER_LEVEL
    ]
    policy = level_policy(db)
    pair = next(
        (
            (first, second)
            for index, first in enumerate(players)
            for second in players[index + 1 :]
            if first["account_id"] != second["account_id"]
            and compatible_levels(policy, first["level"], second["level"])
        ),
        None,
    )
    if pair is None:
        return None
    first, second = pair
    policies = _frozen_policies(db)
    row = db.execute(
        "INSERT INTO objectives_pvp_events(period_key,starts_at,ends_at,first_account_id,first_character_id,first_generation,first_level,"
        "second_account_id,second_character_id,second_generation,second_level,reward_snapshot,level_policy,created_at) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(period_key) DO NOTHING RETURNING *",
        (
            key,
            start,
            end,
            first["account_id"],
            first["character_id"],
            first["generation"],
            first["level"],
            second["account_id"],
            second["character_id"],
            second["generation"],
            second["level"],
            Jsonb(policies),
            Jsonb(policy),
            now,
        ),
    ).fetchone()
    if row:
        _notify(db)
    return row


def mark_fight_started(db, fight_id, account1, char1, account2, char2, *, fight=None):
    """Bind only the selected accounts' real accepted duel inside its transaction."""
    if account1 == account2:
        return None
    duel = db.execute(
        "SELECT i.*,f.status AS fight_status FROM friendly_duel_invitations i JOIN combat_fights f ON f.id=i.fight_id "
        "WHERE i.fight_id=%s AND i.status='accepted' AND f.fight_kind='duel'",
        (fight_id,),
    ).fetchone()
    if duel is None or {
        (duel["challenger_account_id"], duel["challenger_character_id"]),
        (duel["target_account_id"], duel["target_character_id"]),
    } != {(account1, char1), (account2, char2)}:
        return None
    existing = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if existing:
        return existing
    event = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE status='open' AND created_at<=%s AND ends_at>%s "
        "AND ((first_account_id=%s AND second_account_id=%s) "
        "OR (first_account_id=%s AND second_account_id=%s)) "
        "ORDER BY starts_at DESC LIMIT 1 FOR UPDATE",
        (
            duel["responded_at"],
            duel["responded_at"],
            account1,
            account2,
            account2,
            account1,
        ),
    ).fetchone()
    if event is None:
        return None
    roster = _native_roster(db, fight_id, fight)
    if roster is None:
        return None
    leaders = {
        duel["challenger_account_id"]: (
            duel["challenger_character_id"],
            duel["challenger_generation"],
        ),
        duel["target_account_id"]: (
            duel["target_character_id"],
            duel["target_generation"],
        ),
    }
    if fight is not None:
        selected = _selected_accounts(db, leaders)
        if any(
            account not in selected
            or (selected[account]["character_id"], selected[account]["generation"])
            != leader
            for account, leader in leaders.items()
        ):
            return None
    else:
        # Accepted invitations plus durable participant generations prove who
        # was selected at native admission, even after those accounts disconnect.
        admitted = db.execute(
            "SELECT character_id,account_id,session_generation FROM combat_fight_participants WHERE fight_id=%s",
            (fight_id,),
        ).fetchall()
        if any(
            not any(
                row["account_id"] == account
                and row["character_id"] == leader[0]
                and row["session_generation"] == leader[1]
                for row in admitted
            )
            for account, leader in leaders.items()
        ):
            return None
    event = dict(event)
    for prefix in ("first", "second"):
        character_id, generation = leaders[event[prefix + "_account_id"]]
        actor = next(
            (
                row
                for row in roster
                if row["character_id"] == character_id
                and row["account_id"] == event[prefix + "_account_id"]
            ),
            None,
        )
        if actor is None:
            return None
        event.update(
            {
                prefix + "_character_id": character_id,
                prefix + "_generation": generation,
                prefix + "_level": actor["level"],
            }
        )
    if not _valid_roster(event, roster):
        db.execute(
            "UPDATE objectives_pvp_events SET status='expired' WHERE id=%s",
            (event["id"],),
        )
        _notify(db)
        return None
    for member in roster:
        db.execute(
            "INSERT INTO objectives_pvp_fight_roster(event_id,fight_id,character_id,account_id,team,level) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                event["id"],
                fight_id,
                member["character_id"],
                member["account_id"],
                member["team"],
                member["level"],
            ),
        )
    # The native invitation already authenticates both consenting generations.
    # Reconnecting the same selected characters does not cancel their matchup.
    row = db.execute(
        "UPDATE objectives_pvp_events SET status='in_fight',fight_id=%s,map_id=%s,instance_id=%s,"
        "first_character_id=%s,first_generation=%s,first_level=%s,second_character_id=%s,second_generation=%s,second_level=%s "
        "WHERE id=%s RETURNING *",
        (
            fight_id,
            duel["map_id"],
            duel["instance_id"],
            event["first_character_id"],
            event["first_generation"],
            event["first_level"],
            event["second_character_id"],
            event["second_generation"],
            event["second_level"],
            event["id"],
        ),
    ).fetchone()
    _notify(db)
    return row


def record_result(db, fight_id, winnerchar, loserchar, reason, *, fight=None):
    """Reserve participation and victory rewards once from the durable outcome."""
    event = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE fight_id=%s FOR UPDATE", (fight_id,)
    ).fetchone()
    if event is None or event["status"] != "in_fight":
        return event
    outcome = db.execute(
        "SELECT o.*,f.status AS fight_status FROM friendly_duel_outcomes o JOIN combat_fights f ON f.id=o.fight_id WHERE o.fight_id=%s AND f.fight_kind='duel'",
        (fight_id,),
    ).fetchone()
    if (
        outcome is None
        or outcome["fight_status"] != "finished"
        or outcome["winner_character_id"] != winnerchar
        or outcome["loser_character_id"] != loserchar
        or outcome["reason"] != reason
        or {winnerchar, loserchar}
        != {event["first_character_id"], event["second_character_id"]}
    ):
        raise ValueError("Hourly PvP result lacks the matching durable duel outcome")
    roster = db.execute(
        "SELECT character_id,account_id,team,level FROM objectives_pvp_fight_roster WHERE event_id=%s ORDER BY team,character_id",
        (event["id"],),
    ).fetchall()
    actual = _native_roster(db, fight_id, fight)
    if actual is None:
        return None
    roster_valid = _valid_roster(event, roster) and roster == actual
    if reason != "defeat" or not roster_valid:
        row = db.execute(
            "UPDATE objectives_pvp_events SET status='expired' WHERE id=%s RETURNING *",
            (event["id"],),
        ).fetchone()
        _notify(db)
        return row
    from .repository import reserve_rewards

    for prefix in ("first", "second"):
        character_id, level = event[prefix + "_character_id"], event[prefix + "_level"]
        kinds = ["participation"] + (["winner"] if character_id == winnerchar else [])
        for kind in kinds:
            key = "hourly-pvp-" + kind
            policy = event["reward_snapshot"][kind]
            # Internal definition edits cannot alter a previously announced prize.
            definition = {
                "key": key,
                "rewards": [{"kind": "scaled", "policy_key": policy["key"]}],
            }
            counters = {"complete" if kind == "participation" else "win": 1}
            db.execute(
                "INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,counters,completed_at,reward_character_id) VALUES(%s,%s,%s,1,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    event[prefix + "_account_id"],
                    key,
                    event["period_key"],
                    Jsonb(counters),
                    outcome["settled_at"],
                    character_id,
                ),
            )
            db.execute(
                "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at) VALUES(%s,%s,%s,1,%s,%s) ON CONFLICT DO NOTHING",
                (
                    character_id,
                    key,
                    event["period_key"],
                    Jsonb(counters),
                    outcome["settled_at"],
                ),
            )
            reserve_rewards(
                db,
                character_id,
                definition,
                event["period_key"],
                level=level,
                policies={policy["key"]: policy},
            )
            from .points import award_points

            award_points(
                db,
                event[prefix + "_account_id"],
                f"hourly-pvp:{event['id']}:{kind}",
                event["reward_snapshot"]["points"][kind],
                category="hourly_pvp_participation"
                if kind == "participation"
                else "hourly_pvp_win",
                character_id=character_id,
                level=level,
                occurred_at=outcome["settled_at"],
            )
        db.execute(
            "SELECT pg_notify('wakemu_objectives_updates',%s)", (str(character_id),)
        )
    row = db.execute(
        "UPDATE objectives_pvp_events SET status='completed',winner_character_id=%s,completed_at=%s,rewards_reserved=true WHERE id=%s RETURNING *",
        (winnerchar, outcome["settled_at"], event["id"]),
    ).fetchone()
    _notify(db)
    return row


def actions(db, identity):
    result = []
    if not identity.get("generation"):
        return result
    live = db.execute(
        "SELECT 1 FROM sessions WHERE account_id=%s AND character_id=%s AND generation=%s AND expires_at>CURRENT_TIMESTAMP",
        (identity["account_id"], identity["character_id"], identity["generation"]),
    ).fetchone()
    if not live:
        return result
    for event in db.execute(
        "SELECT * FROM objectives_pvp_events WHERE (status='open' AND ends_at>CURRENT_TIMESTAMP) OR status='in_fight' ORDER BY starts_at DESC"
    ).fetchall():
        if event["status"] == "open":
            prefix = next(
                (
                    p
                    for p in ("first", "second")
                    if event[p + "_account_id"] == identity["account_id"]
                ),
                None,
            )
            if prefix is None:
                continue
            other = "second" if prefix == "first" else "first"
            players = _selected_accounts(
                db, (event["first_account_id"], event["second_account_id"])
            )
            own, opponent = players.get(identity["account_id"]), players.get(
                event[other + "_account_id"]
            )
            if (
                own is None
                or opponent is None
                or own["instance_id"] != 0
                or opponent["instance_id"] != 0
                or own["fighting"]
                or opponent["fighting"]
                or not compatible_levels(
                    event["level_policy"], own["level"], opponent["level"]
                )
            ):
                continue
            target = dict(
                kind="pvp",
                action="meet",
                event_id=event["id"],
                opponent_account_id=opponent["account_id"],
                opponent_character_id=opponent["character_id"],
                opponent_generation=opponent["generation"],
            )
            result.append(
                dict(
                    key=f"pvp.meet.{event['id']}",
                    label="Meet opponent",
                    kind="pvp",
                    enabled=True,
                    target=target,
                )
            )
        else:
            fight = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (event["fight_id"],)
            ).fetchone()
            if fight and fight["status"] in ("placement", "active"):
                target = dict(
                    kind="pvp",
                    action="watch",
                    event_id=event["id"],
                    fight_id=event["fight_id"],
                    map_id=event["map_id"],
                    instance_id=event["instance_id"],
                )
                result.append(
                    dict(
                        key=f"pvp.watch.{event['id']}",
                        label="Watch fight",
                        kind="pvp",
                        enabled=True,
                        target=target,
                    )
                )
    return result


def resolve(db, identity, action_key):
    action = next(
        (row for row in actions(db, identity) if row["key"] == action_key), None
    )
    if action is None:
        raise ValueError("Hourly PvP action is unavailable")
    return action


def snapshot(db, identity):
    current = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE status IN('open','in_fight') ORDER BY (first_account_id=%s OR second_account_id=%s) DESC,starts_at DESC LIMIT 1",
        (identity["account_id"], identity["account_id"]),
    ).fetchone()
    history = db.execute(
        "SELECT * FROM objectives_pvp_events WHERE status='completed' ORDER BY completed_at DESC,id DESC LIMIT 20"
    ).fetchall()
    if current and current["status"] == "open":
        current = dict(current)
        players = _selected_accounts(
            db, (current["first_account_id"], current["second_account_id"])
        )
        for prefix in ("first", "second"):
            player = players.get(current[prefix + "_account_id"])
            if player is not None:
                current.update(
                    {
                        prefix + "_character_id": player["character_id"],
                        prefix + "_generation": player["generation"],
                        prefix + "_level": player["level"],
                    }
                )
    visible = ([current] if current else []) + history
    identities = sorted(
        {row[p + "_character_id"] for row in visible for p in ("first", "second")}
    )
    names = {
        row["id"]: row["name"]
        for row in db.execute(
            "SELECT id,name FROM characters WHERE id=ANY(%s::bigint[])", (identities,)
        ).fetchall()
    }
    available = actions(db, identity)

    def public(event):
        participants = [
            dict(
                account_id=event[p + "_account_id"],
                character_id=event[p + "_character_id"],
                name=names.get(event[p + "_character_id"], "Unknown"),
                level=event[p + "_level"],
            )
            for p in ("first", "second")
        ]
        selected = next(
            (
                row
                for row in participants
                if row["account_id"] == identity["account_id"]
            ),
            None,
        )
        opponent = next(
            (
                row
                for row in participants
                if selected and row["account_id"] != selected["account_id"]
            ),
            None,
        )
        rewards = {
            kind: next(
                b["rewards"]
                for b in policy["policy"]["bands"]
                if b["minimum"]
                <= (selected or participants[0])["level"]
                <= b["maximum"]
            )
            for kind, policy in event["reward_snapshot"].items()
            if kind in POLICIES
        }
        return dict(
            id=event["id"],
            period_key=event["period_key"],
            status=event["status"],
            level_policy=event["level_policy"],
            starts_at=event["starts_at"],
            ends_at=event["ends_at"],
            participant_one=participants[0],
            participant_two=participants[1],
            participating=selected is not None,
            opponent_name=opponent["name"] if opponent else None,
            fight_id=event["fight_id"],
            map_id=event["map_id"],
            winner=next(
                (
                    row
                    for row in participants
                    if row["character_id"] == event["winner_character_id"]
                ),
                None,
            ),
            rewards=rewards,
            participation_points=event["reward_snapshot"]["points"]["participation"],
            winner_points=event["reward_snapshot"]["points"]["winner"],
            actions=[
                {k: v for k, v in a.items() if k != "target"}
                for a in available
                if a["target"]["event_id"] == event["id"]
            ],
            completed_at=event["completed_at"],
        )

    return dict(
        current=public(current) if current else None,
        history=[public(row) for row in history],
    )
