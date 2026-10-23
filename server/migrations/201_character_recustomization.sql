-- Identity-preserving native dressing-room entitlements and replay receipts.
CREATE TABLE character_recustomization_receipts (
    account_id bigint NOT NULL REFERENCES accounts(id),
    source_uid bigint NOT NULL CHECK (source_uid > 0),
    character_id bigint NOT NULL REFERENCES characters(id),
    source_ref integer NOT NULL,
    action_id integer NOT NULL,
    mode smallint NOT NULL CHECK (mode IN (13,29)),
    level_cap smallint NOT NULL CHECK (level_cap BETWEEN 1 AND 245),
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    completion jsonb,
    PRIMARY KEY(account_id,source_uid),
    CHECK ((completed_at IS NULL) = (completion IS NULL))
);
CREATE UNIQUE INDEX character_recustomization_pending
    ON character_recustomization_receipts(character_id) WHERE completed_at IS NULL;
