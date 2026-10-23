-- Original placements and explicitly custom content are separate from receipts.
CREATE TABLE account_treasure_claims (
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    content_id TEXT NOT NULL,
    character_id BIGINT NOT NULL REFERENCES characters(id),
    rule_sha256 TEXT NOT NULL CHECK(length(rule_sha256)=64),
    rewards JSONB NOT NULL CHECK(jsonb_typeof(rewards)='array'),
    claimed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(account_id,content_id)
);
