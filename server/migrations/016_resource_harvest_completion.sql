-- Local emulator policy: one primary product; no inferred rare/bonus drops.
INSERT INTO settings(name,value) VALUES
    ('resource_harvest_rewards', '{"version":1,"product_quantity":1,"stage_policy":"catalog_cvF"}'::jsonb);

-- Keep successful identity after a harvested resource has been removed.
CREATE TABLE resource_harvest_receipts (
    token text PRIMARY KEY CHECK (length(token) BETWEEN 1 AND 128),
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL,
    resource_uid bigint NOT NULL,
    action_id integer NOT NULL CHECK (action_id > 0),
    result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
    completed_at timestamptz NOT NULL,
    FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
