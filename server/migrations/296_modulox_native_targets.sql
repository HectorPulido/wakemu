-- Explicit native-derived Wakemu objective/target bindings; no NPC activation.
ALTER TABLE recurring_hunter_rewards DROP CONSTRAINT recurring_hunter_rewards_native_type_check;
ALTER TABLE recurring_hunter_rewards DROP CONSTRAINT recurring_hunter_rewards_check;
ALTER TABLE recurring_hunter_rewards ADD CONSTRAINT recurring_hunter_rewards_native_type_check CHECK(native_type IN(5,6,17));
ALTER TABLE recurring_hunter_rewards ADD CONSTRAINT recurring_hunter_rewards_check
 CHECK((native_type=5 AND reference IS NOT NULL AND reference>0) OR (native_type IN(6,17) AND reference IS NULL));
CREATE TABLE recurring_modulox_category_sources (
 category_id integer PRIMARY KEY CHECK(category_id IN(684,685,686,687,810)),
 expected_members integer NOT NULL CHECK(expected_members>0),
 offer_node_id integer NOT NULL CHECK(offer_node_id=3972), offer_choice_id integer NOT NULL CHECK(offer_choice_id>0),
 offer_minimum_level integer NOT NULL CHECK(offer_minimum_level>0), offer_criterion text NOT NULL,
 offer_source_sha256 text NOT NULL CHECK(offer_source_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TABLE recurring_modulox_category_members (
 definition_id integer PRIMARY KEY CHECK(definition_id>0),
 category_id integer NOT NULL REFERENCES recurring_modulox_category_sources,
 anchor_ms bigint NOT NULL CHECK(anchor_ms>=0), period_ms bigint NOT NULL CHECK(period_ms=86400000),
 original_minimum_level integer NOT NULL CHECK(original_minimum_level>0),
 UNIQUE(definition_id,category_id)
);
CREATE TRIGGER recurring_modulox_category_source_immutable BEFORE UPDATE OR DELETE ON recurring_modulox_category_sources
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TRIGGER recurring_modulox_category_member_immutable BEFORE UPDATE OR DELETE ON recurring_modulox_category_members
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TABLE recurring_modulox_authority (
 definition_id integer NOT NULL, version integer NOT NULL, boss_reference integer NOT NULL,
 dungeon_definition_id integer NOT NULL CHECK(dungeon_definition_id>0), route_key text NOT NULL,
 route_policy_version integer NOT NULL CHECK(route_policy_version>0), final_room_order integer NOT NULL CHECK(final_room_order>0),
 category_id integer NOT NULL CHECK(category_id IN(684,685,686,687,810)),
 minimum_level integer NOT NULL CHECK(minimum_level>0), minimum_level_authority text NOT NULL,
 native_catalog_revision text NOT NULL, monsters_path text NOT NULL CHECK(monsters_path='monsters.json'),
 monsters_sha256 text NOT NULL CHECK(monsters_sha256 ~ '^[0-9a-f]{64}$'),
 plan_sha256 text NOT NULL CHECK(plan_sha256 ~ '^[0-9a-f]{64}$'),
 interpretation_policy text NOT NULL CHECK(interpretation_policy='wakemu.modulox-native-adjusted-final-room-v1'),
 reward_policy text NOT NULL CHECK(reward_policy='native17-frozen-real-level-no-subscription'),
 native_reward_order integer[] NOT NULL CHECK(cardinality(native_reward_order)=2),
 target_effective_level integer NOT NULL CHECK(target_effective_level>0),
 offer_node_id integer NOT NULL CHECK(offer_node_id=3972), offer_choice_id integer NOT NULL CHECK(offer_choice_id>0),
 offer_criterion text NOT NULL CHECK(length(offer_criterion)>0),
 offer_source_sha256 text NOT NULL CHECK(offer_source_sha256 ~ '^[0-9a-f]{64}$'),
 public_corroborated boolean NOT NULL, source_authority text NOT NULL,
 original_activation_criterion text NOT NULL, original_eligibility_criterion text NOT NULL, original_objective_en text NOT NULL,
 PRIMARY KEY(definition_id,version,boss_reference), UNIQUE(definition_id,version),
 FOREIGN KEY(definition_id,version,boss_reference) REFERENCES recurring_hunter_targets,
 FOREIGN KEY(definition_id,category_id) REFERENCES recurring_modulox_category_members(definition_id,category_id),
 FOREIGN KEY(native_catalog_revision,monsters_path,monsters_sha256) REFERENCES recurring_hunter_catalog_sources(native_catalog_revision,monsters_path,monsters_sha256)
);
CREATE TRIGGER recurring_modulox_authority_immutable BEFORE UPDATE OR DELETE ON recurring_modulox_authority
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TABLE recurring_modulox_victory_proofs (
 definition_id integer NOT NULL, version integer NOT NULL, fight_id bigint NOT NULL,
 character_id bigint NOT NULL, account_id bigint NOT NULL, instance_id bigint NOT NULL,
 dungeon_definition_id integer NOT NULL CHECK(dungeon_definition_id>0),
 effective_level integer NOT NULL CHECK(effective_level>0), target_effective_level integer NOT NULL CHECK(target_effective_level>0),
 selection_revision bigint NOT NULL, difficulty_snapshot jsonb NOT NULL CHECK(jsonb_typeof(difficulty_snapshot)='object'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(definition_id,version,fight_id,character_id), CHECK(effective_level<=target_effective_level),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_modulox_authority(definition_id,version),
 FOREIGN KEY(fight_id,character_id,account_id) REFERENCES combat_fight_participants(fight_id,character_id,account_id),
 FOREIGN KEY(fight_id) REFERENCES dungeon_encounter_difficulties(fight_id)
);
CREATE TRIGGER recurring_modulox_victory_immutable BEFORE UPDATE OR DELETE ON recurring_modulox_victory_proofs
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE OR REPLACE FUNCTION recurring_hunter_daily_member_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Daily hunter member is immutable'; END IF;
 PERFORM 1 FROM recurring_hunter_daily_pools WHERE pool_version=NEW.pool_version AND NOT sealed FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Daily hunter pool is sealed'; END IF;
 PERFORM 1 FROM recurring_hunter_contracts c WHERE c.definition_id=NEW.definition_id AND c.version=NEW.version
 AND c.period_ms=86400000 AND (
 EXISTS(SELECT 1 FROM recurring_hunter_target_authority a WHERE a.definition_id=c.definition_id AND a.version=c.version AND a.category_id=NEW.category_id)
 OR EXISTS(SELECT 1 FROM recurring_modulox_authority a WHERE a.definition_id=c.definition_id AND a.version=c.version AND a.category_id=NEW.category_id));
 IF NOT FOUND THEN RAISE EXCEPTION 'Daily hunter member lacks qualified daily authority'; END IF;
 RETURN NEW;
END $$;

INSERT INTO recurring_modulox_category_sources VALUES(684,13,3972,10124,51,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4');
INSERT INTO recurring_modulox_category_sources VALUES(685,23,3972,10019,96,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4');
INSERT INTO recurring_modulox_category_sources VALUES(686,21,3972,10020,141,E'GetRealLevel() >= 141\r\nand GetAchievementCategoryRunningCount(686) < 1\r\nand GetAchievementCategoryCount(686) == GetAchievementCategoryCanBeResetCount(686)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4');
INSERT INTO recurring_modulox_category_sources VALUES(687,21,3972,10441,186,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4');
INSERT INTO recurring_modulox_category_sources VALUES(810,24,3972,11972,231,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4');
INSERT INTO recurring_modulox_category_members VALUES(4062,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4063,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4064,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4065,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4066,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4067,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4068,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4073,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4075,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4085,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4086,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4087,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4089,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4090,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4096,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4097,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4098,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4099,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4100,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4101,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4104,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4105,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4106,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4107,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4108,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4109,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4110,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4111,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4112,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4113,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4114,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4115,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4116,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4117,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4118,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4119,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4121,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4122,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4123,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4124,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4125,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4126,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4127,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4128,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4129,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4130,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4131,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4132,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4133,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4134,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4135,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4136,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4137,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4138,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4226,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4465,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(4467,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4468,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4469,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4470,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4471,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4472,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4473,685,1475452800000,86400000,96);
INSERT INTO recurring_modulox_category_members VALUES(4475,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4476,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4477,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4478,686,1475452800000,86400000,141);
INSERT INTO recurring_modulox_category_members VALUES(4479,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4480,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4481,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4482,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4483,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4652,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4653,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4731,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(4787,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4788,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4789,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4790,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4791,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4792,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4793,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4794,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4954,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4955,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4956,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4957,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4958,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4959,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4960,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(4961,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5118,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(5119,684,1475452800000,86400000,50);
INSERT INTO recurring_modulox_category_members VALUES(5206,687,1475452800000,86400000,186);
INSERT INTO recurring_modulox_category_members VALUES(5387,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5388,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5389,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5390,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5391,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5392,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5393,810,1475452800000,86400000,231);
INSERT INTO recurring_modulox_category_members VALUES(5394,810,1475452800000,86400000,231);
INSERT INTO recurring_hunter_contracts VALUES(4062,1,8549,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4062,1,44,E'wakemu.modulox.boss.44');
INSERT INTO recurring_hunter_rewards VALUES(4062,1,7429,5,20752,2,false);
INSERT INTO recurring_hunter_rewards VALUES(4062,1,7508,17,NULL,1000,false);
INSERT INTO recurring_modulox_authority VALUES(4062,1,44,90,E'native_dungeon_90',2,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'1a66c99276a4dd19b49cb0d7063c74fea0ae6778947b69584a46f634ea100309',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7429,7508],20,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4062)',E'GetRealLevel() >= 50',E'Complete the Gobball Pastures Dungeon at level 20');
INSERT INTO recurring_hunter_contracts VALUES(4063,1,8550,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4063,1,1259,E'wakemu.modulox.boss.1259');
INSERT INTO recurring_hunter_rewards VALUES(4063,1,7549,5,20752,2,false);
INSERT INTO recurring_hunter_rewards VALUES(4063,1,7662,17,NULL,1000,false);
INSERT INTO recurring_modulox_authority VALUES(4063,1,1259,27,E'native_dungeon_27',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'a459541ceb4aaab4cf69ae2e483551cca9a9be8c05e32a57fe50a314fffacd95',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7549,7662],20,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4063)',E'GetRealLevel() >= 50',E'Complete the Tofuhouse Dungeon at level 20');
INSERT INTO recurring_hunter_contracts VALUES(4064,1,8551,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4064,1,2157,E'wakemu.modulox.boss.2157');
INSERT INTO recurring_hunter_rewards VALUES(4064,1,7547,5,20752,2,false);
INSERT INTO recurring_hunter_rewards VALUES(4064,1,7661,17,NULL,1000,false);
INSERT INTO recurring_modulox_authority VALUES(4064,1,2157,65,E'native_dungeon_65',3,4,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'ad1ee2643d5e01043ca95272d64d46138ebac2b85e3f56e91faf94ac04ba1f4c',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7547,7661],20,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4064)',E'GetRealLevel() >= 50',E'Complete the Larventura Dungeon at level 20');
INSERT INTO recurring_hunter_contracts VALUES(4066,1,8553,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4066,1,1187,E'wakemu.modulox.boss.1187');
INSERT INTO recurring_hunter_rewards VALUES(4066,1,7679,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4066,1,7543,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4066,1,1187,26,E'native_dungeon_26',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'87c641dca1aa7e2770166dc1bd49c6d0182951494c91af0aa3fbbf5cca97b864',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7679,7543],35,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4066)',E'GetRealLevel() >= 50',E'Complete the Hoola Hoopiwi Dungeon at level 35');
INSERT INTO recurring_hunter_contracts VALUES(4067,1,8554,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4067,1,3216,E'wakemu.modulox.boss.3216');
INSERT INTO recurring_hunter_rewards VALUES(4067,1,7680,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4067,1,7541,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4067,1,3216,89,E'native_dungeon_89',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'7ead825c3ea84f4e1605e5d25a9f146a9e5e60dab88ed29f436aaabbdd368a4e',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7680,7541],35,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4067)',E'GetRealLevel() >= 50',E'Complete the Raised Vault Dungeon at level 35');
INSERT INTO recurring_hunter_contracts VALUES(4068,1,8555,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4068,1,4107,E'wakemu.modulox.boss.4107');
INSERT INTO recurring_hunter_rewards VALUES(4068,1,7678,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4068,1,7539,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4068,1,4107,125,E'native_dungeon_125',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'38839c974c1eb451f42b0a20fb20a4f37ecabf76e161e14a2b72987615e49688',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7678,7539],35,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4068)',E'GetRealLevel() >= 50',E'Complete the Treechnee Dungeon at level 35');
INSERT INTO recurring_hunter_contracts VALUES(4075,1,8562,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4075,1,4519,E'wakemu.modulox.boss.4519');
INSERT INTO recurring_hunter_rewards VALUES(4075,1,7671,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4075,1,7525,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4075,1,4519,136,E'native_dungeon_136',3,6,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'40a62d11aa0e682c25216e08f53807424a2a26fbd31b944f5c94246980c14b89',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7671,7525],50,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4075)',E'GetRealLevel() >= 50',E'Complete the Hill Hazize Dungeon at level 50');
INSERT INTO recurring_hunter_contracts VALUES(4085,1,8572,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4085,1,2768,E'wakemu.modulox.boss.2768');
INSERT INTO recurring_hunter_rewards VALUES(4085,1,7687,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4085,1,7561,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4085,1,2768,81,E'native_dungeon_81',3,2,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'af13fbbe6539ffccee0808930df9710957658cd3104416278f5dc83ce51757ca',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7687,7561],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4085)',E'GetRealLevel() >= 96',E'Complete the Forgotten Lair Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4086,1,8573,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4086,1,2774,E'wakemu.modulox.boss.2774');
INSERT INTO recurring_hunter_rewards VALUES(4086,1,7686,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4086,1,7559,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4086,1,2774,80,E'native_dungeon_80',3,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'b365406962deb17bf6415b465128fab34201f6d3140178e620b3b5e2ae4c62bb',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7686,7559],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4086)',E'GetRealLevel() >= 96',E'Complete the Bwork Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4089,1,8576,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4089,1,4240,E'wakemu.modulox.boss.4240');
INSERT INTO recurring_hunter_rewards VALUES(4089,1,7683,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4089,1,7555,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4089,1,4240,34,E'native_dungeon_34',3,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'2f82d93f966e185ebc83378e5b5bf4be21b753817d721b57c23d95ee8be7c0c8',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7683,7555],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4089)',E'GetRealLevel() >= 96',E'Complete the Mollusky Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4090,1,8577,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4090,1,4244,E'wakemu.modulox.boss.4244');
INSERT INTO recurring_hunter_rewards VALUES(4090,1,7682,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4090,1,7553,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4090,1,4244,41,E'native_dungeon_41',3,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'7df6b2394e6c8479be577081de92446c456670bb5b02029cefb98beadb6155c1',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7682,7553],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4090)',E'GetRealLevel() >= 96',E'Complete the Dry Selachii Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4096,1,8583,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4096,1,5107,E'wakemu.modulox.boss.5107');
INSERT INTO recurring_hunter_rewards VALUES(4096,1,7693,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4096,1,7573,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4096,1,5107,46,E'native_dungeon_46',3,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'db9155fc94279d733a5124bb9573a361e3d9ac0a5f59fe70ea2231a602589983',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7693,7573],80,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4096)',E'GetRealLevel() >= 96',E'Complete the Arachnee Dungeon at level 80');
INSERT INTO recurring_hunter_contracts VALUES(4097,1,8584,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4097,1,5114,E'wakemu.modulox.boss.5114');
INSERT INTO recurring_hunter_rewards VALUES(4097,1,7692,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4097,1,7571,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4097,1,5114,47,E'native_dungeon_47',3,4,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'959eee5fc10592b9c97827da176bcb811a6324893d87fd5bdc8f5adb37723fdc',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7692,7571],80,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4097)',E'GetRealLevel() >= 96',E'Complete the Boowolf Dungeon at level 80');
INSERT INTO recurring_hunter_contracts VALUES(4098,1,8585,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4098,1,3696,E'wakemu.modulox.boss.3696');
INSERT INTO recurring_hunter_rewards VALUES(4098,1,7691,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4098,1,7569,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4098,1,3696,88,E'native_dungeon_88',3,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'6685375ef510ab414b61b86c31b951aa7b82efaa277f932acd0cc01a287da80e',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7691,7569],80,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4098)',E'GetRealLevel() >= 96',E'Complete the Cro-Cave Dungeon at level 80');
INSERT INTO recurring_hunter_contracts VALUES(4100,1,8587,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4100,1,2313,E'wakemu.modulox.boss.2313');
INSERT INTO recurring_hunter_rewards VALUES(4100,1,7689,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4100,1,7565,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4100,1,2313,12,E'native_dungeon_12',3,2,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'3c058ca09ca69467f19ee425cb81d720537cb11118519a1edd06ee936b89b7e1',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7689,7565],80,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4100)',E'GetRealLevel() >= 96',E'Complete the Ratatombs Dungeon at level 80');
INSERT INTO recurring_hunter_contracts VALUES(4105,1,8592,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4105,1,1786,E'wakemu.modulox.boss.1786');
INSERT INTO recurring_hunter_rewards VALUES(4105,1,7712,17,NULL,3000,false);
INSERT INTO recurring_hunter_rewards VALUES(4105,1,7613,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4105,1,1786,48,E'native_dungeon_48',3,2,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'3c061ea38ad1f52e4792e2a6190fe2af4e9a3c404503725e5053f3cef7df29b5',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7712,7613],95,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4105)',E'GetRealLevel() >= 96',E'Complete the Undieworld Dungeon at level 95');
INSERT INTO recurring_hunter_contracts VALUES(4116,1,8603,141,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4116,1,2354,E'wakemu.modulox.boss.2354');
INSERT INTO recurring_hunter_rewards VALUES(4116,1,7701,17,NULL,3000,false);
INSERT INTO recurring_hunter_rewards VALUES(4116,1,7591,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4116,1,2354,10,E'native_dungeon_10',3,4,686,141,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'07b0a3fbe98be773566db57100ca670523a1164e43e95be591c70220cb424fd7',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7701,7591],125,3972,10020,E'GetRealLevel() >= 141\r\nand GetAchievementCategoryRunningCount(686) < 1\r\nand GetAchievementCategoryCount(686) == GetAchievementCategoryCanBeResetCount(686)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4116)',E'GetRealLevel() >= 141',E'Complete the Frozen Tower Dungeon at level 125');
INSERT INTO recurring_hunter_contracts VALUES(4123,1,8610,141,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4123,1,5471,E'wakemu.modulox.boss.5471');
INSERT INTO recurring_hunter_rewards VALUES(4123,1,7734,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4123,1,7653,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4123,1,5471,193,E'native_dungeon_193',3,2,686,141,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'302203d3f4aa945acef48bbd794d3ede5ab5e63e417303b2f3852c0b8883e2f1',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7734,7653],140,3972,10020,E'GetRealLevel() >= 141\r\nand GetAchievementCategoryRunningCount(686) < 1\r\nand GetAchievementCategoryCount(686) == GetAchievementCategoryCanBeResetCount(686)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4123)',E'GetRealLevel() >= 141',E'Complete the Great Zomkin''s Compost Dungeon at level 140');
INSERT INTO recurring_hunter_contracts VALUES(4132,1,8619,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4132,1,3398,E'wakemu.modulox.boss.3398');
INSERT INTO recurring_hunter_rewards VALUES(4132,1,7725,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4132,1,7635,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4132,1,3398,95,E'native_dungeon_95',3,4,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'05f25213552f63e0d45080adfd11e0589325f97ff1b7793d8275face3cc44113',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7725,7635],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4132)',E'GetRealLevel() >= 186',E'Complete the Mecha Factory Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4133,1,8620,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4133,1,3399,E'wakemu.modulox.boss.3399');
INSERT INTO recurring_hunter_rewards VALUES(4133,1,7724,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4133,1,7633,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4133,1,3399,96,E'native_dungeon_96',3,4,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'5b5ec10765c5c96cbbeb54757022a41d52273241493cf8c6df1279bd041f1fd6',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7724,7633],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4133)',E'GetRealLevel() >= 186',E'Complete the Ow El Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4134,1,8621,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4134,1,4217,E'wakemu.modulox.boss.4217');
INSERT INTO recurring_hunter_rewards VALUES(4134,1,7723,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4134,1,7631,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4134,1,4217,121,E'native_dungeon_121',3,1,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'5e6e7c08be3f17cd9e2f436c37c508e5f178bab6b78e93f46b74a2b92e53be57',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7723,7631],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4134)',E'GetRealLevel() >= 186',E'Complete the Kali''s Lair Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4135,1,8622,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4135,1,3865,E'wakemu.modulox.boss.3865');
INSERT INTO recurring_hunter_rewards VALUES(4135,1,7722,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4135,1,7629,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4135,1,3865,104,E'native_dungeon_104',3,2,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'57e8a3734e73f539d9ab8051ec6f123ca9394634d9de0c13cdb39f740980be37',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7722,7629],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4135)',E'GetRealLevel() >= 186',E'Complete the Tropickle Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4136,1,8623,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4136,1,3864,E'wakemu.modulox.boss.3864');
INSERT INTO recurring_hunter_rewards VALUES(4136,1,7721,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4136,1,7627,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4136,1,3864,106,E'native_dungeon_106',3,2,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'f132b408bae5f106420fc8d15ead93a36f0a57cd7019a7e41601dfed5bceab75',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7721,7627],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4136)',E'GetRealLevel() >= 186',E'Complete the Kanniball Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4137,1,8624,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4137,1,3971,E'wakemu.modulox.boss.3971');
INSERT INTO recurring_hunter_rewards VALUES(4137,1,7720,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4137,1,7625,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4137,1,3971,110,E'native_dungeon_110',3,3,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'164670fd1da7c99ab317aee19efed4f969a69a978e7d2697477542c1135408c3',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7720,7625],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4137)',E'GetRealLevel() >= 186',E'Complete the Crocodyl Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4138,1,8625,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4138,1,3866,E'wakemu.modulox.boss.3866');
INSERT INTO recurring_hunter_rewards VALUES(4138,1,7719,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4138,1,7623,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4138,1,3866,109,E'native_dungeon_109',3,2,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'719692397078360b8e3306f9eb036ce954104af06d851085e4c55f57c93a07d2',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7719,7623],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4138)',E'GetRealLevel() >= 186',E'Complete the Kannivore Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4226,1,8713,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4226,1,4651,E'wakemu.modulox.boss.4651');
INSERT INTO recurring_hunter_rewards VALUES(4226,1,7924,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4226,1,7925,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4226,1,4651,133,E'native_dungeon_133',3,1,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'7c1abc9f51721ffc0ceb987fe3f3e7c2e5883a0708403977c64401ede5577002',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[7924,7925],50,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4226)',E'GetRealLevel() >= 50',E'Complete the Mineral Tower Dungeon at level 50');
INSERT INTO recurring_hunter_contracts VALUES(4465,1,9156,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4465,1,4758,E'wakemu.modulox.boss.4758');
INSERT INTO recurring_hunter_rewards VALUES(4465,1,8332,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(4465,1,8333,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4465,1,4758,137,E'native_dungeon_137',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'8f2b1749b36710dccfc231089745af9b671339c4cdb0575519378c5bc998b2e9',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8332,8333],50,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4465)',E'GetRealLevel() >= 50',E'Complete the Royal Pasturizer Dungeon at level 50');
INSERT INTO recurring_hunter_contracts VALUES(4467,1,9159,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4467,1,4731,E'wakemu.modulox.boss.4731');
INSERT INTO recurring_hunter_rewards VALUES(4467,1,8335,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4467,1,8336,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4467,1,4731,141,E'native_dungeon_141',3,5,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'144fc7faed45824d466bd291d63a4581dd7b90825cac711e7cac8fe737adb21d',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8335,8336],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4467)',E'GetRealLevel() >= 96',E'Complete the Kokokobana Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4468,1,9160,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4468,1,4754,E'wakemu.modulox.boss.4754');
INSERT INTO recurring_hunter_rewards VALUES(4468,1,8337,17,NULL,2000,false);
INSERT INTO recurring_hunter_rewards VALUES(4468,1,8338,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4468,1,4754,140,E'native_dungeon_140',3,4,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'81b62afe11909d927340fbe68a4761f9131dc7030b3522af404377f9081422a9',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8337,8338],65,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4468)',E'GetRealLevel() >= 96',E'Complete the Cwab''s Castle Dungeon at level 65');
INSERT INTO recurring_hunter_contracts VALUES(4473,1,9166,96,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4473,1,4913,E'wakemu.modulox.boss.4913');
INSERT INTO recurring_hunter_rewards VALUES(4473,1,8347,17,NULL,3000,false);
INSERT INTO recurring_hunter_rewards VALUES(4473,1,8348,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4473,1,4913,151,E'native_dungeon_151',2,3,685,96,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'123a1b0512a4d89af4aebd07bc79ee549f139cfbbe6adf40d08ac0a62b660dc0',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8347,8348],95,3972,10019,E'GetRealLevel() >= 96\r\nand GetAchievementCategoryRunningCount(685) < 1\r\nand GetAchievementCategoryCount(685) == GetAchievementCategoryCanBeResetCount(685)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4473)',E'GetRealLevel() >= 96',E'Complete the Abandoned Scarapit Dungeon at level 95');
INSERT INTO recurring_hunter_contracts VALUES(4476,1,9170,141,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4476,1,4720,E'wakemu.modulox.boss.4720');
INSERT INTO recurring_hunter_rewards VALUES(4476,1,8354,17,NULL,3000,false);
INSERT INTO recurring_hunter_rewards VALUES(4476,1,8355,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4476,1,4720,142,E'native_dungeon_142',3,2,686,141,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'4253c0cb5056166b656a51634b7475463aef34c7c6768cc8d88c59c432ad4f71',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8354,8355],125,3972,10020,E'GetRealLevel() >= 141\r\nand GetAchievementCategoryRunningCount(686) < 1\r\nand GetAchievementCategoryCount(686) == GetAchievementCategoryCanBeResetCount(686)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4476)',E'GetRealLevel() >= 141',E'Complete the Puddly Dungeon at level 125');
INSERT INTO recurring_hunter_contracts VALUES(4479,1,9173,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4479,1,4780,E'wakemu.modulox.boss.4780');
INSERT INTO recurring_hunter_rewards VALUES(4479,1,8360,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4479,1,8361,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4479,1,4780,152,E'native_dungeon_152',3,4,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'863b8f0da80ca22adc61221977281ce5aa17d51c80f926712ae69667f6f7df7f',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8360,8361],155,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4479)',E'GetRealLevel() >= 186',E'Complete the Blopera Dungeon at level 155');
INSERT INTO recurring_hunter_contracts VALUES(4480,1,9174,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4480,1,4538,E'wakemu.modulox.boss.4538');
INSERT INTO recurring_hunter_rewards VALUES(4480,1,8362,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4480,1,8363,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4480,1,4538,139,E'native_dungeon_139',2,4,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'21b2266795b0fb22f82a65f8202864f7b3b2454517587862995398611ca1ea0d',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8362,8363],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4480)',E'GetRealLevel() >= 186',E'Complete the Elite Riktus Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4482,1,9176,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4482,1,4924,E'wakemu.modulox.boss.4924');
INSERT INTO recurring_hunter_rewards VALUES(4482,1,8366,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4482,1,8367,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4482,1,4924,149,E'native_dungeon_149',3,8,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'563a79cc984fd3e556f2ba822b86af180e7ae47ebd6a12a906fca7f6c88ba577',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8366,8367],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4482)',E'GetRealLevel() >= 186',E'Complete the Zeppelantern Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4483,1,9177,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4483,1,4923,E'wakemu.modulox.boss.4923');
INSERT INTO recurring_hunter_rewards VALUES(4483,1,8368,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4483,1,8369,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4483,1,4923,153,E'native_dungeon_153',3,4,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'956692a4fbe68921f808ca22eb8787689956d18c73a4d9f2d9e4f2339cc6126e',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8368,8369],170,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4483)',E'GetRealLevel() >= 186',E'Complete the Stalagmotel Dungeon at level 170');
INSERT INTO recurring_hunter_contracts VALUES(4652,1,9567,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4652,1,5040,E'wakemu.modulox.boss.5040');
INSERT INTO recurring_hunter_rewards VALUES(4652,1,8726,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4652,1,8727,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4652,1,5040,154,E'native_dungeon_154',3,3,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'06d18b9815cc531b9ccba4db7bf5304c0649070d5a72a57d0b7d97e1043faae9',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8726,8727],155,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4652)',E'GetRealLevel() >= 186',E'Complete the Wellspring of Evil Dungeon at level 155');
INSERT INTO recurring_hunter_contracts VALUES(4653,1,9568,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4653,1,5046,E'wakemu.modulox.boss.5046');
INSERT INTO recurring_hunter_rewards VALUES(4653,1,8728,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4653,1,8729,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4653,1,5046,155,E'native_dungeon_155',2,1,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'ac3e26af2a1b216d609a40483d5651816bb438157999b3b8395237a9c4fca0cb',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8728,8729],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4653)',E'GetRealLevel() >= 186',E'Complete the Forbidden City Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4731,1,9833,186,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4731,1,5131,E'wakemu.modulox.boss.5131');
INSERT INTO recurring_hunter_rewards VALUES(4731,1,8876,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4731,1,8877,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4731,1,5131,158,E'native_dungeon_158',3,3,687,186,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'f3cf9348f36eaa48de48c3855ce3f8d48c1e1148370cbee568bf021807ba4946',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8876,8877],185,3972,10441,E'GetRealLevel() >= 186\r\nand GetAchievementCategoryRunningCount(687) < 1\r\nand GetAchievementCategoryCount(687) == GetAchievementCategoryCanBeResetCount(687)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4731)',E'GetRealLevel() >= 186',E'Complete the Gerbean Dungeon at level 185');
INSERT INTO recurring_hunter_contracts VALUES(4788,1,9925,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4788,1,4327,E'wakemu.modulox.boss.4327');
INSERT INTO recurring_hunter_rewards VALUES(4788,1,8983,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4788,1,8984,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4788,1,4327,127,E'native_dungeon_127',3,3,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'd75bd37c93968b2b9ba3c278cf9905a99f70d511f817a439b33f75a33dd17cd7',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8983,8984],200,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4788)',E'GetRealLevel() >= 231',E'Complete the Or''Hodruin Volcano Dungeon at level 200');
INSERT INTO recurring_hunter_contracts VALUES(4790,1,9927,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4790,1,4260,E'wakemu.modulox.boss.4260');
INSERT INTO recurring_hunter_rewards VALUES(4790,1,8987,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4790,1,8988,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4790,1,4260,128,E'native_dungeon_128',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'ad94cc4e58cf9bf3b8ff55e6e3c9218bef93c70e14d9fdffa5f08e0f9b97cf10',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8987,8988],200,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4790)',E'GetRealLevel() >= 231',E'Complete the Iced-Over Crest Dungeon at level 200');
INSERT INTO recurring_hunter_contracts VALUES(4791,1,9928,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4791,1,5052,E'wakemu.modulox.boss.5052');
INSERT INTO recurring_hunter_rewards VALUES(4791,1,8989,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4791,1,8990,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4791,1,5052,156,E'native_dungeon_156',3,3,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'd99d45d5cdf8950b1a44bf0b8597c1eba23c5b4051f8eb277a324f6a07b0c2b7',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8989,8990],200,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4791)',E'GetRealLevel() >= 231',E'Complete the Blightopard Canyon Dungeon at level 200');
INSERT INTO recurring_hunter_contracts VALUES(4792,1,9929,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4792,1,5059,E'wakemu.modulox.boss.5059');
INSERT INTO recurring_hunter_rewards VALUES(4792,1,8991,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4792,1,8992,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4792,1,5059,157,E'native_dungeon_157',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'af1646ceaecb20145bfd738925aa80769096c83a82a1c75d27e7223c639a5554',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[8991,8992],200,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4792)',E'GetRealLevel() >= 231',E'Complete the Pandala Tomb Dungeon at level 200');
INSERT INTO recurring_hunter_contracts VALUES(4954,1,10205,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4954,1,5170,E'wakemu.modulox.boss.5170');
INSERT INTO recurring_hunter_rewards VALUES(4954,1,9275,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4954,1,9276,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4954,1,5170,160,E'native_dungeon_160',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'4ddf74a386e1c31c246bf2907dc1c370033520ff8187a440d18dd307918f9fae',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9275,9276],215,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4954)',E'GetRealLevel() >= 231',E'Complete the Vandalophrenic Dungeon at level 215');
INSERT INTO recurring_hunter_contracts VALUES(4956,1,10207,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4956,1,5182,E'wakemu.modulox.boss.5182');
INSERT INTO recurring_hunter_rewards VALUES(4956,1,9279,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4956,1,9280,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4956,1,5182,162,E'native_dungeon_162',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'45ee9529fd0307fd8c2da8f829576456d573647ee916c11c00cce544dfca7bab',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9279,9280],215,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4956)',E'GetRealLevel() >= 231',E'Complete the Crabstacean Dungeon at level 215');
INSERT INTO recurring_hunter_contracts VALUES(4960,1,10211,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4960,1,5241,E'wakemu.modulox.boss.5241');
INSERT INTO recurring_hunter_rewards VALUES(4960,1,9287,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4960,1,9288,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4960,1,5241,166,E'native_dungeon_166',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'b23998a4158278a855f57d4a565e21ef1dcb30e971e9592592a4567ccbe97bc5',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9287,9288],215,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4960)',E'GetRealLevel() >= 231',E'Complete the Plantiguard Dungeon at level 215');
INSERT INTO recurring_hunter_contracts VALUES(4961,1,10212,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(4961,1,5247,E'wakemu.modulox.boss.5247');
INSERT INTO recurring_hunter_rewards VALUES(4961,1,9289,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(4961,1,9290,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(4961,1,5247,167,E'native_dungeon_167',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'1f2d0ef9522e2da345aefdf42b1c9b7f50e8bdce275ded5b23925d2240fd5a7d',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9289,9290],215,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(4961)',E'GetRealLevel() >= 231',E'Complete the Pingwin Dungeon at level 215');
INSERT INTO recurring_hunter_contracts VALUES(5118,1,10505,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5118,1,5376,E'wakemu.modulox.boss.5376');
INSERT INTO recurring_hunter_rewards VALUES(5118,1,9635,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(5118,1,9636,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5118,1,5376,184,E'native_dungeon_184',3,2,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'22561cd9606d9445bae3a5dc0d855f2695a441dbc48e940cdbfff8d4c9a6f539',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9635,9636],50,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5118)',E'GetRealLevel() >= 50',E'Complete the Octopus Crew Dungeon at level 50');
INSERT INTO recurring_hunter_contracts VALUES(5119,1,10506,51,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5119,1,5382,E'wakemu.modulox.boss.5382');
INSERT INTO recurring_hunter_rewards VALUES(5119,1,9637,17,NULL,1000,false);
INSERT INTO recurring_hunter_rewards VALUES(5119,1,9638,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5119,1,5382,185,E'native_dungeon_185',3,3,684,51,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'a02811771aa044bbf968548808596cbf7f7d1a8d0d2fb7637c13733fa700a503',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[9637,9638],50,3972,10124,E'GetRealLevel() >= 51\r\nand GetAchievementCategoryRunningCount(684) < 1\r\nand GetAchievementCategoryCount(684) == GetAchievementCategoryCanBeResetCount(684)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',true,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5119)',E'GetRealLevel() >= 50',E'Complete the Deathburn Dungeon at level 50');
INSERT INTO recurring_hunter_contracts VALUES(5387,1,11097,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5387,1,5277,E'wakemu.modulox.boss.5277');
INSERT INTO recurring_hunter_rewards VALUES(5387,1,10063,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5387,1,10064,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5387,1,5277,176,E'native_dungeon_176',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'f707f6853260777967cb9423456adb16d7bb5c3a1b46db68a09199d67f3dada3',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10063,10064],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5387)',E'GetRealLevel() >= 231',E'Complete the Phytomorph Dungeon at level 230');
INSERT INTO recurring_hunter_contracts VALUES(5388,1,11098,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5388,1,5283,E'wakemu.modulox.boss.5283');
INSERT INTO recurring_hunter_rewards VALUES(5388,1,10065,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5388,1,10066,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5388,1,5283,177,E'native_dungeon_177',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'5bcb1c168412ad06234643643255b84c47f9c80d75d0e20ede5cbc96b187ac55',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10065,10066],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5388)',E'GetRealLevel() >= 231',E'Complete the Voidivion Dungeon at level 230');
INSERT INTO recurring_hunter_contracts VALUES(5389,1,11099,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5389,1,5289,E'wakemu.modulox.boss.5289');
INSERT INTO recurring_hunter_rewards VALUES(5389,1,10067,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5389,1,10068,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5389,1,5289,178,E'native_dungeon_178',3,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'9bced4a2a99a3f5e1e8e56fa01b75253b7c0de6b4b9bce7d7d847d93b0531fdd',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10067,10068],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5389)',E'GetRealLevel() >= 231',E'Complete the Horridemon Dungeon at level 230');
INSERT INTO recurring_hunter_contracts VALUES(5390,1,11100,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5390,1,5295,E'wakemu.modulox.boss.5295');
INSERT INTO recurring_hunter_rewards VALUES(5390,1,10069,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5390,1,10070,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5390,1,5295,179,E'native_dungeon_179',2,2,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'b027b02490f2e5cf1f78ad457253ab23ac18c5ac40e2f6307bcf7a12d289f384',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10069,10070],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5390)',E'GetRealLevel() >= 231',E'Complete the Streye Dungeon at level 230');
INSERT INTO recurring_hunter_contracts VALUES(5393,1,11103,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5393,1,5400,E'wakemu.modulox.boss.5400');
INSERT INTO recurring_hunter_rewards VALUES(5393,1,10075,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5393,1,10076,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5393,1,5400,188,E'native_dungeon_188',3,4,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'a19b01956d54ff551d4e5e6849fc86e3960089a183001ef4f2019224ca6eb30a',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10075,10076],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5393)',E'GetRealLevel() >= 231',E'Complete the Foggernaut Dungeon at level 230');
INSERT INTO recurring_hunter_contracts VALUES(5394,1,11104,231,1,1475452800000,86400000,0,E'wakemu.modulox-native-adjusted-final-room-v1',E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room');
INSERT INTO recurring_hunter_targets VALUES(5394,1,5394,E'wakemu.modulox.boss.5394');
INSERT INTO recurring_hunter_rewards VALUES(5394,1,10077,17,NULL,4000,false);
INSERT INTO recurring_hunter_rewards VALUES(5394,1,10078,5,20752,2,false);
INSERT INTO recurring_modulox_authority VALUES(5394,1,5394,187,E'native_dungeon_187',2,3,810,231,E'native-definition+original-node3972-offer-maximum',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'monsters.json',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4',E'37d0606781705537a3e1f01ae7bce19c00abd5cde053ffa5160fefa9c784630d',E'wakemu.modulox-native-adjusted-final-room-v1',E'native17-frozen-real-level-no-subscription',ARRAY[10077,10078],230,3972,11972,E'GetRealLevel() >= 231\r\nand GetAchievementCategoryRunningCount(810) < 1\r\nand GetAchievementCategoryCount(810) == GetAchievementCategoryCanBeResetCount(810)',E'f5b5134f81c5f736d49409357ac9a97efda3720372751dc786b9d62001fa2ca4',false,E'explicit-Wakemu-native-objective+bilingual-boss+original-aKU+current-final-room',E'IsAchievementRunning(5394)',E'GetRealLevel() >= 231',E'Complete the Abyssal Creeper Dungeon at level 230');
INSERT INTO recurring_hunter_daily_pools VALUES(E'wakemu.daily-hunter45-modulox54-v1',E'wakemu.daily-hunter-utc-sorted-rotation-v1',E'd10ef77dfcc66a1c22e8df7d6c7f21482e21e3fe58ff90e8bb2076e980f12ea0',false);
INSERT INTO recurring_hunter_daily_members SELECT E'wakemu.daily-hunter45-modulox54-v1',category_id,definition_id,version FROM recurring_hunter_daily_members WHERE pool_version=E'wakemu.daily-hunter-qualified45-v1';
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4062,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4063,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4064,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4066,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4067,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4068,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4075,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4085,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4086,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4089,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4090,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4096,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4097,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4098,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4100,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4105,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',686,4116,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',686,4123,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4132,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4133,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4134,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4135,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4136,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4137,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4138,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4226,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,4465,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4467,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4468,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',685,4473,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',686,4476,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4479,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4480,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4482,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4483,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4652,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4653,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',687,4731,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4788,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4790,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4791,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4792,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4954,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4956,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4960,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,4961,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,5118,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',684,5119,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5387,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5388,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5389,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5390,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5393,1);
INSERT INTO recurring_hunter_daily_members VALUES(E'wakemu.daily-hunter45-modulox54-v1',810,5394,1);
UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version=E'wakemu.daily-hunter45-modulox54-v1';
UPDATE recurring_hunter_daily_active SET pool_version=E'wakemu.daily-hunter45-modulox54-v1',enabled=false WHERE singleton;
