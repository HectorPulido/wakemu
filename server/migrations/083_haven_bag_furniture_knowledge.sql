CREATE TABLE account_furniture_knowledge (
    account_id bigint NOT NULL REFERENCES accounts(id),
    item_ref integer NOT NULL CHECK (item_ref > 0),
    learned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, item_ref)
);

CREATE TABLE furniture_learning_receipts (
    account_id bigint NOT NULL REFERENCES accounts(id),
    source_uid bigint NOT NULL CHECK (source_uid > 0),
    character_id bigint NOT NULL REFERENCES characters(id),
    source_ref integer NOT NULL CHECK (source_ref > 0),
    action_id integer NOT NULL CHECK (action_id > 0),
    learned_refs integer[] NOT NULL CHECK (cardinality(learned_refs) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, source_uid)
);
