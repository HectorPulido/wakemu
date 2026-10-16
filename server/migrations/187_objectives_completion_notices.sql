-- Only future completions create notices; historical points are not replayed.
CREATE TABLE objectives_completion_notices (
 id bigserial PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 source_key text NOT NULL CHECK(length(source_key) BETWEEN 1 AND 512),
 title text NOT NULL CHECK(length(title) BETWEEN 1 AND 256),
 points integer NOT NULL CHECK(points BETWEEN 0 AND 1000000),
 occurred_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 delivered_at timestamptz,
 delivered_character_id bigint REFERENCES characters(id) ON DELETE SET NULL,
 UNIQUE(account_id,source_key)
);
CREATE INDEX objectives_completion_notices_pending
ON objectives_completion_notices(account_id,id) WHERE delivered_at IS NULL;
