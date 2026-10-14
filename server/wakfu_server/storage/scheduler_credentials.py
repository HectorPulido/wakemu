"""Provision and renew the scheduler's scoped SQL-backed service credential."""
import hashlib
import hmac
import secrets
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from psycopg.types.json import Jsonb
from wakfu_server.account_bans import require_access

SETTING = "scheduler_service_credential"
LOCK = 5790545582
LIFETIME = timedelta(days=365)
RENEW_BEFORE = timedelta(days=7)


def provision(database, token_file, *, bootstrap=False):
    """Never replace a deployed secret, reactivate a disabled principal or undo revocation."""
    path = Path(token_file)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 1024:
        raise ValueError("Scheduler credential must be a private regular file")
    token = path.read_text().strip()
    if not 32 <= len(token) <= 512:
        raise ValueError("Invalid scheduler service credential")
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
        ).fetchone()
        created = row is None
        new_credential = False
        if created:
            if not bootstrap:
                raise ValueError("Scheduler credential registration is missing")
            existing = db.execute(
                "SELECT account_id,kind FROM tokens WHERE digest=%s", (digest,)
            ).fetchone()
            if existing is not None:
                if existing["kind"] != "scheduler":
                    raise ValueError("Scheduler credential has a different scope")
                account_id = existing["account_id"]
            else:
                new_credential = True
                # No interactive password is issued. A random hash has no known
                # password preimage; the account receives no administrative role.
                username = "svc_cron_" + secrets.token_hex(8)
                account_id = db.execute(
                    "INSERT INTO accounts(username,username_key,salt,password_hash,created_at) "
                    "VALUES(%s,%s,%s,%s,%s) RETURNING id",
                    (
                        username,
                        username,
                        secrets.token_bytes(16),
                        secrets.token_bytes(64),
                        now,
                    ),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO account_wallets(account_id) VALUES(%s)", (account_id,)
                )
            state = dict(
                schema_version=1, digest=digest, account_id=account_id, enabled=True
            )
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s)",
                (SETTING, Jsonb(state)),
            )
        else:
            state = row["value"]
        if (
            not isinstance(state, dict)
            or state.get("schema_version") != 1
            or type(state.get("account_id")) is not int
            or state.get("enabled") is not True
            or not isinstance(state.get("digest"), str)
            or not hmac.compare_digest(state["digest"], digest)
        ):
            raise ValueError(
                "Scheduler credential is disabled or differs from its SQL registration"
            )
        require_access(db, state["account_id"], now)
        credential = db.execute(
            "SELECT account_id,kind,expires_at FROM tokens WHERE digest=%s FOR UPDATE",
            (digest,),
        ).fetchone()
        if credential is None:
            if not new_credential:
                raise ValueError(
                    "Scheduler credential was revoked; operator action required"
                )
            db.execute(
                "INSERT INTO tokens(digest,account_id,kind,expires_at) VALUES(%s,%s,%s,%s)",
                (digest, state["account_id"], "scheduler", now + LIFETIME),
            )
            renewed = True
        else:
            if (
                credential["kind"] != "scheduler"
                or credential["account_id"] != state["account_id"]
            ):
                raise ValueError("Scheduler credential ownership differs")
            renewed = credential["expires_at"] <= now + RENEW_BEFORE
            if renewed:
                db.execute(
                    "UPDATE tokens SET expires_at=%s WHERE digest=%s",
                    (now + LIFETIME, digest),
                )
        return dict(created=created, renewed=renewed)
