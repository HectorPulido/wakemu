-- Local, versioned policy for the 13787 identification adapter.  The installed
-- client's fpK helper is evidence for weights, not proof of the original
-- server's call path or economic policy.  cost_kamas=0 is an explicit local
-- choice authorized for this experiment, not an upstream claim.
INSERT INTO settings(name,value) VALUES (
    'socket_identification_policy',
    '{"version":1,"count_weights":{"0":30,"1":67,"2":38,"3":15},"color_weights":{"1":100,"2":100,"3":100,"4":32},"cost_kamas":0,"charge":0,"minimum_level":"item_level","source":"local_policy_native_fpK_utility"}'::jsonb
) ON CONFLICT(name) DO NOTHING;

-- Retrying a completed request returns the same generated ProtoShard. The
-- receipt intentionally survives item deletion so a delayed retry cannot
-- create a second identified item or spend currency again.
CREATE TABLE inventory_socket_identification_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL,
    uid bigint NOT NULL CHECK (uid > 0),
    reference integer NOT NULL CHECK (reference > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    policy_hash bytea NOT NULL CHECK (octet_length(policy_hash)=32),
    shard_state bytea NOT NULL CHECK (octet_length(shard_state) BETWEEN 1 AND 65536),
    cost_kamas bigint NOT NULL CHECK (cost_kamas >= 0),
    applied_at timestamptz NOT NULL,
    FOREIGN KEY (account_id,character_id) REFERENCES characters(account_id,id),
    UNIQUE (account_id,character_id,uid)
);
