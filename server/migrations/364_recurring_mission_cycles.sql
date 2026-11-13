-- Explicit, server-authorized acceptance and settlement for periodic missions.
-- No mission is published or activated by this schema alone.
CREATE TABLE character_recurring_mission_cycles (
    character_id bigint NOT NULL REFERENCES characters(id),
    definition_id integer NOT NULL CHECK (definition_id > 0),
    cycle_index bigint NOT NULL CHECK (cycle_index >= 0),
    accepted_at_ms bigint NOT NULL CHECK (accepted_at_ms >= 0),
    completed_at_ms bigint CHECK (completed_at_ms >= accepted_at_ms),
    PRIMARY KEY (character_id, definition_id, cycle_index)
);
