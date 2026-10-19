"""Durable allowlisted player intent; only World executes game mutations."""
import re
import uuid
from psycopg.types.json import Jsonb
from . import player_auth
from .repository import ConflictError


def allowed_actions(db, identity):
    identity = player_auth.resolve_account(db, identity)
    character = db.execute(
        "SELECT level,map_id,instance_id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (identity["character_id"], identity["account_id"]),
    ).fetchone()
    if character is None:
        raise player_auth.Unauthorized("Character unavailable")
    connected = player_auth.live_identity(db, identity) is not None
    from .challenges import current_run

    run = current_run(db, identity["account_id"], identity["character_id"])
    fighting = (
        db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=%s AND f.status IN ('placement','active') AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) LIMIT 1",
            (identity["character_id"],),
        ).fetchone()
        is not None
    )
    actions = []
    if run:
        action = "abandon" if run["status"] in ("available", "fighting") else "return"
        actions.append(
            dict(
                key="weekly." + action,
                label="Leave weekly challenge"
                if action == "abandon"
                else "Return from weekly challenge",
                kind="weekly",
                enabled=True,
                target=dict(kind="weekly", action=action),
            )
        )
    # Destinations are resolved exclusively from the published native catalogue.
    from .player_travel import actions as travel_actions

    for entry in travel_actions(db, identity):
        actions.append(
            dict(
                key=entry["action_key"],
                label=entry["label"],
                kind="travel",
                enabled=True,
                definition_key=entry.get("objective_key"),
                cost_kamas=entry.get("cost_kamas", 0),
                target=dict(
                    kind="travel",
                    destination=entry["target"],
                    cost_kamas=entry["cost_kamas"],
                ),
            )
        )
    from . import seasonal_entry

    actions.extend(seasonal_entry.actions(db, identity))
    from . import pvp

    actions.extend(pvp.actions(db, identity))
    for action in actions:
        if not connected:
            action.update(
                enabled=False,
                reason="Connect this character in World to use game actions",
            )
        elif fighting:
            action.update(
                enabled=False,
                reason="Finish your current combat before changing locations",
            )
        elif character["instance_id"] != 0 and (
            action["kind"] in ("travel", "pvp", "seasonal_entry")
            or action["key"] == "weekly.enter"
        ):
            action.update(
                enabled=False, reason="Leave your current private instance first"
            )
    return actions


def public_action(action):
    return {key: value for key, value in action.items() if key != "target"}


def _public_receipt(row):
    return {
        key: row[key]
        for key in (
            "id",
            "action_key",
            "status",
            "result",
            "created_at",
            "completed_at",
        )
    }


def enqueue(db, identity, action_key, request_id):
    if type(action_key) is not str or not 1 <= len(action_key) <= 256:
        raise ValueError("Invalid action key")
    if type(request_id) is not str or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", request_id
    ):
        raise ValueError("Invalid request identity")
    # The action FK must follow the same account-before-session order as
    # earned reward delivery. Ordinary lease reads do not acquire this lock.
    player_auth.lock_account_reference(db, identity)
    current = player_auth.live_identity(db, identity, lock=True)
    if current is None:
        raise ConflictError("Connect this character in World to use game actions")
    identity = dict(
        identity, character_id=current["character_id"], generation=current["generation"]
    )
    prior = db.execute(
        "SELECT * FROM objectives_player_actions WHERE account_id=%s AND request_id=%s ORDER BY created_at,id LIMIT 1",
        (identity["account_id"], request_id),
    ).fetchone()
    if prior:
        if prior["action_key"] != action_key:
            raise ConflictError("Request identity already belongs to another action")
        return _public_receipt(prior)
    action = next(
        (
            a
            for a in allowed_actions(db, identity)
            if a["key"] == action_key and a["enabled"]
        ),
        None,
    )
    if action is None:
        raise ValueError("Action is unavailable")
    pending = db.execute(
        "SELECT count(*) AS n FROM objectives_player_actions WHERE account_id=%s AND generation=%s AND status IN ('pending','running') AND expires_at>CURRENT_TIMESTAMP",
        (identity["account_id"], identity["generation"]),
    ).fetchone()
    if pending["n"] >= 3:
        raise ConflictError("A game action is already pending; wait for World")
    row = db.execute(
        "INSERT INTO objectives_player_actions(id,account_id,character_id,generation,request_id,action_key,target) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            uuid.uuid4(),
            identity["account_id"],
            identity["character_id"],
            identity["generation"],
            request_id,
            action_key,
            Jsonb(action["target"]),
        ),
    ).fetchone()
    db.execute(
        "SELECT pg_notify('wakemu_objectives_updates',%s)",
        (str(identity["character_id"]),),
    )
    return _public_receipt(row)


def receipt(db, identity, action_id):
    try:
        action_id = uuid.UUID(action_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid action receipt identity") from exc
    player_auth.resolve_account(db, identity)
    db.execute(
        "UPDATE objectives_player_actions SET status='rejected',result=%s,completed_at=CURRENT_TIMESTAMP WHERE id=%s AND account_id=%s AND status IN ('pending','running') AND expires_at<CURRENT_TIMESTAMP",
        (
            Jsonb(
                {
                    "error": "Action outcome could not be confirmed; refresh before retrying"
                }
            ),
            action_id,
            identity["account_id"],
        ),
    )
    row = db.execute(
        "SELECT * FROM objectives_player_actions WHERE id=%s AND account_id=%s",
        (action_id, identity["account_id"]),
    ).fetchone()
    return _public_receipt(row) if row else None
