-- Custom local tasks are separate from installed native journal identifiers.
CREATE TABLE character_custom_task_events (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    event_key text NOT NULL CHECK (length(event_key) BETWEEN 1 AND 256),
    signature text NOT NULL CHECK (length(signature) = 64),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, event_key)
);
CREATE TABLE character_custom_task_progress (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    task_key text NOT NULL CHECK (length(task_key) BETWEEN 1 AND 128),
    definition_signature text NOT NULL CHECK (length(definition_signature) = 64),
    count bigint NOT NULL DEFAULT 0 CHECK (count >= 0),
    completed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, task_key)
);
CREATE TABLE character_custom_task_reward_outbox (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    task_key text NOT NULL,
    reward_index integer NOT NULL CHECK (reward_index >= 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at timestamptz,
    PRIMARY KEY (character_id, task_key, reward_index),
    FOREIGN KEY (character_id, task_key)
        REFERENCES character_custom_task_progress(character_id, task_key) ON DELETE CASCADE
);
CREATE INDEX character_custom_task_pending_rewards
ON character_custom_task_reward_outbox(character_id, created_at)
WHERE delivered_at IS NULL;
