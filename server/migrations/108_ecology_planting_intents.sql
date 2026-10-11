-- Durable asynchronous requests; inventory/rewards remain world-side commits.
CREATE TABLE ecology_planting_intents (
    id text PRIMARY KEY,
    world_epoch text NOT NULL,
    account_id bigint NOT NULL,
    generation text NOT NULL,
    character_id bigint NOT NULL,
    intent_version bigint GENERATED ALWAYS AS IDENTITY,
    body bytea NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 4096),
    actor_location jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','applying','applied','cancelled')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ecology_planting_pending ON ecology_planting_intents(world_epoch,intent_version)
    WHERE status='pending';
CREATE INDEX ecology_planting_actor ON ecology_planting_intents(character_id,generation)
    WHERE status='pending';
