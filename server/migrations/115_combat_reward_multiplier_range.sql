-- Preserve existing policy versions while supporting direct multipliers through
-- 9999999.9999 at the existing exact 0.0001 multiplier resolution.
ALTER TABLE combat_reward_policy_versions
    DROP CONSTRAINT combat_reward_policy_versions_xp_rate_bp_check,
    DROP CONSTRAINT combat_reward_policy_versions_kamas_rate_bp_check,
    ALTER COLUMN xp_rate_bp TYPE bigint,
    ALTER COLUMN kamas_rate_bp TYPE bigint,
    ADD CONSTRAINT combat_reward_policy_versions_xp_rate_bp_check
        CHECK (xp_rate_bp BETWEEN 0 AND 99999999999),
    ADD CONSTRAINT combat_reward_policy_versions_kamas_rate_bp_check
        CHECK (kamas_rate_bp BETWEEN 0 AND 99999999999);

ALTER TABLE combat_drop_policy_versions
    DROP CONSTRAINT combat_drop_policy_versions_drop_rate_bp_check,
    ALTER COLUMN drop_rate_bp TYPE bigint,
    ADD CONSTRAINT combat_drop_policy_versions_drop_rate_bp_check
        CHECK (drop_rate_bp BETWEEN 0 AND 99999999999);
