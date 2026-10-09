CREATE TABLE IF NOT EXISTS account_cosmetics (
    account_id bigint PRIMARY KEY REFERENCES accounts(id),
    record jsonb NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0)
);
