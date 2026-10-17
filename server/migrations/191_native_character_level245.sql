-- Original installed MP.aXu supports character levels 1..245. Profession
-- levels and native monster bounds have independent authorities.
ALTER TABLE characters DROP CONSTRAINT characters_level_check;
ALTER TABLE characters ADD CONSTRAINT characters_level_check
    CHECK (level BETWEEN 1 AND 245);

ALTER TABLE fight_rewards DROP CONSTRAINT fight_rewards_start_level_check;
ALTER TABLE fight_rewards ADD CONSTRAINT fight_rewards_start_level_check
    CHECK (start_level BETWEEN 1 AND 245);
ALTER TABLE fight_rewards DROP CONSTRAINT fight_rewards_check1;
ALTER TABLE fight_rewards ADD CONSTRAINT fight_rewards_check1
    CHECK (end_level BETWEEN start_level AND 245);
