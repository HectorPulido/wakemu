-- Freeze server XP presentation rate at the time a fixed quest reward is earned.
CREATE TABLE achievement_flat_xp_rates (
    character_id bigint NOT NULL,
    achievement_id integer NOT NULL,
    cycle_key text NOT NULL,
    reward_key text NOT NULL,
    policy_version bigint NOT NULL,
    xp_rate_bp integer NOT NULL CHECK (xp_rate_bp >= 0),
    base_xp bigint NOT NULL CHECK (base_xp > 0),
    awarded_xp bigint NOT NULL CHECK (awarded_xp >= 0),
    PRIMARY KEY (character_id, achievement_id, cycle_key, reward_key),
    FOREIGN KEY (character_id, achievement_id, cycle_key, reward_key)
      REFERENCES character_achievement_reward_outbox(character_id, achievement_id, cycle_key, reward_key)
);
