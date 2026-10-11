"""Durable account access sanctions, serialized against session/token creation."""
from datetime import datetime, timezone


def require_access(db, account_id, now):
    """Serialize access changes without blocking child-row foreign keys.

    Active gameplay holds its session lease while adding account-owned rows.
    KEY SHARE from those foreign keys must coexist with the account guard,
    otherwise a ban waiting to delete that lease can deadlock against gameplay.
    """
    account = db.execute(
        "SELECT id FROM accounts WHERE id=%s FOR NO KEY UPDATE", (account_id,)
    ).fetchone()
    if account is None:
        raise ValueError("Invalid account")
    ban = db.execute(
        "SELECT 1 FROM account_bans WHERE account_id=%s "
        "AND (expires_at IS NULL OR expires_at>%s)",
        (account_id, now),
    ).fetchone()
    if ban:
        raise ValueError("Account banned")


class AccountBans:
    def ban_account(self, account_id, data, operator):
        if not isinstance(data, dict) or set(data) - {"reason", "expires_at"}:
            raise ValueError("Unsupported ban field")
        reason = self.text(data.get("reason"), "reason", maximum=1000)
        expires = data.get("expires_at")
        now = self.store.now()
        if expires is not None:
            if not isinstance(expires, str):
                raise ValueError("Invalid ban expiry")
            try:
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Invalid ban expiry") from None
            if expires.tzinfo is None or expires <= now:
                raise ValueError("Ban expiry must be a future timestamp with timezone")
            expires = expires.astimezone(timezone.utc)
        with self.store.connection() as db:
            if not db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR NO KEY UPDATE", (account_id,)
            ).fetchone():
                raise LookupError("Account not found")
            previous = db.execute(
                "SELECT * FROM account_bans WHERE account_id=%s", (account_id,)
            ).fetchone()
            db.execute(
                "INSERT INTO account_bans(account_id,reason,operator,banned_at,expires_at) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET reason=excluded.reason,operator=excluded.operator,"
                "banned_at=excluded.banned_at,expires_at=excluded.expires_at",
                (account_id, reason, operator, now, expires),
            )
            db.execute("DELETE FROM tokens WHERE account_id=%s", (account_id,))
            db.execute("DELETE FROM sessions WHERE account_id=%s", (account_id,))

            def safe(row):
                return {
                    k: v.isoformat() if isinstance(v, datetime) else v
                    for k, v in row.items()
                }

            self._audit(
                db,
                operator,
                "account.ban",
                account_id,
                safe(previous) if previous else None,
                dict(
                    reason=reason, expires_at=expires.isoformat() if expires else None
                ),
            )
        return self.account(account_id)

    def unban_account(self, account_id, data, operator):
        if not isinstance(data, dict) or set(data) - {"reason"}:
            raise ValueError("Unsupported unban field")
        reason = self.text(data.get("reason"), "reason", maximum=1000)
        with self.store.connection() as db:
            if not db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR NO KEY UPDATE", (account_id,)
            ).fetchone():
                raise LookupError("Account not found")
            previous = db.execute(
                "DELETE FROM account_bans WHERE account_id=%s RETURNING reason",
                (account_id,),
            ).fetchone()
            self._audit(
                db,
                operator,
                "account.unban",
                account_id,
                dict(previous) if previous else None,
                dict(reason=reason),
            )
        return self.account(account_id)
