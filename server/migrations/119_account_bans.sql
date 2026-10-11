-- Active account sanctions; history remains in the administration audit log.
CREATE TABLE account_bans (
    account_id bigint PRIMARY KEY REFERENCES accounts(id),
    reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 1000),
    operator text NOT NULL CHECK (length(trim(operator)) > 0),
    banned_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamptz,
    CHECK (expires_at IS NULL OR expires_at > banned_at)
);
