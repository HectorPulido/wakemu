-- Disabled sealed destruction profiles from explicitly identified targets; no DB import or activation.
-- Requires original275/278, runtime274/282/284/288/289/290, source/action/population/UI301.
-- Per-group member sizing2..5 is declared Wakemu; no original template composition is claimed.
BEGIN;
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1328 AND map_id=327 AND region_id=56601 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1328 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=327 AND region_id=56601) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1328-327-56601',1,-1328,E'monster_destroy',E'solo',327,56601,600000,NULL,0,81,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'023405db5c0f1deb8737c79c4485631ed4f0bb6e9baa393cad1271d8c2f0bcf0',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1328-327-56601',1,E'mob',E'monster_destroy',2253,265,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,E'wakemu.explicit-public-target-native-destroy-v1',2253,265);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1328-327-56601',1,-1328,0,180,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1328-327-56601',1,E'proposed',0),
(E'destroy-native-1328-327-56601',1,E'active',1),
(E'destroy-native-1328-327-56601',1,E'completed',2),
(E'destroy-native-1328-327-56601',1,E'expired',2),
(E'destroy-native-1328-327-56601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1328-327-56601',1,0,E'xp',NULL,234554,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1328-327-56601',1,1,E'item',21118,3,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1328-327-56601',1,E'installed-environmental-source-v1',-1328,2123,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'personal_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1327 AND map_id=327 AND region_id=56601 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1327 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=327 AND region_id=56601) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1327-327-56601',1,-1327,E'monster_destroy',E'race',327,56601,600000,NULL,0,81,245,1,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'88135f87805f8ca315b2de393379fe291c27cdc7c19b12b7ce4955d96e0c11f2',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1327-327-56601',1,E'mob',E'monster_destroy',2253,265,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,E'wakemu.explicit-public-target-native-destroy-v1',2253,265);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1327-327-56601',1,-1327,0,180,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1327-327-56601',1,E'proposed',0),
(E'destroy-native-1327-327-56601',1,E'active',1),
(E'destroy-native-1327-327-56601',1,E'completed',2),
(E'destroy-native-1327-327-56601',1,E'expired',2),
(E'destroy-native-1327-327-56601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',1,NULL,NULL),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1327-327-56601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-original-destroy-group-capacity.v1;one-character-one-place;not-original-winner-limit');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'ranked_winners',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1327-327-56601',1,E'installed-environmental-source-v1',-1327,0,2122,NULL,NULL);
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1327-327-56601',1,0,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1327-327-56601',1,1,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1326 AND map_id=327 AND region_id=56601 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1326 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=327 AND region_id=56601) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1326-327-56601',1,-1326,E'monster_destroy',E'competitive',327,56601,600000,NULL,0,81,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'50ec614dde6029e602c0894951f3450592278adb0ac8fbdef3ffb57762c13126',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1326-327-56601',1,E'mob',E'monster_destroy',2253,265,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,E'wakemu.explicit-public-target-native-destroy-v1',2253,265);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1326-327-56601',1,-1326,0,180,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1326-327-56601',1,E'proposed',0),
(E'destroy-native-1326-327-56601',1,E'active',1),
(E'destroy-native-1326-327-56601',1,E'completed',2),
(E'destroy-native-1326-327-56601',1,E'expired',2),
(E'destroy-native-1326-327-56601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,10,E'nbMobMax',E'leader_progress',E'mob',NULL,NULL,E'wakemu.group-leading-personal-monster-progress.v1',NULL),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1326-327-56601',1,E'score_at_deadline',2,E'character_id',E'wakemu.original-destroy-rank-conditions.v1;all-eligible-fallback;character-id-ties');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'all_eligible',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,0,2120,1,1),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,1,2121,2,2),
(E'destroy-native-1326-327-56601',1,E'installed-environmental-source-v1',-1326,2,2339,NULL,NULL);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1325 AND map_id=327 AND region_id=56601 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1325 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=327 AND region_id=56601) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1325-327-56601',1,-1325,E'monster_destroy',E'collaborative',327,56601,900000,NULL,0,81,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'c12b33910749b3180ec6dcc2212de86f98a08dbe85675ceabb5f1f2b2658e587',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1325-327-56601',1,E'mob',E'monster_destroy',2253,265,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,E'wakemu.explicit-public-target-native-destroy-v1',2253,265);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1325-327-56601',1,-1325,0,180,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1325-327-56601',1,E'proposed',0),
(E'destroy-native-1325-327-56601',1,E'active',1),
(E'destroy-native-1325-327-56601',1,E'completed',2),
(E'destroy-native-1325-327-56601',1,E'expired',2),
(E'destroy-native-1325-327-56601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,10,E'nbMobMin',E'declared_threshold',NULL,E'nbmobforreward',5,E'wakemu.original-species-group-profiles.v1;native-levels-not-player-bands;random298;ui299',NULL),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1325-327-56601',1,0,E'xp',NULL,1012930,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1325-327-56601',1,1,E'item',21118,12,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1325-327-56601',1,E'installed-environmental-source-v1',-1325,2119,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'global_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1225 AND map_id=1264 AND region_id=89301 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1225 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89301) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1225-1264-89301',1,-1225,E'monster_destroy',E'solo',1264,89301,600000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'6326c56f72140f084d3f515cbb494717095645fe5080943a76185e1ef48eff25',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1225-1264-89301',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1225-1264-89301',1,-1225,0,379,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1225-1264-89301',1,E'proposed',0),
(E'destroy-native-1225-1264-89301',1,E'active',1),
(E'destroy-native-1225-1264-89301',1,E'completed',2),
(E'destroy-native-1225-1264-89301',1,E'expired',2),
(E'destroy-native-1225-1264-89301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1225-1264-89301',1,0,E'xp',NULL,140006,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1225-1264-89301',1,1,E'item',21117,3,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1225-1264-89301',1,E'installed-environmental-source-v1',-1225,2023,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'personal_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1225 AND map_id=1264 AND region_id=89501 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1225 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89501) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1225-1264-89501',1,-1225,E'monster_destroy',E'solo',1264,89501,600000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'29ab1805ef269b16219c4398724e4a106ef79e5d473543fbc6cb37aafd6c2078',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1225-1264-89501',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1225-1264-89501',1,-1225,0,382,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1225-1264-89501',1,E'proposed',0),
(E'destroy-native-1225-1264-89501',1,E'active',1),
(E'destroy-native-1225-1264-89501',1,E'completed',2),
(E'destroy-native-1225-1264-89501',1,E'expired',2),
(E'destroy-native-1225-1264-89501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1225-1264-89501',1,0,E'xp',NULL,140006,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1225-1264-89501',1,1,E'item',21117,3,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1225-1264-89501',1,E'installed-environmental-source-v1',-1225,2023,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'personal_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1223 AND map_id=1264 AND region_id=89301 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1223 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89301) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1223-1264-89301',1,-1223,E'monster_destroy',E'competitive',1264,89301,600000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e2b4f51b6bbf1f7e9109d5917b12f0ffd6737228cfd7b5e8e9fee7b31336649e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1223-1264-89301',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1223-1264-89301',1,-1223,0,379,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1223-1264-89301',1,E'proposed',0),
(E'destroy-native-1223-1264-89301',1,E'active',1),
(E'destroy-native-1223-1264-89301',1,E'completed',2),
(E'destroy-native-1223-1264-89301',1,E'expired',2),
(E'destroy-native-1223-1264-89301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,10,E'nbMobMax',E'leader_progress',E'mob',NULL,NULL,E'wakemu.group-leading-personal-monster-progress.v1',NULL),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1223-1264-89301',1,E'score_at_deadline',2,E'character_id',E'wakemu.original-destroy-rank-conditions.v1;all-eligible-fallback;character-id-ties');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'all_eligible',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,0,2020,1,1),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,1,2021,2,2),
(E'destroy-native-1223-1264-89301',1,E'installed-environmental-source-v1',-1223,2,2353,NULL,NULL);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1223 AND map_id=1264 AND region_id=89501 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1223 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89501) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1223-1264-89501',1,-1223,E'monster_destroy',E'competitive',1264,89501,600000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'af1196a8e5acae25a3f8cf8a8e19b0c28f66d40fec2cf9c6ef0efe54ad41f3e4',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1223-1264-89501',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',5);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1223-1264-89501',1,-1223,0,382,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1223-1264-89501',1,E'proposed',0),
(E'destroy-native-1223-1264-89501',1,E'active',1),
(E'destroy-native-1223-1264-89501',1,E'completed',2),
(E'destroy-native-1223-1264-89501',1,E'expired',2),
(E'destroy-native-1223-1264-89501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,10,E'nbMobMax',E'leader_progress',E'mob',NULL,NULL,E'wakemu.group-leading-personal-monster-progress.v1',NULL),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1223-1264-89501',1,E'score_at_deadline',2,E'character_id',E'wakemu.original-destroy-rank-conditions.v1;all-eligible-fallback;character-id-ties');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'all_eligible',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,0,2020,1,1),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,1,2021,2,2),
(E'destroy-native-1223-1264-89501',1,E'installed-environmental-source-v1',-1223,2,2353,NULL,NULL);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1222 AND map_id=1264 AND region_id=89301 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1222 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89301) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1222-1264-89301',1,-1222,E'monster_destroy',E'collaborative',1264,89301,900000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a3049730be6bf502c024e96727f0d6dd462bd2c3327dbca407c1338c27582ae4',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1222-1264-89301',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1222-1264-89301',1,-1222,0,379,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1222-1264-89301',1,E'proposed',0),
(E'destroy-native-1222-1264-89301',1,E'active',1),
(E'destroy-native-1222-1264-89301',1,E'completed',2),
(E'destroy-native-1222-1264-89301',1,E'expired',2),
(E'destroy-native-1222-1264-89301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,10,E'nbMobMin',E'declared_threshold',NULL,E'nbmobforreward',5,E'wakemu.original-species-group-profiles.v1;native-levels-not-player-bands;random298;ui299',NULL),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1222-1264-89301',1,0,E'xp',NULL,599650,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1222-1264-89301',1,1,E'item',21117,12,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1222-1264-89301',1,E'installed-environmental-source-v1',-1222,2019,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'global_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1222 AND map_id=1264 AND region_id=89501 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1222 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89501) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1222-1264-89501',1,-1222,E'monster_destroy',E'collaborative',1264,89501,900000,NULL,0,66,245,5,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'd46ae920057960905e451221d06033b38a65e2511bbf6d89865a4e02cc1ccacd',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1222-1264-89501',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1222-1264-89501',1,-1222,0,382,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1222-1264-89501',1,E'proposed',0),
(E'destroy-native-1222-1264-89501',1,E'active',1),
(E'destroy-native-1222-1264-89501',1,E'completed',2),
(E'destroy-native-1222-1264-89501',1,E'expired',2),
(E'destroy-native-1222-1264-89501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',5,NULL,NULL),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,10,E'nbMobMin',E'declared_threshold',NULL,E'nbmobforreward',5,E'wakemu.original-species-group-profiles.v1;native-levels-not-player-bands;random298;ui299',NULL),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,11,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,12,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1222-1264-89501',1,0,E'xp',NULL,599650,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1222-1264-89501',1,1,E'item',21117,12,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_profile_simple_result_policy (profile_key,version,source_key,native_scenario_id,reward_id,policy_contract,primary_reward_index,parameter_mode,source_authority,mapping_authority,parameter_authority) VALUES
(E'destroy-native-1222-1264-89501',1,E'installed-environmental-source-v1',-1222,2019,E'wakemu.original-destroy-single-primary-base-result.v1',0,E'global_progress',E'original-single-unconditional-primary-base-reward',E'original-primary-list-index-zero',E'wakemu.result-parameter-personal-or-global-progress.v1');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1221 AND map_id=1264 AND region_id=89301 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1221 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89301) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1221-1264-89301',1,-1221,E'monster_destroy',E'race',1264,89301,600000,NULL,0,66,245,1,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'af8fd2b0a2390973ee4510e479127d9fc9079597300bee1c5baef52af2faad35',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1221-1264-89301',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1221-1264-89301',1,-1221,0,379,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1221-1264-89301',1,E'proposed',0),
(E'destroy-native-1221-1264-89301',1,E'active',1),
(E'destroy-native-1221-1264-89301',1,E'completed',2),
(E'destroy-native-1221-1264-89301',1,E'expired',2),
(E'destroy-native-1221-1264-89301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',1,NULL,NULL),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1221-1264-89301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-original-destroy-group-capacity.v1;one-character-one-place;not-original-winner-limit');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'ranked_winners',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1221-1264-89301',1,E'installed-environmental-source-v1',-1221,0,2018,NULL,NULL);
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1221-1264-89301',1,0,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1221-1264-89301',1,1,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1221 AND map_id=1264 AND region_id=89501 AND native_cells_present AND native_criteria='') OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_bindings WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1221 AND policy_version=E'wakemu.environmental-exact-species-genesis-v1' AND map_id=1264 AND region_id=89501) THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'destroy-native-1221-1264-89501',1,-1221,E'monster_destroy',E'race',1264,89501,600000,NULL,0,66,245,1,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a9c4b7a7e43fbf0af5160158844f023c82c5c78bc435d3b10f13261985733525',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'destroy-native-1221-1264-89501',1,E'mob',E'monster_destroy',2236,263,NULL,E'interaction',1);
INSERT INTO environmental_profile_destroy_ui (profile_key,version,source_key,native_scenario_id,authority) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_destroy_policy (profile_key,version,source_key,scenario_id,policy_version,monster_reference,action_id) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,E'wakemu.explicit-public-target-native-destroy-v1',2236,263);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'destroy-native-1221-1264-89501',1,-1221,0,382,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'destroy-native-1221-1264-89501',1,E'proposed',0),
(E'destroy-native-1221-1264-89501',1,E'active',1),
(E'destroy-native-1221-1264-89501',1,E'completed',2),
(E'destroy-native-1221-1264-89501',1,E'expired',2),
(E'destroy-native-1221-1264-89501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,E'wakemu.durable-native-variable-projection.v1',E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,2,E'nbGroupForReward',E'configconstant',NULL,E'nbgroupforreward',0,NULL,NULL),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,3,E'nbGroupGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,4,E'nbGroupLeft',E'remaining',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,5,E'nbGroupPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'group'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,6,E'nbGroupSpawned',E'spawned',NULL,NULL,NULL,NULL,E'group'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,7,E'nbMobForReward',E'configconstant',NULL,E'nbmobforreward',1,NULL,NULL),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,8,E'nbMobGlobal',E'entity_global_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,9,E'nbMobLeft',E'remaining',NULL,NULL,NULL,NULL,E'monster'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,10,E'nbMobPlayer',E'entity_personal_progress',E'mob',NULL,NULL,E'wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts',E'monster'),
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,11,E'nbMobSpawned',E'spawned',NULL,NULL,NULL,NULL,E'monster');
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'destroy-native-1221-1264-89501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-original-destroy-group-capacity.v1;one-character-one-place;not-original-winner-limit');
INSERT INTO environmental_profile_ranked_reward_policy (profile_key,version,source_key,native_scenario_id,policy_contract,eligibility_contract,source_authority,grant_authority,result_parameter_mode,result_parameter,parameter_authority) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,E'wakemu.original-destroy-rank-bands-base-rewards.v1',E'ranked_winners',E'original-primary-list-and-exact-rank-predicates',E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant',E'winner_score',NULL,E'wakemu.result-parameter-winning-position-one-score.v1');
INSERT INTO environmental_profile_ranked_reward_bands (profile_key,version,source_key,native_scenario_id,primary_reward_index,reward_id,rank_min,rank_max) VALUES
(E'destroy-native-1221-1264-89501',1,E'installed-environmental-source-v1',-1221,0,2018,NULL,NULL);
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'destroy-native-1221-1264-89501',1,0,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'destroy-native-1221-1264-89501',1,1,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-323-56401',7,323,56401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'b20d568cab648edccf00e2b1fcef65673705c0eb14f1ff2fee993315a2e5aeb3',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-323-56401',7,0,E'group-native-1256-323-56401',1),
(E'wakemu-native-resources-323-56401',7,1,E'group-native-1540-323-56401',1),
(E'wakemu-native-resources-323-56401',7,2,E'group-native-1541-323-56401',1),
(E'wakemu-native-resources-323-56401',7,3,E'group-native-1546-323-56401',1),
(E'wakemu-native-resources-323-56401',7,4,E'group-native-1547-323-56401',1),
(E'wakemu-native-resources-323-56401',7,5,E'group-native-1548-323-56401',1),
(E'wakemu-native-resources-323-56401',7,6,E'group-native-1549-323-56401',1),
(E'wakemu-native-resources-323-56401',7,7,E'group-native-1550-323-56401',1),
(E'wakemu-native-resources-323-56401',7,8,E'resource-native-1542-323-56401',1),
(E'wakemu-native-resources-323-56401',7,9,E'resource-native-1543-323-56401',1),
(E'wakemu-native-resources-323-56401',7,10,E'resource-native-1544-323-56401',1),
(E'wakemu-native-resources-323-56401',7,11,E'resource-native-1545-323-56401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-323-56401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-327-56601',7,327,56601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'ea3ef2a02867a536ed54c5cb773a6d4efd95c27fb62a30ae1f0d3191b4d04f25',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-327-56601',7,0,E'destroy-native-1325-327-56601',1),
(E'wakemu-native-resources-327-56601',7,1,E'destroy-native-1326-327-56601',1),
(E'wakemu-native-resources-327-56601',7,2,E'destroy-native-1327-327-56601',1),
(E'wakemu-native-resources-327-56601',7,3,E'destroy-native-1328-327-56601',1),
(E'wakemu-native-resources-327-56601',7,4,E'group-native-1047-327-56601',1),
(E'wakemu-native-resources-327-56601',7,5,E'group-native-1324-327-56601',1),
(E'wakemu-native-resources-327-56601',7,6,E'group-native-1329-327-56601',1),
(E'wakemu-native-resources-327-56601',7,7,E'group-native-1330-327-56601',1),
(E'wakemu-native-resources-327-56601',7,8,E'group-native-1331-327-56601',1),
(E'wakemu-native-resources-327-56601',7,9,E'group-native-1332-327-56601',1),
(E'wakemu-native-resources-327-56601',7,10,E'group-native-1333-327-56601',1),
(E'wakemu-native-resources-327-56601',7,11,E'resource-native-1320-327-56601',1),
(E'wakemu-native-resources-327-56601',7,12,E'resource-native-1321-327-56601',1),
(E'wakemu-native-resources-327-56601',7,13,E'resource-native-1322-327-56601',1),
(E'wakemu-native-resources-327-56601',7,14,E'resource-native-1323-327-56601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-327-56601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-458-61501',7,458,61501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'3163d050019795298dc9838867af6dd330c26d35d24dd1e0a4810e1147c1400f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-458-61501',7,0,E'group-native-1047-458-61501',1),
(E'wakemu-native-resources-458-61501',7,1,E'group-native-1564-458-61501',1),
(E'wakemu-native-resources-458-61501',7,2,E'group-native-1565-458-61501',1),
(E'wakemu-native-resources-458-61501',7,3,E'group-native-1566-458-61501',1),
(E'wakemu-native-resources-458-61501',7,4,E'group-native-1567-458-61501',1),
(E'wakemu-native-resources-458-61501',7,5,E'group-native-1568-458-61501',1),
(E'wakemu-native-resources-458-61501',7,6,E'group-native-1570-458-61501',1),
(E'wakemu-native-resources-458-61501',7,7,E'resource-native-1559-458-61501',1),
(E'wakemu-native-resources-458-61501',7,8,E'resource-native-1560-458-61501',1),
(E'wakemu-native-resources-458-61501',7,9,E'resource-native-1561-458-61501',1),
(E'wakemu-native-resources-458-61501',7,10,E'resource-native-1562-458-61501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-458-61501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-504-60601',7,504,60601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e568379060e73679ce27ffc0f74088ed6c9bdc0fa8ec5205aefd8cbb0eaabea8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-504-60601',7,0,E'group-native-1047-504-60601',1),
(E'wakemu-native-resources-504-60601',7,1,E'group-native-1354-504-60601',1),
(E'wakemu-native-resources-504-60601',7,2,E'group-native-1355-504-60601',1),
(E'wakemu-native-resources-504-60601',7,3,E'group-native-1356-504-60601',1),
(E'wakemu-native-resources-504-60601',7,4,E'group-native-1357-504-60601',1),
(E'wakemu-native-resources-504-60601',7,5,E'group-native-1358-504-60601',1),
(E'wakemu-native-resources-504-60601',7,6,E'group-native-1363-504-60601',1),
(E'wakemu-native-resources-504-60601',7,7,E'group-native-1378-504-60601',1),
(E'wakemu-native-resources-504-60601',7,8,E'resource-native-1350-504-60601',1),
(E'wakemu-native-resources-504-60601',7,9,E'resource-native-1351-504-60601',1),
(E'wakemu-native-resources-504-60601',7,10,E'resource-native-1352-504-60601',1),
(E'wakemu-native-resources-504-60601',7,11,E'resource-native-1353-504-60601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-504-60601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-507-60701',7,507,60701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e9f9b01fbd2e24d9b1e1c7c15f06d54ca251e04dc755850d4e613f0dc38e3d49',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-507-60701',7,0,E'group-native-1369-507-60701',1),
(E'wakemu-native-resources-507-60701',7,1,E'group-native-1370-507-60701',1),
(E'wakemu-native-resources-507-60701',7,2,E'group-native-1371-507-60701',1),
(E'wakemu-native-resources-507-60701',7,3,E'group-native-1372-507-60701',1),
(E'wakemu-native-resources-507-60701',7,4,E'group-native-1373-507-60701',1),
(E'wakemu-native-resources-507-60701',7,5,E'group-native-1490-507-60701',1),
(E'wakemu-native-resources-507-60701',7,6,E'group-native-1571-507-60701',1),
(E'wakemu-native-resources-507-60701',7,7,E'resource-native-1365-507-60701',1),
(E'wakemu-native-resources-507-60701',7,8,E'resource-native-1366-507-60701',1),
(E'wakemu-native-resources-507-60701',7,9,E'resource-native-1367-507-60701',1),
(E'wakemu-native-resources-507-60701',7,10,E'resource-native-1368-507-60701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-507-60701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-508-60801',7,508,60801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'eece49076000c3fde7742dc9c9abefc3c928d2ea33a28c02d91374d9ad31a23c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-508-60801',7,0,E'group-native-1048-508-60801',1),
(E'wakemu-native-resources-508-60801',7,1,E'group-native-1384-508-60801',1),
(E'wakemu-native-resources-508-60801',7,2,E'group-native-1385-508-60801',1),
(E'wakemu-native-resources-508-60801',7,3,E'group-native-1386-508-60801',1),
(E'wakemu-native-resources-508-60801',7,4,E'group-native-1387-508-60801',1),
(E'wakemu-native-resources-508-60801',7,5,E'group-native-1388-508-60801',1),
(E'wakemu-native-resources-508-60801',7,6,E'group-native-1393-508-60801',1),
(E'wakemu-native-resources-508-60801',7,7,E'resource-native-1380-508-60801',1),
(E'wakemu-native-resources-508-60801',7,8,E'resource-native-1381-508-60801',1),
(E'wakemu-native-resources-508-60801',7,9,E'resource-native-1382-508-60801',1),
(E'wakemu-native-resources-508-60801',7,10,E'resource-native-1383-508-60801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-508-60801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75601',7,527,75601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'c468516623a459f4de0db0da7625f1e0fb7ac0863409c595e5ba881f1a186075',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75601',7,0,E'group-native-1000-527-75601',1),
(E'wakemu-native-resources-527-75601',7,1,E'group-native-1005-527-75601',1),
(E'wakemu-native-resources-527-75601',7,2,E'group-native-1010-527-75601',1),
(E'wakemu-native-resources-527-75601',7,3,E'group-native-1015-527-75601',1),
(E'wakemu-native-resources-527-75601',7,4,E'group-native-1021-527-75601',1),
(E'wakemu-native-resources-527-75601',7,5,E'group-native-982-527-75601',1),
(E'wakemu-native-resources-527-75601',7,6,E'group-native-987-527-75601',1),
(E'wakemu-native-resources-527-75601',7,7,E'resource-native-989-527-75601',1),
(E'wakemu-native-resources-527-75601',7,8,E'resource-native-990-527-75601',1),
(E'wakemu-native-resources-527-75601',7,9,E'resource-native-991-527-75601',1),
(E'wakemu-native-resources-527-75601',7,10,E'resource-native-992-527-75601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-75601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75701',7,527,75701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'536f49a12374f67e0e2037e8f0ef7de6df2507e2c73863dc01fc3a9cccac0820',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75701',7,0,E'group-native-1002-527-75701',1),
(E'wakemu-native-resources-527-75701',7,1,E'group-native-1007-527-75701',1),
(E'wakemu-native-resources-527-75701',7,2,E'group-native-1012-527-75701',1),
(E'wakemu-native-resources-527-75701',7,3,E'group-native-1020-527-75701',1),
(E'wakemu-native-resources-527-75701',7,4,E'group-native-979-527-75701',1),
(E'wakemu-native-resources-527-75701',7,5,E'group-native-980-527-75701',1),
(E'wakemu-native-resources-527-75701',7,6,E'group-native-997-527-75701',1),
(E'wakemu-native-resources-527-75701',7,7,E'resource-native-950-527-75701',1),
(E'wakemu-native-resources-527-75701',7,8,E'resource-native-951-527-75701',1),
(E'wakemu-native-resources-527-75701',7,9,E'resource-native-953-527-75701',1),
(E'wakemu-native-resources-527-75701',7,10,E'resource-native-954-527-75701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-75701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75801',7,527,75801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'ca22a0b693eb41ccdde0902c63172c1799a41250f65cf98b83c1b7ae98172aff',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75801',7,0,E'group-native-1020-527-75801',1),
(E'wakemu-native-resources-527-75801',7,1,E'group-native-958-527-75801',1),
(E'wakemu-native-resources-527-75801',7,2,E'group-native-965-527-75801',1),
(E'wakemu-native-resources-527-75801',7,3,E'group-native-967-527-75801',1),
(E'wakemu-native-resources-527-75801',7,4,E'group-native-968-527-75801',1),
(E'wakemu-native-resources-527-75801',7,5,E'group-native-969-527-75801',1),
(E'wakemu-native-resources-527-75801',7,6,E'group-native-979-527-75801',1),
(E'wakemu-native-resources-527-75801',7,7,E'resource-native-950-527-75801',1),
(E'wakemu-native-resources-527-75801',7,8,E'resource-native-951-527-75801',1),
(E'wakemu-native-resources-527-75801',7,9,E'resource-native-953-527-75801',1),
(E'wakemu-native-resources-527-75801',7,10,E'resource-native-954-527-75801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-75801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75901',7,527,75901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'8cd066e15a46299a3d1342de2a6dbd8fee2e96a05d7484bafc60faa347ca9f5f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75901',7,0,E'group-native-1004-527-75901',1),
(E'wakemu-native-resources-527-75901',7,1,E'group-native-1009-527-75901',1),
(E'wakemu-native-resources-527-75901',7,2,E'group-native-1014-527-75901',1),
(E'wakemu-native-resources-527-75901',7,3,E'group-native-1021-527-75901',1),
(E'wakemu-native-resources-527-75901',7,4,E'group-native-982-527-75901',1),
(E'wakemu-native-resources-527-75901',7,5,E'group-native-999-527-75901',1),
(E'wakemu-native-resources-527-75901',7,6,E'resource-native-989-527-75901',1),
(E'wakemu-native-resources-527-75901',7,7,E'resource-native-990-527-75901',1),
(E'wakemu-native-resources-527-75901',7,8,E'resource-native-991-527-75901',1),
(E'wakemu-native-resources-527-75901',7,9,E'resource-native-992-527-75901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-75901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76001',7,527,76001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'fe93de1af208e0779ce3947bd68e341931b746e0e128218daf29bc2c2706b80f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76001',7,0,E'group-native-1001-527-76001',1),
(E'wakemu-native-resources-527-76001',7,1,E'group-native-1006-527-76001',1),
(E'wakemu-native-resources-527-76001',7,2,E'group-native-1011-527-76001',1),
(E'wakemu-native-resources-527-76001',7,3,E'group-native-1016-527-76001',1),
(E'wakemu-native-resources-527-76001',7,4,E'group-native-1021-527-76001',1),
(E'wakemu-native-resources-527-76001',7,5,E'group-native-982-527-76001',1),
(E'wakemu-native-resources-527-76001',7,6,E'group-native-986-527-76001',1),
(E'wakemu-native-resources-527-76001',7,7,E'resource-native-989-527-76001',1),
(E'wakemu-native-resources-527-76001',7,8,E'resource-native-990-527-76001',1),
(E'wakemu-native-resources-527-76001',7,9,E'resource-native-991-527-76001',1),
(E'wakemu-native-resources-527-76001',7,10,E'resource-native-992-527-76001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-76001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76101',7,527,76101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'1789ab5590b942ef4d4490bbe9fb768bb0e9f7c43e21aee1490f68061af1e6ca',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76101',7,0,E'group-native-1020-527-76101',1),
(E'wakemu-native-resources-527-76101',7,1,E'group-native-958-527-76101',1),
(E'wakemu-native-resources-527-76101',7,2,E'group-native-965-527-76101',1),
(E'wakemu-native-resources-527-76101',7,3,E'group-native-967-527-76101',1),
(E'wakemu-native-resources-527-76101',7,4,E'group-native-968-527-76101',1),
(E'wakemu-native-resources-527-76101',7,5,E'group-native-969-527-76101',1),
(E'wakemu-native-resources-527-76101',7,6,E'group-native-979-527-76101',1),
(E'wakemu-native-resources-527-76101',7,7,E'resource-native-950-527-76101',1),
(E'wakemu-native-resources-527-76101',7,8,E'resource-native-951-527-76101',1),
(E'wakemu-native-resources-527-76101',7,9,E'resource-native-953-527-76101',1),
(E'wakemu-native-resources-527-76101',7,10,E'resource-native-954-527-76101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-527-76101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-546-62201',7,546,62201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'd382f4837ddd50f78c5c57e547a1be66f2ffa27cff711c2fd072f7d8cca7658b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-546-62201',7,0,E'group-native-1003-546-62201',1),
(E'wakemu-native-resources-546-62201',7,1,E'group-native-1008-546-62201',1),
(E'wakemu-native-resources-546-62201',7,2,E'group-native-1013-546-62201',1),
(E'wakemu-native-resources-546-62201',7,3,E'group-native-1020-546-62201',1),
(E'wakemu-native-resources-546-62201',7,4,E'group-native-979-546-62201',1),
(E'wakemu-native-resources-546-62201',7,5,E'group-native-985-546-62201',1),
(E'wakemu-native-resources-546-62201',7,6,E'group-native-998-546-62201',1),
(E'wakemu-native-resources-546-62201',7,7,E'resource-native-950-546-62201',1),
(E'wakemu-native-resources-546-62201',7,8,E'resource-native-951-546-62201',1),
(E'wakemu-native-resources-546-62201',7,9,E'resource-native-953-546-62201',1),
(E'wakemu-native-resources-546-62201',7,10,E'resource-native-954-546-62201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-546-62201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-711-63401',7,711,63401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'119b5757a35d99f4922b6563d0946076c6c69d5e335a03dec2c2daa17a07e34c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-711-63401',7,0,E'group-native-1046-711-63401',1),
(E'wakemu-native-resources-711-63401',7,1,E'group-native-1274-711-63401',1),
(E'wakemu-native-resources-711-63401',7,2,E'group-native-1275-711-63401',1),
(E'wakemu-native-resources-711-63401',7,3,E'group-native-1276-711-63401',1),
(E'wakemu-native-resources-711-63401',7,4,E'group-native-1277-711-63401',1),
(E'wakemu-native-resources-711-63401',7,5,E'group-native-1278-711-63401',1),
(E'wakemu-native-resources-711-63401',7,6,E'group-native-1283-711-63401',1),
(E'wakemu-native-resources-711-63401',7,7,E'resource-native-1284-711-63401',1),
(E'wakemu-native-resources-711-63401',7,8,E'resource-native-1285-711-63401',1),
(E'wakemu-native-resources-711-63401',7,9,E'resource-native-1286-711-63401',1),
(E'wakemu-native-resources-711-63401',7,10,E'resource-native-1287-711-63401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-711-63401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-792-64601',7,792,64601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'0767c4f80bbf21c28ab500c23ac1827bd0fd7c4948b000497144307aa0cbc90d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-792-64601',7,0,E'group-native-1048-792-64601',1),
(E'wakemu-native-resources-792-64601',7,1,E'group-native-1399-792-64601',1),
(E'wakemu-native-resources-792-64601',7,2,E'group-native-1400-792-64601',1),
(E'wakemu-native-resources-792-64601',7,3,E'group-native-1401-792-64601',1),
(E'wakemu-native-resources-792-64601',7,4,E'group-native-1402-792-64601',1),
(E'wakemu-native-resources-792-64601',7,5,E'group-native-1403-792-64601',1),
(E'wakemu-native-resources-792-64601',7,6,E'group-native-1408-792-64601',1),
(E'wakemu-native-resources-792-64601',7,7,E'resource-native-1395-792-64601',1),
(E'wakemu-native-resources-792-64601',7,8,E'resource-native-1396-792-64601',1),
(E'wakemu-native-resources-792-64601',7,9,E'resource-native-1397-792-64601',1),
(E'wakemu-native-resources-792-64601',7,10,E'resource-native-1398-792-64601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-792-64601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-793-64801',7,793,64801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2cf94276818215d1bf05081e454b08dbd621de6e56f44e95785857d7a8d36063',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-793-64801',7,0,E'group-native-1490-793-64801',1),
(E'wakemu-native-resources-793-64801',7,1,E'group-native-1517-793-64801',1),
(E'wakemu-native-resources-793-64801',7,2,E'group-native-1518-793-64801',1),
(E'wakemu-native-resources-793-64801',7,3,E'group-native-1519-793-64801',1),
(E'wakemu-native-resources-793-64801',7,4,E'group-native-1520-793-64801',1),
(E'wakemu-native-resources-793-64801',7,5,E'group-native-1521-793-64801',1),
(E'wakemu-native-resources-793-64801',7,6,E'group-native-1526-793-64801',1),
(E'wakemu-native-resources-793-64801',7,7,E'resource-native-1513-793-64801',1),
(E'wakemu-native-resources-793-64801',7,8,E'resource-native-1514-793-64801',1),
(E'wakemu-native-resources-793-64801',7,9,E'resource-native-1515-793-64801',1),
(E'wakemu-native-resources-793-64801',7,10,E'resource-native-1516-793-64801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-793-64801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-796-64701',7,796,64701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a6804e782bd4d01b08212029a22e4b2081c5e39a2b656d9fc4420fce273b0b2a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-796-64701',7,0,E'group-native-1049-796-64701',1),
(E'wakemu-native-resources-796-64701',7,1,E'group-native-1414-796-64701',1),
(E'wakemu-native-resources-796-64701',7,2,E'group-native-1415-796-64701',1),
(E'wakemu-native-resources-796-64701',7,3,E'group-native-1416-796-64701',1),
(E'wakemu-native-resources-796-64701',7,4,E'group-native-1417-796-64701',1),
(E'wakemu-native-resources-796-64701',7,5,E'group-native-1418-796-64701',1),
(E'wakemu-native-resources-796-64701',7,6,E'group-native-1423-796-64701',1),
(E'wakemu-native-resources-796-64701',7,7,E'resource-native-1410-796-64701',1),
(E'wakemu-native-resources-796-64701',7,8,E'resource-native-1411-796-64701',1),
(E'wakemu-native-resources-796-64701',7,9,E'resource-native-1412-796-64701',1),
(E'wakemu-native-resources-796-64701',7,10,E'resource-native-1413-796-64701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-796-64701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-843-65301',7,843,65301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'cfe7e6c034ccb512662f1669627c426b5cd1716c00e5502ef1f05ccbebccebb2',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-843-65301',7,0,E'group-native-1469-843-65301',1),
(E'wakemu-native-resources-843-65301',7,1,E'group-native-1471-843-65301',1),
(E'wakemu-native-resources-843-65301',7,2,E'group-native-1472-843-65301',1),
(E'wakemu-native-resources-843-65301',7,3,E'group-native-1473-843-65301',1),
(E'wakemu-native-resources-843-65301',7,4,E'group-native-1474-843-65301',1),
(E'wakemu-native-resources-843-65301',7,5,E'group-native-1487-843-65301',1),
(E'wakemu-native-resources-843-65301',7,6,E'group-native-1491-843-65301',1),
(E'wakemu-native-resources-843-65301',7,7,E'resource-native-1461-843-65301',1),
(E'wakemu-native-resources-843-65301',7,8,E'resource-native-1462-843-65301',1),
(E'wakemu-native-resources-843-65301',7,9,E'resource-native-1463-843-65301',1),
(E'wakemu-native-resources-843-65301',7,10,E'resource-native-1464-843-65301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-843-65301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-853-65401',7,853,65401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2383922c04b566bb5d63cc3e06d32a0b6cf7d61462781ca97d84b65489e5be04',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-853-65401',7,0,E'group-native-1469-853-65401',1),
(E'wakemu-native-resources-853-65401',7,1,E'group-native-1475-853-65401',1),
(E'wakemu-native-resources-853-65401',7,2,E'group-native-1476-853-65401',1),
(E'wakemu-native-resources-853-65401',7,3,E'group-native-1477-853-65401',1),
(E'wakemu-native-resources-853-65401',7,4,E'group-native-1478-853-65401',1),
(E'wakemu-native-resources-853-65401',7,5,E'group-native-1488-853-65401',1),
(E'wakemu-native-resources-853-65401',7,6,E'group-native-1491-853-65401',1),
(E'wakemu-native-resources-853-65401',7,7,E'resource-native-1465-853-65401',1),
(E'wakemu-native-resources-853-65401',7,8,E'resource-native-1466-853-65401',1),
(E'wakemu-native-resources-853-65401',7,9,E'resource-native-1467-853-65401',1),
(E'wakemu-native-resources-853-65401',7,10,E'resource-native-1468-853-65401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-853-65401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-922-69301',7,922,69301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'd3945dfaab6b55c78c512b55ef117c5cd50e2b2604ec8158fa8e50766fa0769c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-922-69301',7,0,E'group-native-1029-922-69301',1),
(E'wakemu-native-resources-922-69301',7,1,E'group-native-1184-922-69301',1),
(E'wakemu-native-resources-922-69301',7,2,E'group-native-1185-922-69301',1),
(E'wakemu-native-resources-922-69301',7,3,E'group-native-1186-922-69301',1),
(E'wakemu-native-resources-922-69301',7,4,E'group-native-1187-922-69301',1),
(E'wakemu-native-resources-922-69301',7,5,E'group-native-1188-922-69301',1),
(E'wakemu-native-resources-922-69301',7,6,E'group-native-1210-922-69301',1),
(E'wakemu-native-resources-922-69301',7,7,E'resource-native-1190-922-69301',1),
(E'wakemu-native-resources-922-69301',7,8,E'resource-native-1191-922-69301',1),
(E'wakemu-native-resources-922-69301',7,9,E'resource-native-1192-922-69301',1),
(E'wakemu-native-resources-922-69301',7,10,E'resource-native-1193-922-69301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-922-69301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-923-69401',7,923,69401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'ab87291c93b8efad471438e29d254fa9ecb22e869edd4765cf85867f2f0b0dba',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-923-69401',7,0,E'group-native-1029-923-69401',1),
(E'wakemu-native-resources-923-69401',7,1,E'group-native-1184-923-69401',1),
(E'wakemu-native-resources-923-69401',7,2,E'group-native-1189-923-69401',1),
(E'wakemu-native-resources-923-69401',7,3,E'group-native-1198-923-69401',1),
(E'wakemu-native-resources-923-69401',7,4,E'group-native-1199-923-69401',1),
(E'wakemu-native-resources-923-69401',7,5,E'group-native-1200-923-69401',1),
(E'wakemu-native-resources-923-69401',7,6,E'group-native-1201-923-69401',1),
(E'wakemu-native-resources-923-69401',7,7,E'resource-native-1202-923-69401',1),
(E'wakemu-native-resources-923-69401',7,8,E'resource-native-1203-923-69401',1),
(E'wakemu-native-resources-923-69401',7,9,E'resource-native-1204-923-69401',1),
(E'wakemu-native-resources-923-69401',7,10,E'resource-native-1205-923-69401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-923-69401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69501',7,943,69501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a881269e9f698f0ac4c66beaff4b5ece384584343d46d8668cbe34fd0680db00',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69501',7,0,E'group-native-1236-943-69501',1),
(E'wakemu-native-resources-943-69501',7,1,E'group-native-1245-943-69501',1),
(E'wakemu-native-resources-943-69501',7,2,E'group-native-1246-943-69501',1),
(E'wakemu-native-resources-943-69501',7,3,E'group-native-1247-943-69501',1),
(E'wakemu-native-resources-943-69501',7,4,E'group-native-1248-943-69501',1),
(E'wakemu-native-resources-943-69501',7,5,E'group-native-1253-943-69501',1),
(E'wakemu-native-resources-943-69501',7,6,E'group-native-1256-943-69501',1),
(E'wakemu-native-resources-943-69501',7,7,E'resource-native-1228-943-69501',1),
(E'wakemu-native-resources-943-69501',7,8,E'resource-native-1229-943-69501',1),
(E'wakemu-native-resources-943-69501',7,9,E'resource-native-1230-943-69501',1),
(E'wakemu-native-resources-943-69501',7,10,E'resource-native-1231-943-69501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-943-69501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69601',7,943,69601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'338b258bb3227460457053dc2414657bd96d4624ece1670a49577840c8100867',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69601',7,0,E'group-native-1236-943-69601',1),
(E'wakemu-native-resources-943-69601',7,1,E'group-native-1245-943-69601',1),
(E'wakemu-native-resources-943-69601',7,2,E'group-native-1246-943-69601',1),
(E'wakemu-native-resources-943-69601',7,3,E'group-native-1247-943-69601',1),
(E'wakemu-native-resources-943-69601',7,4,E'group-native-1248-943-69601',1),
(E'wakemu-native-resources-943-69601',7,5,E'group-native-1254-943-69601',1),
(E'wakemu-native-resources-943-69601',7,6,E'group-native-1256-943-69601',1),
(E'wakemu-native-resources-943-69601',7,7,E'resource-native-1232-943-69601',1),
(E'wakemu-native-resources-943-69601',7,8,E'resource-native-1233-943-69601',1),
(E'wakemu-native-resources-943-69601',7,9,E'resource-native-1234-943-69601',1),
(E'wakemu-native-resources-943-69601',7,10,E'resource-native-1235-943-69601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-943-69601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-71501',7,999,71501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'7c4d967566af04392a92f828b146cce302d27860f70c9d216da3daaf26c48d6a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-71501',7,0,E'group-native-1169-999-71501',1),
(E'wakemu-native-resources-999-71501',7,1,E'group-native-1182-999-71501',1),
(E'wakemu-native-resources-999-71501',7,2,E'group-native-1593-999-71501',1),
(E'wakemu-native-resources-999-71501',7,3,E'group-native-1594-999-71501',1),
(E'wakemu-native-resources-999-71501',7,4,E'group-native-1595-999-71501',1),
(E'wakemu-native-resources-999-71501',7,5,E'group-native-1596-999-71501',1),
(E'wakemu-native-resources-999-71501',7,6,E'group-native-1597-999-71501',1),
(E'wakemu-native-resources-999-71501',7,7,E'resource-native-1581-999-71501',1),
(E'wakemu-native-resources-999-71501',7,8,E'resource-native-1582-999-71501',1),
(E'wakemu-native-resources-999-71501',7,9,E'resource-native-1583-999-71501',1),
(E'wakemu-native-resources-999-71501',7,10,E'resource-native-1584-999-71501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-999-71501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-82201',7,999,82201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'768ae2458682d6b44e6500d5e9a2294258526f18ae32704e22b95d97e8d6f2d4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-82201',7,0,E'group-native-1161-999-82201',1),
(E'wakemu-native-resources-999-82201',7,1,E'group-native-1162-999-82201',1),
(E'wakemu-native-resources-999-82201',7,2,E'group-native-1163-999-82201',1),
(E'wakemu-native-resources-999-82201',7,3,E'group-native-1164-999-82201',1),
(E'wakemu-native-resources-999-82201',7,4,E'group-native-1169-999-82201',1),
(E'wakemu-native-resources-999-82201',7,5,E'group-native-1266-999-82201',1),
(E'wakemu-native-resources-999-82201',7,6,E'group-native-1267-999-82201',1),
(E'wakemu-native-resources-999-82201',7,7,E'group-native-1598-999-82201',1),
(E'wakemu-native-resources-999-82201',7,8,E'resource-native-1178-999-82201',1),
(E'wakemu-native-resources-999-82201',7,9,E'resource-native-1179-999-82201',1),
(E'wakemu-native-resources-999-82201',7,10,E'resource-native-1180-999-82201',1),
(E'wakemu-native-resources-999-82201',7,11,E'resource-native-1181-999-82201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-999-82201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1053-73701',7,1053,73701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'271654bb4a7e956dceaef973776ede4c53136c7b2896b0df1f0419a13b10fd23',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1053-73701',7,0,E'group-native-1160-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,1,E'group-native-1165-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,2,E'group-native-1166-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,3,E'group-native-1167-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,4,E'group-native-1168-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,5,E'group-native-1169-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,6,E'group-native-1268-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,7,E'resource-native-1585-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,8,E'resource-native-1586-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,9,E'resource-native-1587-1053-73701',1),
(E'wakemu-native-resources-1053-73701',7,10,E'resource-native-1588-1053-73701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1053-73701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1118-78601',7,1118,78601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'ece80ec2dc83fb1db00b47d98a43a7a8133c69b5247bc9a7ccb948dd5db4877c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1118-78601',7,0,E'group-native-1036-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,1,E'group-native-1037-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,2,E'group-native-1046-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,3,E'group-native-1050-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,4,E'group-native-1054-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,5,E'group-native-1058-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,6,E'group-native-1062-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,7,E'group-native-1066-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,8,E'resource-native-1086-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,9,E'resource-native-1090-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,10,E'resource-native-1094-1118-78601',1),
(E'wakemu-native-resources-1118-78601',7,11,E'resource-native-1098-1118-78601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1118-78601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1119-78701',7,1119,78701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'6072b4304271316e29dca3785044e942ace047cbfd6aa6994acf48964c2e92f4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1119-78701',7,0,E'group-native-1039-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,1,E'group-native-1047-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,2,E'group-native-1051-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,3,E'group-native-1055-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,4,E'group-native-1059-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,5,E'group-native-1063-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,6,E'group-native-1067-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,7,E'resource-native-1087-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,8,E'resource-native-1091-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,9,E'resource-native-1095-1119-78701',1),
(E'wakemu-native-resources-1119-78701',7,10,E'resource-native-1099-1119-78701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1119-78701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-79401',7,1120,79401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a2b4a2f869020aa1344631bab63ed30dde43703e841f528a76b43534f30459f4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-79401',7,0,E'group-native-1038-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,1,E'group-native-1048-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,2,E'group-native-1052-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,3,E'group-native-1056-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,4,E'group-native-1060-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,5,E'group-native-1064-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,6,E'group-native-1068-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,7,E'resource-native-1088-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,8,E'resource-native-1092-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,9,E'resource-native-1096-1120-79401',1),
(E'wakemu-native-resources-1120-79401',7,10,E'resource-native-1100-1120-79401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1120-79401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-80601',7,1120,80601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'fb75be06fdf8865014dd7f11a6e2c50141a5e2ca3c2720d107e572f3876b9b64',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-80601',7,0,E'group-native-1040-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,1,E'group-native-1049-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,2,E'group-native-1053-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,3,E'group-native-1057-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,4,E'group-native-1061-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,5,E'group-native-1065-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,6,E'group-native-1069-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,7,E'resource-native-1089-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,8,E'resource-native-1093-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,9,E'resource-native-1097-1120-80601',1),
(E'wakemu-native-resources-1120-80601',7,10,E'resource-native-1101-1120-80601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1120-80601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-79801',7,1122,79801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'0a9306ed2b3f278b072f048ba7d5ccc536075e2645cfb0c6dc8005dc4c268b02',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-79801',7,0,E'group-native-1028-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,1,E'group-native-1029-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,2,E'group-native-1030-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,3,E'group-native-1031-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,4,E'group-native-1032-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,5,E'group-native-1033-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,6,E'group-native-1034-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,7,E'resource-native-1140-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,8,E'resource-native-1143-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,9,E'resource-native-1146-1122-79801',1),
(E'wakemu-native-resources-1122-79801',7,10,E'resource-native-1149-1122-79801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1122-79801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-80001',7,1122,80001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'52de60416ed2ca562cb493c60c4f66613de4c2c2d0443dea9d17925adecc6bbf',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-80001',7,0,E'group-native-1102-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,1,E'group-native-1124-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,2,E'group-native-1128-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,3,E'group-native-1130-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,4,E'group-native-1132-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,5,E'group-native-1134-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,6,E'group-native-1138-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,7,E'resource-native-1141-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,8,E'resource-native-1144-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,9,E'resource-native-1147-1122-80001',1),
(E'wakemu-native-resources-1122-80001',7,10,E'resource-native-1150-1122-80001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1122-80001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1123-80101',7,1123,80101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'823de76dfb6a16059b7f0b81244c02915e3ef1dd56afbb73cf3f391d43c77d49',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1123-80101',7,0,E'group-native-1102-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,1,E'group-native-1125-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,2,E'group-native-1129-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,3,E'group-native-1131-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,4,E'group-native-1133-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,5,E'group-native-1135-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,6,E'group-native-1139-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,7,E'resource-native-1142-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,8,E'resource-native-1145-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,9,E'resource-native-1148-1123-80101',1),
(E'wakemu-native-resources-1123-80101',7,10,E'resource-native-1151-1123-80101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1123-80101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81001',7,1124,81001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'599d1da2f1adf36e01179a0bf871f8f8d1b4b4236f2f243e74334ffdc83f1b4c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81001',7,0,E'group-native-1102-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,1,E'group-native-1498-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,2,E'group-native-1499-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,3,E'group-native-1500-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,4,E'group-native-1501-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,5,E'group-native-1506-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,6,E'group-native-1507-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,7,E'resource-native-1508-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,8,E'resource-native-1509-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,9,E'resource-native-1510-1124-81001',1),
(E'wakemu-native-resources-1124-81001',7,10,E'resource-native-1511-1124-81001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1124-81001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81101',7,1124,81101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'a5a88a349cc988815bacd26367e525a0ace23cea189dda3833ae0002b14b9e82',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81101',7,0,E'group-native-1102-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,1,E'group-native-1103-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,2,E'group-native-1105-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,3,E'group-native-1106-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,4,E'group-native-1107-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,5,E'group-native-1108-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,6,E'group-native-1109-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,7,E'resource-native-1114-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,8,E'resource-native-1115-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,9,E'resource-native-1116-1124-81101',1),
(E'wakemu-native-resources-1124-81101',7,10,E'resource-native-1117-1124-81101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1124-81101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79001',7,1134,79001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2c588508163d32442fcd1bcee8792f895b8b5577f22dfcb0ba410e62a8ccee93',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79001',7,0,E'group-native-1490-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,1,E'group-native-1605-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,2,E'group-native-1670-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,3,E'group-native-1671-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,4,E'group-native-1672-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,5,E'group-native-1673-1134-79001',1),
(E'wakemu-native-resources-1134-79001',7,6,E'group-native-1855-1134-79001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1134-79001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79101',7,1134,79101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'4b132f9a23f45a54fc263a9207b238ae4e25878c8b74a2bf6fe2d67331af7577',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79101',7,0,E'group-native-1489-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,1,E'group-native-1604-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,2,E'group-native-1662-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,3,E'group-native-1663-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,4,E'group-native-1664-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,5,E'group-native-1665-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,6,E'group-native-1853-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,7,E'group-native-1854-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,8,E'resource-native-1305-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,9,E'resource-native-1306-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,10,E'resource-native-1307-1134-79101',1),
(E'wakemu-native-resources-1134-79101',7,11,E'resource-native-1308-1134-79101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1134-79101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79201',7,1134,79201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'bce125543aa2d11525b767d6e12af0a9138d8719522181d04e0429e78e5084eb',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79201',7,0,E'group-native-1318-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,1,E'group-native-1489-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,2,E'group-native-1603-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,3,E'group-native-1658-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,4,E'group-native-1659-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,5,E'group-native-1660-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,6,E'group-native-1661-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,7,E'resource-native-1626-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,8,E'resource-native-1627-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,9,E'resource-native-1628-1134-79201',1),
(E'wakemu-native-resources-1134-79201',7,10,E'resource-native-1629-1134-79201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1134-79201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80801',7,1135,80801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'415fb35131759af6cf292e7af1d77544239c30fdd2b1f8e865f573c8f48a164d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80801',7,0,E'group-native-1048-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,1,E'group-native-1608-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,2,E'group-native-1782-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,3,E'group-native-1783-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,4,E'group-native-1784-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,5,E'group-native-1785-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,6,E'group-native-1869-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,7,E'resource-native-1674-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,8,E'resource-native-1675-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,9,E'resource-native-1676-1135-80801',1),
(E'wakemu-native-resources-1135-80801',7,10,E'resource-native-1677-1135-80801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1135-80801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80901',7,1135,80901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'78ae93f16964dc784b96303388fd43b779375b186c74ee405ebe3c7255cbef5f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80901',7,0,E'group-native-1046-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,1,E'group-native-1606-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,2,E'group-native-1778-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,3,E'group-native-1779-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,4,E'group-native-1780-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,5,E'group-native-1781-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,6,E'group-native-1867-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,7,E'group-native-1868-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,8,E'resource-native-1682-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,9,E'resource-native-1683-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,10,E'resource-native-1684-1135-80901',1),
(E'wakemu-native-resources-1135-80901',7,11,E'resource-native-1685-1135-80901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1135-80901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84301',7,1136,84301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e617211a216b28696564dbc7fcb7bf420f1b6f107d3bdcaf1a7cce2bdd37deee',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84301',7,0,E'group-native-1049-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,1,E'group-native-1600-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,2,E'group-native-1799-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,3,E'group-native-1800-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,4,E'group-native-1801-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,5,E'group-native-1802-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,6,E'group-native-1860-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,7,E'resource-native-1722-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,8,E'resource-native-1723-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,9,E'resource-native-1724-1136-84301',1),
(E'wakemu-native-resources-1136-84301',7,10,E'resource-native-1725-1136-84301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1136-84301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84401',7,1136,84401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e308e72dee576d984b36479376ba4b296506d9f143811041c976f20ad0cd8d1b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84401',7,0,E'group-native-1256-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,1,E'group-native-1601-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,2,E'group-native-1803-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,3,E'group-native-1804-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,4,E'group-native-1805-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,5,E'group-native-1806-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,6,E'group-native-1859-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,7,E'resource-native-1718-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,8,E'resource-native-1719-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,9,E'resource-native-1720-1136-84401',1),
(E'wakemu-native-resources-1136-84401',7,10,E'resource-native-1721-1136-84401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1136-84401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84501',7,1136,84501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'09abfe14329bc7da8536596d66c0711543c21563e3a1dc7fe814d0e06fc2465d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84501',7,0,E'group-native-1256-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,1,E'group-native-1602-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,2,E'group-native-1807-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,3,E'group-native-1808-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,4,E'group-native-1809-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,5,E'group-native-1810-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,6,E'group-native-1858-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,7,E'resource-native-1714-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,8,E'resource-native-1715-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,9,E'resource-native-1716-1136-84501',1),
(E'wakemu-native-resources-1136-84501',7,10,E'resource-native-1717-1136-84501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1136-84501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-81901',7,1137,81901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'aeb2e44050925bd25dd077b8338bb01744030371cdb45bb959f68455045513fe',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-81901',7,0,E'group-native-1047-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,1,E'group-native-1615-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,2,E'group-native-1823-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,3,E'group-native-1824-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,4,E'group-native-1825-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,5,E'group-native-1826-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,6,E'group-native-1863-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,7,E'resource-native-1622-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,8,E'resource-native-1623-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,9,E'resource-native-1624-1137-81901',1),
(E'wakemu-native-resources-1137-81901',7,10,E'resource-native-1625-1137-81901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1137-81901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-82001',7,1137,82001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'b389f8b2650971bdb0c36f33e23a4424c7c5ca1f26f27791ef2e258d14489284',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-82001',7,0,E'group-native-1047-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,1,E'group-native-1616-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,2,E'group-native-1831-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,3,E'group-native-1832-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,4,E'group-native-1833-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,5,E'group-native-1834-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,6,E'group-native-1864-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,7,E'resource-native-1698-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,8,E'resource-native-1699-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,9,E'resource-native-1700-1137-82001',1),
(E'wakemu-native-resources-1137-82001',7,10,E'resource-native-1701-1137-82001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1137-82001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-85901',7,1137,85901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'f5be9ba5f25761d2378cbeb206c81c9b8d10890bd1d0c8f963b24ba91efb4f1e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-85901',7,0,E'group-native-1491-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,1,E'group-native-1617-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,2,E'group-native-1819-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,3,E'group-native-1820-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,4,E'group-native-1821-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,5,E'group-native-1822-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,6,E'group-native-1865-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,7,E'resource-native-1706-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,8,E'resource-native-1707-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,9,E'resource-native-1708-1137-85901',1),
(E'wakemu-native-resources-1137-85901',7,10,E'resource-native-1709-1137-85901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1137-85901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-83801',7,1207,83801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'55c6917b6db01af583aa84036a076620b38d0e0dede2c645f333db27ef1b0f2e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-83801',7,0,E'group-native-1310-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,1,E'group-native-1311-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,2,E'group-native-1312-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,3,E'group-native-1313-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,4,E'group-native-1489-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,5,E'group-native-1607-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,6,E'group-native-1852-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,7,E'resource-native-1630-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,8,E'resource-native-1631-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,9,E'resource-native-1632-1207-83801',1),
(E'wakemu-native-resources-1207-83801',7,10,E'resource-native-1633-1207-83801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1207-83801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-86601',7,1207,86601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'47d254b20de290b9bc21a966fd58dc4a27c007cc8f4e25bd2ec953b80120a5bd',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-86601',7,0,E'group-native-1029-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,1,E'group-native-1666-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,2,E'group-native-1667-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,3,E'group-native-1668-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,4,E'group-native-1669-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,5,E'group-native-1794-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,6,E'group-native-1856-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,7,E'resource-native-1638-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,8,E'resource-native-1639-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,9,E'resource-native-1640-1207-86601',1),
(E'wakemu-native-resources-1207-86601',7,10,E'resource-native-1641-1207-86601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1207-86601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-84101',7,1208,84101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2097272ee85866aa492baaf975fd950305b3c5acd4a5e1ac463376f0cde68cfe',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-84101',7,0,E'group-native-1048-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,1,E'group-native-1611-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,2,E'group-native-1786-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,3,E'group-native-1787-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,4,E'group-native-1788-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,5,E'group-native-1789-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,6,E'group-native-1870-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,7,E'resource-native-1678-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,8,E'resource-native-1679-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,9,E'resource-native-1680-1208-84101',1),
(E'wakemu-native-resources-1208-84101',7,10,E'resource-native-1681-1208-84101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1208-84101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-86801',7,1208,86801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'5d07e387e9d95e18376914a74a1e1f6a698a686cfa658768db3e72bcf2ce18f8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-86801',7,0,E'group-native-1029-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,1,E'group-native-1609-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,2,E'group-native-1790-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,3,E'group-native-1791-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,4,E'group-native-1792-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,5,E'group-native-1793-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,6,E'group-native-1871-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,7,E'resource-native-1686-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,8,E'resource-native-1687-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,9,E'resource-native-1688-1208-86801',1),
(E'wakemu-native-resources-1208-86801',7,10,E'resource-native-1689-1208-86801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1208-86801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-83901',7,1209,83901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2ca22371003838e08637a59a7cb059716da7a6f884dc80a271caae59bd5b8fa4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-83901',7,0,E'group-native-1029-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,1,E'group-native-1612-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,2,E'group-native-1795-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,3,E'group-native-1796-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,4,E'group-native-1797-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,5,E'group-native-1798-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,6,E'group-native-1861-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,7,E'resource-native-1690-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,8,E'resource-native-1691-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,9,E'resource-native-1692-1209-83901',1),
(E'wakemu-native-resources-1209-83901',7,10,E'resource-native-1693-1209-83901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1209-83901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-86701',7,1209,86701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'4732e7bb4240ecec6d1032df00889b12e42256a99eee77ad798ddacac4425b86',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-86701',7,0,E'group-native-1256-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,1,E'group-native-1610-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,2,E'group-native-1811-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,3,E'group-native-1812-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,4,E'group-native-1813-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,5,E'group-native-1814-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,6,E'group-native-1857-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,7,E'resource-native-1710-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,8,E'resource-native-1711-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,9,E'resource-native-1712-1209-86701',1),
(E'wakemu-native-resources-1209-86701',7,10,E'resource-native-1713-1209-86701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1209-86701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-84001',7,1210,84001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'7b1e4fb6e0a9edb76d6090be5aa5d78043505e2b295585eedf91ec8dacdd6295',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-84001',7,0,E'group-native-1047-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,1,E'group-native-1614-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,2,E'group-native-1827-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,3,E'group-native-1828-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,4,E'group-native-1829-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,5,E'group-native-1830-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,6,E'group-native-1862-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,7,E'resource-native-1702-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,8,E'resource-native-1703-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,9,E'resource-native-1704-1210-84001',1),
(E'wakemu-native-resources-1210-84001',7,10,E'resource-native-1705-1210-84001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1210-84001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-86901',7,1210,86901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e9aeac3f7af2e816762deeda3ba27f3a86607eb7f3b78fd1138145330b112e77',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-86901',7,0,E'group-native-1029-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,1,E'group-native-1613-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,2,E'group-native-1815-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,3,E'group-native-1816-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,4,E'group-native-1817-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,5,E'group-native-1818-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,6,E'group-native-1866-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,7,E'resource-native-1694-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,8,E'resource-native-1695-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,9,E'resource-native-1696-1210-86901',1),
(E'wakemu-native-resources-1210-86901',7,10,E'resource-native-1697-1210-86901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1210-86901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88501',7,1252,88501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'7afbac043cdb043ee6ec45e61abfae8416c892c66f191fcdbb941cd63d05103b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88501',7,0,E'group-native-1491-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,1,E'group-native-1905-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,2,E'group-native-1909-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,3,E'group-native-1910-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,4,E'group-native-1911-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,5,E'group-native-1912-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,6,E'group-native-1929-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,7,E'resource-native-1873-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,8,E'resource-native-1874-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,9,E'resource-native-1875-1252-88501',1),
(E'wakemu-native-resources-1252-88501',7,10,E'resource-native-1876-1252-88501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1252-88501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88601',7,1252,88601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'541fb8bee526a26c0b957b1e217576d9a3b72152ab815d8c51ab34d405f7c614',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88601',7,0,E'group-native-1169-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,1,E'group-native-1906-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,2,E'group-native-1913-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,3,E'group-native-1914-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,4,E'group-native-1915-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,5,E'group-native-1916-1252-88601',1),
(E'wakemu-native-resources-1252-88601',7,6,E'group-native-1930-1252-88601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1252-88601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88701',7,1252,88701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'9a8bba1aadc50a2048ce9ea7ad13ab9aa69e49e2cdaa9ff8765caf9c188308bb',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88701',7,0,E'group-native-1102-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,1,E'group-native-1908-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,2,E'group-native-1921-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,3,E'group-native-1922-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,4,E'group-native-1923-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,5,E'group-native-1924-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,6,E'group-native-1932-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,7,E'resource-native-1885-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,8,E'resource-native-1886-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,9,E'resource-native-1887-1252-88701',1),
(E'wakemu-native-resources-1252-88701',7,10,E'resource-native-1888-1252-88701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1252-88701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88801',7,1252,88801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'56de28d6d20c6dac8cff08b4a6341e6c3caff1003c9782860b20c57f4baab883',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88801',7,0,E'group-native-1102-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,1,E'group-native-1907-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,2,E'group-native-1917-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,3,E'group-native-1918-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,4,E'group-native-1919-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,5,E'group-native-1920-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,6,E'group-native-1931-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,7,E'resource-native-1881-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,8,E'resource-native-1882-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,9,E'resource-native-1883-1252-88801',1),
(E'wakemu-native-resources-1252-88801',7,10,E'resource-native-1884-1252-88801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1252-88801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89301',7,1264,89301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'dfd9a85f0abdf9f86d49311678a494c655a3c47b8d1e6118e0b60c5dde8e294f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89301',7,0,E'destroy-native-1221-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,1,E'destroy-native-1222-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,2,E'destroy-native-1223-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,3,E'destroy-native-1225-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,4,E'group-native-1211-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,5,E'group-native-1212-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,6,E'group-native-1213-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,7,E'group-native-1214-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,8,E'group-native-1215-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,9,E'group-native-1224-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,10,E'group-native-1256-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,11,E'resource-native-1217-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,12,E'resource-native-1218-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,13,E'resource-native-1219-1264-89301',1),
(E'wakemu-native-resources-1264-89301',7,14,E'resource-native-1220-1264-89301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1264-89301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89401',7,1264,89401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e0f76ab4834e4655a9f46ae4973830f65283a24c556a72ec1aa4143984571e6d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89401',7,0,E'group-native-1102-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,1,E'group-native-1128-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,2,E'group-native-1130-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,3,E'group-native-1132-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,4,E'group-native-1134-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,5,E'group-native-1138-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,6,E'group-native-1939-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,7,E'resource-native-1141-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,8,E'resource-native-1144-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,9,E'resource-native-1147-1264-89401',1),
(E'wakemu-native-resources-1264-89401',7,10,E'resource-native-1150-1264-89401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1264-89401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89501',7,1264,89501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'6d3c7abb0711131d1d921f65673c5f6a5325ddc6017c18a1b063e8c1ae5fecf3',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89501',7,0,E'destroy-native-1221-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,1,E'destroy-native-1222-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,2,E'destroy-native-1223-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,3,E'destroy-native-1225-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,4,E'group-native-1211-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,5,E'group-native-1212-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,6,E'group-native-1213-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,7,E'group-native-1214-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,8,E'group-native-1215-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,9,E'group-native-1256-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,10,E'group-native-1937-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,11,E'resource-native-1217-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,12,E'resource-native-1218-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,13,E'resource-native-1219-1264-89501',1),
(E'wakemu-native-resources-1264-89501',7,14,E'resource-native-1220-1264-89501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1264-89501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89701',7,1264,89701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'7227a100ccc7eb1fe56d2d11bc3c6ec4ba35ee8cab5b4d0598165b415ff6f7e4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89701',7,0,E'group-native-1160-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,1,E'group-native-1165-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,2,E'group-native-1166-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,3,E'group-native-1167-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,4,E'group-native-1168-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,5,E'group-native-1169-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,6,E'group-native-1938-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,7,E'resource-native-1585-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,8,E'resource-native-1586-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,9,E'resource-native-1587-1264-89701',1),
(E'wakemu-native-resources-1264-89701',7,10,E'resource-native-1588-1264-89701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1264-89701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-89901',7,1276,89901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'03e44471819b8b3e74a658c3b8ec5e6d09c33794e417dc47c7a8c902965eff13',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-89901',7,0,E'group-native-1957-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,1,E'group-native-1961-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,2,E'group-native-1965-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,3,E'group-native-1969-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,4,E'group-native-1977-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,5,E'group-native-2305-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,6,E'resource-native-1941-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,7,E'resource-native-1945-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,8,E'resource-native-1949-1276-89901',1),
(E'wakemu-native-resources-1276-89901',7,9,E'resource-native-1953-1276-89901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1276-89901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90001',7,1276,90001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'd25ed36cbc99d053de57cb55a7ce76707d53bf536cf622da3d65e42f2f6739d2',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90001',7,0,E'group-native-1960-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,1,E'group-native-1964-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,2,E'group-native-1968-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,3,E'group-native-1972-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,4,E'group-native-1977-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,5,E'group-native-2311-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,6,E'resource-native-1944-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,7,E'resource-native-1948-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,8,E'resource-native-1952-1276-90001',1),
(E'wakemu-native-resources-1276-90001',7,9,E'resource-native-1956-1276-90001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1276-90001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90101',7,1276,90101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'6d77d1f21f6170372b9c16b04cbe8c8032121cc37a415968f1aa8d69ed21f551',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90101',7,0,E'group-native-1958-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,1,E'group-native-1962-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,2,E'group-native-1966-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,3,E'group-native-1970-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,4,E'group-native-1977-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,5,E'group-native-2306-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,6,E'resource-native-1942-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,7,E'resource-native-1946-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,8,E'resource-native-1950-1276-90101',1),
(E'wakemu-native-resources-1276-90101',7,9,E'resource-native-1954-1276-90101',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1276-90101' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90201',7,1276,90201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'0d6b0d692f570cc9517f49bcf97ed14d4e189253216d1ec09feb5b0f1a7ebb06',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90201',7,0,E'group-native-1959-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,1,E'group-native-1963-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,2,E'group-native-1967-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,3,E'group-native-1971-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,4,E'group-native-1977-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,5,E'group-native-2307-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,6,E'resource-native-1943-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,7,E'resource-native-1947-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,8,E'resource-native-1951-1276-90201',1),
(E'wakemu-native-resources-1276-90201',7,9,E'resource-native-1955-1276-90201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1276-90201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90601',7,1295,90601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'5a1c222e4f7ea27e3ca93c29655b6894217a7f32b2e6cf5a817650a9100a7cf9',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90601',7,0,E'group-native-1339-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,1,E'group-native-1340-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,2,E'group-native-1341-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,3,E'group-native-1342-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,4,E'group-native-1343-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,5,E'group-native-1348-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,6,E'group-native-1490-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,7,E'resource-native-1335-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,8,E'resource-native-1336-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,9,E'resource-native-1337-1295-90601',1),
(E'wakemu-native-resources-1295-90601',7,10,E'resource-native-1338-1295-90601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1295-90601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90701',7,1295,90701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'639e4ef6aa8e63c9d0ed7d49e89794e0f897599dcb14420ae18654995d052d00',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90701',7,0,E'group-native-1977-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,1,E'group-native-1999-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,2,E'group-native-2002-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,3,E'group-native-2005-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,4,E'group-native-2008-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,5,E'group-native-2309-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,6,E'resource-native-1983-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,7,E'resource-native-1986-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,8,E'resource-native-1989-1295-90701',1),
(E'wakemu-native-resources-1295-90701',7,9,E'resource-native-1992-1295-90701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1295-90701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1297-90801',7,1297,90801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'30367cafc0af5b7ebeedcd5c997a8250cbe7f747de93a0754815b79654c38229',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1297-90801',7,0,E'group-native-1977-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,1,E'group-native-2000-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,2,E'group-native-2003-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,3,E'group-native-2006-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,4,E'group-native-2009-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,5,E'group-native-2310-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,6,E'resource-native-1984-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,7,E'resource-native-1987-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,8,E'resource-native-1990-1297-90801',1),
(E'wakemu-native-resources-1297-90801',7,9,E'resource-native-1993-1297-90801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1297-90801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1298-90901',7,1298,90901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'c6988290d9517c5c12840d48a69f9a151c0d1cd04d64314ec3cddb69bb31a89e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1298-90901',7,0,E'group-native-1977-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,1,E'group-native-1998-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,2,E'group-native-2001-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,3,E'group-native-2004-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,4,E'group-native-2007-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,5,E'group-native-2308-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,6,E'resource-native-1982-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,7,E'resource-native-1985-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,8,E'resource-native-1988-1298-90901',1),
(E'wakemu-native-resources-1298-90901',7,9,E'resource-native-1991-1298-90901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1298-90901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1305-91201',7,1305,91201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'8ab4d90498f4a877370af347498d9bd5d4c966916c7b6c0d3e864eeaf8a715ad',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1305-91201',7,0,E'group-native-2024-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,1,E'group-native-2025-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,2,E'group-native-2026-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,3,E'group-native-2027-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,4,E'group-native-2295-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,5,E'resource-native-2016-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,6,E'resource-native-2017-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,7,E'resource-native-2018-1305-91201',1),
(E'wakemu-native-resources-1305-91201',7,8,E'resource-native-2019-1305-91201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1305-91201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1309-91301',7,1309,91301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'aae6582d24cfd9531f25c69bc63c0c7e8a5852137c630ffa641eababb90d2e33',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1309-91301',7,0,E'group-native-2024-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,1,E'group-native-2025-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,2,E'group-native-2026-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,3,E'group-native-2027-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,4,E'group-native-2296-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,5,E'resource-native-2016-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,6,E'resource-native-2017-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,7,E'resource-native-2018-1309-91301',1),
(E'wakemu-native-resources-1309-91301',7,8,E'resource-native-2019-1309-91301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1309-91301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1326-91401',7,1326,91401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'f7fd22da76a55c509149b0f096ab972163c41dcaea219c74159544bf46c9b511',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1326-91401',7,0,E'group-native-2024-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,1,E'group-native-2025-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,2,E'group-native-2026-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,3,E'group-native-2027-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,4,E'group-native-2297-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,5,E'resource-native-2016-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,6,E'resource-native-2017-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,7,E'resource-native-2018-1326-91401',1),
(E'wakemu-native-resources-1326-91401',7,8,E'resource-native-2019-1326-91401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1326-91401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1333-91801',7,1333,91801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'3cfb5f6956b71943ed7dc5a04fdb9608490d67a460ed061c36c8dccd0bb57c6f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1333-91801',7,0,E'group-native-2024-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,1,E'group-native-2025-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,2,E'group-native-2026-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,3,E'group-native-2027-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,4,E'group-native-2298-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,5,E'resource-native-2016-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,6,E'resource-native-2017-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,7,E'resource-native-2018-1333-91801',1),
(E'wakemu-native-resources-1333-91801',7,8,E'resource-native-2019-1333-91801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1333-91801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1338-92001',7,1338,92001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'fb6a71b6de278806482a16ddea128110f1d1f6d18a54b8214a95cd71b6de20a2',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1338-92001',7,0,E'group-native-2024-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,1,E'group-native-2025-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,2,E'group-native-2026-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,3,E'group-native-2027-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,4,E'group-native-2299-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,5,E'resource-native-2016-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,6,E'resource-native-2017-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,7,E'resource-native-2018-1338-92001',1),
(E'wakemu-native-resources-1338-92001',7,8,E'resource-native-2019-1338-92001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1338-92001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1358-92201',7,1358,92201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'799569ffd3d27040210c26f49a87237d4a3e4e43106a4de90862117c13f7a1f9',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1358-92201',7,0,E'group-native-1489-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,1,E'group-native-2052-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,2,E'group-native-2053-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,3,E'group-native-2054-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,4,E'group-native-2055-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,5,E'group-native-2056-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,6,E'group-native-2290-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,7,E'resource-native-2032-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,8,E'resource-native-2037-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,9,E'resource-native-2042-1358-92201',1),
(E'wakemu-native-resources-1358-92201',7,10,E'resource-native-2043-1358-92201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1358-92201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1359-92301',7,1359,92301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'42b260eacb442e1f19610669fd8e95e9dcd3ff0ef0b217181eb1f9d50e6e4cac',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1359-92301',7,0,E'group-native-1489-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,1,E'group-native-2062-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,2,E'group-native-2086-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,3,E'group-native-2090-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,4,E'group-native-2091-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,5,E'group-native-2092-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,6,E'group-native-2291-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,7,E'resource-native-2033-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,8,E'resource-native-2038-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,9,E'resource-native-2044-1359-92301',1),
(E'wakemu-native-resources-1359-92301',7,10,E'resource-native-2048-1359-92301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1359-92301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1364-93001',7,1364,93001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'e2eac66ba86b2e7c43b41ab34d8078c01d61100d21565714c3cae6ac73261694',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1364-93001',7,0,E'group-native-1046-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,1,E'group-native-2063-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,2,E'group-native-2087-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,3,E'group-native-2093-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,4,E'group-native-2094-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,5,E'group-native-2095-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,6,E'group-native-2292-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,7,E'resource-native-2034-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,8,E'resource-native-2039-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,9,E'resource-native-2045-1364-93001',1),
(E'wakemu-native-resources-1364-93001',7,10,E'resource-native-2049-1364-93001',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1364-93001' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1365-92601',7,1365,92601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'f7aeebb0cffdbc62527000e221ec41325c0d1d4f6b5f424ee741a0f7d600b516',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1365-92601',7,0,E'group-native-2065-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,1,E'group-native-2089-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,2,E'group-native-2099-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,3,E'group-native-2100-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,4,E'group-native-2101-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,5,E'group-native-2106-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,6,E'group-native-2294-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,7,E'resource-native-2036-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,8,E'resource-native-2041-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,9,E'resource-native-2047-1365-92601',1),
(E'wakemu-native-resources-1365-92601',7,10,E'resource-native-2051-1365-92601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1365-92601' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1368-92901',7,1368,92901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'7663fc7fb9dd0187b7bbdc4414322f68f9de615d62e4458c84e74a08ae3fed88',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1368-92901',7,0,E'group-native-2064-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,1,E'group-native-2088-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,2,E'group-native-2096-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,3,E'group-native-2097-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,4,E'group-native-2098-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,5,E'group-native-2106-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,6,E'group-native-2293-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,7,E'resource-native-2035-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,8,E'resource-native-2040-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,9,E'resource-native-2046-1368-92901',1),
(E'wakemu-native-resources-1368-92901',7,10,E'resource-native-2050-1368-92901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1368-92901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93301',7,1384,93301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'c5b5762828d3ac1ccd677a5bd97706124ec915f02e96839fcd1fa412e3fad78e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93301',7,0,E'group-native-1049-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,1,E'group-native-2128-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,2,E'group-native-2132-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,3,E'group-native-2136-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,4,E'group-native-2140-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,5,E'group-native-2144-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,6,E'group-native-2300-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,7,E'resource-native-2112-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,8,E'resource-native-2116-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,9,E'resource-native-2120-1384-93301',1),
(E'wakemu-native-resources-1384-93301',7,10,E'resource-native-2124-1384-93301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1384-93301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93501',7,1384,93501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'274155af43dec8072b58a11eb6d0bd795249cf189ff13deff88811ceb8267233',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93501',7,0,E'group-native-1049-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,1,E'group-native-1528-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,2,E'group-native-1529-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,3,E'group-native-1530-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,4,E'group-native-1531-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,5,E'group-native-1532-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,6,E'group-native-2301-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,7,E'resource-native-1428-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,8,E'resource-native-1429-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,9,E'resource-native-1430-1384-93501',1),
(E'wakemu-native-resources-1384-93501',7,10,E'resource-native-2110-1384-93501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1384-93501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93801',7,1384,93801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'd3c421265403161e4a19a15a2a9bb4685c87b6b9a4bbda060547d33821256bda',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93801',7,0,E'group-native-1440-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,1,E'group-native-1445-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,2,E'group-native-1446-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,3,E'group-native-1447-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,4,E'group-native-1448-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,5,E'group-native-1491-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,6,E'group-native-2303-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,7,E'resource-native-1436-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,8,E'resource-native-1437-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,9,E'resource-native-1438-1384-93801',1),
(E'wakemu-native-resources-1384-93801',7,10,E'resource-native-2109-1384-93801',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1384-93801' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93901',7,1384,93901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'2a464ff650980510509cb14fb65a30a99a04ad031151de273837f3029f394e2c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93901',7,0,E'group-native-1049-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,1,E'group-native-2129-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,2,E'group-native-2133-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,3,E'group-native-2137-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,4,E'group-native-2141-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,5,E'group-native-2145-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,6,E'group-native-2302-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,7,E'resource-native-2113-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,8,E'resource-native-2117-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,9,E'resource-native-2121-1384-93901',1),
(E'wakemu-native-resources-1384-93901',7,10,E'resource-native-2125-1384-93901',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1384-93901' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1390-93701',7,1390,93701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'f97f786c1d504e45931c6c90639b7e52754881ffc96a2dcc4fb5f6be33ada277',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1390-93701',7,0,E'group-native-1491-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,1,E'group-native-2131-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,2,E'group-native-2134-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,3,E'group-native-2138-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,4,E'group-native-2142-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,5,E'group-native-2146-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,6,E'group-native-2304-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,7,E'resource-native-2114-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,8,E'resource-native-2118-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,9,E'resource-native-2122-1390-93701',1),
(E'wakemu-native-resources-1390-93701',7,10,E'resource-native-2126-1390-93701',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1390-93701' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94201',7,1401,94201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'76d0130cf3c7b87e1dac2053a4ba89556f1d8a1ac6dc7a461404a187220c6519',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94201',7,0,E'group-native-2224-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,1,E'group-native-2225-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,2,E'group-native-2226-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,3,E'group-native-2227-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,4,E'group-native-2228-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,5,E'group-native-2261-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,6,E'group-native-2264-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,7,E'resource-native-2220-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,8,E'resource-native-2221-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,9,E'resource-native-2222-1401-94201',1),
(E'wakemu-native-resources-1401-94201',7,10,E'resource-native-2223-1401-94201',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1401-94201' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94301',7,1401,94301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'0e8944c0ea89ef15e0ddf072f662ba2e84b279d4212cf32ed39d097fd07d188a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94301',7,0,E'group-native-2211-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,1,E'group-native-2212-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,2,E'group-native-2213-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,3,E'group-native-2214-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,4,E'group-native-2215-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,5,E'group-native-2260-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,6,E'group-native-2264-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,7,E'resource-native-2207-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,8,E'resource-native-2208-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,9,E'resource-native-2209-1401-94301',1),
(E'wakemu-native-resources-1401-94301',7,10,E'resource-native-2210-1401-94301',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1401-94301' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94401',7,1401,94401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'ef639476a81821c8fae314dd6b41dc39a04cf29a1f9e3f2e903334e39dddf751',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94401',7,0,E'group-native-2198-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,1,E'group-native-2199-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,2,E'group-native-2200-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,3,E'group-native-2201-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,4,E'group-native-2202-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,5,E'group-native-2259-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,6,E'group-native-2264-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,7,E'resource-native-2194-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,8,E'resource-native-2195-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,9,E'resource-native-2196-1401-94401',1),
(E'wakemu-native-resources-1401-94401',7,10,E'resource-native-2197-1401-94401',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1401-94401' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94501',7,1401,94501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'11d23ba3d37038fe7d4794cf72070a2c20bb3dc91ed969c17b7300f3a8bb2e32',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94501',7,0,E'group-native-2237-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,1,E'group-native-2238-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,2,E'group-native-2239-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,3,E'group-native-2240-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,4,E'group-native-2241-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,5,E'group-native-2262-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,6,E'group-native-2264-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,7,E'resource-native-2233-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,8,E'resource-native-2234-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,9,E'resource-native-2235-1401-94501',1),
(E'wakemu-native-resources-1401-94501',7,10,E'resource-native-2236-1401-94501',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1401-94501' AND version=7;
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94601',7,1401,94601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301',E'596572c2d5f47b42b9cc74b9b86c3c684471041fcfbbdf7af927f4f0d7eb4dc1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94601',7,0,E'group-native-2250-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,1,E'group-native-2251-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,2,E'group-native-2252-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,3,E'group-native-2253-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,4,E'group-native-2254-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,5,E'group-native-2263-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,6,E'group-native-2264-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,7,E'resource-native-2246-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,8,E'resource-native-2247-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,9,E'resource-native-2248-1401-94601',1),
(E'wakemu-native-resources-1401-94601',7,10,E'resource-native-2249-1401-94601',1);
UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key=E'wakemu-native-resources-1401-94601' AND version=7;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1328-327-56601' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1327-327-56601' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1326-327-56601' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1325-327-56601' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1225-1264-89301' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1225-1264-89501' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1223-1264-89301' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1223-1264-89501' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1222-1264-89301' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1222-1264-89501' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1221-1264-89301' AND version=1;
UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key=E'destroy-native-1221-1264-89501' AND version=1;
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
