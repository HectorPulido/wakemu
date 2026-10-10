-- NPC levels use the positive native signed-short range, independently of the
-- player progression cap. Existing reference overrides and levels 1..200 stay
-- unchanged. Higher default rows are an explicit DEV nearest-lower extension
-- of migration 041's emulation policy, not official Wakfu reward balance.
ALTER TABLE combat_reward_monster_levels
    DROP CONSTRAINT combat_reward_monster_levels_monster_level_check;
ALTER TABLE combat_reward_monster_levels
    ADD CONSTRAINT combat_reward_monster_levels_monster_level_check
    CHECK (monster_level BETWEEN 1 AND 32767);
ALTER TABLE combat_reward_level_defaults
    DROP CONSTRAINT combat_reward_level_defaults_monster_level_check;
ALTER TABLE combat_reward_level_defaults
    ADD CONSTRAINT combat_reward_level_defaults_monster_level_check
    CHECK (monster_level BETWEEN 1 AND 32767);

INSERT INTO combat_reward_level_defaults
    (monster_level,base_xp,min_kamas,max_kamas,source)
SELECT levels.monster_level,baseline.base_xp,baseline.min_kamas,baseline.max_kamas,
       'explicit-dev-nearest-lower-extension-041;source_level:200;nonofficial-wakfu-balance'
FROM generate_series(201,32767) AS levels(monster_level)
CROSS JOIN combat_reward_level_defaults AS baseline
WHERE baseline.monster_level=200
ON CONFLICT (monster_level) DO NOTHING;
