ALTER TABLE characters ADD COLUMN ecology_value integer NOT NULL DEFAULT 0
    CHECK (ecology_value BETWEEN -10000 AND 10000);
ALTER TABLE characters ADD COLUMN ecology_revision bigint NOT NULL DEFAULT 0
    CHECK (ecology_revision >= 0);

CREATE TABLE personal_ecology_receipts (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    operation text NOT NULL CHECK (length(operation) BETWEEN 1 AND 128),
    requested_delta integer NOT NULL CHECK (requested_delta BETWEEN -10000 AND 10000),
    before_value integer NOT NULL CHECK (before_value BETWEEN -10000 AND 10000),
    after_value integer NOT NULL CHECK (after_value BETWEEN -10000 AND 10000),
    revision bigint NOT NULL CHECK (revision > 0),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    PRIMARY KEY (character_id, operation),
    UNIQUE (character_id, revision)
);
