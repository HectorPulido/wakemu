-- Native intergame tokens are single-use and fenced to the live game session.
CREATE TABLE intergame_tokens (
    digest text PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    generation text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX intergame_tokens_expiry ON intergame_tokens(expires_at);

CREATE TABLE intergame_friend_invites (
    inviter_account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    recipient_account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(inviter_account_id, recipient_account_id),
    CHECK(inviter_account_id <> recipient_account_id)
);

CREATE TABLE intergame_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_account_id bigint NOT NULL REFERENCES accounts(id),
    recipient_account_id bigint NOT NULL REFERENCES accounts(id),
    content text NOT NULL CHECK(octet_length(content) BETWEEN 1 AND 2048),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(sender_account_id <> recipient_account_id)
);
CREATE INDEX intergame_messages_conversation
    ON intergame_messages(LEAST(sender_account_id,recipient_account_id),
                         GREATEST(sender_account_id,recipient_account_id),id DESC);

CREATE TABLE intergame_account_state (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    status smallint NOT NULL DEFAULT 0 CHECK(status BETWEEN 0 AND 2)
);
