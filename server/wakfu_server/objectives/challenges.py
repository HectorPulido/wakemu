"""Owned finite weekly encounters and authoritative settlement receipts.

All writes share the caller's World transaction. This module never broadcasts
packets, creates test outcomes, mutates ecology or accepts client score facts.
"""
import uuid
from datetime import datetime, timezone
from psycopg.types.json import Jsonb


INSTANCE_MINIMUM = 576460752303423489
INSTANCE_MAXIMUM = 648518346341351423


def is_challenge_instance(instance_id):
    return (
        type(instance_id) is int and INSTANCE_MINIMUM <= instance_id <= INSTANCE_MAXIMUM
    )


POSITION_FIELDS = ("map_id", "instance_id", "x", "y", "z")


def week_key(now):
    from .rankings import week_key as ranking_week_key

    if now.tzinfo is None:
        raise ValueError("Challenge timestamp requires timezone")
    return ranking_week_key(now)


def _position(row):
    return {field: row[field] for field in POSITION_FIELDS}


def _owned_character(db, account_id, character_id):
    row = db.execute(
        "SELECT * FROM characters WHERE account_id=%s AND id=%s AND deleted_at IS NULL FOR UPDATE",
        (account_id, character_id),
    ).fetchone()
    if row is None:
        raise ValueError("Challenge character is unavailable or foreign")
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Finish the current fight before changing challenge scenes")
    return row


def current_run(db, account_id, character_id):
    return db.execute(
        "SELECT r.* FROM objectives_challenge_runs r JOIN objectives_challenge_members m USING(attempt_id) WHERE r.owner_account_id=%s AND m.character_id=%s AND r.returned_at IS NULL ORDER BY r.created_at DESC LIMIT 1",
        (account_id, character_id),
    ).fetchone()


def _result(db, run, *, replay):
    group = db.execute(
        "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        (run["map_id"], run["instance_id"], run["group_id"]),
    ).fetchone()
    if group is None:
        raise ValueError("Challenge receipt has no registered native group")
    return dict(
        run,
        x=run["anchor"][0],
        y=run["anchor"][1],
        z=run["anchor"][2],
        members=tuple(group["members"]),
        group_status=group["status"],
        replay=replay,
    )


def recover_escaped_run(db, run):
    """Release an escaped scene without overwriting an already returned owner.

    Defeat recovery or an operator transport can move a character outside the
    instance. Restore only admitted members still inside it, then close the
    receipt so a later entry can reserve a new attempt.
    """
    members = db.execute(
        "SELECT * FROM objectives_challenge_members WHERE attempt_id=%s ORDER BY character_id",
        (run["attempt_id"],),
    ).fetchall()
    for member in members:
        current = _owned_character(db, run["owner_account_id"], member["character_id"])
        if current["instance_id"] != run["instance_id"]:
            continue
        p = member["return_position"]
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s AND instance_id=%s",
            (
                *(p[f] for f in POSITION_FIELDS),
                member["character_id"],
                run["owner_account_id"],
                run["instance_id"],
            ),
        )
    db.execute(
        "UPDATE objectives_challenge_runs SET status=CASE WHEN status IN ('available','fighting') THEN 'abandoned' ELSE status END,returned_at=CURRENT_TIMESTAMP WHERE attempt_id=%s",
        (run["attempt_id"],),
    )
    db.execute(
        "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='available'",
        (run["map_id"], run["instance_id"], run["group_id"]),
    )


def enter_weekly(db, groups, account_id, character_id, *, geometry_loader, now=None):
    from .challenges_profiles import validate_profile
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.monsters import owned_instance

    now = now or datetime.now(timezone.utc)
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"weekly-challenge-account:{account_id}",),
    )
    char = _owned_character(db, account_id, character_id)
    existing = current_run(db, account_id, character_id)
    if existing and (char["map_id"], char["instance_id"]) != (
        existing["map_id"],
        existing["instance_id"],
    ):
        recover_escaped_run(db, existing)
        existing = None
    if existing:
        if existing["status"] == "fighting":
            fight = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (existing["fight_id"],)
            ).fetchone()
            if fight and fight["status"] in ("placement", "active"):
                raise ValueError("Reconnect to the existing challenge fight")
            db.execute(
                "UPDATE objectives_challenge_runs SET status='abandoned',settled_at=CURRENT_TIMESTAMP WHERE attempt_id=%s",
                (existing["attempt_id"],),
            )
            raise ValueError(
                "The interrupted challenge must be returned from before retrying"
            )
        return _result(db, existing, replay=True)
    if char["instance_id"] != 0:
        raise ValueError(
            "Leave the current private scene before starting a weekly challenge"
        )
    if db.execute(
        "SELECT 1 FROM dungeon_instance_members WHERE character_id=%s AND status='active'",
        (character_id,),
    ).fetchone():
        raise ValueError("Leave the active dungeon before entering a weekly challenge")
    hero_rows = db.execute(
        "SELECT c.* FROM account_hero_slots h JOIN account_hero_rosters r USING(account_id) JOIN characters c ON c.id=h.character_id AND c.account_id=h.account_id WHERE h.account_id=%s AND r.leader_id=%s AND c.deleted_at IS NULL ORDER BY c.id FOR UPDATE OF c",
        (account_id, character_id),
    ).fetchall()
    chars = [char, *hero_rows]
    group_level = max(member["level"] for member in chars)
    profiles = db.execute(
        "SELECT * FROM objectives_challenge_profiles WHERE (definition->>'enabled')::boolean AND (definition->>'min_level')::integer<=%s AND (definition->>'max_level')::integer>=%s ORDER BY key FOR SHARE",
        (group_level, group_level),
    ).fetchall()
    if len(profiles) != 1:
        raise ValueError("No unique weekly challenge is configured for your level")
    profile = profiles[0]
    definition = validate_profile(profile["definition"])
    weekly = week_key(now)
    # Account-wide level bracket is frozen for the configured week; switching heroes
    # cannot create a second easier scoring bracket for the same account.
    previous = db.execute(
        "SELECT bracket FROM objectives_challenge_runs WHERE owner_account_id=%s AND week_key=%s ORDER BY created_at LIMIT 1",
        (account_id, weekly),
    ).fetchone()
    bracket = f'{definition["min_level"]:03d}-{definition["max_level"]:03d}'
    if previous and previous["bracket"] != bracket:
        raise ValueError("Your account's weekly challenge bracket is already frozen")
    instance_id = db.execute(
        "SELECT nextval('objectives_challenge_instance_ids') AS id"
    ).fetchone()["id"]
    group_id = db.execute(
        "SELECT nextval('objectives_challenge_group_ids') AS id"
    ).fetchone()["id"]
    attempt_id = uuid.uuid4().hex
    geometry = geometry_loader(definition["map_id"])
    quantity = sum(row["count"] for row in definition["roster"])
    cells = enemy_formation(geometry, definition["anchor"], quantity, player_slots=12)
    base = allocate_block(db, quantity)
    roster = [row for row in definition["roster"] for _ in range(row["count"])]
    members = tuple(
        owned_instance(
            row["ref_id"],
            row["level"],
            -(base + i),
            map_id=definition["map_id"],
            instance_id=instance_id,
            x=cell[0],
            y=cell[1],
            z=cell[2],
        )
        for i, (row, cell) in enumerate(zip(roster, cells))
    )
    groups.register_transaction(
        db, definition["map_id"], instance_id, group_id, members
    )
    run = db.execute(
        "INSERT INTO objectives_challenge_runs(attempt_id,owner_account_id,character_id,profile_key,profile_revision,week_key,bracket,level,group_level,instance_id,map_id,group_id,roster,return_position,anchor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            attempt_id,
            account_id,
            character_id,
            profile["key"],
            profile["revision"],
            weekly,
            bracket,
            char["level"],
            group_level,
            instance_id,
            definition["map_id"],
            group_id,
            Jsonb(list(members)),
            Jsonb(_position(char)),
            Jsonb(definition["anchor"]),
        ),
    ).fetchone()
    # Only the selected character and its currently active, same-location heroes
    # are admitted; other accounts cannot join this owned finite encounter.
    for member in chars:
        if (
            _position(member)["instance_id"] != char["instance_id"]
            or member["map_id"] != char["map_id"]
        ):
            raise ValueError("All active heroes must share the challenge entry scene")
        if member["id"] != character_id:
            _owned_character(db, account_id, member["id"])
        db.execute(
            "INSERT INTO objectives_challenge_members(attempt_id,character_id,return_position) VALUES(%s,%s,%s)",
            (attempt_id, member["id"], Jsonb(_position(member))),
        )
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s",
            (
                definition["map_id"],
                instance_id,
                *definition["anchor"],
                member["id"],
                account_id,
            ),
        )
    return _result(db, run, replay=False)


def return_from_challenge(db, account_id, character_id, *, abandon=False):
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"weekly-challenge-account:{account_id}",),
    )
    char = _owned_character(db, account_id, character_id)
    run = current_run(db, account_id, character_id)
    if run is None:
        raise ValueError("You are not in your owned weekly challenge")
    if (char["map_id"], char["instance_id"]) != (run["map_id"], run["instance_id"]):
        recover_escaped_run(db, run)
        return _position(char)
    if run["status"] in ("available", "fighting") and not abandon:
        raise ValueError("Finish the challenge or use !challenge abandon")
    rows = db.execute(
        "SELECT * FROM objectives_challenge_members WHERE attempt_id=%s ORDER BY character_id",
        (run["attempt_id"],),
    ).fetchall()
    for member in rows:
        _owned_character(db, account_id, member["character_id"])
        p = member["return_position"]
        db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s AND instance_id=%s",
            (
                *(p[f] for f in POSITION_FIELDS),
                member["character_id"],
                account_id,
                run["instance_id"],
            ),
        )
    db.execute(
        "UPDATE objectives_challenge_runs SET status=CASE WHEN status IN ('available','fighting') THEN 'abandoned' ELSE status END,returned_at=CURRENT_TIMESTAMP WHERE attempt_id=%s",
        (run["attempt_id"],),
    )
    db.execute(
        "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=%s AND group_id=%s AND status='available'",
        (run["map_id"], run["instance_id"], run["group_id"]),
    )
    selected = next(member for member in rows if member["character_id"] == character_id)
    return dict(selected["return_position"])


def bind_fight(db, map_id, instance_id, group_id, fight_id):
    run = db.execute(
        "SELECT * FROM objectives_challenge_runs WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
        (map_id, instance_id, group_id),
    ).fetchone()
    if run is None:
        return None
    if run["status"] == "fighting" and run["fight_id"] == fight_id:
        return run
    if run["status"] != "available" or run["returned_at"] is not None:
        raise ValueError("Challenge attempt is unavailable")
    expected = {
        r["character_id"]
        for r in db.execute(
            "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s",
            (run["attempt_id"],),
        ).fetchall()
    }
    participants = db.execute(
        "SELECT * FROM combat_fight_participants WHERE fight_id=%s", (fight_id,)
    ).fetchall()
    if not participants or any(
        r["account_id"] != run["owner_account_id"]
        or r["character_id"] not in expected
        or r["team"] != 0
        for r in participants
    ):
        raise ValueError("Challenge fight contains an unauthorized participant")
    return db.execute(
        "UPDATE objectives_challenge_runs SET status='fighting',fight_id=%s WHERE attempt_id=%s RETURNING *",
        (fight_id, run["attempt_id"]),
    ).fetchone()


def mark_test_fight(db, fight_id):
    return db.execute(
        "UPDATE objectives_challenge_runs SET test_mode=true WHERE fight_id=%s RETURNING attempt_id",
        (fight_id,),
    ).fetchone()


def settle_fight(db, fight, *, now=None):
    from .repository import enqueue

    now = now or datetime.now(timezone.utc)
    run = db.execute(
        "SELECT r.*,f.status AS fight_status FROM objectives_challenge_runs r JOIN combat_fights f ON f.id=r.fight_id WHERE r.fight_id=%s FOR UPDATE OF r",
        (fight.id,),
    ).fetchone()
    if run is None:
        return None
    if run["status"] in ("won", "lost"):
        return run
    if (
        run["status"] != "fighting"
        or run["fight_status"] != "finished"
        or fight.phase != "finished"
        or fight.winner not in (0, 1)
    ):
        raise ValueError("Challenge lacks an authoritative finished fight")
    turns = getattr(fight, "native_timeline_round", None)
    if run["test_mode"] and turns == 0:
        turns = 1  # Operator-ended placement is terminal but never ranked.
    if type(turns) is not int or turns < 1:
        raise ValueError("Challenge has no authoritative turn count")
    won = fight.winner == 0
    run = db.execute(
        "UPDATE objectives_challenge_runs SET status=%s,winner_team=%s,turns=%s,settled_at=%s WHERE attempt_id=%s RETURNING *",
        ("won" if won else "lost", fight.winner, turns, now, run["attempt_id"]),
    ).fetchone()
    # An unfinished prior-week encounter remains playable, but is not a ranked
    # current-week completion and cannot reopen a finalized previous period.
    owner_participated = (
        db.execute(
            "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND account_id=%s AND character_id=%s AND team=0",
            (fight.id, run["owner_account_id"], run["character_id"]),
        ).fetchone()
        is not None
    )
    if (
        won
        and owner_participated
        and not run["test_mode"]
        and run["week_key"] == week_key(now)
    ):
        payload = {
            "kind": "challenge_completed",
            **{
                k: run[k]
                for k in (
                    "attempt_id",
                    "profile_key",
                    "level",
                    "turns",
                    "week_key",
                    "bracket",
                )
            },
            "won": True,
            "ranked": True,
        }
        enqueue(
            db,
            run["owner_account_id"],
            run["character_id"],
            "challenge:" + run["attempt_id"],
            payload,
            now,
        )
    return run


def authorize_fight_participant(db, fight_id, account_id, character_id):
    """Fence late hero/player joins against the immutable admitted roster."""
    run = db.execute(
        "SELECT * FROM objectives_challenge_runs WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if run is None:
        return
    if (
        run["status"] != "fighting"
        or run["owner_account_id"] != account_id
        or db.execute(
            "SELECT 1 FROM objectives_challenge_members WHERE attempt_id=%s AND character_id=%s",
            (run["attempt_id"], character_id),
        ).fetchone()
        is None
    ):
        raise ValueError("This character is not admitted to the owned weekly challenge")


def mark_scene_test(db, instance_id):
    """Persist exclusion before any operator mutation to a private attempt."""
    return db.execute(
        "UPDATE objectives_challenge_runs SET test_mode=true WHERE instance_id=%s AND returned_at IS NULL RETURNING attempt_id",
        (instance_id,),
    ).fetchone()
