-- Original item-to-mission activation only; no objective completion or reward.
CREATE TABLE native_achievement_item_actions (
 item_ref integer PRIMARY KEY,
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 definition_id integer NOT NULL UNIQUE CHECK(definition_id>0),
 minimum_real_level integer NOT NULL CHECK(minimum_real_level>0),
 positional_suffix boolean NOT NULL,
 consumes_source boolean NOT NULL CHECK(NOT consumes_source),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
 descriptor jsonb NOT NULL CHECK(jsonb_typeof(descriptor)='object')
);
INSERT INTO native_achievement_item_actions VALUES
(14539,2594,652,95,false,false,'d8af41b03961255ea5cf6ad7617f99100f515aa85bf8ad6792c239bf84f0c620','{"action_id":2594,"consumes_source":false,"definition_id":652,"duration":0,"item_ref":14539,"minimum_real_level":95,"native_action_criterion":"","native_definition_availability":"","native_definition_criterion":"GetRealLevel()>=95","native_use_criterion":"","native_use_has_criteria":false,"objective_ids":[1397,1418],"period":0,"positional_suffix":false,"repeatable":false,"scope":"initial_activation_only"}'::jsonb),
(16471,3773,1197,105,true,false,'d8af41b03961255ea5cf6ad7617f99100f515aa85bf8ad6792c239bf84f0c620','{"action_id":3773,"consumes_source":false,"definition_id":1197,"duration":0,"item_ref":16471,"minimum_real_level":105,"native_action_criterion":"!IsAchievementActive(1197)","native_definition_availability":"","native_definition_criterion":"GetRealLevel() >= 105","native_use_criterion":"","native_use_has_criteria":false,"objective_ids":[2157],"period":0,"positional_suffix":true,"repeatable":false,"scope":"initial_activation_only"}'::jsonb);
