-- Native1.93 XP authority supports character levels1..245; ship only with191,
-- the complete245 XP catalog and the matching shared character-level readers.
-- This expands eligibility, never rewrites earned/frozen events or rewards.
SELECT pg_advisory_xact_lock(747117401);
ALTER TABLE objectives_events DROP CONSTRAINT objectives_source_level;
ALTER TABLE objectives_events ADD CONSTRAINT objectives_source_level CHECK(character_level BETWEEN 1 AND 245);
ALTER TABLE objectives_pvp_events DROP CONSTRAINT objectives_pvp_events_first_level_check;
ALTER TABLE objectives_pvp_events ADD CONSTRAINT objectives_pvp_events_first_level_check CHECK(first_level BETWEEN 1 AND 245);
ALTER TABLE objectives_pvp_events DROP CONSTRAINT objectives_pvp_events_second_level_check;
ALTER TABLE objectives_pvp_events ADD CONSTRAINT objectives_pvp_events_second_level_check CHECK(second_level BETWEEN 1 AND 245);
ALTER TABLE objectives_pvp_fight_roster DROP CONSTRAINT objectives_pvp_fight_roster_level_check;
ALTER TABLE objectives_pvp_fight_roster ADD CONSTRAINT objectives_pvp_fight_roster_level_check CHECK(level BETWEEN 1 AND 245);
ALTER TABLE objectives_assignment_periods DROP CONSTRAINT objectives_assignment_periods_level_check;
ALTER TABLE objectives_assignment_periods ADD CONSTRAINT objectives_assignment_periods_level_check CHECK(level BETWEEN 1 AND 245);
ALTER TABLE objectives_points DROP CONSTRAINT objectives_points_level_check;
ALTER TABLE objectives_points ADD CONSTRAINT objectives_points_level_check CHECK(level BETWEEN 1 AND 245);
ALTER TABLE objectives_challenge_runs DROP CONSTRAINT objectives_challenge_runs_level_check;
ALTER TABLE objectives_challenge_runs ADD CONSTRAINT objectives_challenge_runs_level_check CHECK(level BETWEEN 1 AND 245);
ALTER TABLE objectives_challenge_runs DROP CONSTRAINT objectives_challenge_runs_check;
ALTER TABLE objectives_challenge_runs ADD CONSTRAINT objectives_challenge_runs_group_level_check CHECK(group_level BETWEEN level AND 245);
-- Hunt levels belong to native NPCs, independently of the player progression cap.
ALTER TABLE objectives_public_hunts DROP CONSTRAINT objectives_public_hunts_level_check;
ALTER TABLE objectives_public_hunts ADD CONSTRAINT objectives_public_hunts_level_check CHECK(level BETWEEN 1 AND 32767);

-- Preserve every existing terminal-band reward amount/item pool, and freeze
-- the new revision through the existing version trigger. Historical200 policy
-- versions remain available for pending source-time events below or at200.
WITH revised AS (
 UPDATE objectives_reward_policies
 SET policy=jsonb_set(policy,ARRAY['bands',(jsonb_array_length(policy->'bands')-1)::text,'maximum'],'245'),
     revision=revision+1,updated_at=CURRENT_TIMESTAMP
 WHERE jsonb_typeof(policy->'bands')='array'
   AND (policy->'bands'->-1->>'maximum')::integer=200
 RETURNING key,revision,policy
)
INSERT INTO objectives_reward_policy_audit(policy_key,revision,operator,policy)
SELECT key,revision,'migration192-native-character-level245',policy FROM revised;

-- Existing generated terminal player bands are local eligibility policy. Do
-- not change custom ranges, achievement thresholds, objective targets, rewards,
-- assignments already issued, progress counters, or frozen definition versions.
WITH revised AS (
 UPDATE objectives_definitions
 SET definition=jsonb_set(jsonb_set(definition,'{level_range,maximum}','245'),'{title}',
       to_jsonb(CASE WHEN key='content-v1.daily.hunt.181-200'
       THEN replace(definition->>'title','181-200','181-245') ELSE definition->>'title' END)),
     revision=revision+1,updated_at=CURRENT_TIMESTAMP
 WHERE (definition->'level_range'->>'maximum')::integer=200
 AND (key LIKE 'content-v1.%' OR key IN (
   'assign-v1.daily.monster.4203','assign-v1.weekly.monster.4203',
   'assign-v1.daily.monster.4204','assign-v1.weekly.monster.4204',
   'assign-v1.daily.monster.4205','assign-v1.weekly.monster.4205',
   'assign-v1.daily.monster.4208','assign-v1.weekly.monster.4208'))
 RETURNING key,revision,definition
)
INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition)
SELECT key,revision,'migration192-native-character-level245',definition FROM revised;

-- Recompute the previously clipped weekly dungeon upper bound from its actual
-- active compiled native roster, retaining the existing +20-level local rule.
WITH native_ranges AS (
 SELECT (c.configuration->'route'->>'definition_id')::integer AS definition_id,
        min((m->>'native_min_level')::integer) AS minimum,
        max((m->>'native_max_level')::integer) AS maximum
 FROM dungeon_runtime_configurations c
 JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version)
 CROSS JOIN LATERAL jsonb_array_elements(c.configuration->'compiled_plan'->'rooms') room
 CROSS JOIN LATERAL jsonb_array_elements(room->'monsters') m
 GROUP BY (c.configuration->'route'->>'definition_id')::integer
), revised AS (
 UPDATE objectives_definitions d
 SET definition=jsonb_set(d.definition,'{level_range,maximum}',to_jsonb(least(245,n.maximum+20))),
     revision=d.revision+1,updated_at=CURRENT_TIMESTAMP
 FROM native_ranges n
 WHERE d.key='assign-v1.weekly.dungeon.'||n.definition_id::text
 AND (d.definition->'level_range'->>'maximum')::integer=200
 AND n.minimum BETWEEN 1 AND 245 AND n.maximum BETWEEN 180 AND 32767
 AND least(245,n.maximum+20)>200
 RETURNING d.key,d.revision,d.definition
)
INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition)
SELECT key,revision,'migration192-native-character-level245',definition FROM revised;

-- Existing terminal encounter remains the same native roster, with a wider
-- player eligibility band. Keys and in-flight run brackets remain immutable.
UPDATE objectives_challenge_profiles
SET definition=jsonb_set(jsonb_set(definition,'{max_level}','245'),'{title}',
       to_jsonb(replace(definition->>'title','181-200','181-245'))),
    revision=revision+1,updated_at=CURRENT_TIMESTAMP
WHERE key='weekly-native-181-200'
AND (definition->>'min_level')::integer=181
AND (definition->>'max_level')::integer=200;

WITH revised AS (
 UPDATE objectives_definitions
 SET definition=jsonb_set(definition,'{description}',to_jsonb('Reach level 245 with any undeleted character on your account.'::text)),
     revision=revision+1,updated_at=CURRENT_TIMESTAMP
 WHERE key='progression-v1.characters.level.245'
 AND definition->>'description' LIKE '%the current cap is 200.%'
 RETURNING key,revision,definition
)
INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition)
SELECT key,revision,'migration192-native-character-level245',definition FROM revised;
