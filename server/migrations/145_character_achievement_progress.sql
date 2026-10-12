-- Server-owned achievement facts. No quest completion or reward grants are seeded.
CREATE TABLE character_achievement_progress (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    state jsonb NOT NULL CHECK (jsonb_typeof(state) = 'object'),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE character_achievement_events (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    event_key text NOT NULL CHECK (length(event_key) BETWEEN 1 AND 256),
    signature text NOT NULL CHECK (length(signature) = 64),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, event_key)
);
CREATE TABLE character_achievement_reward_outbox (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    achievement_id integer NOT NULL CHECK (achievement_id > 0),
    cycle_key text NOT NULL CHECK (length(cycle_key) BETWEEN 1 AND 256),
    reward_key text NOT NULL CHECK (length(reward_key) BETWEEN 1 AND 256),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at timestamptz,
    PRIMARY KEY (character_id, achievement_id, cycle_key, reward_key)
);
CREATE INDEX character_achievement_pending_rewards
ON character_achievement_reward_outbox (character_id, created_at)
WHERE delivered_at IS NULL;

CREATE TABLE character_achievement_notifications (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    event_key text NOT NULL CHECK (length(event_key) BETWEEN 1 AND 256),
    packets jsonb NOT NULL CHECK (jsonb_typeof(packets) = 'array'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at timestamptz,
    PRIMARY KEY (character_id, event_key)
);
CREATE INDEX character_achievement_pending_notifications
ON character_achievement_notifications (character_id, created_at)
WHERE delivered_at IS NULL;
