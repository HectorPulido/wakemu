-- Reviewed server-side thresholds for native objectives without variables.
-- Native objective identity survives profile upgrades; no player journal or
-- native achievement variable is synthesized to represent these counters.
CREATE TABLE character_mission_objective_counts (
    character_id bigint NOT NULL REFERENCES characters(id),
    objective_id integer NOT NULL CHECK (objective_id > 0),
    count bigint NOT NULL CHECK (count >= 0 AND count < 2147483648),
    PRIMARY KEY (character_id, objective_id)
);
