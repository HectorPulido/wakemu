-- Local DEV policy: one account-owned 100-slot chest. Capacity 100 is observed
-- in the official current-client capture, not a claim about default unlocks.
CREATE TABLE account_haven_chests (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    compartment_id uuid NOT NULL UNIQUE,
    capacity smallint NOT NULL DEFAULT 100 CHECK(capacity BETWEEN 1 AND 32767),
    revision bigint NOT NULL DEFAULT 0 CHECK(revision >= 0),
    items jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(items)='array')
);
-- Native chest transfer messages have no transaction nonce. Retain receipts
-- per server-created opening token, rather than trusting optimistic client UI.
CREATE TABLE account_haven_chest_receipts (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    generation text NOT NULL,
    opening_token uuid NOT NULL,
    request_hash bytea NOT NULL CHECK(octet_length(request_hash)=32),
    revision bigint NOT NULL CHECK(revision >= 0),
    completed_at timestamptz NOT NULL,
    PRIMARY KEY(account_id,generation,opening_token,request_hash)
);
