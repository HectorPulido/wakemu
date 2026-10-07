-- Durable flora occupation identity. Balance is configured in PostgreSQL.
INSERT INTO settings(name,value) VALUES
    ('resource_harvest_occupation', '{"completion_grace_ms":5000}'::jsonb);

CREATE TABLE resource_harvest_occupations (
    resource_uid bigint PRIMARY KEY REFERENCES planted_resources(resource_uid) ON DELETE CASCADE,
    token text NOT NULL UNIQUE,
    account_id bigint NOT NULL REFERENCES accounts(id),
    generation text NOT NULL,
    character_id bigint NOT NULL UNIQUE REFERENCES characters(id),
    action_id integer NOT NULL CHECK (action_id > 0),
    started_at timestamptz NOT NULL,
    completes_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    resource_snapshot jsonb NOT NULL CHECK (jsonb_typeof(resource_snapshot)='object'),
    FOREIGN KEY (account_id,character_id) REFERENCES characters(account_id,id),
    CHECK (completes_at >= started_at AND expires_at > completes_at)
);
CREATE INDEX resource_harvest_occupation_expiry ON resource_harvest_occupations(expires_at);
