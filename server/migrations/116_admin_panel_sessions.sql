-- Browser cookies contain opaque random tokens; only their hashes are persisted.
CREATE TABLE admin_panel_sessions (
    token_sha256 char(64) PRIMARY KEY CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
    username text NOT NULL,
    csrf_token text NOT NULL,
    credential_revision char(64) NOT NULL CHECK (credential_revision ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamptz NOT NULL
);
CREATE INDEX admin_panel_sessions_expiry ON admin_panel_sessions(expires_at);
CREATE INDEX admin_panel_sessions_username ON admin_panel_sessions(username);
