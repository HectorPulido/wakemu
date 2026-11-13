-- Durable per-character counters for explicitly configured non-recurring combat missions.
CREATE TABLE character_combat_mission_counts (
    character_id bigint NOT NULL REFERENCES characters(id),
    objective_id integer NOT NULL CHECK (objective_id > 0),
    count bigint NOT NULL CHECK (count >= 0),
    PRIMARY KEY (character_id, objective_id)
);

-- The outer fight transaction persists the eligible event before the isolated
-- mission settlement. Replays may retry an unfinished receipt, never create a
-- receipt for a fight that predates publication or quest eligibility.
CREATE TABLE character_combat_mission_receipts (
    character_id bigint NOT NULL REFERENCES characters(id),
    fight_id bigint NOT NULL CHECK (fight_id > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamptz,
    PRIMARY KEY (character_id, fight_id)
);
