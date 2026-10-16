"""Reusable account-scoped embed links; World selects the active character."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone


class Unauthorized(ValueError):
    pass


def digest(token):
    if type(token) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise Unauthorized("Invalid player credential")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def validate_owner(db, identity):
    row = db.execute(
        "SELECT account_id,id AS character_id FROM characters WHERE account_id=%s AND id=%s AND deleted_at IS NULL",
        (identity["account_id"], identity["character_id"]),
    ).fetchone()
    if row is None:
        raise Unauthorized("Character unavailable or foreign")
    return dict(row)


def live_identity(db, identity, *, lock=False):
    """Resolve the current selected lease, without trusting an old link generation."""
    return db.execute(
        "SELECT s.account_id,s.character_id,s.generation,s.expires_at "
        "FROM sessions s JOIN characters c ON c.id=s.character_id AND c.account_id=s.account_id "
        "WHERE s.account_id=%s "
        "AND s.expires_at>CURRENT_TIMESTAMP AND c.deleted_at IS NULL"
        + (" FOR UPDATE OF s" if lock else ""),
        (identity["account_id"],),
    ).fetchone()


def resolve_account(db, identity, *, lock=False):
    """The token names an account; the live lease names its current game actor."""
    current = live_identity(db, identity, lock=lock)
    if current:
        return dict(
            account_id=identity["account_id"],
            character_id=current["character_id"],
            generation=current["generation"],
            expires_at=identity.get("expires_at"),
        )
    fallback = db.execute(
        "SELECT id FROM characters WHERE account_id=%s AND deleted_at IS NULL "
        "ORDER BY (id=%s) DESC,id LIMIT 1",
        (identity["account_id"], identity.get("character_id")),
    ).fetchone()
    if fallback is None:
        raise Unauthorized("No character is available on this account")
    return dict(
        account_id=identity["account_id"],
        character_id=fallback["id"],
        generation=None,
        expires_at=identity.get("expires_at"),
    )


def validate_identity(db, identity, *, lock=False):
    row = live_identity(db, identity, lock=lock)
    if (
        row is None
        or row["generation"] != identity.get("generation")
        or row["character_id"] != identity.get("character_id")
    ):
        raise Unauthorized("Connect this character in World to use game actions")
    return dict(row)


def issue_embed(db, account_id, character_id):
    validate_owner(db, dict(account_id=account_id, character_id=character_id))
    token = secrets.token_urlsafe(32)
    db.execute(
        "DELETE FROM objectives_player_tokens WHERE expires_at<CURRENT_TIMESTAMP"
    )
    db.execute(
        "INSERT INTO objectives_player_tokens(digest,kind,account_id,character_id,generation,expires_at) VALUES(%s,'embed',%s,%s,'',CURRENT_TIMESTAMP+INTERVAL '30 days')",
        (digest(token), account_id, character_id),
    )
    return token


def issue_launch(db, account_id, character_id, generation):
    # In-game issuance still comes from the actual connected selected character.
    validate_identity(
        db,
        dict(account_id=account_id, character_id=character_id, generation=generation),
        lock=True,
    )
    return issue_embed(db, account_id, character_id)


def exchange_launch(db, token):
    token_digest = digest(token)
    candidate = db.execute(
        "SELECT * FROM objectives_player_tokens WHERE digest=%s AND kind IN ('launch','embed') AND expires_at>CURRENT_TIMESTAMP",
        (token_digest,),
    ).fetchone()
    if candidate is None:
        raise Unauthorized("Player link is invalid or expired")
    identity = resolve_account(db, candidate)
    if candidate["kind"] == "launch":
        # Retain compatibility for already issued legacy one-use launch links.
        validate_identity(db, candidate, lock=True)
        consumed = db.execute(
            "UPDATE objectives_player_tokens SET consumed_at=CURRENT_TIMESTAMP WHERE digest=%s AND kind='launch' AND consumed_at IS NULL AND expires_at>CURRENT_TIMESTAMP RETURNING digest",
            (token_digest,),
        ).fetchone()
        if consumed is None:
            raise Unauthorized("Launch link is invalid, expired or already used")
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        generation = candidate["generation"]
    else:
        expires = candidate["expires_at"]
        generation = ""
    bearer = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO objectives_player_tokens(digest,kind,account_id,character_id,generation,expires_at) VALUES(%s,'session',%s,%s,%s,%s)",
        (
            digest(bearer),
            candidate["account_id"],
            candidate["character_id"],
            generation,
            expires,
        ),
    )
    return dict(token=bearer, expires_at=expires, character_id=identity["character_id"])


def authenticate(db, bearer):
    row = db.execute(
        "SELECT account_id,character_id,generation,expires_at FROM objectives_player_tokens WHERE digest=%s AND kind='session' AND expires_at>CURRENT_TIMESTAMP",
        (digest(bearer),),
    ).fetchone()
    if row is None:
        raise Unauthorized("Player session expired")
    if row["generation"]:
        # Existing legacy sessions keep their original narrow lease semantics.
        validate_identity(db, row)
        return dict(row)
    return resolve_account(db, row)
