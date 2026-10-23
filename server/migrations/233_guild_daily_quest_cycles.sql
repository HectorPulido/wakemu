-- Original guild daily achievement cycles, separate from one-time milestones.
CREATE TABLE character_guild_daily_quests (
 character_id bigint NOT NULL REFERENCES characters(id),
 definition_id integer NOT NULL CHECK(definition_id IN (1389,1390,1391)),
 cycle_index bigint NOT NULL CHECK(cycle_index>=0),
 activation_guild_id bigint NOT NULL REFERENCES guilds(id),
 earned_guild_id bigint REFERENCES guilds(id),
 activated_at_ms bigint NOT NULL CHECK(activated_at_ms>=0),
 completed_at_ms bigint CHECK(completed_at_ms>=activated_at_ms),
 progress integer NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 10),
 PRIMARY KEY(character_id,definition_id,cycle_index),
 CHECK((completed_at_ms IS NULL)=(earned_guild_id IS NULL))
);
