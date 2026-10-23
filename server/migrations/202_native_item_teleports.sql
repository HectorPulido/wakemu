-- Item consumption and full relocation commit together; delivery is retryable.
CREATE TABLE item_teleport_receipts (
    token text PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id),
    generation text NOT NULL,
    character_id bigint NOT NULL REFERENCES characters(id),
    source_item_uid bigint NOT NULL CHECK (source_item_uid > 0),
    source_item_ref integer NOT NULL CHECK (source_item_ref > 0),
    action_id integer NOT NULL CHECK (action_id > 0),
    source jsonb NOT NULL,
    destination jsonb NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    delivered_at timestamptz
);
CREATE UNIQUE INDEX item_teleport_one_pending
    ON item_teleport_receipts(account_id,generation,character_id)
    WHERE delivered_at IS NULL;
