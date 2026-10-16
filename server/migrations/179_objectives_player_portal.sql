-- Player credentials are isolated from service/operator credentials.
CREATE TABLE objectives_player_tokens (
 digest text PRIMARY KEY CHECK(length(digest)=64),
 kind text NOT NULL CHECK(kind IN ('launch','session')),
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 generation text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE INDEX objectives_player_tokens_expiry ON objectives_player_tokens(expires_at);
CREATE TABLE objectives_player_actions (
 id uuid PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 generation text NOT NULL,
 request_id text NOT NULL CHECK(length(request_id) BETWEEN 1 AND 128),
 action_key text NOT NULL CHECK(length(action_key) BETWEEN 1 AND 256),
 target jsonb NOT NULL CHECK(jsonb_typeof(target)='object'),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','rejected')),
 result jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP + INTERVAL '30 seconds',
 completed_at timestamptz,
 UNIQUE(account_id,generation,request_id),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE INDEX objectives_player_actions_pending ON objectives_player_actions(created_at) WHERE status='pending';
UPDATE settings SET value=(SELECT jsonb_agg(command ORDER BY command) FROM (SELECT DISTINCT command FROM jsonb_array_elements_text(value || '["!adventures"]'::jsonb) AS entries(command)) commands) WHERE name='player_allowed_commands';
