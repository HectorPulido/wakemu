-- Generated disabled profiles only; no activation or real DB mutation is performed by the compiler.
-- Requires source275, original locations278, original actions280 and runtime274.
-- Placement281 and regional scheduling282 must be supplied separately before activation.
BEGIN;
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1953 AND map_id=1276 AND region_id=89901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1953-1276-89901',1,-1953,E'resource_collect',E'collaborative',1276,89901,900000,NULL,0,201,245,5,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0e27212e264e9acee14b03ddf761a816642a6add6ae6007fd1a925900130ea11',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1953-1276-89901',1,E'resource',E'resource_collect',757,2118,2,E'interaction',100);
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1953-1276-89901',1,0,E'item',27886,12,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1953-1276-89901',1,1,E'xp',NULL,96703975,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1949 AND map_id=1276 AND region_id=89901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1949-1276-89901',1,-1949,E'resource_collect',E'competitive',1276,89901,600000,NULL,0,201,245,10,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'588b736d2d9dce46024d8431337205fe2e02b9fb38158e8686e9c3750061d0b1',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1949-1276-89901',1,E'resource',E'resource_collect',757,2118,2,E'interaction',10);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1949-1276-89901',1,E'score_at_deadline',2,E'character_id',E'wakemu.resource-competition-top-two-ranks.v1;original-rank-conditions;all-eligible-fallback;character-id-ties');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,E'wakemu.original-resource-rank-bands-base-rewards.v1',E'all_eligible',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,0,2954,1,1),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,1,2955,2,2),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,2,2956,NULL,NULL);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1945 AND map_id=1276 AND region_id=89901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1945-1276-89901',1,-1945,E'resource_collect',E'race',1276,89901,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'766529d12c33d703eaebecbfcc6c48c04046f241ac2ccc5afb103d988efdf0b5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1945-1276-89901',1,E'resource',E'resource_collect',757,2118,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1945-1276-89901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1945-1276-89901',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1945-1276-89901',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1941 AND map_id=1276 AND region_id=89901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1941-1276-89901',1,-1941,E'resource_collect',E'solo',1276,89901,600000,NULL,0,201,245,10,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'600b839af3af47db71469080745f943a2a4c524279cefabaacbc408f59318de3',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1941-1276-89901',1,E'resource',E'resource_collect',757,2118,2,E'interaction',10);
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1941-1276-89901',1,0,E'item',27886,3,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1941-1276-89901',1,1,E'xp',NULL,19684191,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');

INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1953-1276-89901',1,-1953,0,391,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1953-1276-89901',1,E'proposed',0),
(E'resource-native-1953-1276-89901',1,E'active',1),
(E'resource-native-1953-1276-89901',1,E'completed',2),
(E'resource-native-1953-1276-89901',1,E'expired',2),
(E'resource-native-1953-1276-89901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',5,NULL,NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,5,E'nbResourceMin',E'declared_threshold',NULL,E'nbresourceforreward',5,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,6,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,7,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1953-1276-89901',1,0,-72,-110,-1),
(E'resource-native-1953-1276-89901',1,1,-72,-109,-1),
(E'resource-native-1953-1276-89901',1,2,-72,-108,-1),
(E'resource-native-1953-1276-89901',1,3,-71,-110,-2),
(E'resource-native-1953-1276-89901',1,4,-71,-109,-2),
(E'resource-native-1953-1276-89901',1,5,-71,-108,-2),
(E'resource-native-1953-1276-89901',1,6,-70,-110,-2),
(E'resource-native-1953-1276-89901',1,7,-70,-109,-2),
(E'resource-native-1953-1276-89901',1,8,-70,-108,-2),
(E'resource-native-1953-1276-89901',1,9,-69,-110,-3),
(E'resource-native-1953-1276-89901',1,10,-69,-109,-3),
(E'resource-native-1953-1276-89901',1,11,-69,-108,-3),
(E'resource-native-1953-1276-89901',1,12,-68,-110,-3),
(E'resource-native-1953-1276-89901',1,13,-68,-109,-3),
(E'resource-native-1953-1276-89901',1,14,-68,-108,-3),
(E'resource-native-1953-1276-89901',1,15,-67,-110,-4),
(E'resource-native-1953-1276-89901',1,16,-67,-109,-4),
(E'resource-native-1953-1276-89901',1,17,-67,-108,-4),
(E'resource-native-1953-1276-89901',1,18,-66,-110,-4),
(E'resource-native-1953-1276-89901',1,19,-66,-109,-4),
(E'resource-native-1953-1276-89901',1,20,-66,-108,-4),
(E'resource-native-1953-1276-89901',1,21,-65,-110,-4),
(E'resource-native-1953-1276-89901',1,22,-65,-109,-4),
(E'resource-native-1953-1276-89901',1,23,-65,-108,-4),
(E'resource-native-1953-1276-89901',1,24,-64,-110,-4),
(E'resource-native-1953-1276-89901',1,25,-64,-109,-4),
(E'resource-native-1953-1276-89901',1,26,-64,-108,-4),
(E'resource-native-1953-1276-89901',1,27,-63,-110,-4),
(E'resource-native-1953-1276-89901',1,28,-63,-109,-4),
(E'resource-native-1953-1276-89901',1,29,-63,-108,-4),
(E'resource-native-1953-1276-89901',1,30,-62,-110,-4),
(E'resource-native-1953-1276-89901',1,31,-62,-109,-4),
(E'resource-native-1953-1276-89901',1,32,-62,-108,-4),
(E'resource-native-1953-1276-89901',1,33,-61,-110,-4),
(E'resource-native-1953-1276-89901',1,34,-61,-109,-4),
(E'resource-native-1953-1276-89901',1,35,-61,-108,-4),
(E'resource-native-1953-1276-89901',1,36,-60,-110,-4),
(E'resource-native-1953-1276-89901',1,37,-60,-109,-4),
(E'resource-native-1953-1276-89901',1,38,-60,-108,-4),
(E'resource-native-1953-1276-89901',1,39,-59,-110,-3),
(E'resource-native-1953-1276-89901',1,40,-59,-109,-3),
(E'resource-native-1953-1276-89901',1,41,-59,-108,-3),
(E'resource-native-1953-1276-89901',1,42,-58,-110,-3),
(E'resource-native-1953-1276-89901',1,43,-58,-109,-3),
(E'resource-native-1953-1276-89901',1,44,-58,-108,-3),
(E'resource-native-1953-1276-89901',1,45,-57,-110,-2),
(E'resource-native-1953-1276-89901',1,46,-57,-109,-2),
(E'resource-native-1953-1276-89901',1,47,-57,-108,-2),
(E'resource-native-1953-1276-89901',1,48,-56,-110,-2),
(E'resource-native-1953-1276-89901',1,49,-56,-109,-2),
(E'resource-native-1953-1276-89901',1,50,-56,-108,-2),
(E'resource-native-1953-1276-89901',1,51,-55,-110,-1),
(E'resource-native-1953-1276-89901',1,52,-55,-109,-1),
(E'resource-native-1953-1276-89901',1,53,-55,-108,-1),
(E'resource-native-1953-1276-89901',1,54,-54,-115,0),
(E'resource-native-1953-1276-89901',1,55,-54,-114,2),
(E'resource-native-1953-1276-89901',1,56,-54,-110,0),
(E'resource-native-1953-1276-89901',1,57,-54,-109,0),
(E'resource-native-1953-1276-89901',1,58,-54,-108,0),
(E'resource-native-1953-1276-89901',1,59,-53,-115,0),
(E'resource-native-1953-1276-89901',1,60,-53,-114,0),
(E'resource-native-1953-1276-89901',1,61,-53,-113,0),
(E'resource-native-1953-1276-89901',1,62,-53,-110,0),
(E'resource-native-1953-1276-89901',1,63,-53,-109,0),
(E'resource-native-1953-1276-89901',1,64,-53,-108,0),
(E'resource-native-1953-1276-89901',1,65,-53,-105,0),
(E'resource-native-1953-1276-89901',1,66,-53,-104,0),
(E'resource-native-1953-1276-89901',1,67,-53,-103,-2),
(E'resource-native-1953-1276-89901',1,68,-52,-115,0),
(E'resource-native-1953-1276-89901',1,69,-52,-114,0),
(E'resource-native-1953-1276-89901',1,70,-52,-113,0),
(E'resource-native-1953-1276-89901',1,71,-52,-112,0),
(E'resource-native-1953-1276-89901',1,72,-52,-110,0),
(E'resource-native-1953-1276-89901',1,73,-52,-109,0),
(E'resource-native-1953-1276-89901',1,74,-52,-108,0),
(E'resource-native-1953-1276-89901',1,75,-52,-107,0),
(E'resource-native-1953-1276-89901',1,76,-52,-105,0),
(E'resource-native-1953-1276-89901',1,77,-52,-104,0),
(E'resource-native-1953-1276-89901',1,78,-52,-103,0),
(E'resource-native-1953-1276-89901',1,79,-51,-116,0),
(E'resource-native-1953-1276-89901',1,80,-51,-115,0),
(E'resource-native-1953-1276-89901',1,81,-51,-114,0),
(E'resource-native-1953-1276-89901',1,82,-51,-113,0),
(E'resource-native-1953-1276-89901',1,83,-51,-112,0),
(E'resource-native-1953-1276-89901',1,84,-51,-111,0),
(E'resource-native-1953-1276-89901',1,85,-51,-110,0),
(E'resource-native-1953-1276-89901',1,86,-51,-109,0),
(E'resource-native-1953-1276-89901',1,87,-51,-108,0),
(E'resource-native-1953-1276-89901',1,88,-51,-107,0),
(E'resource-native-1953-1276-89901',1,89,-51,-106,0),
(E'resource-native-1953-1276-89901',1,90,-51,-105,0),
(E'resource-native-1953-1276-89901',1,91,-51,-104,0),
(E'resource-native-1953-1276-89901',1,92,-51,-103,0),
(E'resource-native-1953-1276-89901',1,93,-51,-102,0),
(E'resource-native-1953-1276-89901',1,94,-50,-116,0),
(E'resource-native-1953-1276-89901',1,95,-50,-115,0),
(E'resource-native-1953-1276-89901',1,96,-50,-114,0),
(E'resource-native-1953-1276-89901',1,97,-50,-113,0),
(E'resource-native-1953-1276-89901',1,98,-50,-112,0),
(E'resource-native-1953-1276-89901',1,99,-50,-111,0),
(E'resource-native-1953-1276-89901',1,100,-50,-110,0),
(E'resource-native-1953-1276-89901',1,101,-50,-109,0),
(E'resource-native-1953-1276-89901',1,102,-50,-108,0),
(E'resource-native-1953-1276-89901',1,103,-50,-107,0),
(E'resource-native-1953-1276-89901',1,104,-50,-106,0),
(E'resource-native-1953-1276-89901',1,105,-50,-105,0),
(E'resource-native-1953-1276-89901',1,106,-50,-104,0),
(E'resource-native-1953-1276-89901',1,107,-50,-103,0),
(E'resource-native-1953-1276-89901',1,108,-50,-102,2),
(E'resource-native-1953-1276-89901',1,109,-50,-101,2),
(E'resource-native-1953-1276-89901',1,110,-49,-116,0),
(E'resource-native-1953-1276-89901',1,111,-49,-115,0),
(E'resource-native-1953-1276-89901',1,112,-49,-114,0),
(E'resource-native-1953-1276-89901',1,113,-49,-113,0),
(E'resource-native-1953-1276-89901',1,114,-49,-112,0),
(E'resource-native-1953-1276-89901',1,115,-49,-111,0),
(E'resource-native-1953-1276-89901',1,116,-49,-110,0),
(E'resource-native-1953-1276-89901',1,117,-49,-109,0),
(E'resource-native-1953-1276-89901',1,118,-49,-108,0),
(E'resource-native-1953-1276-89901',1,119,-49,-107,0),
(E'resource-native-1953-1276-89901',1,120,-49,-106,0),
(E'resource-native-1953-1276-89901',1,121,-49,-105,0),
(E'resource-native-1953-1276-89901',1,122,-49,-104,0),
(E'resource-native-1953-1276-89901',1,123,-49,-103,0),
(E'resource-native-1953-1276-89901',1,124,-49,-102,0),
(E'resource-native-1953-1276-89901',1,125,-48,-116,2),
(E'resource-native-1953-1276-89901',1,126,-48,-113,0),
(E'resource-native-1953-1276-89901',1,127,-48,-112,0),
(E'resource-native-1953-1276-89901',1,128,-48,-111,0),
(E'resource-native-1953-1276-89901',1,129,-48,-110,0),
(E'resource-native-1953-1276-89901',1,130,-48,-109,0),
(E'resource-native-1953-1276-89901',1,131,-48,-108,0),
(E'resource-native-1953-1276-89901',1,132,-48,-107,0),
(E'resource-native-1953-1276-89901',1,133,-48,-106,0),
(E'resource-native-1953-1276-89901',1,134,-48,-105,0),
(E'resource-native-1953-1276-89901',1,135,-48,-104,0),
(E'resource-native-1953-1276-89901',1,136,-48,-103,0),
(E'resource-native-1953-1276-89901',1,137,-48,-102,0),
(E'resource-native-1953-1276-89901',1,138,-47,-114,0),
(E'resource-native-1953-1276-89901',1,139,-47,-113,0),
(E'resource-native-1953-1276-89901',1,140,-47,-112,0),
(E'resource-native-1953-1276-89901',1,141,-47,-111,0),
(E'resource-native-1953-1276-89901',1,142,-47,-110,0),
(E'resource-native-1953-1276-89901',1,143,-47,-109,0),
(E'resource-native-1953-1276-89901',1,144,-47,-108,0),
(E'resource-native-1953-1276-89901',1,145,-47,-107,0),
(E'resource-native-1953-1276-89901',1,146,-47,-106,0),
(E'resource-native-1953-1276-89901',1,147,-47,-105,0),
(E'resource-native-1953-1276-89901',1,148,-47,-103,0),
(E'resource-native-1953-1276-89901',1,149,-47,-102,0),
(E'resource-native-1953-1276-89901',1,150,-46,-115,0),
(E'resource-native-1953-1276-89901',1,151,-46,-114,0),
(E'resource-native-1953-1276-89901',1,152,-46,-113,0),
(E'resource-native-1953-1276-89901',1,153,-46,-112,0),
(E'resource-native-1953-1276-89901',1,154,-46,-111,0),
(E'resource-native-1953-1276-89901',1,155,-46,-110,0),
(E'resource-native-1953-1276-89901',1,156,-46,-109,0),
(E'resource-native-1953-1276-89901',1,157,-46,-108,0),
(E'resource-native-1953-1276-89901',1,158,-46,-107,0),
(E'resource-native-1953-1276-89901',1,159,-46,-106,0),
(E'resource-native-1953-1276-89901',1,160,-46,-105,0),
(E'resource-native-1953-1276-89901',1,161,-46,-103,0),
(E'resource-native-1953-1276-89901',1,162,-45,-115,-2),
(E'resource-native-1953-1276-89901',1,163,-45,-114,0),
(E'resource-native-1953-1276-89901',1,164,-45,-113,0),
(E'resource-native-1953-1276-89901',1,165,-45,-112,0),
(E'resource-native-1953-1276-89901',1,166,-45,-111,0),
(E'resource-native-1953-1276-89901',1,167,-45,-110,0),
(E'resource-native-1953-1276-89901',1,168,-45,-109,0),
(E'resource-native-1953-1276-89901',1,169,-45,-108,0),
(E'resource-native-1953-1276-89901',1,170,-45,-107,0),
(E'resource-native-1953-1276-89901',1,171,-45,-106,0),
(E'resource-native-1953-1276-89901',1,172,-45,-105,0),
(E'resource-native-1953-1276-89901',1,173,-45,-104,0),
(E'resource-native-1953-1276-89901',1,174,-44,-115,-2),
(E'resource-native-1953-1276-89901',1,175,-44,-111,0),
(E'resource-native-1953-1276-89901',1,176,-44,-110,0),
(E'resource-native-1953-1276-89901',1,177,-44,-109,0),
(E'resource-native-1953-1276-89901',1,178,-44,-108,0),
(E'resource-native-1953-1276-89901',1,179,-44,-107,0),
(E'resource-native-1953-1276-89901',1,180,-44,-106,0),
(E'resource-native-1953-1276-89901',1,181,-44,-105,0),
(E'resource-native-1953-1276-89901',1,182,-44,-104,0),
(E'resource-native-1953-1276-89901',1,183,-43,-110,0),
(E'resource-native-1953-1276-89901',1,184,-43,-109,0),
(E'resource-native-1953-1276-89901',1,185,-43,-108,0),
(E'resource-native-1953-1276-89901',1,186,-43,-106,0),
(E'resource-native-1953-1276-89901',1,187,-43,-105,-2),
(E'resource-native-1953-1276-89901',1,188,-42,-110,0),
(E'resource-native-1953-1276-89901',1,189,-42,-109,0),
(E'resource-native-1953-1276-89901',1,190,-42,-108,0),
(E'resource-native-1953-1276-89901',1,191,-41,-110,-1),
(E'resource-native-1953-1276-89901',1,192,-41,-109,-1),
(E'resource-native-1953-1276-89901',1,193,-41,-108,-1),
(E'resource-native-1953-1276-89901',1,194,-40,-110,-1),
(E'resource-native-1953-1276-89901',1,195,-40,-109,-1),
(E'resource-native-1953-1276-89901',1,196,-40,-108,-1),
(E'resource-native-1953-1276-89901',1,197,-40,-93,0),
(E'resource-native-1953-1276-89901',1,198,-40,-92,-2),
(E'resource-native-1953-1276-89901',1,199,-39,-110,-1),
(E'resource-native-1953-1276-89901',1,200,-39,-109,-1),
(E'resource-native-1953-1276-89901',1,201,-39,-108,-1),
(E'resource-native-1953-1276-89901',1,202,-39,-92,0),
(E'resource-native-1953-1276-89901',1,203,-38,-110,0),
(E'resource-native-1953-1276-89901',1,204,-38,-109,0),
(E'resource-native-1953-1276-89901',1,205,-38,-108,0),
(E'resource-native-1953-1276-89901',1,206,-38,-101,2),
(E'resource-native-1953-1276-89901',1,207,-38,-99,2),
(E'resource-native-1953-1276-89901',1,208,-38,-97,2),
(E'resource-native-1953-1276-89901',1,209,-38,-96,0),
(E'resource-native-1953-1276-89901',1,210,-38,-94,0),
(E'resource-native-1953-1276-89901',1,211,-38,-93,0),
(E'resource-native-1953-1276-89901',1,212,-38,-92,0),
(E'resource-native-1953-1276-89901',1,213,-38,-91,0),
(E'resource-native-1953-1276-89901',1,214,-37,-110,0),
(E'resource-native-1953-1276-89901',1,215,-37,-109,0),
(E'resource-native-1953-1276-89901',1,216,-37,-108,0),
(E'resource-native-1953-1276-89901',1,217,-37,-105,0),
(E'resource-native-1953-1276-89901',1,218,-37,-104,0),
(E'resource-native-1953-1276-89901',1,219,-37,-102,0),
(E'resource-native-1953-1276-89901',1,220,-37,-101,0),
(E'resource-native-1953-1276-89901',1,221,-37,-100,0),
(E'resource-native-1953-1276-89901',1,222,-37,-99,2),
(E'resource-native-1953-1276-89901',1,223,-37,-98,2),
(E'resource-native-1953-1276-89901',1,224,-37,-97,2),
(E'resource-native-1953-1276-89901',1,225,-37,-96,0),
(E'resource-native-1953-1276-89901',1,226,-37,-94,0),
(E'resource-native-1953-1276-89901',1,227,-37,-93,0),
(E'resource-native-1953-1276-89901',1,228,-37,-92,0),
(E'resource-native-1953-1276-89901',1,229,-37,-91,0),
(E'resource-native-1953-1276-89901',1,230,-36,-111,0),
(E'resource-native-1953-1276-89901',1,231,-36,-110,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1949-1276-89901',1,-1949,0,391,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1949-1276-89901',1,E'proposed',0),
(E'resource-native-1949-1276-89901',1,E'active',1),
(E'resource-native-1949-1276-89901',1,E'completed',2),
(E'resource-native-1949-1276-89901',1,E'expired',2),
(E'resource-native-1949-1276-89901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',10,NULL,NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,5,E'nbResourceMax',E'leader_progress',E'resource',NULL,NULL,E'wakemu.resource-competition-leading-personal-progress.v1;max-not-stock-or-threshold',NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,6,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',-1949,7,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1949-1276-89901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1949-1276-89901',1,0,-72,-110,-1),
(E'resource-native-1949-1276-89901',1,1,-72,-109,-1),
(E'resource-native-1949-1276-89901',1,2,-72,-108,-1),
(E'resource-native-1949-1276-89901',1,3,-71,-110,-2),
(E'resource-native-1949-1276-89901',1,4,-71,-109,-2),
(E'resource-native-1949-1276-89901',1,5,-71,-108,-2),
(E'resource-native-1949-1276-89901',1,6,-70,-110,-2),
(E'resource-native-1949-1276-89901',1,7,-70,-109,-2),
(E'resource-native-1949-1276-89901',1,8,-70,-108,-2),
(E'resource-native-1949-1276-89901',1,9,-69,-110,-3),
(E'resource-native-1949-1276-89901',1,10,-69,-109,-3),
(E'resource-native-1949-1276-89901',1,11,-69,-108,-3),
(E'resource-native-1949-1276-89901',1,12,-68,-110,-3),
(E'resource-native-1949-1276-89901',1,13,-68,-109,-3),
(E'resource-native-1949-1276-89901',1,14,-68,-108,-3),
(E'resource-native-1949-1276-89901',1,15,-67,-110,-4),
(E'resource-native-1949-1276-89901',1,16,-67,-109,-4),
(E'resource-native-1949-1276-89901',1,17,-67,-108,-4),
(E'resource-native-1949-1276-89901',1,18,-66,-110,-4),
(E'resource-native-1949-1276-89901',1,19,-66,-109,-4),
(E'resource-native-1949-1276-89901',1,20,-66,-108,-4),
(E'resource-native-1949-1276-89901',1,21,-65,-110,-4),
(E'resource-native-1949-1276-89901',1,22,-65,-109,-4),
(E'resource-native-1949-1276-89901',1,23,-65,-108,-4),
(E'resource-native-1949-1276-89901',1,24,-64,-110,-4),
(E'resource-native-1949-1276-89901',1,25,-64,-109,-4),
(E'resource-native-1949-1276-89901',1,26,-64,-108,-4),
(E'resource-native-1949-1276-89901',1,27,-63,-110,-4),
(E'resource-native-1949-1276-89901',1,28,-63,-109,-4),
(E'resource-native-1949-1276-89901',1,29,-63,-108,-4),
(E'resource-native-1949-1276-89901',1,30,-62,-110,-4),
(E'resource-native-1949-1276-89901',1,31,-62,-109,-4),
(E'resource-native-1949-1276-89901',1,32,-62,-108,-4),
(E'resource-native-1949-1276-89901',1,33,-61,-110,-4),
(E'resource-native-1949-1276-89901',1,34,-61,-109,-4),
(E'resource-native-1949-1276-89901',1,35,-61,-108,-4),
(E'resource-native-1949-1276-89901',1,36,-60,-110,-4),
(E'resource-native-1949-1276-89901',1,37,-60,-109,-4),
(E'resource-native-1949-1276-89901',1,38,-60,-108,-4),
(E'resource-native-1949-1276-89901',1,39,-59,-110,-3),
(E'resource-native-1949-1276-89901',1,40,-59,-109,-3),
(E'resource-native-1949-1276-89901',1,41,-59,-108,-3),
(E'resource-native-1949-1276-89901',1,42,-58,-110,-3),
(E'resource-native-1949-1276-89901',1,43,-58,-109,-3),
(E'resource-native-1949-1276-89901',1,44,-58,-108,-3),
(E'resource-native-1949-1276-89901',1,45,-57,-110,-2),
(E'resource-native-1949-1276-89901',1,46,-57,-109,-2),
(E'resource-native-1949-1276-89901',1,47,-57,-108,-2),
(E'resource-native-1949-1276-89901',1,48,-56,-110,-2),
(E'resource-native-1949-1276-89901',1,49,-56,-109,-2),
(E'resource-native-1949-1276-89901',1,50,-56,-108,-2),
(E'resource-native-1949-1276-89901',1,51,-55,-110,-1),
(E'resource-native-1949-1276-89901',1,52,-55,-109,-1),
(E'resource-native-1949-1276-89901',1,53,-55,-108,-1),
(E'resource-native-1949-1276-89901',1,54,-54,-115,0),
(E'resource-native-1949-1276-89901',1,55,-54,-114,2),
(E'resource-native-1949-1276-89901',1,56,-54,-110,0),
(E'resource-native-1949-1276-89901',1,57,-54,-109,0),
(E'resource-native-1949-1276-89901',1,58,-54,-108,0),
(E'resource-native-1949-1276-89901',1,59,-53,-115,0),
(E'resource-native-1949-1276-89901',1,60,-53,-114,0),
(E'resource-native-1949-1276-89901',1,61,-53,-113,0),
(E'resource-native-1949-1276-89901',1,62,-53,-110,0),
(E'resource-native-1949-1276-89901',1,63,-53,-109,0),
(E'resource-native-1949-1276-89901',1,64,-53,-108,0),
(E'resource-native-1949-1276-89901',1,65,-53,-105,0),
(E'resource-native-1949-1276-89901',1,66,-53,-104,0),
(E'resource-native-1949-1276-89901',1,67,-53,-103,-2),
(E'resource-native-1949-1276-89901',1,68,-52,-115,0),
(E'resource-native-1949-1276-89901',1,69,-52,-114,0),
(E'resource-native-1949-1276-89901',1,70,-52,-113,0),
(E'resource-native-1949-1276-89901',1,71,-52,-112,0),
(E'resource-native-1949-1276-89901',1,72,-52,-110,0),
(E'resource-native-1949-1276-89901',1,73,-52,-109,0),
(E'resource-native-1949-1276-89901',1,74,-52,-108,0),
(E'resource-native-1949-1276-89901',1,75,-52,-107,0),
(E'resource-native-1949-1276-89901',1,76,-52,-105,0),
(E'resource-native-1949-1276-89901',1,77,-52,-104,0),
(E'resource-native-1949-1276-89901',1,78,-52,-103,0),
(E'resource-native-1949-1276-89901',1,79,-51,-116,0),
(E'resource-native-1949-1276-89901',1,80,-51,-115,0),
(E'resource-native-1949-1276-89901',1,81,-51,-114,0),
(E'resource-native-1949-1276-89901',1,82,-51,-113,0),
(E'resource-native-1949-1276-89901',1,83,-51,-112,0),
(E'resource-native-1949-1276-89901',1,84,-51,-111,0),
(E'resource-native-1949-1276-89901',1,85,-51,-110,0),
(E'resource-native-1949-1276-89901',1,86,-51,-109,0),
(E'resource-native-1949-1276-89901',1,87,-51,-108,0),
(E'resource-native-1949-1276-89901',1,88,-51,-107,0),
(E'resource-native-1949-1276-89901',1,89,-51,-106,0),
(E'resource-native-1949-1276-89901',1,90,-51,-105,0),
(E'resource-native-1949-1276-89901',1,91,-51,-104,0),
(E'resource-native-1949-1276-89901',1,92,-51,-103,0),
(E'resource-native-1949-1276-89901',1,93,-51,-102,0),
(E'resource-native-1949-1276-89901',1,94,-50,-116,0),
(E'resource-native-1949-1276-89901',1,95,-50,-115,0),
(E'resource-native-1949-1276-89901',1,96,-50,-114,0),
(E'resource-native-1949-1276-89901',1,97,-50,-113,0),
(E'resource-native-1949-1276-89901',1,98,-50,-112,0),
(E'resource-native-1949-1276-89901',1,99,-50,-111,0),
(E'resource-native-1949-1276-89901',1,100,-50,-110,0),
(E'resource-native-1949-1276-89901',1,101,-50,-109,0),
(E'resource-native-1949-1276-89901',1,102,-50,-108,0),
(E'resource-native-1949-1276-89901',1,103,-50,-107,0),
(E'resource-native-1949-1276-89901',1,104,-50,-106,0),
(E'resource-native-1949-1276-89901',1,105,-50,-105,0),
(E'resource-native-1949-1276-89901',1,106,-50,-104,0),
(E'resource-native-1949-1276-89901',1,107,-50,-103,0),
(E'resource-native-1949-1276-89901',1,108,-50,-102,2),
(E'resource-native-1949-1276-89901',1,109,-50,-101,2),
(E'resource-native-1949-1276-89901',1,110,-49,-116,0),
(E'resource-native-1949-1276-89901',1,111,-49,-115,0),
(E'resource-native-1949-1276-89901',1,112,-49,-114,0),
(E'resource-native-1949-1276-89901',1,113,-49,-113,0),
(E'resource-native-1949-1276-89901',1,114,-49,-112,0),
(E'resource-native-1949-1276-89901',1,115,-49,-111,0),
(E'resource-native-1949-1276-89901',1,116,-49,-110,0),
(E'resource-native-1949-1276-89901',1,117,-49,-109,0),
(E'resource-native-1949-1276-89901',1,118,-49,-108,0),
(E'resource-native-1949-1276-89901',1,119,-49,-107,0),
(E'resource-native-1949-1276-89901',1,120,-49,-106,0),
(E'resource-native-1949-1276-89901',1,121,-49,-105,0),
(E'resource-native-1949-1276-89901',1,122,-49,-104,0),
(E'resource-native-1949-1276-89901',1,123,-49,-103,0),
(E'resource-native-1949-1276-89901',1,124,-49,-102,0),
(E'resource-native-1949-1276-89901',1,125,-48,-116,2),
(E'resource-native-1949-1276-89901',1,126,-48,-113,0),
(E'resource-native-1949-1276-89901',1,127,-48,-112,0),
(E'resource-native-1949-1276-89901',1,128,-48,-111,0),
(E'resource-native-1949-1276-89901',1,129,-48,-110,0),
(E'resource-native-1949-1276-89901',1,130,-48,-109,0),
(E'resource-native-1949-1276-89901',1,131,-48,-108,0),
(E'resource-native-1949-1276-89901',1,132,-48,-107,0),
(E'resource-native-1949-1276-89901',1,133,-48,-106,0),
(E'resource-native-1949-1276-89901',1,134,-48,-105,0),
(E'resource-native-1949-1276-89901',1,135,-48,-104,0),
(E'resource-native-1949-1276-89901',1,136,-48,-103,0),
(E'resource-native-1949-1276-89901',1,137,-48,-102,0),
(E'resource-native-1949-1276-89901',1,138,-47,-114,0),
(E'resource-native-1949-1276-89901',1,139,-47,-113,0),
(E'resource-native-1949-1276-89901',1,140,-47,-112,0),
(E'resource-native-1949-1276-89901',1,141,-47,-111,0),
(E'resource-native-1949-1276-89901',1,142,-47,-110,0),
(E'resource-native-1949-1276-89901',1,143,-47,-109,0),
(E'resource-native-1949-1276-89901',1,144,-47,-108,0),
(E'resource-native-1949-1276-89901',1,145,-47,-107,0),
(E'resource-native-1949-1276-89901',1,146,-47,-106,0),
(E'resource-native-1949-1276-89901',1,147,-47,-105,0),
(E'resource-native-1949-1276-89901',1,148,-47,-103,0),
(E'resource-native-1949-1276-89901',1,149,-47,-102,0),
(E'resource-native-1949-1276-89901',1,150,-46,-115,0),
(E'resource-native-1949-1276-89901',1,151,-46,-114,0),
(E'resource-native-1949-1276-89901',1,152,-46,-113,0),
(E'resource-native-1949-1276-89901',1,153,-46,-112,0),
(E'resource-native-1949-1276-89901',1,154,-46,-111,0),
(E'resource-native-1949-1276-89901',1,155,-46,-110,0),
(E'resource-native-1949-1276-89901',1,156,-46,-109,0),
(E'resource-native-1949-1276-89901',1,157,-46,-108,0),
(E'resource-native-1949-1276-89901',1,158,-46,-107,0),
(E'resource-native-1949-1276-89901',1,159,-46,-106,0),
(E'resource-native-1949-1276-89901',1,160,-46,-105,0),
(E'resource-native-1949-1276-89901',1,161,-46,-103,0),
(E'resource-native-1949-1276-89901',1,162,-45,-115,-2),
(E'resource-native-1949-1276-89901',1,163,-45,-114,0),
(E'resource-native-1949-1276-89901',1,164,-45,-113,0),
(E'resource-native-1949-1276-89901',1,165,-45,-112,0),
(E'resource-native-1949-1276-89901',1,166,-45,-111,0),
(E'resource-native-1949-1276-89901',1,167,-45,-110,0),
(E'resource-native-1949-1276-89901',1,168,-45,-109,0),
(E'resource-native-1949-1276-89901',1,169,-45,-108,0),
(E'resource-native-1949-1276-89901',1,170,-45,-107,0),
(E'resource-native-1949-1276-89901',1,171,-45,-106,0),
(E'resource-native-1949-1276-89901',1,172,-45,-105,0),
(E'resource-native-1949-1276-89901',1,173,-45,-104,0),
(E'resource-native-1949-1276-89901',1,174,-44,-115,-2),
(E'resource-native-1949-1276-89901',1,175,-44,-111,0),
(E'resource-native-1949-1276-89901',1,176,-44,-110,0),
(E'resource-native-1949-1276-89901',1,177,-44,-109,0),
(E'resource-native-1949-1276-89901',1,178,-44,-108,0),
(E'resource-native-1949-1276-89901',1,179,-44,-107,0),
(E'resource-native-1949-1276-89901',1,180,-44,-106,0),
(E'resource-native-1949-1276-89901',1,181,-44,-105,0),
(E'resource-native-1949-1276-89901',1,182,-44,-104,0),
(E'resource-native-1949-1276-89901',1,183,-43,-110,0),
(E'resource-native-1949-1276-89901',1,184,-43,-109,0),
(E'resource-native-1949-1276-89901',1,185,-43,-108,0),
(E'resource-native-1949-1276-89901',1,186,-43,-106,0),
(E'resource-native-1949-1276-89901',1,187,-43,-105,-2),
(E'resource-native-1949-1276-89901',1,188,-42,-110,0),
(E'resource-native-1949-1276-89901',1,189,-42,-109,0),
(E'resource-native-1949-1276-89901',1,190,-42,-108,0),
(E'resource-native-1949-1276-89901',1,191,-41,-110,-1),
(E'resource-native-1949-1276-89901',1,192,-41,-109,-1),
(E'resource-native-1949-1276-89901',1,193,-41,-108,-1),
(E'resource-native-1949-1276-89901',1,194,-40,-110,-1),
(E'resource-native-1949-1276-89901',1,195,-40,-109,-1),
(E'resource-native-1949-1276-89901',1,196,-40,-108,-1),
(E'resource-native-1949-1276-89901',1,197,-40,-93,0),
(E'resource-native-1949-1276-89901',1,198,-40,-92,-2),
(E'resource-native-1949-1276-89901',1,199,-39,-110,-1),
(E'resource-native-1949-1276-89901',1,200,-39,-109,-1),
(E'resource-native-1949-1276-89901',1,201,-39,-108,-1),
(E'resource-native-1949-1276-89901',1,202,-39,-92,0),
(E'resource-native-1949-1276-89901',1,203,-38,-110,0),
(E'resource-native-1949-1276-89901',1,204,-38,-109,0),
(E'resource-native-1949-1276-89901',1,205,-38,-108,0),
(E'resource-native-1949-1276-89901',1,206,-38,-101,2),
(E'resource-native-1949-1276-89901',1,207,-38,-99,2),
(E'resource-native-1949-1276-89901',1,208,-38,-97,2),
(E'resource-native-1949-1276-89901',1,209,-38,-96,0),
(E'resource-native-1949-1276-89901',1,210,-38,-94,0),
(E'resource-native-1949-1276-89901',1,211,-38,-93,0),
(E'resource-native-1949-1276-89901',1,212,-38,-92,0),
(E'resource-native-1949-1276-89901',1,213,-38,-91,0),
(E'resource-native-1949-1276-89901',1,214,-37,-110,0),
(E'resource-native-1949-1276-89901',1,215,-37,-109,0),
(E'resource-native-1949-1276-89901',1,216,-37,-108,0),
(E'resource-native-1949-1276-89901',1,217,-37,-105,0),
(E'resource-native-1949-1276-89901',1,218,-37,-104,0),
(E'resource-native-1949-1276-89901',1,219,-37,-102,0),
(E'resource-native-1949-1276-89901',1,220,-37,-101,0),
(E'resource-native-1949-1276-89901',1,221,-37,-100,0),
(E'resource-native-1949-1276-89901',1,222,-37,-99,2),
(E'resource-native-1949-1276-89901',1,223,-37,-98,2),
(E'resource-native-1949-1276-89901',1,224,-37,-97,2),
(E'resource-native-1949-1276-89901',1,225,-37,-96,0),
(E'resource-native-1949-1276-89901',1,226,-37,-94,0),
(E'resource-native-1949-1276-89901',1,227,-37,-93,0),
(E'resource-native-1949-1276-89901',1,228,-37,-92,0),
(E'resource-native-1949-1276-89901',1,229,-37,-91,0),
(E'resource-native-1949-1276-89901',1,230,-36,-111,0),
(E'resource-native-1949-1276-89901',1,231,-36,-110,0),
(E'resource-native-1949-1276-89901',1,232,-36,-109,0),
(E'resource-native-1949-1276-89901',1,233,-36,-108,0),
(E'resource-native-1949-1276-89901',1,234,-36,-107,0),
(E'resource-native-1949-1276-89901',1,235,-36,-105,0),
(E'resource-native-1949-1276-89901',1,236,-36,-104,0),
(E'resource-native-1949-1276-89901',1,237,-36,-102,1),
(E'resource-native-1949-1276-89901',1,238,-36,-101,1),
(E'resource-native-1949-1276-89901',1,239,-36,-100,1),
(E'resource-native-1949-1276-89901',1,240,-36,-99,2),
(E'resource-native-1949-1276-89901',1,241,-36,-98,2),
(E'resource-native-1949-1276-89901',1,242,-36,-97,2),
(E'resource-native-1949-1276-89901',1,243,-36,-93,0),
(E'resource-native-1949-1276-89901',1,244,-36,-92,2),
(E'resource-native-1949-1276-89901',1,245,-35,-129,41),
(E'resource-native-1949-1276-89901',1,246,-35,-111,0),
(E'resource-native-1949-1276-89901',1,247,-35,-110,0),
(E'resource-native-1949-1276-89901',1,248,-35,-109,0),
(E'resource-native-1949-1276-89901',1,249,-35,-108,0),
(E'resource-native-1949-1276-89901',1,250,-35,-107,0),
(E'resource-native-1949-1276-89901',1,251,-35,-105,0),
(E'resource-native-1949-1276-89901',1,252,-35,-104,0),
(E'resource-native-1949-1276-89901',1,253,-35,-102,1),
(E'resource-native-1949-1276-89901',1,254,-35,-101,1),
(E'resource-native-1949-1276-89901',1,255,-35,-100,1),
(E'resource-native-1949-1276-89901',1,256,-35,-99,1),
(E'resource-native-1949-1276-89901',1,257,-35,-98,1),
(E'resource-native-1949-1276-89901',1,258,-35,-97,0),
(E'resource-native-1949-1276-89901',1,259,-35,-96,0),
(E'resource-native-1949-1276-89901',1,260,-35,-94,0),
(E'resource-native-1949-1276-89901',1,261,-35,-93,0),
(E'resource-native-1949-1276-89901',1,262,-35,-92,-2),
(E'resource-native-1949-1276-89901',1,263,-35,-86,0),
(E'resource-native-1949-1276-89901',1,264,-35,-85,-2),
(E'resource-native-1949-1276-89901',1,265,-34,-111,0),
(E'resource-native-1949-1276-89901',1,266,-34,-110,0),
(E'resource-native-1949-1276-89901',1,267,-34,-109,0),
(E'resource-native-1949-1276-89901',1,268,-34,-108,0),
(E'resource-native-1949-1276-89901',1,269,-34,-107,0),
(E'resource-native-1949-1276-89901',1,270,-34,-105,1),
(E'resource-native-1949-1276-89901',1,271,-34,-104,1),
(E'resource-native-1949-1276-89901',1,272,-34,-102,1),
(E'resource-native-1949-1276-89901',1,273,-34,-101,1),
(E'resource-native-1949-1276-89901',1,274,-34,-100,1),
(E'resource-native-1949-1276-89901',1,275,-34,-99,1),
(E'resource-native-1949-1276-89901',1,276,-34,-98,1),
(E'resource-native-1949-1276-89901',1,277,-34,-97,0),
(E'resource-native-1949-1276-89901',1,278,-34,-96,0),
(E'resource-native-1949-1276-89901',1,279,-34,-95,0),
(E'resource-native-1949-1276-89901',1,280,-34,-94,0),
(E'resource-native-1949-1276-89901',1,281,-34,-93,0),
(E'resource-native-1949-1276-89901',1,282,-34,-92,-2),
(E'resource-native-1949-1276-89901',1,283,-34,-86,0),
(E'resource-native-1949-1276-89901',1,284,-33,-111,0),
(E'resource-native-1949-1276-89901',1,285,-33,-110,0),
(E'resource-native-1949-1276-89901',1,286,-33,-109,0),
(E'resource-native-1949-1276-89901',1,287,-33,-108,0),
(E'resource-native-1949-1276-89901',1,288,-33,-107,0),
(E'resource-native-1949-1276-89901',1,289,-33,-105,1),
(E'resource-native-1949-1276-89901',1,290,-33,-104,1),
(E'resource-native-1949-1276-89901',1,291,-33,-98,0),
(E'resource-native-1949-1276-89901',1,292,-33,-97,0),
(E'resource-native-1949-1276-89901',1,293,-33,-96,0),
(E'resource-native-1949-1276-89901',1,294,-33,-95,0),
(E'resource-native-1949-1276-89901',1,295,-33,-94,0),
(E'resource-native-1949-1276-89901',1,296,-33,-93,0),
(E'resource-native-1949-1276-89901',1,297,-33,-92,0),
(E'resource-native-1949-1276-89901',1,298,-33,-91,0),
(E'resource-native-1949-1276-89901',1,299,-33,-90,0),
(E'resource-native-1949-1276-89901',1,300,-33,-89,0),
(E'resource-native-1949-1276-89901',1,301,-33,-88,0),
(E'resource-native-1949-1276-89901',1,302,-33,-87,1),
(E'resource-native-1949-1276-89901',1,303,-33,-86,1),
(E'resource-native-1949-1276-89901',1,304,-33,-85,1),
(E'resource-native-1949-1276-89901',1,305,-33,-83,0),
(E'resource-native-1949-1276-89901',1,306,-33,-82,-4),
(E'resource-native-1949-1276-89901',1,307,-32,-152,10),
(E'resource-native-1949-1276-89901',1,308,-32,-151,10),
(E'resource-native-1949-1276-89901',1,309,-32,-150,14),
(E'resource-native-1949-1276-89901',1,310,-32,-110,0),
(E'resource-native-1949-1276-89901',1,311,-32,-109,0),
(E'resource-native-1949-1276-89901',1,312,-32,-108,0),
(E'resource-native-1949-1276-89901',1,313,-32,-107,0),
(E'resource-native-1949-1276-89901',1,314,-32,-106,0),
(E'resource-native-1949-1276-89901',1,315,-32,-105,0),
(E'resource-native-1949-1276-89901',1,316,-32,-104,0),
(E'resource-native-1949-1276-89901',1,317,-32,-103,0),
(E'resource-native-1949-1276-89901',1,318,-32,-100,0),
(E'resource-native-1949-1276-89901',1,319,-32,-99,0),
(E'resource-native-1949-1276-89901',1,320,-32,-98,0),
(E'resource-native-1949-1276-89901',1,321,-32,-97,0),
(E'resource-native-1949-1276-89901',1,322,-32,-96,0),
(E'resource-native-1949-1276-89901',1,323,-32,-95,0),
(E'resource-native-1949-1276-89901',1,324,-32,-94,0),
(E'resource-native-1949-1276-89901',1,325,-32,-93,0),
(E'resource-native-1949-1276-89901',1,326,-32,-92,0),
(E'resource-native-1949-1276-89901',1,327,-32,-89,1),
(E'resource-native-1949-1276-89901',1,328,-32,-88,1),
(E'resource-native-1949-1276-89901',1,329,-32,-87,1),
(E'resource-native-1949-1276-89901',1,330,-32,-86,1),
(E'resource-native-1949-1276-89901',1,331,-32,-85,1),
(E'resource-native-1949-1276-89901',1,332,-32,-83,0),
(E'resource-native-1949-1276-89901',1,333,-32,-82,2),
(E'resource-native-1949-1276-89901',1,334,-31,-155,10),
(E'resource-native-1949-1276-89901',1,335,-31,-154,10),
(E'resource-native-1949-1276-89901',1,336,-31,-153,10),
(E'resource-native-1949-1276-89901',1,337,-31,-152,10),
(E'resource-native-1949-1276-89901',1,338,-31,-151,10),
(E'resource-native-1949-1276-89901',1,339,-31,-111,0),
(E'resource-native-1949-1276-89901',1,340,-31,-110,0),
(E'resource-native-1949-1276-89901',1,341,-31,-109,0),
(E'resource-native-1949-1276-89901',1,342,-31,-108,0),
(E'resource-native-1949-1276-89901',1,343,-31,-107,0),
(E'resource-native-1949-1276-89901',1,344,-31,-106,0),
(E'resource-native-1949-1276-89901',1,345,-31,-105,0),
(E'resource-native-1949-1276-89901',1,346,-31,-104,0),
(E'resource-native-1949-1276-89901',1,347,-31,-103,0),
(E'resource-native-1949-1276-89901',1,348,-31,-101,0),
(E'resource-native-1949-1276-89901',1,349,-31,-100,0),
(E'resource-native-1949-1276-89901',1,350,-31,-99,0),
(E'resource-native-1949-1276-89901',1,351,-31,-98,0),
(E'resource-native-1949-1276-89901',1,352,-31,-97,0),
(E'resource-native-1949-1276-89901',1,353,-31,-96,0),
(E'resource-native-1949-1276-89901',1,354,-31,-95,0),
(E'resource-native-1949-1276-89901',1,355,-31,-94,0),
(E'resource-native-1949-1276-89901',1,356,-31,-93,0),
(E'resource-native-1949-1276-89901',1,357,-31,-92,0),
(E'resource-native-1949-1276-89901',1,358,-31,-91,0),
(E'resource-native-1949-1276-89901',1,359,-31,-90,0),
(E'resource-native-1949-1276-89901',1,360,-31,-89,1),
(E'resource-native-1949-1276-89901',1,361,-31,-88,1),
(E'resource-native-1949-1276-89901',1,362,-31,-87,1),
(E'resource-native-1949-1276-89901',1,363,-31,-86,1),
(E'resource-native-1949-1276-89901',1,364,-31,-85,1),
(E'resource-native-1949-1276-89901',1,365,-31,-84,0),
(E'resource-native-1949-1276-89901',1,366,-31,-83,0),
(E'resource-native-1949-1276-89901',1,367,-31,-82,0),
(E'resource-native-1949-1276-89901',1,368,-30,-159,12),
(E'resource-native-1949-1276-89901',1,369,-30,-158,10),
(E'resource-native-1949-1276-89901',1,370,-30,-157,10),
(E'resource-native-1949-1276-89901',1,371,-30,-155,10),
(E'resource-native-1949-1276-89901',1,372,-30,-153,10),
(E'resource-native-1949-1276-89901',1,373,-30,-152,10),
(E'resource-native-1949-1276-89901',1,374,-30,-151,10),
(E'resource-native-1949-1276-89901',1,375,-30,-150,10),
(E'resource-native-1949-1276-89901',1,376,-30,-136,23),
(E'resource-native-1949-1276-89901',1,377,-30,-126,0),
(E'resource-native-1949-1276-89901',1,378,-30,-112,0),
(E'resource-native-1949-1276-89901',1,379,-30,-111,0),
(E'resource-native-1949-1276-89901',1,380,-30,-110,0),
(E'resource-native-1949-1276-89901',1,381,-30,-109,0),
(E'resource-native-1949-1276-89901',1,382,-30,-108,0),
(E'resource-native-1949-1276-89901',1,383,-30,-107,0),
(E'resource-native-1949-1276-89901',1,384,-30,-106,0),
(E'resource-native-1949-1276-89901',1,385,-30,-105,0),
(E'resource-native-1949-1276-89901',1,386,-30,-104,0),
(E'resource-native-1949-1276-89901',1,387,-30,-103,0),
(E'resource-native-1949-1276-89901',1,388,-30,-102,0),
(E'resource-native-1949-1276-89901',1,389,-30,-101,0),
(E'resource-native-1949-1276-89901',1,390,-30,-100,0),
(E'resource-native-1949-1276-89901',1,391,-30,-99,0),
(E'resource-native-1949-1276-89901',1,392,-30,-98,0),
(E'resource-native-1949-1276-89901',1,393,-30,-97,0),
(E'resource-native-1949-1276-89901',1,394,-30,-96,0),
(E'resource-native-1949-1276-89901',1,395,-30,-95,0),
(E'resource-native-1949-1276-89901',1,396,-30,-94,0),
(E'resource-native-1949-1276-89901',1,397,-30,-93,0),
(E'resource-native-1949-1276-89901',1,398,-30,-92,0),
(E'resource-native-1949-1276-89901',1,399,-30,-91,0),
(E'resource-native-1949-1276-89901',1,400,-30,-90,0),
(E'resource-native-1949-1276-89901',1,401,-30,-89,0),
(E'resource-native-1949-1276-89901',1,402,-30,-88,1),
(E'resource-native-1949-1276-89901',1,403,-30,-87,1),
(E'resource-native-1949-1276-89901',1,404,-30,-86,0),
(E'resource-native-1949-1276-89901',1,405,-30,-85,0),
(E'resource-native-1949-1276-89901',1,406,-30,-84,0),
(E'resource-native-1949-1276-89901',1,407,-30,-83,0),
(E'resource-native-1949-1276-89901',1,408,-30,-82,0),
(E'resource-native-1949-1276-89901',1,409,-29,-167,50),
(E'resource-native-1949-1276-89901',1,410,-29,-164,26),
(E'resource-native-1949-1276-89901',1,411,-29,-160,47),
(E'resource-native-1949-1276-89901',1,412,-29,-159,10),
(E'resource-native-1949-1276-89901',1,413,-29,-158,10),
(E'resource-native-1949-1276-89901',1,414,-29,-157,10),
(E'resource-native-1949-1276-89901',1,415,-29,-156,10),
(E'resource-native-1949-1276-89901',1,416,-29,-155,10),
(E'resource-native-1949-1276-89901',1,417,-29,-154,10),
(E'resource-native-1949-1276-89901',1,418,-29,-153,10),
(E'resource-native-1949-1276-89901',1,419,-29,-152,10),
(E'resource-native-1949-1276-89901',1,420,-29,-151,10),
(E'resource-native-1949-1276-89901',1,421,-29,-150,10),
(E'resource-native-1949-1276-89901',1,422,-29,-134,12),
(E'resource-native-1949-1276-89901',1,423,-29,-130,0),
(E'resource-native-1949-1276-89901',1,424,-29,-129,0),
(E'resource-native-1949-1276-89901',1,425,-29,-127,0),
(E'resource-native-1949-1276-89901',1,426,-29,-126,0),
(E'resource-native-1949-1276-89901',1,427,-29,-125,-2),
(E'resource-native-1949-1276-89901',1,428,-29,-112,0),
(E'resource-native-1949-1276-89901',1,429,-29,-111,0),
(E'resource-native-1949-1276-89901',1,430,-29,-110,0),
(E'resource-native-1949-1276-89901',1,431,-29,-109,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1945-1276-89901',1,-1945,0,391,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1945-1276-89901',1,E'proposed',0),
(E'resource-native-1945-1276-89901',1,E'active',1),
(E'resource-native-1945-1276-89901',1,E'completed',2),
(E'resource-native-1945-1276-89901',1,E'expired',2),
(E'resource-native-1945-1276-89901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1945-1276-89901',1,0,-72,-110,-1),
(E'resource-native-1945-1276-89901',1,1,-72,-109,-1),
(E'resource-native-1945-1276-89901',1,2,-72,-108,-1),
(E'resource-native-1945-1276-89901',1,3,-71,-110,-2),
(E'resource-native-1945-1276-89901',1,4,-71,-109,-2),
(E'resource-native-1945-1276-89901',1,5,-71,-108,-2),
(E'resource-native-1945-1276-89901',1,6,-70,-110,-2),
(E'resource-native-1945-1276-89901',1,7,-70,-109,-2),
(E'resource-native-1945-1276-89901',1,8,-70,-108,-2),
(E'resource-native-1945-1276-89901',1,9,-69,-110,-3),
(E'resource-native-1945-1276-89901',1,10,-69,-109,-3),
(E'resource-native-1945-1276-89901',1,11,-69,-108,-3),
(E'resource-native-1945-1276-89901',1,12,-68,-110,-3),
(E'resource-native-1945-1276-89901',1,13,-68,-109,-3),
(E'resource-native-1945-1276-89901',1,14,-68,-108,-3),
(E'resource-native-1945-1276-89901',1,15,-67,-110,-4),
(E'resource-native-1945-1276-89901',1,16,-67,-109,-4),
(E'resource-native-1945-1276-89901',1,17,-67,-108,-4),
(E'resource-native-1945-1276-89901',1,18,-66,-110,-4),
(E'resource-native-1945-1276-89901',1,19,-66,-109,-4),
(E'resource-native-1945-1276-89901',1,20,-66,-108,-4),
(E'resource-native-1945-1276-89901',1,21,-65,-110,-4),
(E'resource-native-1945-1276-89901',1,22,-65,-109,-4),
(E'resource-native-1945-1276-89901',1,23,-65,-108,-4),
(E'resource-native-1945-1276-89901',1,24,-64,-110,-4),
(E'resource-native-1945-1276-89901',1,25,-64,-109,-4),
(E'resource-native-1945-1276-89901',1,26,-64,-108,-4),
(E'resource-native-1945-1276-89901',1,27,-63,-110,-4),
(E'resource-native-1945-1276-89901',1,28,-63,-109,-4),
(E'resource-native-1945-1276-89901',1,29,-63,-108,-4),
(E'resource-native-1945-1276-89901',1,30,-62,-110,-4),
(E'resource-native-1945-1276-89901',1,31,-62,-109,-4),
(E'resource-native-1945-1276-89901',1,32,-62,-108,-4),
(E'resource-native-1945-1276-89901',1,33,-61,-110,-4),
(E'resource-native-1945-1276-89901',1,34,-61,-109,-4),
(E'resource-native-1945-1276-89901',1,35,-61,-108,-4),
(E'resource-native-1945-1276-89901',1,36,-60,-110,-4),
(E'resource-native-1945-1276-89901',1,37,-60,-109,-4);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1941-1276-89901',1,-1941,0,391,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1941-1276-89901',1,E'proposed',0),
(E'resource-native-1941-1276-89901',1,E'active',1),
(E'resource-native-1941-1276-89901',1,E'completed',2),
(E'resource-native-1941-1276-89901',1,E'expired',2),
(E'resource-native-1941-1276-89901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',10,NULL,NULL),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1941-1276-89901',1,0,-72,-110,-1),
(E'resource-native-1941-1276-89901',1,1,-72,-109,-1),
(E'resource-native-1941-1276-89901',1,2,-72,-108,-1),
(E'resource-native-1941-1276-89901',1,3,-71,-110,-2),
(E'resource-native-1941-1276-89901',1,4,-71,-109,-2),
(E'resource-native-1941-1276-89901',1,5,-71,-108,-2),
(E'resource-native-1941-1276-89901',1,6,-70,-110,-2),
(E'resource-native-1941-1276-89901',1,7,-70,-109,-2),
(E'resource-native-1941-1276-89901',1,8,-70,-108,-2),
(E'resource-native-1941-1276-89901',1,9,-69,-110,-3),
(E'resource-native-1941-1276-89901',1,10,-69,-109,-3),
(E'resource-native-1941-1276-89901',1,11,-69,-108,-3),
(E'resource-native-1941-1276-89901',1,12,-68,-110,-3),
(E'resource-native-1941-1276-89901',1,13,-68,-109,-3),
(E'resource-native-1941-1276-89901',1,14,-68,-108,-3),
(E'resource-native-1941-1276-89901',1,15,-67,-110,-4),
(E'resource-native-1941-1276-89901',1,16,-67,-109,-4),
(E'resource-native-1941-1276-89901',1,17,-67,-108,-4),
(E'resource-native-1941-1276-89901',1,18,-66,-110,-4),
(E'resource-native-1941-1276-89901',1,19,-66,-109,-4),
(E'resource-native-1941-1276-89901',1,20,-66,-108,-4),
(E'resource-native-1941-1276-89901',1,21,-65,-110,-4),
(E'resource-native-1941-1276-89901',1,22,-65,-109,-4),
(E'resource-native-1941-1276-89901',1,23,-65,-108,-4),
(E'resource-native-1941-1276-89901',1,24,-64,-110,-4),
(E'resource-native-1941-1276-89901',1,25,-64,-109,-4),
(E'resource-native-1941-1276-89901',1,26,-64,-108,-4),
(E'resource-native-1941-1276-89901',1,27,-63,-110,-4),
(E'resource-native-1941-1276-89901',1,28,-63,-109,-4),
(E'resource-native-1941-1276-89901',1,29,-63,-108,-4),
(E'resource-native-1941-1276-89901',1,30,-62,-110,-4),
(E'resource-native-1941-1276-89901',1,31,-62,-109,-4),
(E'resource-native-1941-1276-89901',1,32,-62,-108,-4),
(E'resource-native-1941-1276-89901',1,33,-61,-110,-4),
(E'resource-native-1941-1276-89901',1,34,-61,-109,-4),
(E'resource-native-1941-1276-89901',1,35,-61,-108,-4),
(E'resource-native-1941-1276-89901',1,36,-60,-110,-4),
(E'resource-native-1941-1276-89901',1,37,-60,-109,-4),
(E'resource-native-1941-1276-89901',1,38,-60,-108,-4),
(E'resource-native-1941-1276-89901',1,39,-59,-110,-3),
(E'resource-native-1941-1276-89901',1,40,-59,-109,-3),
(E'resource-native-1941-1276-89901',1,41,-59,-108,-3),
(E'resource-native-1941-1276-89901',1,42,-58,-110,-3),
(E'resource-native-1941-1276-89901',1,43,-58,-109,-3),
(E'resource-native-1941-1276-89901',1,44,-58,-108,-3),
(E'resource-native-1941-1276-89901',1,45,-57,-110,-2),
(E'resource-native-1941-1276-89901',1,46,-57,-109,-2),
(E'resource-native-1941-1276-89901',1,47,-57,-108,-2),
(E'resource-native-1941-1276-89901',1,48,-56,-110,-2),
(E'resource-native-1941-1276-89901',1,49,-56,-109,-2),
(E'resource-native-1941-1276-89901',1,50,-56,-108,-2),
(E'resource-native-1941-1276-89901',1,51,-55,-110,-1),
(E'resource-native-1941-1276-89901',1,52,-55,-109,-1),
(E'resource-native-1941-1276-89901',1,53,-55,-108,-1),
(E'resource-native-1941-1276-89901',1,54,-54,-115,0),
(E'resource-native-1941-1276-89901',1,55,-54,-114,2),
(E'resource-native-1941-1276-89901',1,56,-54,-110,0),
(E'resource-native-1941-1276-89901',1,57,-54,-109,0),
(E'resource-native-1941-1276-89901',1,58,-54,-108,0),
(E'resource-native-1941-1276-89901',1,59,-53,-115,0),
(E'resource-native-1941-1276-89901',1,60,-53,-114,0),
(E'resource-native-1941-1276-89901',1,61,-53,-113,0),
(E'resource-native-1941-1276-89901',1,62,-53,-110,0),
(E'resource-native-1941-1276-89901',1,63,-53,-109,0),
(E'resource-native-1941-1276-89901',1,64,-53,-108,0),
(E'resource-native-1941-1276-89901',1,65,-53,-105,0),
(E'resource-native-1941-1276-89901',1,66,-53,-104,0),
(E'resource-native-1941-1276-89901',1,67,-53,-103,-2),
(E'resource-native-1941-1276-89901',1,68,-52,-115,0),
(E'resource-native-1941-1276-89901',1,69,-52,-114,0),
(E'resource-native-1941-1276-89901',1,70,-52,-113,0),
(E'resource-native-1941-1276-89901',1,71,-52,-112,0),
(E'resource-native-1941-1276-89901',1,72,-52,-110,0),
(E'resource-native-1941-1276-89901',1,73,-52,-109,0),
(E'resource-native-1941-1276-89901',1,74,-52,-108,0),
(E'resource-native-1941-1276-89901',1,75,-52,-107,0),
(E'resource-native-1941-1276-89901',1,76,-52,-105,0),
(E'resource-native-1941-1276-89901',1,77,-52,-104,0),
(E'resource-native-1941-1276-89901',1,78,-52,-103,0),
(E'resource-native-1941-1276-89901',1,79,-51,-116,0),
(E'resource-native-1941-1276-89901',1,80,-51,-115,0),
(E'resource-native-1941-1276-89901',1,81,-51,-114,0),
(E'resource-native-1941-1276-89901',1,82,-51,-113,0),
(E'resource-native-1941-1276-89901',1,83,-51,-112,0),
(E'resource-native-1941-1276-89901',1,84,-51,-111,0),
(E'resource-native-1941-1276-89901',1,85,-51,-110,0),
(E'resource-native-1941-1276-89901',1,86,-51,-109,0),
(E'resource-native-1941-1276-89901',1,87,-51,-108,0),
(E'resource-native-1941-1276-89901',1,88,-51,-107,0),
(E'resource-native-1941-1276-89901',1,89,-51,-106,0),
(E'resource-native-1941-1276-89901',1,90,-51,-105,0),
(E'resource-native-1941-1276-89901',1,91,-51,-104,0),
(E'resource-native-1941-1276-89901',1,92,-51,-103,0),
(E'resource-native-1941-1276-89901',1,93,-51,-102,0),
(E'resource-native-1941-1276-89901',1,94,-50,-116,0),
(E'resource-native-1941-1276-89901',1,95,-50,-115,0),
(E'resource-native-1941-1276-89901',1,96,-50,-114,0),
(E'resource-native-1941-1276-89901',1,97,-50,-113,0),
(E'resource-native-1941-1276-89901',1,98,-50,-112,0),
(E'resource-native-1941-1276-89901',1,99,-50,-111,0),
(E'resource-native-1941-1276-89901',1,100,-50,-110,0),
(E'resource-native-1941-1276-89901',1,101,-50,-109,0),
(E'resource-native-1941-1276-89901',1,102,-50,-108,0),
(E'resource-native-1941-1276-89901',1,103,-50,-107,0),
(E'resource-native-1941-1276-89901',1,104,-50,-106,0),
(E'resource-native-1941-1276-89901',1,105,-50,-105,0),
(E'resource-native-1941-1276-89901',1,106,-50,-104,0),
(E'resource-native-1941-1276-89901',1,107,-50,-103,0),
(E'resource-native-1941-1276-89901',1,108,-50,-102,2),
(E'resource-native-1941-1276-89901',1,109,-50,-101,2),
(E'resource-native-1941-1276-89901',1,110,-49,-116,0),
(E'resource-native-1941-1276-89901',1,111,-49,-115,0),
(E'resource-native-1941-1276-89901',1,112,-49,-114,0),
(E'resource-native-1941-1276-89901',1,113,-49,-113,0),
(E'resource-native-1941-1276-89901',1,114,-49,-112,0),
(E'resource-native-1941-1276-89901',1,115,-49,-111,0),
(E'resource-native-1941-1276-89901',1,116,-49,-110,0),
(E'resource-native-1941-1276-89901',1,117,-49,-109,0),
(E'resource-native-1941-1276-89901',1,118,-49,-108,0),
(E'resource-native-1941-1276-89901',1,119,-49,-107,0),
(E'resource-native-1941-1276-89901',1,120,-49,-106,0),
(E'resource-native-1941-1276-89901',1,121,-49,-105,0),
(E'resource-native-1941-1276-89901',1,122,-49,-104,0),
(E'resource-native-1941-1276-89901',1,123,-49,-103,0),
(E'resource-native-1941-1276-89901',1,124,-49,-102,0),
(E'resource-native-1941-1276-89901',1,125,-48,-116,2),
(E'resource-native-1941-1276-89901',1,126,-48,-113,0),
(E'resource-native-1941-1276-89901',1,127,-48,-112,0),
(E'resource-native-1941-1276-89901',1,128,-48,-111,0),
(E'resource-native-1941-1276-89901',1,129,-48,-110,0),
(E'resource-native-1941-1276-89901',1,130,-48,-109,0),
(E'resource-native-1941-1276-89901',1,131,-48,-108,0),
(E'resource-native-1941-1276-89901',1,132,-48,-107,0),
(E'resource-native-1941-1276-89901',1,133,-48,-106,0),
(E'resource-native-1941-1276-89901',1,134,-48,-105,0),
(E'resource-native-1941-1276-89901',1,135,-48,-104,0),
(E'resource-native-1941-1276-89901',1,136,-48,-103,0),
(E'resource-native-1941-1276-89901',1,137,-48,-102,0),
(E'resource-native-1941-1276-89901',1,138,-47,-114,0),
(E'resource-native-1941-1276-89901',1,139,-47,-113,0),
(E'resource-native-1941-1276-89901',1,140,-47,-112,0),
(E'resource-native-1941-1276-89901',1,141,-47,-111,0),
(E'resource-native-1941-1276-89901',1,142,-47,-110,0),
(E'resource-native-1941-1276-89901',1,143,-47,-109,0),
(E'resource-native-1941-1276-89901',1,144,-47,-108,0),
(E'resource-native-1941-1276-89901',1,145,-47,-107,0),
(E'resource-native-1941-1276-89901',1,146,-47,-106,0),
(E'resource-native-1941-1276-89901',1,147,-47,-105,0),
(E'resource-native-1941-1276-89901',1,148,-47,-103,0),
(E'resource-native-1941-1276-89901',1,149,-47,-102,0),
(E'resource-native-1941-1276-89901',1,150,-46,-115,0),
(E'resource-native-1941-1276-89901',1,151,-46,-114,0),
(E'resource-native-1941-1276-89901',1,152,-46,-113,0),
(E'resource-native-1941-1276-89901',1,153,-46,-112,0),
(E'resource-native-1941-1276-89901',1,154,-46,-111,0),
(E'resource-native-1941-1276-89901',1,155,-46,-110,0),
(E'resource-native-1941-1276-89901',1,156,-46,-109,0),
(E'resource-native-1941-1276-89901',1,157,-46,-108,0),
(E'resource-native-1941-1276-89901',1,158,-46,-107,0),
(E'resource-native-1941-1276-89901',1,159,-46,-106,0),
(E'resource-native-1941-1276-89901',1,160,-46,-105,0),
(E'resource-native-1941-1276-89901',1,161,-46,-103,0),
(E'resource-native-1941-1276-89901',1,162,-45,-115,-2),
(E'resource-native-1941-1276-89901',1,163,-45,-114,0),
(E'resource-native-1941-1276-89901',1,164,-45,-113,0),
(E'resource-native-1941-1276-89901',1,165,-45,-112,0),
(E'resource-native-1941-1276-89901',1,166,-45,-111,0),
(E'resource-native-1941-1276-89901',1,167,-45,-110,0),
(E'resource-native-1941-1276-89901',1,168,-45,-109,0),
(E'resource-native-1941-1276-89901',1,169,-45,-108,0),
(E'resource-native-1941-1276-89901',1,170,-45,-107,0),
(E'resource-native-1941-1276-89901',1,171,-45,-106,0),
(E'resource-native-1941-1276-89901',1,172,-45,-105,0),
(E'resource-native-1941-1276-89901',1,173,-45,-104,0),
(E'resource-native-1941-1276-89901',1,174,-44,-115,-2),
(E'resource-native-1941-1276-89901',1,175,-44,-111,0),
(E'resource-native-1941-1276-89901',1,176,-44,-110,0),
(E'resource-native-1941-1276-89901',1,177,-44,-109,0),
(E'resource-native-1941-1276-89901',1,178,-44,-108,0),
(E'resource-native-1941-1276-89901',1,179,-44,-107,0),
(E'resource-native-1941-1276-89901',1,180,-44,-106,0),
(E'resource-native-1941-1276-89901',1,181,-44,-105,0),
(E'resource-native-1941-1276-89901',1,182,-44,-104,0),
(E'resource-native-1941-1276-89901',1,183,-43,-110,0),
(E'resource-native-1941-1276-89901',1,184,-43,-109,0),
(E'resource-native-1941-1276-89901',1,185,-43,-108,0),
(E'resource-native-1941-1276-89901',1,186,-43,-106,0),
(E'resource-native-1941-1276-89901',1,187,-43,-105,-2),
(E'resource-native-1941-1276-89901',1,188,-42,-110,0),
(E'resource-native-1941-1276-89901',1,189,-42,-109,0),
(E'resource-native-1941-1276-89901',1,190,-42,-108,0),
(E'resource-native-1941-1276-89901',1,191,-41,-110,-1),
(E'resource-native-1941-1276-89901',1,192,-41,-109,-1),
(E'resource-native-1941-1276-89901',1,193,-41,-108,-1),
(E'resource-native-1941-1276-89901',1,194,-40,-110,-1),
(E'resource-native-1941-1276-89901',1,195,-40,-109,-1),
(E'resource-native-1941-1276-89901',1,196,-40,-108,-1),
(E'resource-native-1941-1276-89901',1,197,-40,-93,0),
(E'resource-native-1941-1276-89901',1,198,-40,-92,-2),
(E'resource-native-1941-1276-89901',1,199,-39,-110,-1),
(E'resource-native-1941-1276-89901',1,200,-39,-109,-1),
(E'resource-native-1941-1276-89901',1,201,-39,-108,-1),
(E'resource-native-1941-1276-89901',1,202,-39,-92,0),
(E'resource-native-1941-1276-89901',1,203,-38,-110,0),
(E'resource-native-1941-1276-89901',1,204,-38,-109,0),
(E'resource-native-1941-1276-89901',1,205,-38,-108,0),
(E'resource-native-1941-1276-89901',1,206,-38,-101,2),
(E'resource-native-1941-1276-89901',1,207,-38,-99,2),
(E'resource-native-1941-1276-89901',1,208,-38,-97,2),
(E'resource-native-1941-1276-89901',1,209,-38,-96,0),
(E'resource-native-1941-1276-89901',1,210,-38,-94,0),
(E'resource-native-1941-1276-89901',1,211,-38,-93,0),
(E'resource-native-1941-1276-89901',1,212,-38,-92,0),
(E'resource-native-1941-1276-89901',1,213,-38,-91,0),
(E'resource-native-1941-1276-89901',1,214,-37,-110,0),
(E'resource-native-1941-1276-89901',1,215,-37,-109,0),
(E'resource-native-1941-1276-89901',1,216,-37,-108,0),
(E'resource-native-1941-1276-89901',1,217,-37,-105,0),
(E'resource-native-1941-1276-89901',1,218,-37,-104,0),
(E'resource-native-1941-1276-89901',1,219,-37,-102,0),
(E'resource-native-1941-1276-89901',1,220,-37,-101,0),
(E'resource-native-1941-1276-89901',1,221,-37,-100,0),
(E'resource-native-1941-1276-89901',1,222,-37,-99,2),
(E'resource-native-1941-1276-89901',1,223,-37,-98,2),
(E'resource-native-1941-1276-89901',1,224,-37,-97,2),
(E'resource-native-1941-1276-89901',1,225,-37,-96,0),
(E'resource-native-1941-1276-89901',1,226,-37,-94,0),
(E'resource-native-1941-1276-89901',1,227,-37,-93,0),
(E'resource-native-1941-1276-89901',1,228,-37,-92,0),
(E'resource-native-1941-1276-89901',1,229,-37,-91,0),
(E'resource-native-1941-1276-89901',1,230,-36,-111,0),
(E'resource-native-1941-1276-89901',1,231,-36,-110,0),
(E'resource-native-1941-1276-89901',1,232,-36,-109,0),
(E'resource-native-1941-1276-89901',1,233,-36,-108,0),
(E'resource-native-1941-1276-89901',1,234,-36,-107,0),
(E'resource-native-1941-1276-89901',1,235,-36,-105,0),
(E'resource-native-1941-1276-89901',1,236,-36,-104,0),
(E'resource-native-1941-1276-89901',1,237,-36,-102,1),
(E'resource-native-1941-1276-89901',1,238,-36,-101,1),
(E'resource-native-1941-1276-89901',1,239,-36,-100,1),
(E'resource-native-1941-1276-89901',1,240,-36,-99,2),
(E'resource-native-1941-1276-89901',1,241,-36,-98,2),
(E'resource-native-1941-1276-89901',1,242,-36,-97,2),
(E'resource-native-1941-1276-89901',1,243,-36,-93,0),
(E'resource-native-1941-1276-89901',1,244,-36,-92,2),
(E'resource-native-1941-1276-89901',1,245,-35,-129,41),
(E'resource-native-1941-1276-89901',1,246,-35,-111,0),
(E'resource-native-1941-1276-89901',1,247,-35,-110,0),
(E'resource-native-1941-1276-89901',1,248,-35,-109,0),
(E'resource-native-1941-1276-89901',1,249,-35,-108,0),
(E'resource-native-1941-1276-89901',1,250,-35,-107,0),
(E'resource-native-1941-1276-89901',1,251,-35,-105,0),
(E'resource-native-1941-1276-89901',1,252,-35,-104,0),
(E'resource-native-1941-1276-89901',1,253,-35,-102,1),
(E'resource-native-1941-1276-89901',1,254,-35,-101,1),
(E'resource-native-1941-1276-89901',1,255,-35,-100,1),
(E'resource-native-1941-1276-89901',1,256,-35,-99,1),
(E'resource-native-1941-1276-89901',1,257,-35,-98,1),
(E'resource-native-1941-1276-89901',1,258,-35,-97,0),
(E'resource-native-1941-1276-89901',1,259,-35,-96,0),
(E'resource-native-1941-1276-89901',1,260,-35,-94,0),
(E'resource-native-1941-1276-89901',1,261,-35,-93,0),
(E'resource-native-1941-1276-89901',1,262,-35,-92,-2),
(E'resource-native-1941-1276-89901',1,263,-35,-86,0),
(E'resource-native-1941-1276-89901',1,264,-35,-85,-2),
(E'resource-native-1941-1276-89901',1,265,-34,-111,0),
(E'resource-native-1941-1276-89901',1,266,-34,-110,0),
(E'resource-native-1941-1276-89901',1,267,-34,-109,0),
(E'resource-native-1941-1276-89901',1,268,-34,-108,0),
(E'resource-native-1941-1276-89901',1,269,-34,-107,0),
(E'resource-native-1941-1276-89901',1,270,-34,-105,1),
(E'resource-native-1941-1276-89901',1,271,-34,-104,1),
(E'resource-native-1941-1276-89901',1,272,-34,-102,1),
(E'resource-native-1941-1276-89901',1,273,-34,-101,1),
(E'resource-native-1941-1276-89901',1,274,-34,-100,1),
(E'resource-native-1941-1276-89901',1,275,-34,-99,1),
(E'resource-native-1941-1276-89901',1,276,-34,-98,1),
(E'resource-native-1941-1276-89901',1,277,-34,-97,0),
(E'resource-native-1941-1276-89901',1,278,-34,-96,0),
(E'resource-native-1941-1276-89901',1,279,-34,-95,0),
(E'resource-native-1941-1276-89901',1,280,-34,-94,0),
(E'resource-native-1941-1276-89901',1,281,-34,-93,0),
(E'resource-native-1941-1276-89901',1,282,-34,-92,-2),
(E'resource-native-1941-1276-89901',1,283,-34,-86,0),
(E'resource-native-1941-1276-89901',1,284,-33,-111,0),
(E'resource-native-1941-1276-89901',1,285,-33,-110,0),
(E'resource-native-1941-1276-89901',1,286,-33,-109,0),
(E'resource-native-1941-1276-89901',1,287,-33,-108,0),
(E'resource-native-1941-1276-89901',1,288,-33,-107,0),
(E'resource-native-1941-1276-89901',1,289,-33,-105,1),
(E'resource-native-1941-1276-89901',1,290,-33,-104,1),
(E'resource-native-1941-1276-89901',1,291,-33,-98,0),
(E'resource-native-1941-1276-89901',1,292,-33,-97,0),
(E'resource-native-1941-1276-89901',1,293,-33,-96,0),
(E'resource-native-1941-1276-89901',1,294,-33,-95,0),
(E'resource-native-1941-1276-89901',1,295,-33,-94,0),
(E'resource-native-1941-1276-89901',1,296,-33,-93,0),
(E'resource-native-1941-1276-89901',1,297,-33,-92,0),
(E'resource-native-1941-1276-89901',1,298,-33,-91,0),
(E'resource-native-1941-1276-89901',1,299,-33,-90,0),
(E'resource-native-1941-1276-89901',1,300,-33,-89,0),
(E'resource-native-1941-1276-89901',1,301,-33,-88,0),
(E'resource-native-1941-1276-89901',1,302,-33,-87,1),
(E'resource-native-1941-1276-89901',1,303,-33,-86,1),
(E'resource-native-1941-1276-89901',1,304,-33,-85,1),
(E'resource-native-1941-1276-89901',1,305,-33,-83,0),
(E'resource-native-1941-1276-89901',1,306,-33,-82,-4),
(E'resource-native-1941-1276-89901',1,307,-32,-152,10),
(E'resource-native-1941-1276-89901',1,308,-32,-151,10),
(E'resource-native-1941-1276-89901',1,309,-32,-150,14),
(E'resource-native-1941-1276-89901',1,310,-32,-110,0),
(E'resource-native-1941-1276-89901',1,311,-32,-109,0),
(E'resource-native-1941-1276-89901',1,312,-32,-108,0),
(E'resource-native-1941-1276-89901',1,313,-32,-107,0),
(E'resource-native-1941-1276-89901',1,314,-32,-106,0),
(E'resource-native-1941-1276-89901',1,315,-32,-105,0),
(E'resource-native-1941-1276-89901',1,316,-32,-104,0),
(E'resource-native-1941-1276-89901',1,317,-32,-103,0),
(E'resource-native-1941-1276-89901',1,318,-32,-100,0),
(E'resource-native-1941-1276-89901',1,319,-32,-99,0),
(E'resource-native-1941-1276-89901',1,320,-32,-98,0),
(E'resource-native-1941-1276-89901',1,321,-32,-97,0),
(E'resource-native-1941-1276-89901',1,322,-32,-96,0),
(E'resource-native-1941-1276-89901',1,323,-32,-95,0),
(E'resource-native-1941-1276-89901',1,324,-32,-94,0),
(E'resource-native-1941-1276-89901',1,325,-32,-93,0),
(E'resource-native-1941-1276-89901',1,326,-32,-92,0),
(E'resource-native-1941-1276-89901',1,327,-32,-89,1),
(E'resource-native-1941-1276-89901',1,328,-32,-88,1),
(E'resource-native-1941-1276-89901',1,329,-32,-87,1),
(E'resource-native-1941-1276-89901',1,330,-32,-86,1),
(E'resource-native-1941-1276-89901',1,331,-32,-85,1),
(E'resource-native-1941-1276-89901',1,332,-32,-83,0),
(E'resource-native-1941-1276-89901',1,333,-32,-82,2),
(E'resource-native-1941-1276-89901',1,334,-31,-155,10),
(E'resource-native-1941-1276-89901',1,335,-31,-154,10),
(E'resource-native-1941-1276-89901',1,336,-31,-153,10),
(E'resource-native-1941-1276-89901',1,337,-31,-152,10),
(E'resource-native-1941-1276-89901',1,338,-31,-151,10),
(E'resource-native-1941-1276-89901',1,339,-31,-111,0),
(E'resource-native-1941-1276-89901',1,340,-31,-110,0),
(E'resource-native-1941-1276-89901',1,341,-31,-109,0),
(E'resource-native-1941-1276-89901',1,342,-31,-108,0),
(E'resource-native-1941-1276-89901',1,343,-31,-107,0),
(E'resource-native-1941-1276-89901',1,344,-31,-106,0),
(E'resource-native-1941-1276-89901',1,345,-31,-105,0),
(E'resource-native-1941-1276-89901',1,346,-31,-104,0),
(E'resource-native-1941-1276-89901',1,347,-31,-103,0),
(E'resource-native-1941-1276-89901',1,348,-31,-101,0),
(E'resource-native-1941-1276-89901',1,349,-31,-100,0),
(E'resource-native-1941-1276-89901',1,350,-31,-99,0),
(E'resource-native-1941-1276-89901',1,351,-31,-98,0),
(E'resource-native-1941-1276-89901',1,352,-31,-97,0),
(E'resource-native-1941-1276-89901',1,353,-31,-96,0),
(E'resource-native-1941-1276-89901',1,354,-31,-95,0),
(E'resource-native-1941-1276-89901',1,355,-31,-94,0),
(E'resource-native-1941-1276-89901',1,356,-31,-93,0),
(E'resource-native-1941-1276-89901',1,357,-31,-92,0),
(E'resource-native-1941-1276-89901',1,358,-31,-91,0),
(E'resource-native-1941-1276-89901',1,359,-31,-90,0),
(E'resource-native-1941-1276-89901',1,360,-31,-89,1),
(E'resource-native-1941-1276-89901',1,361,-31,-88,1),
(E'resource-native-1941-1276-89901',1,362,-31,-87,1),
(E'resource-native-1941-1276-89901',1,363,-31,-86,1),
(E'resource-native-1941-1276-89901',1,364,-31,-85,1),
(E'resource-native-1941-1276-89901',1,365,-31,-84,0),
(E'resource-native-1941-1276-89901',1,366,-31,-83,0),
(E'resource-native-1941-1276-89901',1,367,-31,-82,0),
(E'resource-native-1941-1276-89901',1,368,-30,-159,12),
(E'resource-native-1941-1276-89901',1,369,-30,-158,10),
(E'resource-native-1941-1276-89901',1,370,-30,-157,10),
(E'resource-native-1941-1276-89901',1,371,-30,-155,10),
(E'resource-native-1941-1276-89901',1,372,-30,-153,10),
(E'resource-native-1941-1276-89901',1,373,-30,-152,10),
(E'resource-native-1941-1276-89901',1,374,-30,-151,10),
(E'resource-native-1941-1276-89901',1,375,-30,-150,10),
(E'resource-native-1941-1276-89901',1,376,-30,-136,23),
(E'resource-native-1941-1276-89901',1,377,-30,-126,0),
(E'resource-native-1941-1276-89901',1,378,-30,-112,0),
(E'resource-native-1941-1276-89901',1,379,-30,-111,0),
(E'resource-native-1941-1276-89901',1,380,-30,-110,0),
(E'resource-native-1941-1276-89901',1,381,-30,-109,0),
(E'resource-native-1941-1276-89901',1,382,-30,-108,0),
(E'resource-native-1941-1276-89901',1,383,-30,-107,0),
(E'resource-native-1941-1276-89901',1,384,-30,-106,0),
(E'resource-native-1941-1276-89901',1,385,-30,-105,0),
(E'resource-native-1941-1276-89901',1,386,-30,-104,0),
(E'resource-native-1941-1276-89901',1,387,-30,-103,0),
(E'resource-native-1941-1276-89901',1,388,-30,-102,0),
(E'resource-native-1941-1276-89901',1,389,-30,-101,0),
(E'resource-native-1941-1276-89901',1,390,-30,-100,0),
(E'resource-native-1941-1276-89901',1,391,-30,-99,0),
(E'resource-native-1941-1276-89901',1,392,-30,-98,0),
(E'resource-native-1941-1276-89901',1,393,-30,-97,0),
(E'resource-native-1941-1276-89901',1,394,-30,-96,0),
(E'resource-native-1941-1276-89901',1,395,-30,-95,0),
(E'resource-native-1941-1276-89901',1,396,-30,-94,0),
(E'resource-native-1941-1276-89901',1,397,-30,-93,0),
(E'resource-native-1941-1276-89901',1,398,-30,-92,0),
(E'resource-native-1941-1276-89901',1,399,-30,-91,0),
(E'resource-native-1941-1276-89901',1,400,-30,-90,0),
(E'resource-native-1941-1276-89901',1,401,-30,-89,0),
(E'resource-native-1941-1276-89901',1,402,-30,-88,1),
(E'resource-native-1941-1276-89901',1,403,-30,-87,1),
(E'resource-native-1941-1276-89901',1,404,-30,-86,0),
(E'resource-native-1941-1276-89901',1,405,-30,-85,0),
(E'resource-native-1941-1276-89901',1,406,-30,-84,0),
(E'resource-native-1941-1276-89901',1,407,-30,-83,0),
(E'resource-native-1941-1276-89901',1,408,-30,-82,0),
(E'resource-native-1941-1276-89901',1,409,-29,-167,50),
(E'resource-native-1941-1276-89901',1,410,-29,-164,26),
(E'resource-native-1941-1276-89901',1,411,-29,-160,47),
(E'resource-native-1941-1276-89901',1,412,-29,-159,10),
(E'resource-native-1941-1276-89901',1,413,-29,-158,10),
(E'resource-native-1941-1276-89901',1,414,-29,-157,10),
(E'resource-native-1941-1276-89901',1,415,-29,-156,10),
(E'resource-native-1941-1276-89901',1,416,-29,-155,10),
(E'resource-native-1941-1276-89901',1,417,-29,-154,10),
(E'resource-native-1941-1276-89901',1,418,-29,-153,10),
(E'resource-native-1941-1276-89901',1,419,-29,-152,10),
(E'resource-native-1941-1276-89901',1,420,-29,-151,10),
(E'resource-native-1941-1276-89901',1,421,-29,-150,10),
(E'resource-native-1941-1276-89901',1,422,-29,-134,12),
(E'resource-native-1941-1276-89901',1,423,-29,-130,0),
(E'resource-native-1941-1276-89901',1,424,-29,-129,0),
(E'resource-native-1941-1276-89901',1,425,-29,-127,0),
(E'resource-native-1941-1276-89901',1,426,-29,-126,0),
(E'resource-native-1941-1276-89901',1,427,-29,-125,-2),
(E'resource-native-1941-1276-89901',1,428,-29,-112,0),
(E'resource-native-1941-1276-89901',1,429,-29,-111,0),
(E'resource-native-1941-1276-89901',1,430,-29,-110,0),
(E'resource-native-1941-1276-89901',1,431,-29,-109,0);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-323-56401',4,323,56401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7d29e3e575f931e8c4d016ab8fd11d9367f5d9e529f6e91d5593faf97541181e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-323-56401',4,0,E'resource-native-1542-323-56401',1),
(E'wakemu-native-resources-323-56401',4,1,E'resource-native-1543-323-56401',1),
(E'wakemu-native-resources-323-56401',4,2,E'resource-native-1544-323-56401',1),
(E'wakemu-native-resources-323-56401',4,3,E'resource-native-1545-323-56401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-327-56601',4,327,56601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'05be93b84a934f125a4e0fad74eea134f4c5853cafc17b606f35f5eb86d10a03',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-327-56601',4,0,E'resource-native-1320-327-56601',1),
(E'wakemu-native-resources-327-56601',4,1,E'resource-native-1321-327-56601',1),
(E'wakemu-native-resources-327-56601',4,2,E'resource-native-1322-327-56601',1),
(E'wakemu-native-resources-327-56601',4,3,E'resource-native-1323-327-56601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-458-61501',4,458,61501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'faaa11ec64d745b498f55d1932dd89165c41fc4bfbb3f9c31dd9cf5f0d88d70c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-458-61501',4,0,E'resource-native-1559-458-61501',1),
(E'wakemu-native-resources-458-61501',4,1,E'resource-native-1560-458-61501',1),
(E'wakemu-native-resources-458-61501',4,2,E'resource-native-1561-458-61501',1),
(E'wakemu-native-resources-458-61501',4,3,E'resource-native-1562-458-61501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-504-60601',4,504,60601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'b8b54a264334f9807d896663294fa61245de50a30d46b01ecd3061d8c60a849d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-504-60601',4,0,E'resource-native-1350-504-60601',1),
(E'wakemu-native-resources-504-60601',4,1,E'resource-native-1351-504-60601',1),
(E'wakemu-native-resources-504-60601',4,2,E'resource-native-1352-504-60601',1),
(E'wakemu-native-resources-504-60601',4,3,E'resource-native-1353-504-60601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-507-60701',4,507,60701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9100909dca249ffd445f1854b99d72f7c8723315c9510ffd550aa3beb17ca56b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-507-60701',4,0,E'resource-native-1365-507-60701',1),
(E'wakemu-native-resources-507-60701',4,1,E'resource-native-1366-507-60701',1),
(E'wakemu-native-resources-507-60701',4,2,E'resource-native-1367-507-60701',1),
(E'wakemu-native-resources-507-60701',4,3,E'resource-native-1368-507-60701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-508-60801',4,508,60801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7efc3020cc047bb95632cac0da50bd9c0cdf9a6603bd44c79ce54b7d6063c004',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-508-60801',4,0,E'resource-native-1380-508-60801',1),
(E'wakemu-native-resources-508-60801',4,1,E'resource-native-1381-508-60801',1),
(E'wakemu-native-resources-508-60801',4,2,E'resource-native-1382-508-60801',1),
(E'wakemu-native-resources-508-60801',4,3,E'resource-native-1383-508-60801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75601',4,527,75601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8d9ba36185d3f78aae63240f57936dfbb5ac160f7d89c513d84faa65ac6971a2',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75601',4,0,E'resource-native-989-527-75601',1),
(E'wakemu-native-resources-527-75601',4,1,E'resource-native-990-527-75601',1),
(E'wakemu-native-resources-527-75601',4,2,E'resource-native-991-527-75601',1),
(E'wakemu-native-resources-527-75601',4,3,E'resource-native-992-527-75601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75701',4,527,75701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ff0bbdb0f2a4dac993ac2d79898fe24ee8d6f8f1a41f2529ab374a72fc541778',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75701',4,0,E'resource-native-950-527-75701',1),
(E'wakemu-native-resources-527-75701',4,1,E'resource-native-951-527-75701',1),
(E'wakemu-native-resources-527-75701',4,2,E'resource-native-953-527-75701',1),
(E'wakemu-native-resources-527-75701',4,3,E'resource-native-954-527-75701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75801',4,527,75801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7dc1f24a0fa14d0f52941c8edef45ff7c6c4563320cc96cfc4b5227c7fc1ec6d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75801',4,0,E'resource-native-950-527-75801',1),
(E'wakemu-native-resources-527-75801',4,1,E'resource-native-951-527-75801',1),
(E'wakemu-native-resources-527-75801',4,2,E'resource-native-953-527-75801',1),
(E'wakemu-native-resources-527-75801',4,3,E'resource-native-954-527-75801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75901',4,527,75901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'b4eeba0bc1bde8fe8bfc6778113f98f7801e2ed0541506cb587cc40ae68d662b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75901',4,0,E'resource-native-989-527-75901',1),
(E'wakemu-native-resources-527-75901',4,1,E'resource-native-990-527-75901',1),
(E'wakemu-native-resources-527-75901',4,2,E'resource-native-991-527-75901',1),
(E'wakemu-native-resources-527-75901',4,3,E'resource-native-992-527-75901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76001',4,527,76001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7e8bf8aa531282c2561af0af829139df234689edd1e761e46c068444ef1b5642',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76001',4,0,E'resource-native-989-527-76001',1),
(E'wakemu-native-resources-527-76001',4,1,E'resource-native-990-527-76001',1),
(E'wakemu-native-resources-527-76001',4,2,E'resource-native-991-527-76001',1),
(E'wakemu-native-resources-527-76001',4,3,E'resource-native-992-527-76001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76101',4,527,76101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7039a2dc6fa6c15e033f24dab415480ed2cf95ffc4b9015eddd0507677efee51',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76101',4,0,E'resource-native-950-527-76101',1),
(E'wakemu-native-resources-527-76101',4,1,E'resource-native-951-527-76101',1),
(E'wakemu-native-resources-527-76101',4,2,E'resource-native-953-527-76101',1),
(E'wakemu-native-resources-527-76101',4,3,E'resource-native-954-527-76101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-546-62201',4,546,62201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1934dcbf73bb4dfaaa920c4d075e6879fc137d6333e86c735619df3d18ba3c7b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-546-62201',4,0,E'resource-native-950-546-62201',1),
(E'wakemu-native-resources-546-62201',4,1,E'resource-native-951-546-62201',1),
(E'wakemu-native-resources-546-62201',4,2,E'resource-native-953-546-62201',1),
(E'wakemu-native-resources-546-62201',4,3,E'resource-native-954-546-62201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-711-63401',4,711,63401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'70a835fabe9919261bee79628863107fc1c5fd3b3c05e912a58552056ea8fc69',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-711-63401',4,0,E'resource-native-1284-711-63401',1),
(E'wakemu-native-resources-711-63401',4,1,E'resource-native-1285-711-63401',1),
(E'wakemu-native-resources-711-63401',4,2,E'resource-native-1286-711-63401',1),
(E'wakemu-native-resources-711-63401',4,3,E'resource-native-1287-711-63401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-792-64601',4,792,64601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'eda8391c4a385b7ddf78722432d6b69c85e115a5ba72e2517d332e41190027eb',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-792-64601',4,0,E'resource-native-1395-792-64601',1),
(E'wakemu-native-resources-792-64601',4,1,E'resource-native-1396-792-64601',1),
(E'wakemu-native-resources-792-64601',4,2,E'resource-native-1397-792-64601',1),
(E'wakemu-native-resources-792-64601',4,3,E'resource-native-1398-792-64601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-793-64801',4,793,64801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4bcb0464ac03585549cba254dc3df6a444f3a8dd0a15f0112c4c70587139daf1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-793-64801',4,0,E'resource-native-1513-793-64801',1),
(E'wakemu-native-resources-793-64801',4,1,E'resource-native-1514-793-64801',1),
(E'wakemu-native-resources-793-64801',4,2,E'resource-native-1515-793-64801',1),
(E'wakemu-native-resources-793-64801',4,3,E'resource-native-1516-793-64801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-796-64701',4,796,64701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fa776e25f0a99f4effc620ec293470023b381d9c482ebc37124f4c740d0dd060',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-796-64701',4,0,E'resource-native-1410-796-64701',1),
(E'wakemu-native-resources-796-64701',4,1,E'resource-native-1411-796-64701',1),
(E'wakemu-native-resources-796-64701',4,2,E'resource-native-1412-796-64701',1),
(E'wakemu-native-resources-796-64701',4,3,E'resource-native-1413-796-64701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-843-65301',4,843,65301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2e5a404d79b1e613492542571124928738c697a5153905ee20d875e5c531e12d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-843-65301',4,0,E'resource-native-1461-843-65301',1),
(E'wakemu-native-resources-843-65301',4,1,E'resource-native-1462-843-65301',1),
(E'wakemu-native-resources-843-65301',4,2,E'resource-native-1463-843-65301',1),
(E'wakemu-native-resources-843-65301',4,3,E'resource-native-1464-843-65301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-853-65401',4,853,65401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9a9f3a04cf25f54801cc5406621f7cbf1a5a93a25156d78578abfdc605531dba',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-853-65401',4,0,E'resource-native-1465-853-65401',1),
(E'wakemu-native-resources-853-65401',4,1,E'resource-native-1466-853-65401',1),
(E'wakemu-native-resources-853-65401',4,2,E'resource-native-1467-853-65401',1),
(E'wakemu-native-resources-853-65401',4,3,E'resource-native-1468-853-65401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-922-69301',4,922,69301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'578608ad8ba0a37cbbb3f859d6fd0c904cb2cad7eb443fd76c074fc4f226b2ed',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-922-69301',4,0,E'resource-native-1190-922-69301',1),
(E'wakemu-native-resources-922-69301',4,1,E'resource-native-1191-922-69301',1),
(E'wakemu-native-resources-922-69301',4,2,E'resource-native-1192-922-69301',1),
(E'wakemu-native-resources-922-69301',4,3,E'resource-native-1193-922-69301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-923-69401',4,923,69401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f2445fd4cc6b1c89d4b9554f43ce1ce1c4825598cbbb536f554ac39093992726',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-923-69401',4,0,E'resource-native-1202-923-69401',1),
(E'wakemu-native-resources-923-69401',4,1,E'resource-native-1203-923-69401',1),
(E'wakemu-native-resources-923-69401',4,2,E'resource-native-1204-923-69401',1),
(E'wakemu-native-resources-923-69401',4,3,E'resource-native-1205-923-69401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69501',4,943,69501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'74bf819ba4303d3bce2dd5efd27b847379f916e67ced05cca13b4a7fb0d3e814',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69501',4,0,E'resource-native-1228-943-69501',1),
(E'wakemu-native-resources-943-69501',4,1,E'resource-native-1229-943-69501',1),
(E'wakemu-native-resources-943-69501',4,2,E'resource-native-1230-943-69501',1),
(E'wakemu-native-resources-943-69501',4,3,E'resource-native-1231-943-69501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69601',4,943,69601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'89f4893dd84588b871ec3b406c1c1765f8ab2174c7c15a84bd3b32d738a6b5f1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69601',4,0,E'resource-native-1232-943-69601',1),
(E'wakemu-native-resources-943-69601',4,1,E'resource-native-1233-943-69601',1),
(E'wakemu-native-resources-943-69601',4,2,E'resource-native-1234-943-69601',1),
(E'wakemu-native-resources-943-69601',4,3,E'resource-native-1235-943-69601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-71501',4,999,71501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c98ab70e55fa6b9a9c763a71e084fb8a37590a279052f4680c24f10d6c1b4540',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-71501',4,0,E'resource-native-1581-999-71501',1),
(E'wakemu-native-resources-999-71501',4,1,E'resource-native-1582-999-71501',1),
(E'wakemu-native-resources-999-71501',4,2,E'resource-native-1583-999-71501',1),
(E'wakemu-native-resources-999-71501',4,3,E'resource-native-1584-999-71501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-82201',4,999,82201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f388d576c4b03a989d1a92bb5e1ebcfbce059460629d02a51d38007dfe99e0a8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-82201',4,0,E'resource-native-1178-999-82201',1),
(E'wakemu-native-resources-999-82201',4,1,E'resource-native-1179-999-82201',1),
(E'wakemu-native-resources-999-82201',4,2,E'resource-native-1180-999-82201',1),
(E'wakemu-native-resources-999-82201',4,3,E'resource-native-1181-999-82201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1053-73701',4,1053,73701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'51fb651f5c3a82f83af3b86d509b3e2af89f3aa7edf5b1f361ff7d4ec4aebe2b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1053-73701',4,0,E'resource-native-1585-1053-73701',1),
(E'wakemu-native-resources-1053-73701',4,1,E'resource-native-1586-1053-73701',1),
(E'wakemu-native-resources-1053-73701',4,2,E'resource-native-1587-1053-73701',1),
(E'wakemu-native-resources-1053-73701',4,3,E'resource-native-1588-1053-73701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1118-78601',4,1118,78601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'07997cc44f78779e35ec5c3a3908b604d078dc00abe696294d56ea99e472917f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1118-78601',4,0,E'resource-native-1086-1118-78601',1),
(E'wakemu-native-resources-1118-78601',4,1,E'resource-native-1090-1118-78601',1),
(E'wakemu-native-resources-1118-78601',4,2,E'resource-native-1094-1118-78601',1),
(E'wakemu-native-resources-1118-78601',4,3,E'resource-native-1098-1118-78601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1119-78701',4,1119,78701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2c86dd3553f4f48fb99911bdd04985de91977cd2c348f6ddb40b1569e02ae192',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1119-78701',4,0,E'resource-native-1087-1119-78701',1),
(E'wakemu-native-resources-1119-78701',4,1,E'resource-native-1091-1119-78701',1),
(E'wakemu-native-resources-1119-78701',4,2,E'resource-native-1095-1119-78701',1),
(E'wakemu-native-resources-1119-78701',4,3,E'resource-native-1099-1119-78701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-79401',4,1120,79401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd5dae9268adb63c44a89e76aa338eccfa421597de0aa928abb6923bbf5f9981c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-79401',4,0,E'resource-native-1088-1120-79401',1),
(E'wakemu-native-resources-1120-79401',4,1,E'resource-native-1092-1120-79401',1),
(E'wakemu-native-resources-1120-79401',4,2,E'resource-native-1096-1120-79401',1),
(E'wakemu-native-resources-1120-79401',4,3,E'resource-native-1100-1120-79401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-80601',4,1120,80601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'97a8c4509b2d66786d078139464814654ac2d53a6c7b6f89cec2e5b1428cd01a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-80601',4,0,E'resource-native-1089-1120-80601',1),
(E'wakemu-native-resources-1120-80601',4,1,E'resource-native-1093-1120-80601',1),
(E'wakemu-native-resources-1120-80601',4,2,E'resource-native-1097-1120-80601',1),
(E'wakemu-native-resources-1120-80601',4,3,E'resource-native-1101-1120-80601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-79801',4,1122,79801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'762217736d87351546f1377a5e2183bfc6fa766c5a71d2437e123b468e862cbc',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-79801',4,0,E'resource-native-1140-1122-79801',1),
(E'wakemu-native-resources-1122-79801',4,1,E'resource-native-1143-1122-79801',1),
(E'wakemu-native-resources-1122-79801',4,2,E'resource-native-1146-1122-79801',1),
(E'wakemu-native-resources-1122-79801',4,3,E'resource-native-1149-1122-79801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-80001',4,1122,80001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cf9028ad8012044eb2ee8ecfbd8254518d1e9283bc7618779fbe706fc372b7ca',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-80001',4,0,E'resource-native-1141-1122-80001',1),
(E'wakemu-native-resources-1122-80001',4,1,E'resource-native-1144-1122-80001',1),
(E'wakemu-native-resources-1122-80001',4,2,E'resource-native-1147-1122-80001',1),
(E'wakemu-native-resources-1122-80001',4,3,E'resource-native-1150-1122-80001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1123-80101',4,1123,80101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9851d67b5eda9dea8410b829d197596dc0e457408abe62fd935ae0761bd1804f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1123-80101',4,0,E'resource-native-1142-1123-80101',1),
(E'wakemu-native-resources-1123-80101',4,1,E'resource-native-1145-1123-80101',1),
(E'wakemu-native-resources-1123-80101',4,2,E'resource-native-1148-1123-80101',1),
(E'wakemu-native-resources-1123-80101',4,3,E'resource-native-1151-1123-80101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81001',4,1124,81001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ae862f21607fe18a03d396f819a0c0954ed9f43bd56450e4a54768424e626e15',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81001',4,0,E'resource-native-1508-1124-81001',1),
(E'wakemu-native-resources-1124-81001',4,1,E'resource-native-1509-1124-81001',1),
(E'wakemu-native-resources-1124-81001',4,2,E'resource-native-1510-1124-81001',1),
(E'wakemu-native-resources-1124-81001',4,3,E'resource-native-1511-1124-81001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81101',4,1124,81101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c83242e938a67962089f87adb078148d9d201510a7ae6877e2b064e251b6c1a1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81101',4,0,E'resource-native-1114-1124-81101',1),
(E'wakemu-native-resources-1124-81101',4,1,E'resource-native-1115-1124-81101',1),
(E'wakemu-native-resources-1124-81101',4,2,E'resource-native-1116-1124-81101',1),
(E'wakemu-native-resources-1124-81101',4,3,E'resource-native-1117-1124-81101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79101',4,1134,79101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5a77b8f6211328be213037950dcabf6db1e8667f658605f413eddc77fda66a74',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79101',4,0,E'resource-native-1305-1134-79101',1),
(E'wakemu-native-resources-1134-79101',4,1,E'resource-native-1306-1134-79101',1),
(E'wakemu-native-resources-1134-79101',4,2,E'resource-native-1307-1134-79101',1),
(E'wakemu-native-resources-1134-79101',4,3,E'resource-native-1308-1134-79101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79201',4,1134,79201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'612b10dca855598512bf83bd677d63475794053ff9f94aa48f01f2fb471410a8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79201',4,0,E'resource-native-1626-1134-79201',1),
(E'wakemu-native-resources-1134-79201',4,1,E'resource-native-1627-1134-79201',1),
(E'wakemu-native-resources-1134-79201',4,2,E'resource-native-1628-1134-79201',1),
(E'wakemu-native-resources-1134-79201',4,3,E'resource-native-1629-1134-79201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80801',4,1135,80801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4e1b9f67e1cdb828f1ee635220c8762bdb8bfe6f25d3e11cd48aa5b9c78c9c84',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80801',4,0,E'resource-native-1674-1135-80801',1),
(E'wakemu-native-resources-1135-80801',4,1,E'resource-native-1675-1135-80801',1),
(E'wakemu-native-resources-1135-80801',4,2,E'resource-native-1676-1135-80801',1),
(E'wakemu-native-resources-1135-80801',4,3,E'resource-native-1677-1135-80801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80901',4,1135,80901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c17acb7d8319944a9cea227f2107ddc559033a20e159c789e604cc30bfef008f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80901',4,0,E'resource-native-1682-1135-80901',1),
(E'wakemu-native-resources-1135-80901',4,1,E'resource-native-1683-1135-80901',1),
(E'wakemu-native-resources-1135-80901',4,2,E'resource-native-1684-1135-80901',1),
(E'wakemu-native-resources-1135-80901',4,3,E'resource-native-1685-1135-80901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84301',4,1136,84301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1e449a6a99cb335423ba94f8263d852497396910c2a270633d6fc64d958f00f0',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84301',4,0,E'resource-native-1722-1136-84301',1),
(E'wakemu-native-resources-1136-84301',4,1,E'resource-native-1723-1136-84301',1),
(E'wakemu-native-resources-1136-84301',4,2,E'resource-native-1724-1136-84301',1),
(E'wakemu-native-resources-1136-84301',4,3,E'resource-native-1725-1136-84301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84401',4,1136,84401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8693c22f21ccee1361798c04925f366be1e0035f4dd15045e99708fb25a3e399',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84401',4,0,E'resource-native-1718-1136-84401',1),
(E'wakemu-native-resources-1136-84401',4,1,E'resource-native-1719-1136-84401',1),
(E'wakemu-native-resources-1136-84401',4,2,E'resource-native-1720-1136-84401',1),
(E'wakemu-native-resources-1136-84401',4,3,E'resource-native-1721-1136-84401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84501',4,1136,84501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'871b0fea1dfe7bb672d35f6ad6daada6c2e93b3e675281e4f5ea12f36c6755ec',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84501',4,0,E'resource-native-1714-1136-84501',1),
(E'wakemu-native-resources-1136-84501',4,1,E'resource-native-1715-1136-84501',1),
(E'wakemu-native-resources-1136-84501',4,2,E'resource-native-1716-1136-84501',1),
(E'wakemu-native-resources-1136-84501',4,3,E'resource-native-1717-1136-84501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-81901',4,1137,81901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ac2e5d24d4c4111db9b4516bd404eed646a5339000f9d4b07a7e4eceffb95353',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-81901',4,0,E'resource-native-1622-1137-81901',1),
(E'wakemu-native-resources-1137-81901',4,1,E'resource-native-1623-1137-81901',1),
(E'wakemu-native-resources-1137-81901',4,2,E'resource-native-1624-1137-81901',1),
(E'wakemu-native-resources-1137-81901',4,3,E'resource-native-1625-1137-81901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-82001',4,1137,82001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fbb48e40a843c3d22f44887f6e39d5b016984083f02da02c11e4d46b5e8aeb0d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-82001',4,0,E'resource-native-1698-1137-82001',1),
(E'wakemu-native-resources-1137-82001',4,1,E'resource-native-1699-1137-82001',1),
(E'wakemu-native-resources-1137-82001',4,2,E'resource-native-1700-1137-82001',1),
(E'wakemu-native-resources-1137-82001',4,3,E'resource-native-1701-1137-82001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-85901',4,1137,85901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5ae463549f56212cf7d361793d872b9f6645ba5e5eb448e1139ab0f7656bcd1a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-85901',4,0,E'resource-native-1706-1137-85901',1),
(E'wakemu-native-resources-1137-85901',4,1,E'resource-native-1707-1137-85901',1),
(E'wakemu-native-resources-1137-85901',4,2,E'resource-native-1708-1137-85901',1),
(E'wakemu-native-resources-1137-85901',4,3,E'resource-native-1709-1137-85901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-83801',4,1207,83801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e5b43d176fc320ad3df59685bb3635d34b2f1e91e477c2163c6c917e94fe23ee',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-83801',4,0,E'resource-native-1630-1207-83801',1),
(E'wakemu-native-resources-1207-83801',4,1,E'resource-native-1631-1207-83801',1),
(E'wakemu-native-resources-1207-83801',4,2,E'resource-native-1632-1207-83801',1),
(E'wakemu-native-resources-1207-83801',4,3,E'resource-native-1633-1207-83801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-86601',4,1207,86601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9739388a33e84e6fdd0440909896e6168e6bf47921f5c75431ee366b5373c53e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-86601',4,0,E'resource-native-1638-1207-86601',1),
(E'wakemu-native-resources-1207-86601',4,1,E'resource-native-1639-1207-86601',1),
(E'wakemu-native-resources-1207-86601',4,2,E'resource-native-1640-1207-86601',1),
(E'wakemu-native-resources-1207-86601',4,3,E'resource-native-1641-1207-86601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-84101',4,1208,84101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'76ff4e89bfef2a6ae4c51f41b6d321a9009e94428b60c9de99aaa777cdd1d985',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-84101',4,0,E'resource-native-1678-1208-84101',1),
(E'wakemu-native-resources-1208-84101',4,1,E'resource-native-1679-1208-84101',1),
(E'wakemu-native-resources-1208-84101',4,2,E'resource-native-1680-1208-84101',1),
(E'wakemu-native-resources-1208-84101',4,3,E'resource-native-1681-1208-84101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-86801',4,1208,86801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1ec7c3b781954500fd6ddaad17e27d83e670f73dd0fd55b6af5ed1feec225418',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-86801',4,0,E'resource-native-1686-1208-86801',1),
(E'wakemu-native-resources-1208-86801',4,1,E'resource-native-1687-1208-86801',1),
(E'wakemu-native-resources-1208-86801',4,2,E'resource-native-1688-1208-86801',1),
(E'wakemu-native-resources-1208-86801',4,3,E'resource-native-1689-1208-86801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-83901',4,1209,83901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'44305409aa58f65954eab915e831bb00bfddb5ca34267ff21d88675b44852d80',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-83901',4,0,E'resource-native-1690-1209-83901',1),
(E'wakemu-native-resources-1209-83901',4,1,E'resource-native-1691-1209-83901',1),
(E'wakemu-native-resources-1209-83901',4,2,E'resource-native-1692-1209-83901',1),
(E'wakemu-native-resources-1209-83901',4,3,E'resource-native-1693-1209-83901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-86701',4,1209,86701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'acd23e21a87c19d7909656ca99befed393e2b36ff3fb3c92fe5796e974439655',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-86701',4,0,E'resource-native-1710-1209-86701',1),
(E'wakemu-native-resources-1209-86701',4,1,E'resource-native-1711-1209-86701',1),
(E'wakemu-native-resources-1209-86701',4,2,E'resource-native-1712-1209-86701',1),
(E'wakemu-native-resources-1209-86701',4,3,E'resource-native-1713-1209-86701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-84001',4,1210,84001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5253fc9c74909c4f79db183eb4bc8a5f041cffbaf8b52baef16443c84387037d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-84001',4,0,E'resource-native-1702-1210-84001',1),
(E'wakemu-native-resources-1210-84001',4,1,E'resource-native-1703-1210-84001',1),
(E'wakemu-native-resources-1210-84001',4,2,E'resource-native-1704-1210-84001',1),
(E'wakemu-native-resources-1210-84001',4,3,E'resource-native-1705-1210-84001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-86901',4,1210,86901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'54f755da7b199c96d67e1aace849e5c35ce2959e20c826726170311617500928',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-86901',4,0,E'resource-native-1694-1210-86901',1),
(E'wakemu-native-resources-1210-86901',4,1,E'resource-native-1695-1210-86901',1),
(E'wakemu-native-resources-1210-86901',4,2,E'resource-native-1696-1210-86901',1),
(E'wakemu-native-resources-1210-86901',4,3,E'resource-native-1697-1210-86901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88501',4,1252,88501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e5685f00b291f5a952f46c95eca65eff5421e6dac5153d978558ab56dab3bc58',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88501',4,0,E'resource-native-1873-1252-88501',1),
(E'wakemu-native-resources-1252-88501',4,1,E'resource-native-1874-1252-88501',1),
(E'wakemu-native-resources-1252-88501',4,2,E'resource-native-1875-1252-88501',1),
(E'wakemu-native-resources-1252-88501',4,3,E'resource-native-1876-1252-88501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88701',4,1252,88701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9f198eecb19b03d6d7c84d98205ef6e004eb64bf223b40c1c05aec85bf15cb03',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88701',4,0,E'resource-native-1885-1252-88701',1),
(E'wakemu-native-resources-1252-88701',4,1,E'resource-native-1886-1252-88701',1),
(E'wakemu-native-resources-1252-88701',4,2,E'resource-native-1887-1252-88701',1),
(E'wakemu-native-resources-1252-88701',4,3,E'resource-native-1888-1252-88701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88801',4,1252,88801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ab913abd3cb15fa3a7e025baccb5cd89a4822fcd49d2ce75c1062b63a1f9d2e4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88801',4,0,E'resource-native-1881-1252-88801',1),
(E'wakemu-native-resources-1252-88801',4,1,E'resource-native-1882-1252-88801',1),
(E'wakemu-native-resources-1252-88801',4,2,E'resource-native-1883-1252-88801',1),
(E'wakemu-native-resources-1252-88801',4,3,E'resource-native-1884-1252-88801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89301',4,1264,89301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'22107703bd66d2290989fcc9a66be33171d94adb554fecd9d42b6b8e6ab8a434',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89301',4,0,E'resource-native-1217-1264-89301',1),
(E'wakemu-native-resources-1264-89301',4,1,E'resource-native-1218-1264-89301',1),
(E'wakemu-native-resources-1264-89301',4,2,E'resource-native-1219-1264-89301',1),
(E'wakemu-native-resources-1264-89301',4,3,E'resource-native-1220-1264-89301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89401',4,1264,89401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4041b51c21e5db820d3cbeb8485f3ebe29d72c012f3622432df3c4905bc9f24a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89401',4,0,E'resource-native-1141-1264-89401',1),
(E'wakemu-native-resources-1264-89401',4,1,E'resource-native-1144-1264-89401',1),
(E'wakemu-native-resources-1264-89401',4,2,E'resource-native-1147-1264-89401',1),
(E'wakemu-native-resources-1264-89401',4,3,E'resource-native-1150-1264-89401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89501',4,1264,89501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'84d687f7b1476e315e24c76cf8144210833d3d24b4582fa668b9eec3e9c96d04',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89501',4,0,E'resource-native-1217-1264-89501',1),
(E'wakemu-native-resources-1264-89501',4,1,E'resource-native-1218-1264-89501',1),
(E'wakemu-native-resources-1264-89501',4,2,E'resource-native-1219-1264-89501',1),
(E'wakemu-native-resources-1264-89501',4,3,E'resource-native-1220-1264-89501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89701',4,1264,89701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5696d64d17299715b84d836e1e4af1ed9104af5a563cd8d640d24dcc201db0c1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89701',4,0,E'resource-native-1585-1264-89701',1),
(E'wakemu-native-resources-1264-89701',4,1,E'resource-native-1586-1264-89701',1),
(E'wakemu-native-resources-1264-89701',4,2,E'resource-native-1587-1264-89701',1),
(E'wakemu-native-resources-1264-89701',4,3,E'resource-native-1588-1264-89701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-89901',4,1276,89901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'94414ee417c6a67ac3d939f63c329a8bd6f748657315e3028fe6912ab2e9f47a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-89901',4,0,E'resource-native-1941-1276-89901',1),
(E'wakemu-native-resources-1276-89901',4,1,E'resource-native-1945-1276-89901',1),
(E'wakemu-native-resources-1276-89901',4,2,E'resource-native-1949-1276-89901',1),
(E'wakemu-native-resources-1276-89901',4,3,E'resource-native-1953-1276-89901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90001',4,1276,90001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6fb0500c75a5b1696064b51d14e4f13a85bfc6966f62acb48b301ae46af083e4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90001',4,0,E'resource-native-1944-1276-90001',1),
(E'wakemu-native-resources-1276-90001',4,1,E'resource-native-1948-1276-90001',1),
(E'wakemu-native-resources-1276-90001',4,2,E'resource-native-1952-1276-90001',1),
(E'wakemu-native-resources-1276-90001',4,3,E'resource-native-1956-1276-90001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90101',4,1276,90101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a102dd89d06332ec7c61d5bd2bd86e60b93ce638642b404561c2c976f9e94da8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90101',4,0,E'resource-native-1942-1276-90101',1),
(E'wakemu-native-resources-1276-90101',4,1,E'resource-native-1946-1276-90101',1),
(E'wakemu-native-resources-1276-90101',4,2,E'resource-native-1950-1276-90101',1),
(E'wakemu-native-resources-1276-90101',4,3,E'resource-native-1954-1276-90101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90201',4,1276,90201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'58c0d5894875ab87c17dcd0ed8d54c68190bf2d65d8f0d6e79b9a305fd042903',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90201',4,0,E'resource-native-1943-1276-90201',1),
(E'wakemu-native-resources-1276-90201',4,1,E'resource-native-1947-1276-90201',1),
(E'wakemu-native-resources-1276-90201',4,2,E'resource-native-1951-1276-90201',1),
(E'wakemu-native-resources-1276-90201',4,3,E'resource-native-1955-1276-90201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90601',4,1295,90601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0ba8210a6fbcf544abcdc826e5951a3f40fbc8bfd6103ff45fc0131945f45996',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90601',4,0,E'resource-native-1335-1295-90601',1),
(E'wakemu-native-resources-1295-90601',4,1,E'resource-native-1336-1295-90601',1),
(E'wakemu-native-resources-1295-90601',4,2,E'resource-native-1337-1295-90601',1),
(E'wakemu-native-resources-1295-90601',4,3,E'resource-native-1338-1295-90601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90701',4,1295,90701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fac14cf77239e6a35bb1c7b4895deb8d6b7747a8dd7d31b5feb5126e6c9883e7',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90701',4,0,E'resource-native-1983-1295-90701',1),
(E'wakemu-native-resources-1295-90701',4,1,E'resource-native-1986-1295-90701',1),
(E'wakemu-native-resources-1295-90701',4,2,E'resource-native-1989-1295-90701',1),
(E'wakemu-native-resources-1295-90701',4,3,E'resource-native-1992-1295-90701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1297-90801',4,1297,90801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'91805cfc2fd3e5ded7f4825bb62cbfdcf796385ef01717388b264a8c9fffa6fa',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1297-90801',4,0,E'resource-native-1984-1297-90801',1),
(E'wakemu-native-resources-1297-90801',4,1,E'resource-native-1987-1297-90801',1),
(E'wakemu-native-resources-1297-90801',4,2,E'resource-native-1990-1297-90801',1),
(E'wakemu-native-resources-1297-90801',4,3,E'resource-native-1993-1297-90801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1298-90901',4,1298,90901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'da6ca25a197d011dd423ba537e7cd396920ed428a44e00b38f063827d192cdc0',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1298-90901',4,0,E'resource-native-1982-1298-90901',1),
(E'wakemu-native-resources-1298-90901',4,1,E'resource-native-1985-1298-90901',1),
(E'wakemu-native-resources-1298-90901',4,2,E'resource-native-1988-1298-90901',1),
(E'wakemu-native-resources-1298-90901',4,3,E'resource-native-1991-1298-90901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1305-91201',4,1305,91201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f12a0f6b991586cf60ba20b647ca68d1677cf78d1df2d69ea1b68c43f77ccdda',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1305-91201',4,0,E'resource-native-2016-1305-91201',1),
(E'wakemu-native-resources-1305-91201',4,1,E'resource-native-2017-1305-91201',1),
(E'wakemu-native-resources-1305-91201',4,2,E'resource-native-2018-1305-91201',1),
(E'wakemu-native-resources-1305-91201',4,3,E'resource-native-2019-1305-91201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1309-91301',4,1309,91301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fb29d8903c58129c762c21f20c81673685fd7107a5f0617776c67f9ccba95d0b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1309-91301',4,0,E'resource-native-2016-1309-91301',1),
(E'wakemu-native-resources-1309-91301',4,1,E'resource-native-2017-1309-91301',1),
(E'wakemu-native-resources-1309-91301',4,2,E'resource-native-2018-1309-91301',1),
(E'wakemu-native-resources-1309-91301',4,3,E'resource-native-2019-1309-91301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1326-91401',4,1326,91401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8c7e32efc7a018c4ae1255d39ca34b56212daa1e94fc70234d53b7e82c539e17',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1326-91401',4,0,E'resource-native-2016-1326-91401',1),
(E'wakemu-native-resources-1326-91401',4,1,E'resource-native-2017-1326-91401',1),
(E'wakemu-native-resources-1326-91401',4,2,E'resource-native-2018-1326-91401',1),
(E'wakemu-native-resources-1326-91401',4,3,E'resource-native-2019-1326-91401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1333-91801',4,1333,91801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'08d1cf4d665f3d6d5845ba510ec99127092a761032c7095c48fab098e79230ba',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1333-91801',4,0,E'resource-native-2016-1333-91801',1),
(E'wakemu-native-resources-1333-91801',4,1,E'resource-native-2017-1333-91801',1),
(E'wakemu-native-resources-1333-91801',4,2,E'resource-native-2018-1333-91801',1),
(E'wakemu-native-resources-1333-91801',4,3,E'resource-native-2019-1333-91801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1338-92001',4,1338,92001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f65bde9aa7807bd1c1034b70ea284826ec92c02d3216bf38dcab5009f6a36329',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1338-92001',4,0,E'resource-native-2016-1338-92001',1),
(E'wakemu-native-resources-1338-92001',4,1,E'resource-native-2017-1338-92001',1),
(E'wakemu-native-resources-1338-92001',4,2,E'resource-native-2018-1338-92001',1),
(E'wakemu-native-resources-1338-92001',4,3,E'resource-native-2019-1338-92001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1358-92201',4,1358,92201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c72b548d8ccc8b91f2d68de36b319785669c47f20811c677d6b7d005fd8ccd41',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1358-92201',4,0,E'resource-native-2032-1358-92201',1),
(E'wakemu-native-resources-1358-92201',4,1,E'resource-native-2037-1358-92201',1),
(E'wakemu-native-resources-1358-92201',4,2,E'resource-native-2042-1358-92201',1),
(E'wakemu-native-resources-1358-92201',4,3,E'resource-native-2043-1358-92201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1359-92301',4,1359,92301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'00f6cb0a0082aff7974608c3528edd30b149bfd928bb4fb68bfffc2a30c1d01a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1359-92301',4,0,E'resource-native-2033-1359-92301',1),
(E'wakemu-native-resources-1359-92301',4,1,E'resource-native-2038-1359-92301',1),
(E'wakemu-native-resources-1359-92301',4,2,E'resource-native-2044-1359-92301',1),
(E'wakemu-native-resources-1359-92301',4,3,E'resource-native-2048-1359-92301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1364-93001',4,1364,93001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0cdd690bb5dca5fdcee2213a830732726e428ad8469ddf3b215a2d5aa735c195',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1364-93001',4,0,E'resource-native-2034-1364-93001',1),
(E'wakemu-native-resources-1364-93001',4,1,E'resource-native-2039-1364-93001',1),
(E'wakemu-native-resources-1364-93001',4,2,E'resource-native-2045-1364-93001',1),
(E'wakemu-native-resources-1364-93001',4,3,E'resource-native-2049-1364-93001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1365-92601',4,1365,92601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'793766c67b355e5c852471cba4435fcf3206535df1d16397caabc88b3b36fd32',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1365-92601',4,0,E'resource-native-2036-1365-92601',1),
(E'wakemu-native-resources-1365-92601',4,1,E'resource-native-2041-1365-92601',1),
(E'wakemu-native-resources-1365-92601',4,2,E'resource-native-2047-1365-92601',1),
(E'wakemu-native-resources-1365-92601',4,3,E'resource-native-2051-1365-92601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1368-92901',4,1368,92901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7b4ddaa1b9765fa2c91c76c03a30967ea98d4572f26c3711dedcf823bbb0130d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1368-92901',4,0,E'resource-native-2035-1368-92901',1),
(E'wakemu-native-resources-1368-92901',4,1,E'resource-native-2040-1368-92901',1),
(E'wakemu-native-resources-1368-92901',4,2,E'resource-native-2046-1368-92901',1),
(E'wakemu-native-resources-1368-92901',4,3,E'resource-native-2050-1368-92901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93301',4,1384,93301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6b98605d07dd21d31a8510862bf73fb1522287d6f9e6e674599adce3d198ed36',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93301',4,0,E'resource-native-2112-1384-93301',1),
(E'wakemu-native-resources-1384-93301',4,1,E'resource-native-2116-1384-93301',1),
(E'wakemu-native-resources-1384-93301',4,2,E'resource-native-2120-1384-93301',1),
(E'wakemu-native-resources-1384-93301',4,3,E'resource-native-2124-1384-93301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93501',4,1384,93501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5d50d79f5673a3b058b85d26ff2f61b9da2c05e00fa3b2e812cf444729b18d04',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93501',4,0,E'resource-native-1428-1384-93501',1),
(E'wakemu-native-resources-1384-93501',4,1,E'resource-native-1429-1384-93501',1),
(E'wakemu-native-resources-1384-93501',4,2,E'resource-native-1430-1384-93501',1),
(E'wakemu-native-resources-1384-93501',4,3,E'resource-native-2110-1384-93501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93801',4,1384,93801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ed8b58939232e1e552cc8aac468c7c0d48deee8876034d52d7f35bba95173d60',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93801',4,0,E'resource-native-1436-1384-93801',1),
(E'wakemu-native-resources-1384-93801',4,1,E'resource-native-1437-1384-93801',1),
(E'wakemu-native-resources-1384-93801',4,2,E'resource-native-1438-1384-93801',1),
(E'wakemu-native-resources-1384-93801',4,3,E'resource-native-2109-1384-93801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93901',4,1384,93901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'77b35e9df0bf189e36de782c325a47e1d1f39fae80f14ee38c5dc184c325549e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93901',4,0,E'resource-native-2113-1384-93901',1),
(E'wakemu-native-resources-1384-93901',4,1,E'resource-native-2117-1384-93901',1),
(E'wakemu-native-resources-1384-93901',4,2,E'resource-native-2121-1384-93901',1),
(E'wakemu-native-resources-1384-93901',4,3,E'resource-native-2125-1384-93901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1390-93701',4,1390,93701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0ecdc8d2100dacd50818e57d7af986c4335b9ae629e1ef5083ace74cb3307846',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1390-93701',4,0,E'resource-native-2114-1390-93701',1),
(E'wakemu-native-resources-1390-93701',4,1,E'resource-native-2118-1390-93701',1),
(E'wakemu-native-resources-1390-93701',4,2,E'resource-native-2122-1390-93701',1),
(E'wakemu-native-resources-1390-93701',4,3,E'resource-native-2126-1390-93701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94201',4,1401,94201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5e34b15955e25e03cfaa4174e5d06fbad583a9b744d146d08dad1dec7de5ad59',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94201',4,0,E'resource-native-2220-1401-94201',1),
(E'wakemu-native-resources-1401-94201',4,1,E'resource-native-2221-1401-94201',1),
(E'wakemu-native-resources-1401-94201',4,2,E'resource-native-2222-1401-94201',1),
(E'wakemu-native-resources-1401-94201',4,3,E'resource-native-2223-1401-94201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94301',4,1401,94301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e1d3a65c627375020c61c3729d4a5e2d03de344a5f6d2b7577c18788769169b5',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94301',4,0,E'resource-native-2207-1401-94301',1),
(E'wakemu-native-resources-1401-94301',4,1,E'resource-native-2208-1401-94301',1),
(E'wakemu-native-resources-1401-94301',4,2,E'resource-native-2209-1401-94301',1),
(E'wakemu-native-resources-1401-94301',4,3,E'resource-native-2210-1401-94301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94401',4,1401,94401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'75bf0f09273a9b54b5a647b1e5b1410caa58cd1b3f32b732a0ed64e089421e54',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94401',4,0,E'resource-native-2194-1401-94401',1),
(E'wakemu-native-resources-1401-94401',4,1,E'resource-native-2195-1401-94401',1),
(E'wakemu-native-resources-1401-94401',4,2,E'resource-native-2196-1401-94401',1),
(E'wakemu-native-resources-1401-94401',4,3,E'resource-native-2197-1401-94401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94501',4,1401,94501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cb9954b31d3ff33879b34569e87f6451227b1576137b7084db8b9513bdc499d4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94501',4,0,E'resource-native-2233-1401-94501',1),
(E'wakemu-native-resources-1401-94501',4,1,E'resource-native-2234-1401-94501',1),
(E'wakemu-native-resources-1401-94501',4,2,E'resource-native-2235-1401-94501',1),
(E'wakemu-native-resources-1401-94501',4,3,E'resource-native-2236-1401-94501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94601',4,1401,94601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'abcb0406cb66ddf1529843cb52c69dff16402b829933856180fd07c071a2d18c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94601',4,0,E'resource-native-2246-1401-94601',1),
(E'wakemu-native-resources-1401-94601',4,1,E'resource-native-2247-1401-94601',1),
(E'wakemu-native-resources-1401-94601',4,2,E'resource-native-2248-1401-94601',1),
(E'wakemu-native-resources-1401-94601',4,3,E'resource-native-2249-1401-94601',1);

-- Explicit result mappings only. Import before sealing existing disabled profiles.
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'resource-native-1953-1276-89901',1,E'installed-environmental-source-v1',-1953,2966,E'wakemu.original-resource-single-primary-base-result.v1',0,E'global_progress',E'original-single-unconditional-primary-list',E'original-primary-result-index-zero',E'wakemu.simple-resource-completed-objective-score.v1');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,E'wakemu.original-resource-rank-bands-base-rewards.v1',E'ranked_winners',E'original-single-unconditional-primary-list',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.race-result-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'resource-native-1945-1276-89901',1,E'installed-environmental-source-v1',-1945,0,2950,NULL,NULL);
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'resource-native-1941-1276-89901',1,E'installed-environmental-source-v1',-1941,2946,E'wakemu.original-resource-single-primary-base-result.v1',0,E'personal_progress',E'original-single-unconditional-primary-list',E'original-primary-result-index-zero',E'wakemu.simple-resource-completed-objective-score.v1');
COMMIT;
