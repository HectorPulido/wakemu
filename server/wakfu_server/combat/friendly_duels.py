"""Durable consent and no-reward settlement for friendly player duels.

This module owns only invitation and storage policy. The normal combat FSM
continues to resolve turns and effects; the dispatcher must use the duel
settlement path instead of PvE reward/loot callbacks for ``fight_kind='duel'``.
"""
from datetime import timedelta

from psycopg.pq import TransactionStatus

from .friendly_duel_wire import cancellation, decode_answer, decode_challenge, invite


def _invitation_policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='friendly_duel_policy'"
    ).fetchone()
    value = row["value"] if row is not None else None
    if not isinstance(value, dict) or set(value) != {
        "invitation_ttl_seconds",
        "reply_quarantine_seconds",
    }:
        raise ValueError("Friendly duel invitation policy is unavailable or invalid")
    ttl = value["invitation_ttl_seconds"]
    quarantine = value["reply_quarantine_seconds"]
    if (
        type(ttl) is not int
        or not 1 <= ttl <= 300
        or type(quarantine) is not int
        or not ttl <= quarantine <= 3600
    ):
        raise ValueError("Friendly duel invitation policy is unavailable or invalid")
    return ttl, quarantine


def _session_fields(session):
    values = tuple(
        getattr(session, key, None)
        for key in ("account_id", "character_id", "generation")
    )
    if (
        type(values[0]) is not int
        or values[0] <= 0
        or type(values[1]) is not int
        or values[1] <= 0
        or not isinstance(values[2], str)
        or not values[2]
    ):
        raise ValueError("Invalid duel session identity")
    return values


def _lock_pair(store, db, first, second):
    a = _session_fields(first)
    b = _session_fields(second)
    if a[0] == b[0] or a[1] == b[1]:
        raise ValueError("Friendly duel requires two distinct account owners")
    for account, character, generation in sorted((a, b)):
        store.lock_character(db, account, generation, character)
    left = store.character(a[0], a[1], db)
    right = store.character(b[0], b[1], db)
    if (
        (left["map_id"], left.get("instance_id", 0))
        != (right["map_id"], right.get("instance_id", 0))
        or left["hp"] <= 0
        or right["hp"] <= 0
        or left.get("health_dead", False)
        or right.get("health_dead", False)
    ):
        raise ValueError("Duel participants are not alive in the same location")
    active = db.execute(
        "SELECT p.character_id FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=ANY(%s) AND f.status IN ('placement','active') "
        "FOR UPDATE OF f",
        ([a[1], b[1]],),
    ).fetchone()
    if active is not None:
        raise ValueError("Duel participant is already fighting")
    return a, b, left, right


def invite_challenge(
    store,
    challenger_session,
    target_session,
    request_body,
):
    """Persist one current-session challenge and return its native invite.

    Coordinates carried by12117 are parsed but never used as authority. The
    only locations persisted are the two server-owned character rows.
    """
    request = decode_challenge(request_body)
    challenger = _session_fields(challenger_session)
    target = _session_fields(target_session)
    if request["target_character_id"] != target[1]:
        raise ValueError("Duel request target does not match live target")
    now = store.now()
    with store.connection() as db:
        ttl_seconds, quarantine_seconds = _invitation_policy(db)
        a, b, source, recipient = _lock_pair(
            store, db, challenger_session, target_session
        )
        # A reply has no nonce. Keep one unresolved request per target and
        # pair, so a stale reply cannot select among concurrent invitations.
        db.execute(
            "UPDATE friendly_duel_invitations SET status='expired',responded_at=%s "
            "WHERE target_account_id=%s AND target_character_id=%s "
            "AND status='pending' AND expires_at<=%s",
            (now, b[0], b[1], now),
        )
        if db.execute(
            "SELECT id FROM friendly_duel_invitations WHERE target_account_id=%s "
            "AND target_character_id=%s AND status='pending' FOR UPDATE",
            (b[0], b[1]),
        ).fetchone():
            raise ValueError("Target already has a pending duel invitation")
        created = db.execute(
            "SELECT id,expires_at,responded_at FROM friendly_duel_invitations "
            "WHERE challenger_account_id=%s AND challenger_character_id=%s "
            "AND target_account_id=%s AND target_character_id=%s "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (a[0], a[1], b[0], b[1]),
        ).fetchone()
        if (
            created is not None
            and (created["responded_at"] or created["expires_at"])
            + timedelta(seconds=quarantine_seconds)
            > now
        ):
            raise ValueError("A recent same-pair duel reply may still be in flight")
        result = db.execute(
            "INSERT INTO friendly_duel_invitations("
            "challenger_account_id,challenger_character_id,challenger_generation,"
            "target_account_id,target_character_id,target_generation,map_id,instance_id,"
            "challenger_x,challenger_y,challenger_z,target_x,target_y,target_z,mode,"
            "auto_lock,status,created_at,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s) "
            "RETURNING id,expires_at",
            (
                a[0],
                a[1],
                a[2],
                b[0],
                b[1],
                b[2],
                source["map_id"],
                source.get("instance_id", 0),
                source["x"],
                source["y"],
                source["z"],
                recipient["x"],
                recipient["y"],
                recipient["z"],
                request["mode"],
                request["auto_lock"],
                now,
                store.now(ttl_seconds),
            ),
        ).fetchone()
        return {
            "invitation_id": result["id"],
            "target_account_id": b[0],
            "target_character_id": b[1],
            "packet": invite(a[1], request["mode"]),
            "expires_at": result["expires_at"],
            "source": source,
            "target": recipient,
        }


def _answer_challenge_inner(
    store,
    target_session,
    request_body,
    *,
    prepare_duel=None,
):
    """Accept/refuse the unique pending native invitation from its challenger.

    For acceptance ``prepare_duel(db, fight_id, invitation, source, target)``
    must build and serialize the runtime before this transaction commits. It
    returns ``(prepared, rollback)``; rollback is called if SQL commit fails.
    No packets are sent from inside this transaction.
    """
    request = decode_answer(request_body)
    target = _session_fields(target_session)
    with store.connection() as db:
        # Read the challenger identity to acquire both session/character locks
        # in the same deterministic order used by challenge creation.
        hint = db.execute(
            "SELECT challenger_account_id,challenger_character_id "
            "FROM friendly_duel_invitations WHERE target_account_id=%s "
            "AND target_character_id=%s AND challenger_character_id=%s "
            "AND status='pending' ORDER BY id DESC LIMIT 1",
            (target[0], target[1], request["challenger_character_id"]),
        ).fetchone()
        if hint is None:
            return {
                "accepted": False,
                "packet": cancellation(5),
                "fight_id": None,
                "notify_account_id": target[0],
            }
        challenger = db.execute(
            "SELECT generation FROM sessions WHERE account_id=%s AND character_id=%s "
            "AND expires_at>%s",
            (
                hint["challenger_account_id"],
                hint["challenger_character_id"],
                store.now(),
            ),
        ).fetchone()
        if challenger is None:
            db.execute(
                "UPDATE friendly_duel_invitations SET status='cancelled',responded_at=%s "
                "WHERE target_account_id=%s AND target_character_id=%s "
                "AND challenger_character_id=%s AND status='pending'",
                (store.now(), target[0], target[1], request["challenger_character_id"]),
            )
            return {
                "accepted": False,
                "packet": cancellation(6),
                "fight_id": None,
                "notify_account_id": hint["challenger_account_id"],
            }
        from types import SimpleNamespace

        challenger_session = SimpleNamespace(
            account_id=hint["challenger_account_id"],
            character_id=hint["challenger_character_id"],
            generation=challenger["generation"],
        )
        try:
            a, b, source, recipient = _lock_pair(
                store, db, challenger_session, target_session
            )
        except ValueError:
            db.execute(
                "UPDATE friendly_duel_invitations SET status='cancelled',responded_at=%s "
                "WHERE target_account_id=%s AND target_character_id=%s "
                "AND challenger_character_id=%s AND status='pending'",
                (store.now(), target[0], target[1], request["challenger_character_id"]),
            )
            return {"accepted": False, "packet": cancellation(6), "fight_id": None}
        row = db.execute(
            "SELECT * FROM friendly_duel_invitations WHERE challenger_account_id=%s "
            "AND challenger_character_id=%s AND challenger_generation=%s "
            "AND target_account_id=%s AND target_character_id=%s "
            "AND target_generation=%s AND status='pending' "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (a[0], a[1], a[2], b[0], b[1], b[2]),
        ).fetchone()
        if row is None:
            # The native answer identifies only the challenger, not an
            # invitation nonce. Retire stale-generation invitations for this
            # pair so they cannot occupy the target's pending slot forever.
            db.execute(
                "UPDATE friendly_duel_invitations SET status='cancelled',responded_at=%s "
                "WHERE target_account_id=%s AND target_character_id=%s "
                "AND challenger_account_id=%s AND challenger_character_id=%s "
                "AND status='pending' AND (target_generation<>%s "
                "OR challenger_generation<>%s)",
                (store.now(), b[0], b[1], a[0], a[1], b[2], a[2]),
            )
            return {
                "accepted": False,
                "packet": cancellation(5),
                "fight_id": None,
                "notify_account_id": target[0],
            }
        if row["expires_at"] <= store.now():
            db.execute(
                "UPDATE friendly_duel_invitations SET status='expired',responded_at=%s "
                "WHERE id=%s",
                (store.now(), row["id"]),
            )
            return {"accepted": False, "packet": cancellation(5), "fight_id": None}
        if not request["accepted"]:
            db.execute(
                "UPDATE friendly_duel_invitations SET status='rejected',responded_at=%s "
                "WHERE id=%s",
                (store.now(), row["id"]),
            )
            return {
                "accepted": False,
                "packet": cancellation(1),
                "fight_id": None,
                "invitation_id": row["id"],
                "notify_account_id": a[0],
                "notify_character_id": a[1],
                "notify_generation": a[2],
            }
        if not callable(prepare_duel):
            raise ValueError("Accepted duel requires a runtime preparation callback")
        if (
            source["map_id"] != row["map_id"]
            or source.get("instance_id", 0) != row["instance_id"]
            or recipient["map_id"] != row["map_id"]
            or recipient.get("instance_id", 0) != row["instance_id"]
            or any(
                character[key] != row[f"{prefix}_{key}"]
                for character, prefix in ((source, "challenger"), (recipient, "target"))
                for key in ("x", "y", "z")
            )
        ):
            db.execute(
                "UPDATE friendly_duel_invitations SET status='cancelled',responded_at=%s "
                "WHERE id=%s",
                (store.now(), row["id"]),
            )
            return {
                "accepted": False,
                "packet": cancellation(6),
                "fight_id": None,
                "notify_account_id": a[0],
            }
        fight_id = db.execute(
            "INSERT INTO combat_fights(status,fight_kind) VALUES('placement','duel') RETURNING id"
        ).fetchone()["id"]
        from .fight_store import _health_baseline

        for identity, team in ((a, 0), (b, 1)):
            baseline = _health_baseline(db, identity[0], identity[1])
            db.execute(
                "INSERT INTO combat_fight_participants "
                "(fight_id,character_id,account_id,team,session_generation,"
                "entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (fight_id, identity[1], identity[0], team, identity[2], *baseline),
            )
        db.execute(
            "UPDATE friendly_duel_invitations SET status='accepted',fight_id=%s,responded_at=%s "
            "WHERE id=%s",
            (fight_id, store.now(), row["id"]),
        )
        prepared, rollback = prepare_duel(db, fight_id, row, source, recipient)
        if not callable(rollback):
            raise ValueError("Duel runtime preparation must provide rollback")
        return {
            "accepted": True,
            "fight_id": fight_id,
            "invitation_id": row["id"],
            "challenger": source,
            "target": recipient,
            "auto_lock": request["auto_lock"],
            "notify_account_id": a[0],
            "prepared": prepared,
            "rollback": rollback,
        }


def answer_challenge(store, target_session, request_body, *, prepare_duel=None):
    """Wrap SQL commit so a pre-registered in-memory fight can be undone."""
    rollback_callbacks = []

    def prepare(*args):
        if not callable(prepare_duel):
            raise ValueError("Accepted duel requires a runtime preparation callback")
        result = prepare_duel(*args)
        if not isinstance(result, tuple) or len(result) != 2 or not callable(result[1]):
            raise ValueError("Duel runtime preparation must provide rollback")
        rollback_callbacks.append(result[1])
        return result

    try:
        result = _answer_challenge_inner(
            store,
            target_session,
            request_body,
            prepare_duel=prepare if prepare_duel is not None else None,
        )
    except Exception:
        for rollback in reversed(rollback_callbacks):
            rollback()
        raise
    result.pop("rollback", None)
    return result


def expire(store, *, limit=128):
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("Invalid duel invitation expiry batch")
    with store.connection() as db:
        rows = db.execute(
            "WITH expired AS (SELECT id FROM friendly_duel_invitations "
            "WHERE status='pending' AND expires_at<=%s ORDER BY expires_at,id "
            "FOR UPDATE SKIP LOCKED LIMIT %s) "
            "UPDATE friendly_duel_invitations i SET status='expired',responded_at=%s "
            "FROM expired e WHERE i.id=e.id RETURNING i.id",
            (store.now(), limit, store.now()),
        ).fetchall()
        return tuple(row["id"] for row in rows)


def cancel_undelivered_invitation(store, account_id, character_id, invitation_id):
    """Release a pending invite when native delivery to its captured lease fails."""
    if any(
        type(value) is not int or value <= 0
        for value in (account_id, character_id, invitation_id)
    ):
        raise ValueError("Invalid duel invitation cancellation identity")
    with store.connection() as db:
        return (
            db.execute(
                "UPDATE friendly_duel_invitations SET status='cancelled',responded_at=%s "
                "WHERE id=%s AND challenger_account_id=%s AND challenger_character_id=%s "
                "AND status='pending'",
                (store.now(), invitation_id, account_id, character_id),
            ).rowcount
            == 1
        )


def settle(
    store,
    account_id,
    generation,
    character_id,
    fight,
    *,
    reason="defeat",
    disconnected_character_id=None,
):
    """Restore both duelists to full effective HP without rewards or teleport."""
    if reason not in ("defeat", "disconnect"):
        raise ValueError("Invalid friendly duel result reason")
    if reason == "disconnect":
        if type(disconnected_character_id) is not int or disconnected_character_id <= 0:
            raise ValueError("Disconnect settlement requires the disconnected owner")
    elif disconnected_character_id is not None:
        raise ValueError("Defeat settlement cannot name a disconnected owner")
    if getattr(fight, "phase", None) != "finished" or getattr(
        fight, "winner", None
    ) not in (0, 1):
        raise ValueError("Friendly duel must have a winner before settlement")
    from .fight_store import settle_shared

    def apply(db, members, candidate):
        prior_outcome = db.execute(
            "SELECT winner_character_id,loser_character_id,reason "
            "FROM friendly_duel_outcomes WHERE fight_id=%s FOR UPDATE",
            (candidate.id,),
        ).fetchone()
        if prior_outcome is not None:
            return {
                "fight_id": candidate.id,
                "outcome": dict(prior_outcome),
                "positions": {},
                "replayed": True,
            }
        duel = db.execute(
            "SELECT i.id,i.challenger_character_id,i.target_character_id,i.map_id,i.instance_id,"
            "i.challenger_x,i.challenger_y,i.challenger_z,i.target_x,i.target_y,i.target_z "
            "FROM friendly_duel_invitations i JOIN combat_fights f ON f.id=i.fight_id "
            "WHERE i.fight_id=%s AND i.status='accepted' AND f.fight_kind='duel' "
            "FOR UPDATE OF i,f",
            (candidate.id,),
        ).fetchone()
        if duel is None or len(members) != 2:
            raise ValueError("Fight is not a complete friendly duel")
        if {row["character_id"] for row in members} != {
            duel["challenger_character_id"],
            duel["target_character_id"],
        }:
            raise ValueError("Friendly duel roster differs from its consent")
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health_policy import visible

        actors = {
            actor.id: actor for actor in candidate.actors.values() if actor.controlled
        }
        if set(actors) != {row["character_id"] for row in members}:
            raise ValueError("Friendly duel runtime roster is incomplete")
        winner = next(
            actor.id for actor in actors.values() if actor.team == candidate.winner
        )
        loser = next(
            actor.id for actor in actors.values() if actor.team != candidate.winner
        )
        if reason == "disconnect" and disconnected_character_id != loser:
            raise ValueError("Disconnected duelist must be the losing owner")
        positions = {}
        for member in members:
            owner, actor_id = member["account_id"], member["character_id"]
            if db.execute(
                "SELECT 1 FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                (candidate.id, actor_id),
            ).fetchone():
                raise ValueError("Friendly duel already has a conflicting health exit")
            character = store.character(owner, actor_id, db)
            effective = effective_character(character)
            maximum = effective["max_hp"]
            prefix = (
                "challenger"
                if actor_id == duel["challenger_character_id"]
                else "target"
            )
            original_position = (
                duel["map_id"],
                duel["instance_id"],
                duel[f"{prefix}_x"],
                duel[f"{prefix}_y"],
                duel[f"{prefix}_z"],
            )
            # A duel loss is presentation/state only. Restore the captured
            # exterior tile and full effective health; never retain fight cells.
            db.execute(
                "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=0,health_dead=false,"
                "map_id=%s,instance_id=%s,x=%s,y=%s,z=%s "
                "WHERE id=%s AND account_id=%s",
                (maximum, maximum, *original_position, actor_id, owner),
            )
            now = store.now()
            db.execute(
                "INSERT INTO character_regeneration(character_id,initial_hp,initial_damage,started_at,coefficient,last_at) "
                "VALUES(%s,%s,0,%s,1,%s) ON CONFLICT(character_id) DO UPDATE SET "
                "initial_hp=excluded.initial_hp,initial_damage=0,started_at=excluded.started_at,"
                "coefficient=excluded.coefficient,last_at=excluded.last_at",
                (actor_id, maximum, now, now),
            )
            saved = store.character(owner, actor_id, db)
            positions[actor_id] = tuple(
                saved[key] for key in ("map_id", "instance_id", "x", "y", "z")
            )
            db.execute(
                "INSERT INTO fight_health_exits(fight_id,character_id,generation,reason,created_at) "
                "VALUES(%s,%s,%s,'return',%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
                (candidate.id, actor_id, member["session_generation"], now),
            )
        db.execute(
            "INSERT INTO friendly_duel_outcomes(fight_id,invitation_id,winner_character_id,loser_character_id,reason,settled_at) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(fight_id) DO NOTHING",
            (candidate.id, duel["id"], winner, loser, reason, store.now()),
        )
        outcome = db.execute(
            "SELECT winner_character_id,loser_character_id,reason "
            "FROM friendly_duel_outcomes WHERE fight_id=%s",
            (candidate.id,),
        ).fetchone()
        if (
            outcome["winner_character_id"] != winner
            or outcome["loser_character_id"] != loser
        ):
            raise ValueError("Conflicting friendly duel result replay")
        # Deliberately no fight_rewards, kamas, drop, or ecology writes here.
        return {
            "fight_id": candidate.id,
            "outcome": dict(outcome),
            "positions": positions,
            "replayed": False,
        }

    return settle_shared(store, account_id, generation, character_id, fight, apply)


def return_packets(
    store, account_id, generation, character_id, fight, body, *, wp=None
):
    """Publish the already-committed full-health duel exit after native12925."""
    from .combat_results import continuation
    from wakfu_server.health import packet as health_packet
    from wakfu_server.wire import account_kamas
    import struct

    if fight.phase != "finished" or character_id not in fight.actors:
        raise ValueError("Friendly duel is not ready to return")
    continuation(fight.id, body)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        outcome = db.execute(
            "SELECT 1 FROM friendly_duel_outcomes WHERE fight_id=%s",
            (fight.id,),
        ).fetchone()
        exit_row = db.execute(
            "SELECT reason,return_acknowledged_at FROM fight_health_exits "
            "WHERE fight_id=%s AND character_id=%s",
            (fight.id, character_id),
        ).fetchone()
        if outcome is None or exit_row is None or exit_row["reason"] != "return":
            raise ValueError("Duel health settlement is not committed")
        # The native 12925 request proves the client consumed its result and
        # cleaned up the fight UI. Persist that acknowledgement separately from
        # the earlier HP reset so a disconnect before 12925 can replay results.
        db.execute(
            "UPDATE fight_health_exits SET return_acknowledged_at="
            "COALESCE(return_acknowledged_at,%s) "
            "WHERE fight_id=%s AND character_id=%s AND reason='return'",
            (store.now(), fight.id, character_id),
        )
        member = db.execute(
            "SELECT account_id FROM combat_fight_participants "
            "WHERE fight_id=%s AND character_id=%s",
            (fight.id, character_id),
        ).fetchone()
        if member is None or member["account_id"] != account_id:
            raise ValueError("Duel return actor is not owned by this account")
        saved = store.character(account_id, character_id, db)
    from .combat_lifecycle import outside_progression as duel_progression

    return {
        "character": saved,
        "applied": True,
        "packets": [
            duel_progression(saved, wp=wp),
            (12436, health_packet(saved["id"], saved["hp"], 0)),
            (13021, struct.pack(">q", saved["kamas"])),
            (13873, account_kamas(saved["kamas"])),
        ],
    }
