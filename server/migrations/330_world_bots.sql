-- Dedicated identities for externally controlled native characters.
CREATE TABLE IF NOT EXISTS world_bots (
    bot_id text PRIMARY KEY,
    account_id bigint NOT NULL UNIQUE REFERENCES accounts(id),
    character_id bigint NOT NULL UNIQUE REFERENCES characters(id),
    capabilities jsonb NOT NULL,
    creation_config jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (jsonb_typeof(capabilities) = 'array')
);
