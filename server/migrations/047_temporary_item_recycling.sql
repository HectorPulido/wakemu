-- Idempotent recycle outcomes for cxf/13447 requests. Temporary source rows
-- are removed on success, so the exact request and result must outlive them.
CREATE TABLE temporary_item_recycling_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL,
    request_hash bytea NOT NULL CHECK (octet_length(request_hash)=32),
    request_body bytea NOT NULL CHECK (octet_length(request_body)>=10),
    request_uids jsonb NOT NULL CHECK (jsonb_typeof(request_uids)='array'),
    recovered_resources integer NOT NULL CHECK (recovered_resources BETWEEN 0 AND 2147483647),
    destroyed_items integer NOT NULL CHECK (destroyed_items BETWEEN 0 AND 2147483647),
    products jsonb NOT NULL CHECK (jsonb_typeof(products)='object'),
    rounding_draws jsonb NOT NULL CHECK (jsonb_typeof(rounding_draws)='object'),
    applied_at timestamptz NOT NULL,
    FOREIGN KEY (account_id,character_id) REFERENCES characters(account_id,id),
    UNIQUE (account_id,character_id,request_hash)
);
