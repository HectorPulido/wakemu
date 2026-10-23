-- Generated disabled profiles only; no activation or real DB mutation is performed by the compiler.
-- Requires source275, original locations278, original actions280 and runtime274.
-- Placement281 and regional scheduling282 must be supplied separately before activation.
BEGIN;
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2248 AND map_id=1401 AND region_id=94601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2248-1401-94601',1,-2248,E'resource_collect',E'race',1401,94601,600000,NULL,0,231,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2e7ae57bce4387b8fdae7d6cd67107b8edaecdde54b3e9ff662c5e852d422882',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2248-1401-94601',1,E'resource',E'resource_collect',849,2331,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2248-1401-94601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2248-1401-94601',1,0,E'item',31808,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2248-1401-94601',1,1,E'xp',NULL,84558494,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2235 AND map_id=1401 AND region_id=94501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2235-1401-94501',1,-2235,E'resource_collect',E'race',1401,94501,600000,NULL,0,231,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9f57e0fcb995a38956f91e41765be216f7abc39f297e476af5ef2f6027bbea0e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2235-1401-94501',1,E'resource',E'resource_collect',848,2330,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2235-1401-94501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2235-1401-94501',1,0,E'item',31808,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2235-1401-94501',1,1,E'xp',NULL,84558494,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2222 AND map_id=1401 AND region_id=94201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2222-1401-94201',1,-2222,E'resource_collect',E'race',1401,94201,600000,NULL,0,231,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1dadc8ef0c664bc8a3614d0255d2cd4d761b2ad4051e060db5c2e01fb8d86dae',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2222-1401-94201',1,E'resource',E'resource_collect',847,2329,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2222-1401-94201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2222-1401-94201',1,0,E'item',31808,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2222-1401-94201',1,1,E'xp',NULL,84558494,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2209 AND map_id=1401 AND region_id=94301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2209-1401-94301',1,-2209,E'resource_collect',E'race',1401,94301,600000,NULL,0,231,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'40126dda4f65766e4810429e895859cb74ab62244a604dfc240bbb49c14fa7cf',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2209-1401-94301',1,E'resource',E'resource_collect',846,2328,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2209-1401-94301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2209-1401-94301',1,0,E'item',31808,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2209-1401-94301',1,1,E'xp',NULL,84558494,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2196 AND map_id=1401 AND region_id=94401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2196-1401-94401',1,-2196,E'resource_collect',E'race',1401,94401,600000,NULL,0,231,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7870c4ff696d3533d27b233829e249c4642df88c0e731e3cb07726cd64eb5346',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2196-1401-94401',1,E'resource',E'resource_collect',845,2327,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2196-1401-94401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2196-1401-94401',1,0,E'item',31808,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2196-1401-94401',1,1,E'xp',NULL,84558494,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2122 AND map_id=1390 AND region_id=93701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2122-1390-93701',1,-2122,E'resource_collect',E'race',1390,93701,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'b72d1f4e87bcde21b21462f5fadeb53abe792912c90d9da443ae696a8a2eba2b',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2122-1390-93701',1,E'resource',E'resource_collect',831,2277,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2122-1390-93701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2122-1390-93701',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2122-1390-93701',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2121 AND map_id=1384 AND region_id=93901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2121-1384-93901',1,-2121,E'resource_collect',E'race',1384,93901,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e95f04322cd9fe118c554c3d8f2ae1e3ac7c43072a0c7bad857b716a098ef6a4',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2121-1384-93901',1,E'resource',E'resource_collect',687,1983,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2121-1384-93901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2121-1384-93901',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2121-1384-93901',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2120 AND map_id=1384 AND region_id=93301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2120-1384-93301',1,-2120,E'resource_collect',E'race',1384,93301,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'679c59b33f4fd793506d17bea824b8cc2a3ec8abdaffb45f85284992f5a47ee9',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2120-1384-93301',1,E'resource',E'resource_collect',686,1982,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2120-1384-93301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2120-1384-93301',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2120-1384-93301',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2047 AND map_id=1365 AND region_id=92601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2047-1365-92601',1,-2047,E'resource_collect',E'race',1365,92601,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'80fb401231a22516e8a2287907115f5e12b1fa50a11f9d3d8ca5635228813108',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2047-1365-92601',1,E'resource',E'resource_collect',813,2240,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2047-1365-92601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2047-1365-92601',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2047-1365-92601',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2046 AND map_id=1368 AND region_id=92901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2046-1368-92901',1,-2046,E'resource_collect',E'race',1368,92901,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'56c268286ac5914a5cb5c0e8a5b08fa50d8ff52825ce36ec8597d238ce5dc121',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2046-1368-92901',1,E'resource',E'resource_collect',812,2239,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2046-1368-92901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2046-1368-92901',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2046-1368-92901',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2045 AND map_id=1364 AND region_id=93001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2045-1364-93001',1,-2045,E'resource_collect',E'race',1364,93001,600000,NULL,0,51,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6332658191c38b5bfba6c985ff9c0d1d3793e075953ad0b9b91ce267ee75fbd8',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2045-1364-93001',1,E'resource',E'resource_collect',811,2238,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2045-1364-93001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2045-1364-93001',1,0,E'item',21116,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2045-1364-93001',1,1,E'xp',NULL,177130,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2044 AND map_id=1359 AND region_id=92301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2044-1359-92301',1,-2044,E'resource_collect',E'race',1359,92301,600000,NULL,0,36,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'abdb57975eaf4d7f286eb4f778fe23448e0414adf3e387f098db333cd1385fbf',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2044-1359-92301',1,E'resource',E'resource_collect',810,2237,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2044-1359-92301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2044-1359-92301',1,0,E'item',21115,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2044-1359-92301',1,1,E'xp',NULL,82847,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2042 AND map_id=1358 AND region_id=92201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2042-1358-92201',1,-2042,E'resource_collect',E'race',1358,92201,600000,NULL,0,36,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'abff351e9e1209cf04d05bbd5ac45b7340b06d240a14307998b81d298a3bf823',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2042-1358-92201',1,E'resource',E'resource_collect',689,1985,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2042-1358-92201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2042-1358-92201',1,0,E'item',21115,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2042-1358-92201',1,1,E'xp',NULL,82847,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2017 AND map_id=1305 AND region_id=91201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2017-1305-91201',1,-2017,E'resource_collect',E'race',1305,91201,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7b359884e34da0f6b5ab5e3bd02cce5802a85bac0a462ed54bfec7e5bb4fc26d',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2017-1305-91201',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2017-1305-91201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2017-1305-91201',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2017-1305-91201',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2017 AND map_id=1309 AND region_id=91301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2017-1309-91301',1,-2017,E'resource_collect',E'race',1309,91301,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9de0a5d010be3755824c666da31bf6d9d394f6c8624cc95a998741044bfbf2fc',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2017-1309-91301',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2017-1309-91301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2017-1309-91301',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2017-1309-91301',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2017 AND map_id=1326 AND region_id=91401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2017-1326-91401',1,-2017,E'resource_collect',E'race',1326,91401,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7fb1e2196da7f179b8474930caa1fcd66023de02230b3fe9f1765237c269cc98',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2017-1326-91401',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2017-1326-91401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2017-1326-91401',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2017-1326-91401',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2017 AND map_id=1333 AND region_id=91801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2017-1333-91801',1,-2017,E'resource_collect',E'race',1333,91801,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fd15a95654d2d274298e97dba801675ad8f945870a1539fb1d4810f68c7e2d0f',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2017-1333-91801',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2017-1333-91801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2017-1333-91801',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2017-1333-91801',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-2017 AND map_id=1338 AND region_id=92001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-2017-1338-92001',1,-2017,E'resource_collect',E'race',1338,92001,600000,NULL,0,216,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd205822a40f8dc7437e0adc8749badfb1c4583b9786f9db91240a045b5f250ea',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-2017-1338-92001',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-2017-1338-92001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-2017-1338-92001',1,0,E'item',29041,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-2017-1338-92001',1,1,E'xp',NULL,62063090,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1987 AND map_id=1297 AND region_id=90801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1987-1297-90801',1,-1987,E'resource_collect',E'race',1297,90801,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'dd900da394eaf56f35982600515110067f7aa4fc3633df6bc178651f172c4997',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1987-1297-90801',1,E'resource',E'resource_collect',780,2169,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1987-1297-90801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1987-1297-90801',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1987-1297-90801',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1986 AND map_id=1295 AND region_id=90701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1986-1295-90701',1,-1986,E'resource_collect',E'race',1295,90701,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'bd065d0b8e5411b3c52004ed85e2a0e6783df1dc4f3e65b436e847a7d848270e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1986-1295-90701',1,E'resource',E'resource_collect',779,2167,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1986-1295-90701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1986-1295-90701',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1986-1295-90701',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1985 AND map_id=1298 AND region_id=90901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1985-1298-90901',1,-1985,E'resource_collect',E'race',1298,90901,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a2cba5d84880fa015e2d7870f338a96e6cf072ac5dc0d760f532e7b27c804cc5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1985-1298-90901',1,E'resource',E'resource_collect',778,2166,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1985-1298-90901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1985-1298-90901',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1985-1298-90901',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1948 AND map_id=1276 AND region_id=90001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1948-1276-90001',1,-1948,E'resource_collect',E'race',1276,90001,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cac151e7f477d2298d5fac34cbd43639a32b6f504edf07b49e11194a00a0d325',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1948-1276-90001',1,E'resource',E'resource_collect',760,2121,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1948-1276-90001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1948-1276-90001',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1948-1276-90001',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1947 AND map_id=1276 AND region_id=90201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1947-1276-90201',1,-1947,E'resource_collect',E'race',1276,90201,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'52de4840f7cfcdb8bf08a38d8cc87d58487ef1f338f9ac3351c5be871db762a9',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1947-1276-90201',1,E'resource',E'resource_collect',759,2120,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1947-1276-90201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1947-1276-90201',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1947-1276-90201',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1946 AND map_id=1276 AND region_id=90101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1946-1276-90101',1,-1946,E'resource_collect',E'race',1276,90101,600000,NULL,0,201,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'effdb3c998373f8216cc647080086a6777549819e8ac9be6d93c47e55b0e025e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1946-1276-90101',1,E'resource',E'resource_collect',758,2119,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1946-1276-90101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1946-1276-90101',1,0,E'item',27886,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1946-1276-90101',1,1,E'xp',NULL,48351988,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1887 AND map_id=1252 AND region_id=88701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1887-1252-88701',1,-1887,E'resource_collect',E'race',1252,88701,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'eba534783b2a987f0666215a8af22218742430a6c352883e47ac6bfcfaa3cc8b',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1887-1252-88701',1,E'resource',E'resource_collect',746,2104,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1887-1252-88701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1887-1252-88701',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1887-1252-88701',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1883 AND map_id=1252 AND region_id=88801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1883-1252-88801',1,-1883,E'resource_collect',E'race',1252,88801,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cbbfcaeb65522fa189441496ee7cb3372f3eff440c7992b8a89846fb5c4a990b',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1883-1252-88801',1,E'resource',E'resource_collect',745,2103,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1883-1252-88801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1883-1252-88801',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1883-1252-88801',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1875 AND map_id=1252 AND region_id=88501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1875-1252-88501',1,-1875,E'resource_collect',E'race',1252,88501,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f5b31ceb360a070be8b5a2ba38854790279e2f911a99f2ec82b57b6e8aad8e2b',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1875-1252-88501',1,E'resource',E'resource_collect',743,2101,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1875-1252-88501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1875-1252-88501',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1875-1252-88501',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1723 AND map_id=1136 AND region_id=84301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1723-1136-84301',1,-1723,E'resource_collect',E'race',1136,84301,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a73bfeb0fa9009e686a6d89839722638965d1ff102c0c0ba3859eb9d334991d7',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1723-1136-84301',1,E'resource',E'resource_collect',726,2087,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1723-1136-84301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1723-1136-84301',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1723-1136-84301',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1720 AND map_id=1136 AND region_id=84401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1720-1136-84401',1,-1720,E'resource_collect',E'race',1136,84401,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'3554af7de332dc09deaab1039732ff895ac1a60485c55f028c78bca864b1afba',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1720-1136-84401',1,E'resource',E'resource_collect',723,2084,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1720-1136-84401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1720-1136-84401',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1720-1136-84401',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1716 AND map_id=1136 AND region_id=84501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1716-1136-84501',1,-1716,E'resource_collect',E'race',1136,84501,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ffb13d58d82461afe7f28cadcb31dbf421d05b67352a11938633f5cb7274e361',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1716-1136-84501',1,E'resource',E'resource_collect',724,2085,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1716-1136-84501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1716-1136-84501',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1716-1136-84501',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1711 AND map_id=1209 AND region_id=86701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1711-1209-86701',1,-1711,E'resource_collect',E'race',1209,86701,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'03b077c729f0aa5f613f4be95e8c905c53f109a9330d0fd7b2cc1a44dd5f41ff',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1711-1209-86701',1,E'resource',E'resource_collect',725,2086,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1711-1209-86701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1711-1209-86701',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1711-1209-86701',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1707 AND map_id=1137 AND region_id=85901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1707-1137-85901',1,-1707,E'resource_collect',E'race',1137,85901,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'92cf450be67dc9d8d71dff4d9a869a63cc4ec3ebeb79c37eaac3b3ea44a50f3e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1707-1137-85901',1,E'resource',E'resource_collect',732,2093,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1707-1137-85901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1707-1137-85901',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1707-1137-85901',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1704 AND map_id=1210 AND region_id=84001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1704-1210-84001',1,-1704,E'resource_collect',E'race',1210,84001,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'42c708e57b7370e52c16c173e20d9e72f1b2067ef42162c034a38541f5673a21',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1704-1210-84001',1,E'resource',E'resource_collect',719,2080,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1704-1210-84001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1704-1210-84001',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1704-1210-84001',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1699 AND map_id=1137 AND region_id=82001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1699-1137-82001',1,-1699,E'resource_collect',E'race',1137,82001,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'04734db75efb7cba675f48eb454409a1f134a3b84bf1e40df32dda77554d484a',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1699-1137-82001',1,E'resource',E'resource_collect',733,2094,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1699-1137-82001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1699-1137-82001',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1699-1137-82001',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1695 AND map_id=1210 AND region_id=86901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1695-1210-86901',1,-1695,E'resource_collect',E'race',1210,86901,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'119d20068a592ea37b51b53f2273467c592d622cd1a03e2522c8fb011c7c5c56',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1695-1210-86901',1,E'resource',E'resource_collect',734,2095,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1695-1210-86901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1695-1210-86901',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1695-1210-86901',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1692 AND map_id=1209 AND region_id=83901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1692-1209-83901',1,-1692,E'resource_collect',E'race',1209,83901,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'370ac1738ba1091a969b1f31b2c2976187e1ad2b5944fdf0a407543f51a76cd9',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1692-1209-83901',1,E'resource',E'resource_collect',727,2088,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1692-1209-83901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1692-1209-83901',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1692-1209-83901',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1688 AND map_id=1208 AND region_id=86801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1688-1208-86801',1,-1688,E'resource_collect',E'race',1208,86801,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f592ecebb457418d9d170855b7196fa4d9cbcdd941e485e3389d897919e176b5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1688-1208-86801',1,E'resource',E'resource_collect',736,2100,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1688-1208-86801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1688-1208-86801',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1688-1208-86801',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1683 AND map_id=1135 AND region_id=80901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1683-1135-80901',1,-1683,E'resource_collect',E'race',1135,80901,600000,NULL,0,51,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8a282394cce990e67d975340356d1efa69b9159f647eb37105080d9878c71fa8',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1683-1135-80901',1,E'resource',E'resource_collect',718,2079,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1683-1135-80901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1683-1135-80901',1,0,E'item',21116,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1683-1135-80901',1,1,E'xp',NULL,177130,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1680 AND map_id=1208 AND region_id=84101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1680-1208-84101',1,-1680,E'resource_collect',E'race',1208,84101,600000,NULL,0,111,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'90b3f1bf8f3e0be088a8b5e55d58d44acaf645839e684c49df487648e41e7a20',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1680-1208-84101',1,E'resource',E'resource_collect',721,2082,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1680-1208-84101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1680-1208-84101',1,0,E'item',21120,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1680-1208-84101',1,1,E'xp',NULL,2119775,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1676 AND map_id=1135 AND region_id=80801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1676-1135-80801',1,-1676,E'resource_collect',E'race',1135,80801,600000,NULL,0,111,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'722c607df79ca7ab48af9b204b12b082d4965f889c388a7c2716cad19ec5c9fa',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1676-1135-80801',1,E'resource',E'resource_collect',735,2098,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1676-1135-80801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1676-1135-80801',1,0,E'item',21120,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1676-1135-80801',1,1,E'xp',NULL,2119775,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1639 AND map_id=1207 AND region_id=86601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1639-1207-86601',1,-1639,E'resource_collect',E'race',1207,86601,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4dd807c119b17239cb2cc7943fd6b98f5fe6caaad1120ef3d2fd726048a503d2',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1639-1207-86601',1,E'resource',E'resource_collect',731,2092,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1639-1207-86601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1639-1207-86601',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1639-1207-86601',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1631 AND map_id=1207 AND region_id=83801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1631-1207-83801',1,-1631,E'resource_collect',E'race',1207,83801,600000,NULL,0,36,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f2d198809d5e6dafee72d5936dc8f0120de7c99c1a954373b7bedcc660ed69cc',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1631-1207-83801',1,E'resource',E'resource_collect',729,2090,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1631-1207-83801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1631-1207-83801',1,0,E'item',21115,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1631-1207-83801',1,1,E'xp',NULL,82847,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1627 AND map_id=1134 AND region_id=79201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1627-1134-79201',1,-1627,E'resource_collect',E'race',1134,79201,600000,NULL,0,36,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ac94eb5756acf8238b6d0fbe95e6471937b78e9ea2bf6d5a5c38269baadbbd0e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1627-1134-79201',1,E'resource',E'resource_collect',728,2089,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1627-1134-79201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1627-1134-79201',1,0,E'item',21115,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1627-1134-79201',1,1,E'xp',NULL,82847,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1625 AND map_id=1137 AND region_id=81901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1625-1137-81901',1,-1625,E'resource_collect',E'race',1137,81901,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f805e55bd7d1810540ebfeb628ee089c1716f133391ff09a2e1a8e55f4a1fe99',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1625-1137-81901',1,E'resource',E'resource_collect',722,2083,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1625-1137-81901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1625-1137-81901',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1625-1137-81901',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1586 AND map_id=1053 AND region_id=73701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1586-1053-73701',1,-1586,E'resource_collect',E'race',1053,73701,600000,NULL,0,171,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'83804baed552463ec43f938a6efdcd05ba53abab9277c1afadae9c11fe56a869',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1586-1053-73701',1,E'resource',E'resource_collect',693,1989,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1586-1053-73701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1586-1053-73701',1,0,E'item',21124,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1586-1053-73701',1,1,E'xp',NULL,31560004,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1586 AND map_id=1264 AND region_id=89701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1586-1264-89701',1,-1586,E'resource_collect',E'race',1264,89701,600000,NULL,0,171,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6f230123aa8762953e4edcddc29d1b9b8ad28b8ce3fdf0d4a87c29c23aaf78da',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1586-1264-89701',1,E'resource',E'resource_collect',693,1989,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1586-1264-89701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1586-1264-89701',1,0,E'item',21124,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1586-1264-89701',1,1,E'xp',NULL,31560004,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1582 AND map_id=999 AND region_id=71501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1582-999-71501',1,-1582,E'resource_collect',E'race',999,71501,600000,NULL,0,171,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'957e6a0e8ffc8786e9294edb46c649a5f058597f992a5b460bb816894f30ac15',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1582-999-71501',1,E'resource',E'resource_collect',692,1990,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1582-999-71501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1582-999-71501',1,0,E'item',21124,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1582-999-71501',1,1,E'xp',NULL,31560004,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1561 AND map_id=458 AND region_id=61501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1561-458-61501',1,-1561,E'resource_collect',E'race',458,61501,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f8de47101e206cf50ffe4e67e9da11c3ccaa808f3ca370601e98ee4b6656dbd5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1561-458-61501',1,E'resource',E'resource_collect',528,1277,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1561-458-61501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1561-458-61501',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1561-458-61501',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1544 AND map_id=323 AND region_id=56401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1544-323-56401',1,-1544,E'resource_collect',E'race',323,56401,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'bbf5633e22fd77669094737226300ab75742f3c49c21faed523d4bb252563fe5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1544-323-56401',1,E'resource',E'resource_collect',474,1186,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1544-323-56401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1544-323-56401',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1544-323-56401',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1515 AND map_id=793 AND region_id=64801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1515-793-64801',1,-1515,E'resource_collect',E'race',793,64801,600000,NULL,0,96,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ea06a55024b656a5d27ac7e34e4cd8b109fd28079cffdcf09bc83165a3d0a4a1',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1515-793-64801',1,E'resource',E'resource_collect',690,1986,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1515-793-64801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1515-793-64801',1,0,E'item',21119,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1515-793-64801',1,1,E'xp',NULL,1016321,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1509 AND map_id=1124 AND region_id=81001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1509-1124-81001',1,-1509,E'resource_collect',E'race',1124,81001,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'75f4abebb58a1248125d438dbe577373ce730de1b173dd6a989492855517a0ae',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1509-1124-81001',1,E'resource',E'resource_collect',685,1981,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1509-1124-81001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1509-1124-81001',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1509-1124-81001',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1467 AND map_id=853 AND region_id=65401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1467-853-65401',1,-1467,E'resource_collect',E'race',853,65401,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'519186e3a19f32f063e729bb34cb03522bc7cc643d1665319da1a3c2f9a11e35',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1467-853-65401',1,E'resource',E'resource_collect',582,1454,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1467-853-65401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1467-853-65401',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1467-853-65401',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1463 AND map_id=843 AND region_id=65301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1463-843-65301',1,-1463,E'resource_collect',E'race',843,65301,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a817b55a459ba77f5ddac5ec6ed5a4ffaefd45b5da6d6d197a4f3061979348f8',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1463-843-65301',1,E'resource',E'resource_collect',581,1453,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1463-843-65301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1463-843-65301',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1463-843-65301',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1437 AND map_id=1384 AND region_id=93801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1437-1384-93801',1,-1437,E'resource_collect',E'race',1384,93801,600000,NULL,0,141,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'11809b471a2cb5c29e1726627daf5bb0939d3d5559bde4023f881edbdc0d09c3',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1437-1384-93801',1,E'resource',E'resource_collect',688,1984,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1437-1384-93801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1437-1384-93801',1,0,E'item',21122,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1437-1384-93801',1,1,E'xp',NULL,8525285,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1429 AND map_id=1384 AND region_id=93501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1429-1384-93501',1,-1429,E'resource_collect',E'race',1384,93501,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'43dfceed165b919692a2eb76ede456b34197e8cd8e935194867a48aa6bd6aaec',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1429-1384-93501',1,E'resource',E'resource_collect',830,2276,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1429-1384-93501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1429-1384-93501',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1429-1384-93501',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1412 AND map_id=796 AND region_id=64701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1412-796-64701',1,-1412,E'resource_collect',E'race',796,64701,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'126c5f5d422880d641b73cf1aacdf25d766dfd0b35b67bd218bab31b7d0b4e5d',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1412-796-64701',1,E'resource',E'resource_collect',567,1406,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1412-796-64701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1412-796-64701',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1412-796-64701',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1397 AND map_id=792 AND region_id=64601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1397-792-64601',1,-1397,E'resource_collect',E'race',792,64601,600000,NULL,0,111,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7280033b5431aa82c1b1f83c3eeb4b2414bd14f843dc0930d54a870362011571',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1397-792-64601',1,E'resource',E'resource_collect',566,1405,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1397-792-64601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1397-792-64601',1,0,E'item',21120,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1397-792-64601',1,1,E'xp',NULL,2119775,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1382 AND map_id=508 AND region_id=60801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1382-508-60801',1,-1382,E'resource_collect',E'race',508,60801,600000,NULL,0,111,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7da4b4d9ad9074818c99bfd16af20446920ee1a7e2fad9677f65774236f58831',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1382-508-60801',1,E'resource',E'resource_collect',506,1233,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1382-508-60801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1382-508-60801',1,0,E'item',21120,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1382-508-60801',1,1,E'xp',NULL,2119775,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1367 AND map_id=507 AND region_id=60701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1367-507-60701',1,-1367,E'resource_collect',E'race',507,60701,600000,NULL,0,96,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4645e7b26b585c8ddc531ceb913cbf5427e90a491f36deabe2461b9285150717',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1367-507-60701',1,E'resource',E'resource_collect',509,1238,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1367-507-60701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1367-507-60701',1,0,E'item',21119,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1367-507-60701',1,1,E'xp',NULL,1016321,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1352 AND map_id=504 AND region_id=60601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1352-504-60601',1,-1352,E'resource_collect',E'race',504,60601,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'75871ce9ac9d848f76557581cb1153089da1dcf36f7134562706020862e1e95a',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1352-504-60601',1,E'resource',E'resource_collect',504,1231,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1352-504-60601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1352-504-60601',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1352-504-60601',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1337 AND map_id=1295 AND region_id=90601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1337-1295-90601',1,-1337,E'resource_collect',E'race',1295,90601,600000,NULL,0,96,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c68622af4128da5b6ee59b014a33177ec77aea89b15528a52061785d4fc67df5',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1337-1295-90601',1,E'resource',E'resource_collect',515,1254,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1337-1295-90601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1337-1295-90601',1,0,E'item',21119,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1337-1295-90601',1,1,E'xp',NULL,1016321,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1322 AND map_id=327 AND region_id=56601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1322-327-56601',1,-1322,E'resource_collect',E'race',327,56601,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0d73831502c1751c7e436ecbb669038f467db111f54536720049b723ac08f9ed',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1322-327-56601',1,E'resource',E'resource_collect',478,1190,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1322-327-56601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1322-327-56601',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1322-327-56601',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1307 AND map_id=1134 AND region_id=79101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1307-1134-79101',1,-1307,E'resource_collect',E'race',1134,79101,600000,NULL,0,36,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4db28e0d235e24030b9a979375a51ecf72f385ff744df164c2a4cc1924766333',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1307-1134-79101',1,E'resource',E'resource_collect',720,2081,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1307-1134-79101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1307-1134-79101',1,0,E'item',21115,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1307-1134-79101',1,1,E'xp',NULL,82847,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1286 AND map_id=711 AND region_id=63401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1286-711-63401',1,-1286,E'resource_collect',E'race',711,63401,600000,NULL,0,51,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1dabe67d1fd8aa12b2b584e42d3ba98bb1410cdfc6f729408b3ede06314fd917',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1286-711-63401',1,E'resource',E'resource_collect',545,1348,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1286-711-63401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1286-711-63401',1,0,E'item',21116,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1286-711-63401',1,1,E'xp',NULL,177130,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1234 AND map_id=943 AND region_id=69601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1234-943-69601',1,-1234,E'resource_collect',E'race',943,69601,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'61cb087f6347fb1ede4a1e402aa7b095c813b0239cfa86f93f4f4ff24409d27e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1234-943-69601',1,E'resource',E'resource_collect',472,1184,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1234-943-69601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1234-943-69601',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1234-943-69601',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1230 AND map_id=943 AND region_id=69501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1230-943-69501',1,-1230,E'resource_collect',E'race',943,69501,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c40349ffa2d52738a65244ab80d946b5c90064928b4423d17186763aa03feab1',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1230-943-69501',1,E'resource',E'resource_collect',473,1185,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1230-943-69501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1230-943-69501',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1230-943-69501',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1219 AND map_id=1264 AND region_id=89301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1219-1264-89301',1,-1219,E'resource_collect',E'race',1264,89301,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd5b4e0f02669ee06431ca02718bdba2b43e969533b7debeaafaf3bdce540d562',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1219-1264-89301',1,E'resource',E'resource_collect',467,1179,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1219-1264-89301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1219-1264-89301',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1219-1264-89301',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1219 AND map_id=1264 AND region_id=89501 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1219-1264-89501',1,-1219,E'resource_collect',E'race',1264,89501,600000,NULL,0,66,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'56c4f9595f886a133d25f1fc06ce50204728c7c5457dd696bd4e41e3ac41923c',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1219-1264-89501',1,E'resource',E'resource_collect',467,1179,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1219-1264-89501',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1219-1264-89501',1,0,E'item',21117,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1219-1264-89501',1,1,E'xp',NULL,299825,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1203 AND map_id=923 AND region_id=69401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1203-923-69401',1,-1203,E'resource_collect',E'race',923,69401,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'20aa5c6f2f778396ed4e187a6aa81aebc240634e83662dc0e847c382243be831',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1203-923-69401',1,E'resource',E'resource_collect',595,1502,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1203-923-69401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1203-923-69401',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1203-923-69401',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1191 AND map_id=922 AND region_id=69301 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1191-922-69301',1,-1191,E'resource_collect',E'race',922,69301,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cb885b006ab91c7c5c3bb3cb47a99348ba6ec097d0f5bd91a521c301c3f4bb8e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1191-922-69301',1,E'resource',E'resource_collect',594,1501,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1191-922-69301',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1191-922-69301',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1191-922-69301',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1179 AND map_id=999 AND region_id=82201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1179-999-82201',1,-1179,E'resource_collect',E'race',999,82201,600000,NULL,0,171,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'54784ad7f99c0668f6295e24c2983b49070184b1c6d13f6e7acb180c65e983f6',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1179-999-82201',1,E'resource',E'resource_collect',619,1616,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1179-999-82201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1179-999-82201',1,0,E'item',21124,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1179-999-82201',1,1,E'xp',NULL,31560004,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1145 AND map_id=1123 AND region_id=80101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1145-1123-80101',1,-1145,E'resource_collect',E'race',1123,80101,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'bee4783a14a19ad6f32a0ebe6f85b95cee3a31a54a8eea9b0b5f15c892b60ab7',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1145-1123-80101',1,E'resource',E'resource_collect',658,1849,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1145-1123-80101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1145-1123-80101',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1145-1123-80101',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1144 AND map_id=1122 AND region_id=80001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1144-1122-80001',1,-1144,E'resource_collect',E'race',1122,80001,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'bd255e44a459e223fb38f2d028e76d47a8f468155001632c364fce9a962d5fd2',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1144-1122-80001',1,E'resource',E'resource_collect',657,1848,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1144-1122-80001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1144-1122-80001',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1144-1122-80001',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1144 AND map_id=1264 AND region_id=89401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1144-1264-89401',1,-1144,E'resource_collect',E'race',1264,89401,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'01df4a9e9acd9719c06cb8cd015ab2ddf2e85eb44465cd1e295f311ba0131db7',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1144-1264-89401',1,E'resource',E'resource_collect',657,1848,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1144-1264-89401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1144-1264-89401',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1144-1264-89401',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1143 AND map_id=1122 AND region_id=79801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1143-1122-79801',1,-1143,E'resource_collect',E'race',1122,79801,600000,NULL,0,156,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e9db94dfac9288d172dace93321dd22a7207da29d4c0a2ed06e266a6c1a67b17',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1143-1122-79801',1,E'resource',E'resource_collect',656,1847,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1143-1122-79801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1143-1122-79801',1,0,E'item',21123,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1143-1122-79801',1,1,E'xp',NULL,16544245,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1116 AND map_id=1124 AND region_id=81101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1116-1124-81101',1,-1116,E'resource_collect',E'race',1124,81101,600000,NULL,0,186,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e7e05f2942889519aff9419ea6ab5da94e576f982b8eb70d6b82dcf369035fd1',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1116-1124-81101',1,E'resource',E'resource_collect',637,1775,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1116-1124-81101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1116-1124-81101',1,0,E'item',21125,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1116-1124-81101',1,1,E'xp',NULL,39571458,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1097 AND map_id=1120 AND region_id=80601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1097-1120-80601',1,-1097,E'resource_collect',E'race',1120,80601,600000,NULL,0,126,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'857f045f5acf95dc41224d70fe219aa33547d42dcd746f9633b147fd92cb406f',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1097-1120-80601',1,E'resource',E'resource_collect',635,1778,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1097-1120-80601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1097-1120-80601',1,0,E'item',21121,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1097-1120-80601',1,1,E'xp',NULL,4303403,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1096 AND map_id=1120 AND region_id=79401 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1096-1120-79401',1,-1096,E'resource_collect',E'race',1120,79401,600000,NULL,0,111,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'460909aece743f48a455b8af69c3934066df870ea2f2760c2a2fa56b985741fe',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1096-1120-79401',1,E'resource',E'resource_collect',633,1776,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1096-1120-79401',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1096-1120-79401',1,0,E'item',21120,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1096-1120-79401',1,1,E'xp',NULL,2119775,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1095 AND map_id=1119 AND region_id=78701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1095-1119-78701',1,-1095,E'resource_collect',E'race',1119,78701,600000,NULL,0,81,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fc276bf3b9753264fae8934c00be48c838bf8ace4da27cdc4eb5fcbeb607f07e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1095-1119-78701',1,E'resource',E'resource_collect',634,1773,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1095-1119-78701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1095-1119-78701',1,0,E'item',21118,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1095-1119-78701',1,1,E'xp',NULL,506465,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1094 AND map_id=1118 AND region_id=78601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-1094-1118-78601',1,-1094,E'resource_collect',E'race',1118,78601,600000,NULL,0,51,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'deae2c1cf64269ed2740bb9ab66e4b3276dcf115bba1ac1be412f24159b3d137',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-1094-1118-78601',1,E'resource',E'resource_collect',632,1771,2,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-1094-1118-78601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-1094-1118-78601',1,0,E'item',21116,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-1094-1118-78601',1,1,E'xp',NULL,177130,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-991 AND map_id=527 AND region_id=75601 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-991-527-75601',1,-991,E'resource_collect',E'race',527,75601,600000,NULL,0,21,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7d226bcebd0ecc96bfcb2c3eaae842b5d65b1669fcd99a6f3bde7ee251a92075',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-991-527-75601',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-991-527-75601',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-991-527-75601',1,0,E'item',20606,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-991-527-75601',1,1,E'xp',NULL,27410,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-991 AND map_id=527 AND region_id=75901 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-991-527-75901',1,-991,E'resource_collect',E'race',527,75901,600000,NULL,0,21,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'24ab3cb32ff3869a290eb65a678275dbc4c7fc9e8a1430d96b4942dadd6af7f8',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-991-527-75901',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-991-527-75901',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-991-527-75901',1,0,E'item',20606,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-991-527-75901',1,1,E'xp',NULL,27410,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-991 AND map_id=527 AND region_id=76001 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-991-527-76001',1,-991,E'resource_collect',E'race',527,76001,600000,NULL,0,21,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd5f621cfbfb9cc99253aa3498eda62f548b51ad125e0c16263aa092cac344b8e',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-991-527-76001',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-991-527-76001',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-991-527-76001',1,0,E'item',20606,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-991-527-76001',1,1,E'xp',NULL,27410,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-954 AND map_id=527 AND region_id=75701 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-954-527-75701',1,-954,E'resource_collect',E'race',527,75701,600000,NULL,0,1,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'76bc0dfab15207ae22f2b128e4e19b271ca53c9b2098bfef9f7a0d0244db8ced',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-954-527-75701',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-954-527-75701',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-954-527-75701',1,0,E'item',20605,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-954-527-75701',1,1,E'xp',NULL,7314,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-954 AND map_id=527 AND region_id=75801 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-954-527-75801',1,-954,E'resource_collect',E'race',527,75801,600000,NULL,0,1,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'283f307be42b2bc0d1d041a45074484bcfe9159783871009b55e872fcb7fb0b8',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-954-527-75801',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-954-527-75801',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-954-527-75801',1,0,E'item',20605,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-954-527-75801',1,1,E'xp',NULL,7314,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-954 AND map_id=527 AND region_id=76101 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-954-527-76101',1,-954,E'resource_collect',E'race',527,76101,600000,NULL,0,1,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'e51c0907a5f3bc58b771d483849737c8d9090e4561ba8410f2e024fc2ec38209',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-954-527-76101',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-954-527-76101',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-954-527-76101',1,0,E'item',20605,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-954-527-76101',1,1,E'xp',NULL,7314,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-954 AND map_id=546 AND region_id=62201 AND native_cells_present AND native_criteria='') THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;
INSERT INTO environmental_runtime_profiles (profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision,enabled,sealed) VALUES
(E'resource-native-954-546-62201',1,-954,E'resource_collect',E'race',546,62201,600000,NULL,0,1,245,1,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6b6b81639620c0972b60070e5e8f445149b398c79e9253dedc4aee9b215a0480',E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',FALSE,FALSE);
INSERT INTO environmental_profile_objectives (profile_key,version,objective_key,family,target_reference,action_id,resource_step,unit,required_quantity) VALUES
(E'resource-native-954-546-62201',1,E'resource',E'resource_collect',628,1766,1,E'interaction',1);
INSERT INTO environmental_profile_evaluation (profile_key,version,evaluator,winner_count,tie_policy,source_authority) VALUES
(E'resource-native-954-546-62201',1,E'first_completion',3,E'commit_order',E'wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit');
INSERT INTO environmental_profile_rewards (profile_key,version,ordinal,kind,reference,quantity,source_authority) VALUES
(E'resource-native-954-546-62201',1,0,E'item',20605,5,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant'),
(E'resource-native-954-546-62201',1,1,E'xp',NULL,7314,E'wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant');

INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2248-1401-94601',1,-2248,0,445,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2248-1401-94601',1,E'proposed',0),
(E'resource-native-2248-1401-94601',1,E'active',1),
(E'resource-native-2248-1401-94601',1,E'completed',2),
(E'resource-native-2248-1401-94601',1,E'expired',2),
(E'resource-native-2248-1401-94601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',231,NULL,NULL),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',-2248,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2248-1401-94601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2248-1401-94601',1,0,-42,-262,49),
(E'resource-native-2248-1401-94601',1,1,-40,-312,9),
(E'resource-native-2248-1401-94601',1,2,-38,-281,16),
(E'resource-native-2248-1401-94601',1,3,-38,-280,16),
(E'resource-native-2248-1401-94601',1,4,-37,-281,16),
(E'resource-native-2248-1401-94601',1,5,-37,-280,16),
(E'resource-native-2248-1401-94601',1,6,-37,-277,48),
(E'resource-native-2248-1401-94601',1,7,-37,-275,40),
(E'resource-native-2248-1401-94601',1,8,-36,-299,20),
(E'resource-native-2248-1401-94601',1,9,-36,-298,20),
(E'resource-native-2248-1401-94601',1,10,-36,-282,16),
(E'resource-native-2248-1401-94601',1,11,-36,-281,16),
(E'resource-native-2248-1401-94601',1,12,-36,-280,16),
(E'resource-native-2248-1401-94601',1,13,-36,-279,16),
(E'resource-native-2248-1401-94601',1,14,-36,-278,16),
(E'resource-native-2248-1401-94601',1,15,-36,-275,27),
(E'resource-native-2248-1401-94601',1,16,-36,-271,20),
(E'resource-native-2248-1401-94601',1,17,-36,-270,23),
(E'resource-native-2248-1401-94601',1,18,-36,-260,0),
(E'resource-native-2248-1401-94601',1,19,-36,-259,4),
(E'resource-native-2248-1401-94601',1,20,-36,-258,4),
(E'resource-native-2248-1401-94601',1,21,-36,-257,4),
(E'resource-native-2248-1401-94601',1,22,-36,-256,7),
(E'resource-native-2248-1401-94601',1,23,-36,-255,4),
(E'resource-native-2248-1401-94601',1,24,-36,-253,0),
(E'resource-native-2248-1401-94601',1,25,-36,-252,0),
(E'resource-native-2248-1401-94601',1,26,-36,-251,0),
(E'resource-native-2248-1401-94601',1,27,-36,-250,0),
(E'resource-native-2248-1401-94601',1,28,-36,-249,0),
(E'resource-native-2248-1401-94601',1,29,-36,-248,0),
(E'resource-native-2248-1401-94601',1,30,-36,-247,0),
(E'resource-native-2248-1401-94601',1,31,-36,-246,0),
(E'resource-native-2248-1401-94601',1,32,-36,-245,0),
(E'resource-native-2248-1401-94601',1,33,-36,-244,0),
(E'resource-native-2248-1401-94601',1,34,-36,-243,0),
(E'resource-native-2248-1401-94601',1,35,-36,-242,0),
(E'resource-native-2248-1401-94601',1,36,-36,-241,0),
(E'resource-native-2248-1401-94601',1,37,-36,-240,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2235-1401-94501',1,-2235,0,441,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2235-1401-94501',1,E'proposed',0),
(E'resource-native-2235-1401-94501',1,E'active',1),
(E'resource-native-2235-1401-94501',1,E'completed',2),
(E'resource-native-2235-1401-94501',1,E'expired',2),
(E'resource-native-2235-1401-94501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',231,NULL,NULL),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',-2235,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2235-1401-94501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2235-1401-94501',1,0,0,-108,0),
(E'resource-native-2235-1401-94501',1,1,0,-107,1),
(E'resource-native-2235-1401-94501',1,2,0,-106,0),
(E'resource-native-2235-1401-94501',1,3,0,-105,0),
(E'resource-native-2235-1401-94501',1,4,0,-104,0),
(E'resource-native-2235-1401-94501',1,5,0,-103,0),
(E'resource-native-2235-1401-94501',1,6,0,-102,0),
(E'resource-native-2235-1401-94501',1,7,0,-101,0),
(E'resource-native-2235-1401-94501',1,8,0,-100,0),
(E'resource-native-2235-1401-94501',1,9,0,-99,0),
(E'resource-native-2235-1401-94501',1,10,0,-95,0),
(E'resource-native-2235-1401-94501',1,11,0,-94,0),
(E'resource-native-2235-1401-94501',1,12,0,-93,0),
(E'resource-native-2235-1401-94501',1,13,0,-92,0),
(E'resource-native-2235-1401-94501',1,14,0,-91,0),
(E'resource-native-2235-1401-94501',1,15,0,-90,0),
(E'resource-native-2235-1401-94501',1,16,0,-89,0),
(E'resource-native-2235-1401-94501',1,17,0,-88,0),
(E'resource-native-2235-1401-94501',1,18,0,-87,0),
(E'resource-native-2235-1401-94501',1,19,0,-86,0),
(E'resource-native-2235-1401-94501',1,20,0,-85,0),
(E'resource-native-2235-1401-94501',1,21,0,-84,0),
(E'resource-native-2235-1401-94501',1,22,0,-83,0),
(E'resource-native-2235-1401-94501',1,23,0,-81,0),
(E'resource-native-2235-1401-94501',1,24,0,-80,0),
(E'resource-native-2235-1401-94501',1,25,0,-79,0),
(E'resource-native-2235-1401-94501',1,26,0,-78,0),
(E'resource-native-2235-1401-94501',1,27,0,-77,0),
(E'resource-native-2235-1401-94501',1,28,0,-76,0),
(E'resource-native-2235-1401-94501',1,29,0,-73,0),
(E'resource-native-2235-1401-94501',1,30,1,-108,2),
(E'resource-native-2235-1401-94501',1,31,1,-107,0),
(E'resource-native-2235-1401-94501',1,32,1,-106,0),
(E'resource-native-2235-1401-94501',1,33,1,-105,0),
(E'resource-native-2235-1401-94501',1,34,1,-95,0),
(E'resource-native-2235-1401-94501',1,35,1,-94,0),
(E'resource-native-2235-1401-94501',1,36,1,-93,0),
(E'resource-native-2235-1401-94501',1,37,1,-92,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2222-1401-94201',1,-2222,0,442,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2222-1401-94201',1,E'proposed',0),
(E'resource-native-2222-1401-94201',1,E'active',1),
(E'resource-native-2222-1401-94201',1,E'completed',2),
(E'resource-native-2222-1401-94201',1,E'expired',2),
(E'resource-native-2222-1401-94201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',231,NULL,NULL),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',-2222,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2222-1401-94201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2222-1401-94201',1,0,-72,-90,5),
(E'resource-native-2222-1401-94201',1,1,-72,-89,3),
(E'resource-native-2222-1401-94201',1,2,-72,-88,0),
(E'resource-native-2222-1401-94201',1,3,-72,-87,12),
(E'resource-native-2222-1401-94201',1,4,-72,-86,12),
(E'resource-native-2222-1401-94201',1,5,-72,-81,12),
(E'resource-native-2222-1401-94201',1,6,-72,-80,10),
(E'resource-native-2222-1401-94201',1,7,-72,-79,10),
(E'resource-native-2222-1401-94201',1,8,-72,-78,10),
(E'resource-native-2222-1401-94201',1,9,-72,-75,0),
(E'resource-native-2222-1401-94201',1,10,-72,-74,0),
(E'resource-native-2222-1401-94201',1,11,-72,-73,0),
(E'resource-native-2222-1401-94201',1,12,-72,-54,2),
(E'resource-native-2222-1401-94201',1,13,-72,-53,0),
(E'resource-native-2222-1401-94201',1,14,-72,-52,0),
(E'resource-native-2222-1401-94201',1,15,-72,-51,0),
(E'resource-native-2222-1401-94201',1,16,-72,-46,0),
(E'resource-native-2222-1401-94201',1,17,-72,-45,0),
(E'resource-native-2222-1401-94201',1,18,-72,-44,0),
(E'resource-native-2222-1401-94201',1,19,-72,-43,0),
(E'resource-native-2222-1401-94201',1,20,-72,-42,0),
(E'resource-native-2222-1401-94201',1,21,-72,-41,0),
(E'resource-native-2222-1401-94201',1,22,-72,-40,0),
(E'resource-native-2222-1401-94201',1,23,-71,-89,0),
(E'resource-native-2222-1401-94201',1,24,-71,-88,0),
(E'resource-native-2222-1401-94201',1,25,-71,-87,0),
(E'resource-native-2222-1401-94201',1,26,-71,-86,3),
(E'resource-native-2222-1401-94201',1,27,-71,-85,0),
(E'resource-native-2222-1401-94201',1,28,-71,-81,3),
(E'resource-native-2222-1401-94201',1,29,-71,-80,6),
(E'resource-native-2222-1401-94201',1,30,-71,-79,6),
(E'resource-native-2222-1401-94201',1,31,-71,-78,6),
(E'resource-native-2222-1401-94201',1,32,-71,-76,0),
(E'resource-native-2222-1401-94201',1,33,-71,-75,0),
(E'resource-native-2222-1401-94201',1,34,-71,-74,0),
(E'resource-native-2222-1401-94201',1,35,-71,-73,0),
(E'resource-native-2222-1401-94201',1,36,-71,-54,0),
(E'resource-native-2222-1401-94201',1,37,-71,-53,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2209-1401-94301',1,-2209,0,443,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2209-1401-94301',1,E'proposed',0),
(E'resource-native-2209-1401-94301',1,E'active',1),
(E'resource-native-2209-1401-94301',1,E'completed',2),
(E'resource-native-2209-1401-94301',1,E'expired',2),
(E'resource-native-2209-1401-94301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',231,NULL,NULL),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',-2209,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2209-1401-94301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2209-1401-94301',1,0,-177,-100,36),
(E'resource-native-2209-1401-94301',1,1,-177,-99,36),
(E'resource-native-2209-1401-94301',1,2,-177,-98,36),
(E'resource-native-2209-1401-94301',1,3,-176,-100,36),
(E'resource-native-2209-1401-94301',1,4,-176,-99,36),
(E'resource-native-2209-1401-94301',1,5,-176,-98,36),
(E'resource-native-2209-1401-94301',1,6,-175,-100,36),
(E'resource-native-2209-1401-94301',1,7,-175,-99,36),
(E'resource-native-2209-1401-94301',1,8,-175,-98,36),
(E'resource-native-2209-1401-94301',1,9,-174,-100,36),
(E'resource-native-2209-1401-94301',1,10,-174,-99,36),
(E'resource-native-2209-1401-94301',1,11,-174,-98,36),
(E'resource-native-2209-1401-94301',1,12,-173,-100,36),
(E'resource-native-2209-1401-94301',1,13,-173,-99,36),
(E'resource-native-2209-1401-94301',1,14,-173,-98,36),
(E'resource-native-2209-1401-94301',1,15,-172,-100,36),
(E'resource-native-2209-1401-94301',1,16,-172,-99,36),
(E'resource-native-2209-1401-94301',1,17,-172,-98,36),
(E'resource-native-2209-1401-94301',1,18,-171,-101,38),
(E'resource-native-2209-1401-94301',1,19,-171,-100,36),
(E'resource-native-2209-1401-94301',1,20,-171,-99,36),
(E'resource-native-2209-1401-94301',1,21,-171,-98,36),
(E'resource-native-2209-1401-94301',1,22,-171,-93,15),
(E'resource-native-2209-1401-94301',1,23,-171,-92,15),
(E'resource-native-2209-1401-94301',1,24,-170,-100,36),
(E'resource-native-2209-1401-94301',1,25,-170,-99,36),
(E'resource-native-2209-1401-94301',1,26,-170,-98,36),
(E'resource-native-2209-1401-94301',1,27,-170,-97,14),
(E'resource-native-2209-1401-94301',1,28,-170,-96,12),
(E'resource-native-2209-1401-94301',1,29,-170,-93,12),
(E'resource-native-2209-1401-94301',1,30,-169,-101,38),
(E'resource-native-2209-1401-94301',1,31,-169,-100,34),
(E'resource-native-2209-1401-94301',1,32,-169,-99,34),
(E'resource-native-2209-1401-94301',1,33,-169,-98,34),
(E'resource-native-2209-1401-94301',1,34,-169,-97,18),
(E'resource-native-2209-1401-94301',1,35,-169,-96,12),
(E'resource-native-2209-1401-94301',1,36,-169,-93,12),
(E'resource-native-2209-1401-94301',1,37,-168,-101,16);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2196-1401-94401',1,-2196,0,440,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2196-1401-94401',1,E'proposed',0),
(E'resource-native-2196-1401-94401',1,E'active',1),
(E'resource-native-2196-1401-94401',1,E'completed',2),
(E'resource-native-2196-1401-94401',1,E'expired',2),
(E'resource-native-2196-1401-94401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',231,NULL,NULL),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',-2196,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2196-1401-94401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2196-1401-94401',1,0,-90,-158,0),
(E'resource-native-2196-1401-94401',1,1,-90,-157,0),
(E'resource-native-2196-1401-94401',1,2,-90,-156,0),
(E'resource-native-2196-1401-94401',1,3,-90,-155,0),
(E'resource-native-2196-1401-94401',1,4,-90,-154,0),
(E'resource-native-2196-1401-94401',1,5,-90,-153,0),
(E'resource-native-2196-1401-94401',1,6,-90,-152,0),
(E'resource-native-2196-1401-94401',1,7,-90,-140,0),
(E'resource-native-2196-1401-94401',1,8,-90,-139,0),
(E'resource-native-2196-1401-94401',1,9,-90,-138,0),
(E'resource-native-2196-1401-94401',1,10,-90,-137,0),
(E'resource-native-2196-1401-94401',1,11,-90,-136,0),
(E'resource-native-2196-1401-94401',1,12,-90,-135,0),
(E'resource-native-2196-1401-94401',1,13,-90,-134,0),
(E'resource-native-2196-1401-94401',1,14,-90,-133,0),
(E'resource-native-2196-1401-94401',1,15,-90,-132,0),
(E'resource-native-2196-1401-94401',1,16,-90,-127,0),
(E'resource-native-2196-1401-94401',1,17,-89,-158,0),
(E'resource-native-2196-1401-94401',1,18,-89,-156,0),
(E'resource-native-2196-1401-94401',1,19,-89,-155,0),
(E'resource-native-2196-1401-94401',1,20,-89,-152,0),
(E'resource-native-2196-1401-94401',1,21,-89,-151,0),
(E'resource-native-2196-1401-94401',1,22,-89,-150,1),
(E'resource-native-2196-1401-94401',1,23,-89,-142,0),
(E'resource-native-2196-1401-94401',1,24,-89,-141,0),
(E'resource-native-2196-1401-94401',1,25,-89,-140,0),
(E'resource-native-2196-1401-94401',1,26,-89,-139,0),
(E'resource-native-2196-1401-94401',1,27,-89,-138,0),
(E'resource-native-2196-1401-94401',1,28,-89,-137,0),
(E'resource-native-2196-1401-94401',1,29,-89,-136,0),
(E'resource-native-2196-1401-94401',1,30,-89,-135,0),
(E'resource-native-2196-1401-94401',1,31,-89,-134,0),
(E'resource-native-2196-1401-94401',1,32,-89,-127,0),
(E'resource-native-2196-1401-94401',1,33,-88,-159,0),
(E'resource-native-2196-1401-94401',1,34,-88,-158,0),
(E'resource-native-2196-1401-94401',1,35,-88,-157,0),
(E'resource-native-2196-1401-94401',1,36,-88,-156,0),
(E'resource-native-2196-1401-94401',1,37,-88,-155,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2122-1390-93701',1,-2122,0,438,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2122-1390-93701',1,E'proposed',0),
(E'resource-native-2122-1390-93701',1,E'active',1),
(E'resource-native-2122-1390-93701',1,E'completed',2),
(E'resource-native-2122-1390-93701',1,E'expired',2),
(E'resource-native-2122-1390-93701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',-2122,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2122-1390-93701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2122-1390-93701',1,0,-168,-49,-8),
(E'resource-native-2122-1390-93701',1,1,-168,-48,-7),
(E'resource-native-2122-1390-93701',1,2,-168,-47,-8),
(E'resource-native-2122-1390-93701',1,3,-168,-46,-8),
(E'resource-native-2122-1390-93701',1,4,-168,-44,8),
(E'resource-native-2122-1390-93701',1,5,-168,-43,8),
(E'resource-native-2122-1390-93701',1,6,-168,-42,8),
(E'resource-native-2122-1390-93701',1,7,-168,-41,8),
(E'resource-native-2122-1390-93701',1,8,-168,-40,8),
(E'resource-native-2122-1390-93701',1,9,-168,-38,9),
(E'resource-native-2122-1390-93701',1,10,-168,-37,9),
(E'resource-native-2122-1390-93701',1,11,-167,-51,-6),
(E'resource-native-2122-1390-93701',1,12,-167,-50,-8),
(E'resource-native-2122-1390-93701',1,13,-167,-49,-8),
(E'resource-native-2122-1390-93701',1,14,-167,-48,-7),
(E'resource-native-2122-1390-93701',1,15,-167,-47,-8),
(E'resource-native-2122-1390-93701',1,16,-167,-46,-8),
(E'resource-native-2122-1390-93701',1,17,-167,-43,8),
(E'resource-native-2122-1390-93701',1,18,-167,-42,8),
(E'resource-native-2122-1390-93701',1,19,-167,-41,8),
(E'resource-native-2122-1390-93701',1,20,-167,-39,8),
(E'resource-native-2122-1390-93701',1,21,-167,-38,9),
(E'resource-native-2122-1390-93701',1,22,-167,-37,9),
(E'resource-native-2122-1390-93701',1,23,-166,-50,-8),
(E'resource-native-2122-1390-93701',1,24,-166,-49,-8),
(E'resource-native-2122-1390-93701',1,25,-166,-48,-7),
(E'resource-native-2122-1390-93701',1,26,-166,-47,-8),
(E'resource-native-2122-1390-93701',1,27,-166,-46,-8),
(E'resource-native-2122-1390-93701',1,28,-166,-43,8),
(E'resource-native-2122-1390-93701',1,29,-166,-42,8),
(E'resource-native-2122-1390-93701',1,30,-166,-41,8),
(E'resource-native-2122-1390-93701',1,31,-166,-39,9),
(E'resource-native-2122-1390-93701',1,32,-166,-38,9),
(E'resource-native-2122-1390-93701',1,33,-166,-36,-7),
(E'resource-native-2122-1390-93701',1,34,-165,-115,12),
(E'resource-native-2122-1390-93701',1,35,-165,-110,9),
(E'resource-native-2122-1390-93701',1,36,-165,-51,-8),
(E'resource-native-2122-1390-93701',1,37,-165,-50,-8);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2121-1384-93901',1,-2121,0,434,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2121-1384-93901',1,E'proposed',0),
(E'resource-native-2121-1384-93901',1,E'active',1),
(E'resource-native-2121-1384-93901',1,E'completed',2),
(E'resource-native-2121-1384-93901',1,E'expired',2),
(E'resource-native-2121-1384-93901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',-2121,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2121-1384-93901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2121-1384-93901',1,0,-323,-198,28),
(E'resource-native-2121-1384-93901',1,1,-323,-197,28),
(E'resource-native-2121-1384-93901',1,2,-322,-198,28),
(E'resource-native-2121-1384-93901',1,3,-322,-197,28),
(E'resource-native-2121-1384-93901',1,4,-322,-196,24),
(E'resource-native-2121-1384-93901',1,5,-322,-195,24),
(E'resource-native-2121-1384-93901',1,6,-322,-194,24),
(E'resource-native-2121-1384-93901',1,7,-322,-193,24),
(E'resource-native-2121-1384-93901',1,8,-322,-192,22),
(E'resource-native-2121-1384-93901',1,9,-322,-191,18),
(E'resource-native-2121-1384-93901',1,10,-322,-190,14),
(E'resource-native-2121-1384-93901',1,11,-322,-189,12),
(E'resource-native-2121-1384-93901',1,12,-321,-197,24),
(E'resource-native-2121-1384-93901',1,13,-321,-196,24),
(E'resource-native-2121-1384-93901',1,14,-321,-195,24),
(E'resource-native-2121-1384-93901',1,15,-321,-194,24),
(E'resource-native-2121-1384-93901',1,16,-321,-193,24),
(E'resource-native-2121-1384-93901',1,17,-321,-192,24),
(E'resource-native-2121-1384-93901',1,18,-321,-191,24),
(E'resource-native-2121-1384-93901',1,19,-321,-189,12),
(E'resource-native-2121-1384-93901',1,20,-320,-198,24),
(E'resource-native-2121-1384-93901',1,21,-320,-197,24),
(E'resource-native-2121-1384-93901',1,22,-320,-196,24),
(E'resource-native-2121-1384-93901',1,23,-320,-195,24),
(E'resource-native-2121-1384-93901',1,24,-320,-194,24),
(E'resource-native-2121-1384-93901',1,25,-320,-193,24),
(E'resource-native-2121-1384-93901',1,26,-320,-192,24),
(E'resource-native-2121-1384-93901',1,27,-320,-191,24),
(E'resource-native-2121-1384-93901',1,28,-320,-190,24),
(E'resource-native-2121-1384-93901',1,29,-320,-189,12),
(E'resource-native-2121-1384-93901',1,30,-319,-198,24),
(E'resource-native-2121-1384-93901',1,31,-319,-197,24),
(E'resource-native-2121-1384-93901',1,32,-319,-196,24),
(E'resource-native-2121-1384-93901',1,33,-319,-194,24),
(E'resource-native-2121-1384-93901',1,34,-319,-193,24),
(E'resource-native-2121-1384-93901',1,35,-319,-192,24),
(E'resource-native-2121-1384-93901',1,36,-319,-191,24),
(E'resource-native-2121-1384-93901',1,37,-319,-189,10);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2120-1384-93301',1,-2120,0,429,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2120-1384-93301',1,E'proposed',0),
(E'resource-native-2120-1384-93301',1,E'active',1),
(E'resource-native-2120-1384-93301',1,E'completed',2),
(E'resource-native-2120-1384-93301',1,E'expired',2),
(E'resource-native-2120-1384-93301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',-2120,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2120-1384-93301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2120-1384-93301',1,0,-118,-54,12),
(E'resource-native-2120-1384-93301',1,1,-117,-65,12),
(E'resource-native-2120-1384-93301',1,2,-117,-55,12),
(E'resource-native-2120-1384-93301',1,3,-117,-54,12),
(E'resource-native-2120-1384-93301',1,4,-116,-57,12),
(E'resource-native-2120-1384-93301',1,5,-116,-56,12),
(E'resource-native-2120-1384-93301',1,6,-116,-55,12),
(E'resource-native-2120-1384-93301',1,7,-116,-54,12),
(E'resource-native-2120-1384-93301',1,8,-116,-53,12),
(E'resource-native-2120-1384-93301',1,9,-115,-72,12),
(E'resource-native-2120-1384-93301',1,10,-115,-71,12),
(E'resource-native-2120-1384-93301',1,11,-115,-70,12),
(E'resource-native-2120-1384-93301',1,12,-115,-69,12),
(E'resource-native-2120-1384-93301',1,13,-115,-68,12),
(E'resource-native-2120-1384-93301',1,14,-115,-64,16),
(E'resource-native-2120-1384-93301',1,15,-115,-63,16),
(E'resource-native-2120-1384-93301',1,16,-115,-62,16),
(E'resource-native-2120-1384-93301',1,17,-115,-57,12),
(E'resource-native-2120-1384-93301',1,18,-115,-56,12),
(E'resource-native-2120-1384-93301',1,19,-115,-55,12),
(E'resource-native-2120-1384-93301',1,20,-115,-53,18),
(E'resource-native-2120-1384-93301',1,21,-114,-71,15),
(E'resource-native-2120-1384-93301',1,22,-114,-70,12),
(E'resource-native-2120-1384-93301',1,23,-114,-69,12),
(E'resource-native-2120-1384-93301',1,24,-114,-68,12),
(E'resource-native-2120-1384-93301',1,25,-114,-64,16),
(E'resource-native-2120-1384-93301',1,26,-114,-63,16),
(E'resource-native-2120-1384-93301',1,27,-114,-62,16),
(E'resource-native-2120-1384-93301',1,28,-114,-57,12),
(E'resource-native-2120-1384-93301',1,29,-114,-56,12),
(E'resource-native-2120-1384-93301',1,30,-114,-55,12),
(E'resource-native-2120-1384-93301',1,31,-114,-53,18),
(E'resource-native-2120-1384-93301',1,32,-114,-51,2),
(E'resource-native-2120-1384-93301',1,33,-113,-71,15),
(E'resource-native-2120-1384-93301',1,34,-113,-70,12),
(E'resource-native-2120-1384-93301',1,35,-113,-69,12),
(E'resource-native-2120-1384-93301',1,36,-113,-68,12),
(E'resource-native-2120-1384-93301',1,37,-113,-64,16);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2047-1365-92601',1,-2047,0,422,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2047-1365-92601',1,E'proposed',0),
(E'resource-native-2047-1365-92601',1,E'active',1),
(E'resource-native-2047-1365-92601',1,E'completed',2),
(E'resource-native-2047-1365-92601',1,E'expired',2),
(E'resource-native-2047-1365-92601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',-2047,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2047-1365-92601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2047-1365-92601',1,0,-124,-31,-49),
(E'resource-native-2047-1365-92601',1,1,-124,-30,-49),
(E'resource-native-2047-1365-92601',1,2,-124,-29,-47),
(E'resource-native-2047-1365-92601',1,3,-124,-28,-44),
(E'resource-native-2047-1365-92601',1,4,-124,-27,-47),
(E'resource-native-2047-1365-92601',1,5,-124,9,-47),
(E'resource-native-2047-1365-92601',1,6,-124,10,-48),
(E'resource-native-2047-1365-92601',1,7,-124,11,-41),
(E'resource-native-2047-1365-92601',1,8,-124,12,-44),
(E'resource-native-2047-1365-92601',1,9,-124,13,-47),
(E'resource-native-2047-1365-92601',1,10,-124,37,-49),
(E'resource-native-2047-1365-92601',1,11,-124,38,-49),
(E'resource-native-2047-1365-92601',1,12,-124,39,-47),
(E'resource-native-2047-1365-92601',1,13,-124,40,-44),
(E'resource-native-2047-1365-92601',1,14,-124,41,-47),
(E'resource-native-2047-1365-92601',1,15,-124,74,-41),
(E'resource-native-2047-1365-92601',1,16,-124,75,-44),
(E'resource-native-2047-1365-92601',1,17,-124,76,-47),
(E'resource-native-2047-1365-92601',1,18,-124,80,-47),
(E'resource-native-2047-1365-92601',1,19,-124,81,-49),
(E'resource-native-2047-1365-92601',1,20,-124,82,-47),
(E'resource-native-2047-1365-92601',1,21,-124,83,-44),
(E'resource-native-2047-1365-92601',1,22,-124,84,-47),
(E'resource-native-2047-1365-92601',1,23,-123,-32,-50),
(E'resource-native-2047-1365-92601',1,24,-123,-31,-50),
(E'resource-native-2047-1365-92601',1,25,-123,-27,-50),
(E'resource-native-2047-1365-92601',1,26,-123,-26,-50),
(E'resource-native-2047-1365-92601',1,27,-123,-25,-50),
(E'resource-native-2047-1365-92601',1,28,-123,-21,-50),
(E'resource-native-2047-1365-92601',1,29,-123,-20,-50),
(E'resource-native-2047-1365-92601',1,30,-123,1,-46),
(E'resource-native-2047-1365-92601',1,31,-123,2,-47),
(E'resource-native-2047-1365-92601',1,32,-123,3,-50),
(E'resource-native-2047-1365-92601',1,33,-123,8,-50),
(E'resource-native-2047-1365-92601',1,34,-123,9,-50),
(E'resource-native-2047-1365-92601',1,35,-123,10,-50),
(E'resource-native-2047-1365-92601',1,36,-123,11,-50),
(E'resource-native-2047-1365-92601',1,37,-123,12,-50);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2046-1368-92901',1,-2046,0,421,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2046-1368-92901',1,E'proposed',0),
(E'resource-native-2046-1368-92901',1,E'active',1),
(E'resource-native-2046-1368-92901',1,E'completed',2),
(E'resource-native-2046-1368-92901',1,E'expired',2),
(E'resource-native-2046-1368-92901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',-2046,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2046-1368-92901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2046-1368-92901',1,0,-65,42,0),
(E'resource-native-2046-1368-92901',1,1,-64,42,0),
(E'resource-native-2046-1368-92901',1,2,-63,19,5),
(E'resource-native-2046-1368-92901',1,3,-63,42,0),
(E'resource-native-2046-1368-92901',1,4,-62,19,0),
(E'resource-native-2046-1368-92901',1,5,-62,20,0),
(E'resource-native-2046-1368-92901',1,6,-62,28,10),
(E'resource-native-2046-1368-92901',1,7,-62,29,10),
(E'resource-native-2046-1368-92901',1,8,-62,30,10),
(E'resource-native-2046-1368-92901',1,9,-62,34,4),
(E'resource-native-2046-1368-92901',1,10,-62,35,2),
(E'resource-native-2046-1368-92901',1,11,-62,42,0),
(E'resource-native-2046-1368-92901',1,12,-61,15,5),
(E'resource-native-2046-1368-92901',1,13,-61,17,12),
(E'resource-native-2046-1368-92901',1,14,-61,18,0),
(E'resource-native-2046-1368-92901',1,15,-61,19,0),
(E'resource-native-2046-1368-92901',1,16,-61,20,0),
(E'resource-native-2046-1368-92901',1,17,-61,21,0),
(E'resource-native-2046-1368-92901',1,18,-61,23,5),
(E'resource-native-2046-1368-92901',1,19,-61,24,0),
(E'resource-native-2046-1368-92901',1,20,-61,28,6),
(E'resource-native-2046-1368-92901',1,21,-61,29,6),
(E'resource-native-2046-1368-92901',1,22,-61,30,6),
(E'resource-native-2046-1368-92901',1,23,-61,34,3),
(E'resource-native-2046-1368-92901',1,24,-61,35,1),
(E'resource-native-2046-1368-92901',1,25,-61,40,5),
(E'resource-native-2046-1368-92901',1,26,-61,43,0),
(E'resource-native-2046-1368-92901',1,27,-61,44,0),
(E'resource-native-2046-1368-92901',1,28,-61,45,0),
(E'resource-native-2046-1368-92901',1,29,-61,46,0),
(E'resource-native-2046-1368-92901',1,30,-60,18,0),
(E'resource-native-2046-1368-92901',1,31,-60,19,0),
(E'resource-native-2046-1368-92901',1,32,-60,20,0),
(E'resource-native-2046-1368-92901',1,33,-60,21,0),
(E'resource-native-2046-1368-92901',1,34,-60,22,0),
(E'resource-native-2046-1368-92901',1,35,-60,23,0),
(E'resource-native-2046-1368-92901',1,36,-60,24,0),
(E'resource-native-2046-1368-92901',1,37,-60,25,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2045-1364-93001',1,-2045,0,420,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2045-1364-93001',1,E'proposed',0),
(E'resource-native-2045-1364-93001',1,E'active',1),
(E'resource-native-2045-1364-93001',1,E'completed',2),
(E'resource-native-2045-1364-93001',1,E'expired',2),
(E'resource-native-2045-1364-93001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',51,NULL,NULL),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',-2045,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2045-1364-93001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2045-1364-93001',1,0,-25,-172,-28),
(E'resource-native-2045-1364-93001',1,1,-25,-170,-33),
(E'resource-native-2045-1364-93001',1,2,-25,-165,-38),
(E'resource-native-2045-1364-93001',1,3,-25,-64,-48),
(E'resource-native-2045-1364-93001',1,4,-25,-63,-48),
(E'resource-native-2045-1364-93001',1,5,-25,-62,-48),
(E'resource-native-2045-1364-93001',1,6,-25,-61,-48),
(E'resource-native-2045-1364-93001',1,7,-25,-60,-48),
(E'resource-native-2045-1364-93001',1,8,-25,-59,-48),
(E'resource-native-2045-1364-93001',1,9,-25,-58,-48),
(E'resource-native-2045-1364-93001',1,10,-25,-57,-48),
(E'resource-native-2045-1364-93001',1,11,-25,-56,-48),
(E'resource-native-2045-1364-93001',1,12,-25,-55,-48),
(E'resource-native-2045-1364-93001',1,13,-25,-54,-48),
(E'resource-native-2045-1364-93001',1,14,-25,-53,-48),
(E'resource-native-2045-1364-93001',1,15,-25,-52,-48),
(E'resource-native-2045-1364-93001',1,16,-25,-51,-48),
(E'resource-native-2045-1364-93001',1,17,-25,-50,-48),
(E'resource-native-2045-1364-93001',1,18,-25,-48,-48),
(E'resource-native-2045-1364-93001',1,19,-24,-174,-33),
(E'resource-native-2045-1364-93001',1,20,-24,-170,-33),
(E'resource-native-2045-1364-93001',1,21,-24,-169,-38),
(E'resource-native-2045-1364-93001',1,22,-24,-168,-34),
(E'resource-native-2045-1364-93001',1,23,-24,-167,-37),
(E'resource-native-2045-1364-93001',1,24,-24,-166,-38),
(E'resource-native-2045-1364-93001',1,25,-24,-165,-38),
(E'resource-native-2045-1364-93001',1,26,-24,-164,-38),
(E'resource-native-2045-1364-93001',1,27,-24,-64,-48),
(E'resource-native-2045-1364-93001',1,28,-24,-63,-48),
(E'resource-native-2045-1364-93001',1,29,-24,-62,-48),
(E'resource-native-2045-1364-93001',1,30,-24,-51,-48),
(E'resource-native-2045-1364-93001',1,31,-24,-50,-48),
(E'resource-native-2045-1364-93001',1,32,-24,-49,-48),
(E'resource-native-2045-1364-93001',1,33,-24,-48,-48),
(E'resource-native-2045-1364-93001',1,34,-23,-174,-33),
(E'resource-native-2045-1364-93001',1,35,-23,-172,-38),
(E'resource-native-2045-1364-93001',1,36,-23,-171,-38),
(E'resource-native-2045-1364-93001',1,37,-23,-170,-38);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2044-1359-92301',1,-2044,0,419,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2044-1359-92301',1,E'proposed',0),
(E'resource-native-2044-1359-92301',1,E'active',1),
(E'resource-native-2044-1359-92301',1,E'completed',2),
(E'resource-native-2044-1359-92301',1,E'expired',2),
(E'resource-native-2044-1359-92301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',36,NULL,NULL),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',-2044,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2044-1359-92301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2044-1359-92301',1,0,-28,-162,-13),
(E'resource-native-2044-1359-92301',1,1,-27,-149,-42),
(E'resource-native-2044-1359-92301',1,2,-26,-175,-42),
(E'resource-native-2044-1359-92301',1,3,-26,-174,-42),
(E'resource-native-2044-1359-92301',1,4,-26,-169,-42),
(E'resource-native-2044-1359-92301',1,5,-26,-168,-42),
(E'resource-native-2044-1359-92301',1,6,-26,-160,-30),
(E'resource-native-2044-1359-92301',1,7,-26,-153,-42),
(E'resource-native-2044-1359-92301',1,8,-26,-152,-42),
(E'resource-native-2044-1359-92301',1,9,-26,-151,-42),
(E'resource-native-2044-1359-92301',1,10,-26,-150,-42),
(E'resource-native-2044-1359-92301',1,11,-26,-149,-42),
(E'resource-native-2044-1359-92301',1,12,-26,-146,-42),
(E'resource-native-2044-1359-92301',1,13,-25,-175,-42),
(E'resource-native-2044-1359-92301',1,14,-25,-174,-42),
(E'resource-native-2044-1359-92301',1,15,-25,-172,-42),
(E'resource-native-2044-1359-92301',1,16,-25,-169,-42),
(E'resource-native-2044-1359-92301',1,17,-25,-168,-42),
(E'resource-native-2044-1359-92301',1,18,-25,-161,-42),
(E'resource-native-2044-1359-92301',1,19,-25,-160,-42),
(E'resource-native-2044-1359-92301',1,20,-25,-159,-42),
(E'resource-native-2044-1359-92301',1,21,-25,-155,-42),
(E'resource-native-2044-1359-92301',1,22,-25,-154,-42),
(E'resource-native-2044-1359-92301',1,23,-25,-153,-42),
(E'resource-native-2044-1359-92301',1,24,-25,-152,-42),
(E'resource-native-2044-1359-92301',1,25,-25,-151,-42),
(E'resource-native-2044-1359-92301',1,26,-25,-147,-42),
(E'resource-native-2044-1359-92301',1,27,-25,-146,-42),
(E'resource-native-2044-1359-92301',1,28,-25,-142,-42),
(E'resource-native-2044-1359-92301',1,29,-24,-178,-42),
(E'resource-native-2044-1359-92301',1,30,-24,-175,-42),
(E'resource-native-2044-1359-92301',1,31,-24,-174,-42),
(E'resource-native-2044-1359-92301',1,32,-24,-173,-42),
(E'resource-native-2044-1359-92301',1,33,-24,-172,-42),
(E'resource-native-2044-1359-92301',1,34,-24,-171,-42),
(E'resource-native-2044-1359-92301',1,35,-24,-170,-42),
(E'resource-native-2044-1359-92301',1,36,-24,-169,-42),
(E'resource-native-2044-1359-92301',1,37,-24,-168,-42);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2042-1358-92201',1,-2042,0,418,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2042-1358-92201',1,E'proposed',0),
(E'resource-native-2042-1358-92201',1,E'active',1),
(E'resource-native-2042-1358-92201',1,E'completed',2),
(E'resource-native-2042-1358-92201',1,E'expired',2),
(E'resource-native-2042-1358-92201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',36,NULL,NULL),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',-2042,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2042-1358-92201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2042-1358-92201',1,0,-166,40,-51),
(E'resource-native-2042-1358-92201',1,1,-166,41,-51),
(E'resource-native-2042-1358-92201',1,2,-166,42,-51),
(E'resource-native-2042-1358-92201',1,3,-166,43,-51),
(E'resource-native-2042-1358-92201',1,4,-165,35,-49),
(E'resource-native-2042-1358-92201',1,5,-165,40,-51),
(E'resource-native-2042-1358-92201',1,6,-165,41,-51),
(E'resource-native-2042-1358-92201',1,7,-165,42,-51),
(E'resource-native-2042-1358-92201',1,8,-165,43,-51),
(E'resource-native-2042-1358-92201',1,9,-164,35,-51),
(E'resource-native-2042-1358-92201',1,10,-164,36,-51),
(E'resource-native-2042-1358-92201',1,11,-164,37,-51),
(E'resource-native-2042-1358-92201',1,12,-164,38,-51),
(E'resource-native-2042-1358-92201',1,13,-164,39,-51),
(E'resource-native-2042-1358-92201',1,14,-164,40,-51),
(E'resource-native-2042-1358-92201',1,15,-164,41,-51),
(E'resource-native-2042-1358-92201',1,16,-164,42,-51),
(E'resource-native-2042-1358-92201',1,17,-164,43,-51),
(E'resource-native-2042-1358-92201',1,18,-163,34,-51),
(E'resource-native-2042-1358-92201',1,19,-163,35,-51),
(E'resource-native-2042-1358-92201',1,20,-163,36,-51),
(E'resource-native-2042-1358-92201',1,21,-163,37,-51),
(E'resource-native-2042-1358-92201',1,22,-163,38,-51),
(E'resource-native-2042-1358-92201',1,23,-163,39,-51),
(E'resource-native-2042-1358-92201',1,24,-163,40,-51),
(E'resource-native-2042-1358-92201',1,25,-163,41,-51),
(E'resource-native-2042-1358-92201',1,26,-163,42,-51),
(E'resource-native-2042-1358-92201',1,27,-163,43,-51),
(E'resource-native-2042-1358-92201',1,28,-163,44,-51),
(E'resource-native-2042-1358-92201',1,29,-162,34,-51),
(E'resource-native-2042-1358-92201',1,30,-162,35,-51),
(E'resource-native-2042-1358-92201',1,31,-162,36,-51),
(E'resource-native-2042-1358-92201',1,32,-162,37,-51),
(E'resource-native-2042-1358-92201',1,33,-162,38,-51),
(E'resource-native-2042-1358-92201',1,34,-162,39,-51),
(E'resource-native-2042-1358-92201',1,35,-162,40,-51),
(E'resource-native-2042-1358-92201',1,36,-162,41,-51),
(E'resource-native-2042-1358-92201',1,37,-162,43,-51);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2017-1305-91201',1,-2017,0,413,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2017-1305-91201',1,E'proposed',0),
(E'resource-native-2017-1305-91201',1,E'active',1),
(E'resource-native-2017-1305-91201',1,E'completed',2),
(E'resource-native-2017-1305-91201',1,E'expired',2),
(E'resource-native-2017-1305-91201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',-2017,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2017-1305-91201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2017-1305-91201',1,0,-46,-99,31),
(E'resource-native-2017-1305-91201',1,1,-46,-98,31),
(E'resource-native-2017-1305-91201',1,2,-46,-97,29),
(E'resource-native-2017-1305-91201',1,3,-46,-96,25),
(E'resource-native-2017-1305-91201',1,4,-46,-95,23),
(E'resource-native-2017-1305-91201',1,5,-46,-94,23),
(E'resource-native-2017-1305-91201',1,6,-46,-93,21),
(E'resource-native-2017-1305-91201',1,7,-46,-92,17),
(E'resource-native-2017-1305-91201',1,8,-46,-90,11),
(E'resource-native-2017-1305-91201',1,9,-46,-89,11),
(E'resource-native-2017-1305-91201',1,10,-46,-88,9),
(E'resource-native-2017-1305-91201',1,11,-46,-87,5),
(E'resource-native-2017-1305-91201',1,12,-46,-86,1),
(E'resource-native-2017-1305-91201',1,13,-46,-85,-1),
(E'resource-native-2017-1305-91201',1,14,-46,-84,-1),
(E'resource-native-2017-1305-91201',1,15,-46,-83,-1),
(E'resource-native-2017-1305-91201',1,16,-46,-82,-1),
(E'resource-native-2017-1305-91201',1,17,-46,-81,-1),
(E'resource-native-2017-1305-91201',1,18,-46,-80,-1),
(E'resource-native-2017-1305-91201',1,19,-46,-79,-1),
(E'resource-native-2017-1305-91201',1,20,-46,-78,-1),
(E'resource-native-2017-1305-91201',1,21,-45,-101,31),
(E'resource-native-2017-1305-91201',1,22,-45,-100,31),
(E'resource-native-2017-1305-91201',1,23,-45,-99,31),
(E'resource-native-2017-1305-91201',1,24,-45,-98,31),
(E'resource-native-2017-1305-91201',1,25,-45,-97,29),
(E'resource-native-2017-1305-91201',1,26,-45,-96,25),
(E'resource-native-2017-1305-91201',1,27,-45,-95,23),
(E'resource-native-2017-1305-91201',1,28,-45,-94,23),
(E'resource-native-2017-1305-91201',1,29,-45,-93,21),
(E'resource-native-2017-1305-91201',1,30,-45,-92,17),
(E'resource-native-2017-1305-91201',1,31,-45,-91,13),
(E'resource-native-2017-1305-91201',1,32,-45,-90,11),
(E'resource-native-2017-1305-91201',1,33,-45,-89,11),
(E'resource-native-2017-1305-91201',1,34,-45,-88,9),
(E'resource-native-2017-1305-91201',1,35,-45,-87,5),
(E'resource-native-2017-1305-91201',1,36,-45,-86,1),
(E'resource-native-2017-1305-91201',1,37,-45,-85,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2017-1309-91301',1,-2017,0,414,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2017-1309-91301',1,E'proposed',0),
(E'resource-native-2017-1309-91301',1,E'active',1),
(E'resource-native-2017-1309-91301',1,E'completed',2),
(E'resource-native-2017-1309-91301',1,E'expired',2),
(E'resource-native-2017-1309-91301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',-2017,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2017-1309-91301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2017-1309-91301',1,0,-72,-33,10),
(E'resource-native-2017-1309-91301',1,1,-72,-32,10),
(E'resource-native-2017-1309-91301',1,2,-72,-31,10),
(E'resource-native-2017-1309-91301',1,3,-72,-27,10),
(E'resource-native-2017-1309-91301',1,4,-72,-19,3),
(E'resource-native-2017-1309-91301',1,5,-72,-18,0),
(E'resource-native-2017-1309-91301',1,6,-72,-17,0),
(E'resource-native-2017-1309-91301',1,7,-72,-16,0),
(E'resource-native-2017-1309-91301',1,8,-72,-15,3),
(E'resource-native-2017-1309-91301',1,9,-72,-12,0),
(E'resource-native-2017-1309-91301',1,10,-72,-11,0),
(E'resource-native-2017-1309-91301',1,11,-72,-9,0),
(E'resource-native-2017-1309-91301',1,12,-72,-3,0),
(E'resource-native-2017-1309-91301',1,13,-72,-2,0),
(E'resource-native-2017-1309-91301',1,14,-72,-1,0),
(E'resource-native-2017-1309-91301',1,15,-72,0,0),
(E'resource-native-2017-1309-91301',1,16,-72,3,0),
(E'resource-native-2017-1309-91301',1,17,-72,4,0),
(E'resource-native-2017-1309-91301',1,18,-71,-33,10),
(E'resource-native-2017-1309-91301',1,19,-71,-32,10),
(E'resource-native-2017-1309-91301',1,20,-71,-31,10),
(E'resource-native-2017-1309-91301',1,21,-71,-30,10),
(E'resource-native-2017-1309-91301',1,22,-71,-29,10),
(E'resource-native-2017-1309-91301',1,23,-71,-28,10),
(E'resource-native-2017-1309-91301',1,24,-71,-27,10),
(E'resource-native-2017-1309-91301',1,25,-71,-26,10),
(E'resource-native-2017-1309-91301',1,26,-71,-21,0),
(E'resource-native-2017-1309-91301',1,27,-71,-20,0),
(E'resource-native-2017-1309-91301',1,28,-71,-19,0),
(E'resource-native-2017-1309-91301',1,29,-71,-18,0),
(E'resource-native-2017-1309-91301',1,30,-71,-17,0),
(E'resource-native-2017-1309-91301',1,31,-71,-16,0),
(E'resource-native-2017-1309-91301',1,32,-71,-15,0),
(E'resource-native-2017-1309-91301',1,33,-71,-14,0),
(E'resource-native-2017-1309-91301',1,34,-71,-13,0),
(E'resource-native-2017-1309-91301',1,35,-71,-12,0),
(E'resource-native-2017-1309-91301',1,36,-71,-11,0),
(E'resource-native-2017-1309-91301',1,37,-71,-9,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2017-1326-91401',1,-2017,0,415,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2017-1326-91401',1,E'proposed',0),
(E'resource-native-2017-1326-91401',1,E'active',1),
(E'resource-native-2017-1326-91401',1,E'completed',2),
(E'resource-native-2017-1326-91401',1,E'expired',2),
(E'resource-native-2017-1326-91401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',-2017,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2017-1326-91401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2017-1326-91401',1,0,-180,-119,36),
(E'resource-native-2017-1326-91401',1,1,-178,-119,36),
(E'resource-native-2017-1326-91401',1,2,-171,-124,50),
(E'resource-native-2017-1326-91401',1,3,-170,-125,50),
(E'resource-native-2017-1326-91401',1,4,-170,-124,50),
(E'resource-native-2017-1326-91401',1,5,-169,-142,50),
(E'resource-native-2017-1326-91401',1,6,-169,-141,50),
(E'resource-native-2017-1326-91401',1,7,-169,-133,49),
(E'resource-native-2017-1326-91401',1,8,-169,-132,49),
(E'resource-native-2017-1326-91401',1,9,-169,-131,49),
(E'resource-native-2017-1326-91401',1,10,-169,-126,50),
(E'resource-native-2017-1326-91401',1,11,-169,-125,50),
(E'resource-native-2017-1326-91401',1,12,-169,-124,50),
(E'resource-native-2017-1326-91401',1,13,-169,-123,50),
(E'resource-native-2017-1326-91401',1,14,-168,-142,50),
(E'resource-native-2017-1326-91401',1,15,-168,-141,50),
(E'resource-native-2017-1326-91401',1,16,-168,-140,50),
(E'resource-native-2017-1326-91401',1,17,-168,-139,50),
(E'resource-native-2017-1326-91401',1,18,-168,-133,49),
(E'resource-native-2017-1326-91401',1,19,-168,-132,49),
(E'resource-native-2017-1326-91401',1,20,-168,-131,49),
(E'resource-native-2017-1326-91401',1,21,-168,-126,50),
(E'resource-native-2017-1326-91401',1,22,-168,-125,50),
(E'resource-native-2017-1326-91401',1,23,-168,-124,50),
(E'resource-native-2017-1326-91401',1,24,-168,-123,50),
(E'resource-native-2017-1326-91401',1,25,-167,-142,50),
(E'resource-native-2017-1326-91401',1,26,-167,-141,50),
(E'resource-native-2017-1326-91401',1,27,-167,-140,50),
(E'resource-native-2017-1326-91401',1,28,-167,-139,50),
(E'resource-native-2017-1326-91401',1,29,-167,-138,51),
(E'resource-native-2017-1326-91401',1,30,-167,-137,50),
(E'resource-native-2017-1326-91401',1,31,-167,-136,50),
(E'resource-native-2017-1326-91401',1,32,-167,-134,54),
(E'resource-native-2017-1326-91401',1,33,-167,-133,49),
(E'resource-native-2017-1326-91401',1,34,-167,-132,49),
(E'resource-native-2017-1326-91401',1,35,-167,-131,49),
(E'resource-native-2017-1326-91401',1,36,-167,-127,51),
(E'resource-native-2017-1326-91401',1,37,-167,-126,50);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2017-1333-91801',1,-2017,0,416,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2017-1333-91801',1,E'proposed',0),
(E'resource-native-2017-1333-91801',1,E'active',1),
(E'resource-native-2017-1333-91801',1,E'completed',2),
(E'resource-native-2017-1333-91801',1,E'expired',2),
(E'resource-native-2017-1333-91801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',-2017,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2017-1333-91801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2017-1333-91801',1,0,-68,-165,24),
(E'resource-native-2017-1333-91801',1,1,-68,-164,24),
(E'resource-native-2017-1333-91801',1,2,-68,-163,24),
(E'resource-native-2017-1333-91801',1,3,-68,-162,24),
(E'resource-native-2017-1333-91801',1,4,-68,-161,24),
(E'resource-native-2017-1333-91801',1,5,-68,-160,24),
(E'resource-native-2017-1333-91801',1,6,-68,-159,24),
(E'resource-native-2017-1333-91801',1,7,-68,-158,24),
(E'resource-native-2017-1333-91801',1,8,-68,-157,24),
(E'resource-native-2017-1333-91801',1,9,-68,-156,26),
(E'resource-native-2017-1333-91801',1,10,-68,-155,30),
(E'resource-native-2017-1333-91801',1,11,-67,-165,24),
(E'resource-native-2017-1333-91801',1,12,-67,-164,24),
(E'resource-native-2017-1333-91801',1,13,-67,-163,24),
(E'resource-native-2017-1333-91801',1,14,-67,-162,24),
(E'resource-native-2017-1333-91801',1,15,-67,-161,24),
(E'resource-native-2017-1333-91801',1,16,-67,-160,24),
(E'resource-native-2017-1333-91801',1,17,-67,-159,24),
(E'resource-native-2017-1333-91801',1,18,-67,-158,24),
(E'resource-native-2017-1333-91801',1,19,-67,-157,24),
(E'resource-native-2017-1333-91801',1,20,-67,-156,26),
(E'resource-native-2017-1333-91801',1,21,-67,-155,30),
(E'resource-native-2017-1333-91801',1,22,-67,-154,34),
(E'resource-native-2017-1333-91801',1,23,-66,-165,24),
(E'resource-native-2017-1333-91801',1,24,-66,-164,24),
(E'resource-native-2017-1333-91801',1,25,-66,-163,24),
(E'resource-native-2017-1333-91801',1,26,-66,-162,24),
(E'resource-native-2017-1333-91801',1,27,-66,-161,24),
(E'resource-native-2017-1333-91801',1,28,-66,-160,24),
(E'resource-native-2017-1333-91801',1,29,-66,-159,24),
(E'resource-native-2017-1333-91801',1,30,-66,-158,24),
(E'resource-native-2017-1333-91801',1,31,-66,-157,24),
(E'resource-native-2017-1333-91801',1,32,-66,-156,26),
(E'resource-native-2017-1333-91801',1,33,-66,-155,30),
(E'resource-native-2017-1333-91801',1,34,-66,-154,34),
(E'resource-native-2017-1333-91801',1,35,-65,-165,22),
(E'resource-native-2017-1333-91801',1,36,-65,-164,22),
(E'resource-native-2017-1333-91801',1,37,-65,-163,22);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-2017-1338-92001',1,-2017,0,417,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-2017-1338-92001',1,E'proposed',0),
(E'resource-native-2017-1338-92001',1,E'active',1),
(E'resource-native-2017-1338-92001',1,E'completed',2),
(E'resource-native-2017-1338-92001',1,E'expired',2),
(E'resource-native-2017-1338-92001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',216,NULL,NULL),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',-2017,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-2017-1338-92001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-2017-1338-92001',1,0,-196,-137,16),
(E'resource-native-2017-1338-92001',1,1,-195,-137,16),
(E'resource-native-2017-1338-92001',1,2,-195,-136,16),
(E'resource-native-2017-1338-92001',1,3,-194,-137,16),
(E'resource-native-2017-1338-92001',1,4,-194,-136,16),
(E'resource-native-2017-1338-92001',1,5,-193,-138,16),
(E'resource-native-2017-1338-92001',1,6,-193,-137,16),
(E'resource-native-2017-1338-92001',1,7,-193,-136,16),
(E'resource-native-2017-1338-92001',1,8,-192,-137,16),
(E'resource-native-2017-1338-92001',1,9,-192,-136,16),
(E'resource-native-2017-1338-92001',1,10,-191,-136,16),
(E'resource-native-2017-1338-92001',1,11,-190,-137,16),
(E'resource-native-2017-1338-92001',1,12,-190,-136,16),
(E'resource-native-2017-1338-92001',1,13,-190,-135,16),
(E'resource-native-2017-1338-92001',1,14,-189,-137,16),
(E'resource-native-2017-1338-92001',1,15,-189,-136,16),
(E'resource-native-2017-1338-92001',1,16,-189,-135,16),
(E'resource-native-2017-1338-92001',1,17,-188,-138,16),
(E'resource-native-2017-1338-92001',1,18,-188,-137,16),
(E'resource-native-2017-1338-92001',1,19,-188,-136,16),
(E'resource-native-2017-1338-92001',1,20,-187,-140,16),
(E'resource-native-2017-1338-92001',1,21,-187,-138,16),
(E'resource-native-2017-1338-92001',1,22,-187,-137,16),
(E'resource-native-2017-1338-92001',1,23,-186,-140,16),
(E'resource-native-2017-1338-92001',1,24,-186,-139,16),
(E'resource-native-2017-1338-92001',1,25,-186,-138,16),
(E'resource-native-2017-1338-92001',1,26,-186,-137,16),
(E'resource-native-2017-1338-92001',1,27,-185,-141,17),
(E'resource-native-2017-1338-92001',1,28,-185,-140,17),
(E'resource-native-2017-1338-92001',1,29,-185,-139,16),
(E'resource-native-2017-1338-92001',1,30,-185,-138,16),
(E'resource-native-2017-1338-92001',1,31,-185,-137,16),
(E'resource-native-2017-1338-92001',1,32,-184,-149,46),
(E'resource-native-2017-1338-92001',1,33,-184,-143,46),
(E'resource-native-2017-1338-92001',1,34,-184,-140,16),
(E'resource-native-2017-1338-92001',1,35,-184,-139,16),
(E'resource-native-2017-1338-92001',1,36,-184,-138,16),
(E'resource-native-2017-1338-92001',1,37,-183,-141,16);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1987-1297-90801',1,-1987,0,403,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1987-1297-90801',1,E'proposed',0),
(E'resource-native-1987-1297-90801',1,E'active',1),
(E'resource-native-1987-1297-90801',1,E'completed',2),
(E'resource-native-1987-1297-90801',1,E'expired',2),
(E'resource-native-1987-1297-90801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',-1987,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1987-1297-90801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1987-1297-90801',1,0,-67,-43,32),
(E'resource-native-1987-1297-90801',1,1,-67,-41,29),
(E'resource-native-1987-1297-90801',1,2,-67,-40,29),
(E'resource-native-1987-1297-90801',1,3,-67,-39,32),
(E'resource-native-1987-1297-90801',1,4,-67,-38,31),
(E'resource-native-1987-1297-90801',1,5,-67,-37,29),
(E'resource-native-1987-1297-90801',1,6,-67,-36,29),
(E'resource-native-1987-1297-90801',1,7,-67,-35,25),
(E'resource-native-1987-1297-90801',1,8,-67,-34,22),
(E'resource-native-1987-1297-90801',1,9,-67,-33,19),
(E'resource-native-1987-1297-90801',1,10,-67,-32,19),
(E'resource-native-1987-1297-90801',1,11,-66,-46,29),
(E'resource-native-1987-1297-90801',1,12,-66,-45,29),
(E'resource-native-1987-1297-90801',1,13,-66,-43,29),
(E'resource-native-1987-1297-90801',1,14,-66,-42,29),
(E'resource-native-1987-1297-90801',1,15,-66,-41,29),
(E'resource-native-1987-1297-90801',1,16,-66,-40,29),
(E'resource-native-1987-1297-90801',1,17,-66,-39,29),
(E'resource-native-1987-1297-90801',1,18,-66,-38,29),
(E'resource-native-1987-1297-90801',1,19,-66,-37,29),
(E'resource-native-1987-1297-90801',1,20,-66,-36,29),
(E'resource-native-1987-1297-90801',1,21,-66,-33,19),
(E'resource-native-1987-1297-90801',1,22,-66,-32,19),
(E'resource-native-1987-1297-90801',1,23,-66,-31,19),
(E'resource-native-1987-1297-90801',1,24,-66,-30,19),
(E'resource-native-1987-1297-90801',1,25,-65,-47,32),
(E'resource-native-1987-1297-90801',1,26,-65,-46,29),
(E'resource-native-1987-1297-90801',1,27,-65,-45,29),
(E'resource-native-1987-1297-90801',1,28,-65,-44,29),
(E'resource-native-1987-1297-90801',1,29,-65,-43,29),
(E'resource-native-1987-1297-90801',1,30,-65,-42,29),
(E'resource-native-1987-1297-90801',1,31,-65,-41,29),
(E'resource-native-1987-1297-90801',1,32,-65,-39,29),
(E'resource-native-1987-1297-90801',1,33,-65,-38,29),
(E'resource-native-1987-1297-90801',1,34,-65,-37,29),
(E'resource-native-1987-1297-90801',1,35,-65,-36,23),
(E'resource-native-1987-1297-90801',1,36,-65,-35,19),
(E'resource-native-1987-1297-90801',1,37,-65,-34,19);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1986-1295-90701',1,-1986,0,402,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1986-1295-90701',1,E'proposed',0),
(E'resource-native-1986-1295-90701',1,E'active',1),
(E'resource-native-1986-1295-90701',1,E'completed',2),
(E'resource-native-1986-1295-90701',1,E'expired',2),
(E'resource-native-1986-1295-90701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',-1986,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1986-1295-90701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1986-1295-90701',1,0,-270,29,-80),
(E'resource-native-1986-1295-90701',1,1,-270,30,-80),
(E'resource-native-1986-1295-90701',1,2,-270,31,-80),
(E'resource-native-1986-1295-90701',1,3,-270,32,-80),
(E'resource-native-1986-1295-90701',1,4,-270,33,-80),
(E'resource-native-1986-1295-90701',1,5,-270,39,-79),
(E'resource-native-1986-1295-90701',1,6,-270,68,-83),
(E'resource-native-1986-1295-90701',1,7,-270,69,-83),
(E'resource-native-1986-1295-90701',1,8,-270,70,-83),
(E'resource-native-1986-1295-90701',1,9,-270,71,-83),
(E'resource-native-1986-1295-90701',1,10,-269,27,-80),
(E'resource-native-1986-1295-90701',1,11,-269,28,-80),
(E'resource-native-1986-1295-90701',1,12,-269,29,-80),
(E'resource-native-1986-1295-90701',1,13,-269,30,-80),
(E'resource-native-1986-1295-90701',1,14,-269,31,-80),
(E'resource-native-1986-1295-90701',1,15,-269,32,-80),
(E'resource-native-1986-1295-90701',1,16,-269,33,-80),
(E'resource-native-1986-1295-90701',1,17,-269,34,-80),
(E'resource-native-1986-1295-90701',1,18,-269,37,-80),
(E'resource-native-1986-1295-90701',1,19,-269,38,-80),
(E'resource-native-1986-1295-90701',1,20,-269,39,-79),
(E'resource-native-1986-1295-90701',1,21,-269,40,-80),
(E'resource-native-1986-1295-90701',1,22,-269,41,-80),
(E'resource-native-1986-1295-90701',1,23,-269,47,-77),
(E'resource-native-1986-1295-90701',1,24,-269,48,-79),
(E'resource-native-1986-1295-90701',1,25,-269,49,-80),
(E'resource-native-1986-1295-90701',1,26,-269,50,-80),
(E'resource-native-1986-1295-90701',1,27,-269,56,-82),
(E'resource-native-1986-1295-90701',1,28,-269,57,-83),
(E'resource-native-1986-1295-90701',1,29,-269,58,-83),
(E'resource-native-1986-1295-90701',1,30,-269,59,-82),
(E'resource-native-1986-1295-90701',1,31,-269,60,-82),
(E'resource-native-1986-1295-90701',1,32,-269,61,-83),
(E'resource-native-1986-1295-90701',1,33,-269,62,-83),
(E'resource-native-1986-1295-90701',1,34,-269,63,-83),
(E'resource-native-1986-1295-90701',1,35,-269,68,-83),
(E'resource-native-1986-1295-90701',1,36,-269,69,-83),
(E'resource-native-1986-1295-90701',1,37,-269,70,-83);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1985-1298-90901',1,-1985,0,404,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1985-1298-90901',1,E'proposed',0),
(E'resource-native-1985-1298-90901',1,E'active',1),
(E'resource-native-1985-1298-90901',1,E'completed',2),
(E'resource-native-1985-1298-90901',1,E'expired',2),
(E'resource-native-1985-1298-90901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',-1985,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1985-1298-90901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1985-1298-90901',1,0,-120,-50,40),
(E'resource-native-1985-1298-90901',1,1,-120,-49,40),
(E'resource-native-1985-1298-90901',1,2,-120,-48,40),
(E'resource-native-1985-1298-90901',1,3,-120,-47,40),
(E'resource-native-1985-1298-90901',1,4,-120,-46,40),
(E'resource-native-1985-1298-90901',1,5,-119,-52,40),
(E'resource-native-1985-1298-90901',1,6,-119,-50,40),
(E'resource-native-1985-1298-90901',1,7,-119,-49,40),
(E'resource-native-1985-1298-90901',1,8,-119,-48,40),
(E'resource-native-1985-1298-90901',1,9,-119,-47,40),
(E'resource-native-1985-1298-90901',1,10,-119,-46,40),
(E'resource-native-1985-1298-90901',1,11,-118,-52,40),
(E'resource-native-1985-1298-90901',1,12,-118,-50,40),
(E'resource-native-1985-1298-90901',1,13,-118,-49,40),
(E'resource-native-1985-1298-90901',1,14,-118,-48,40),
(E'resource-native-1985-1298-90901',1,15,-118,-47,40),
(E'resource-native-1985-1298-90901',1,16,-118,-46,40),
(E'resource-native-1985-1298-90901',1,17,-118,-45,40),
(E'resource-native-1985-1298-90901',1,18,-117,-52,40),
(E'resource-native-1985-1298-90901',1,19,-117,-51,40),
(E'resource-native-1985-1298-90901',1,20,-117,-50,40),
(E'resource-native-1985-1298-90901',1,21,-117,-48,40),
(E'resource-native-1985-1298-90901',1,22,-117,-47,40),
(E'resource-native-1985-1298-90901',1,23,-117,-46,40),
(E'resource-native-1985-1298-90901',1,24,-117,-45,40),
(E'resource-native-1985-1298-90901',1,25,-117,-44,40),
(E'resource-native-1985-1298-90901',1,26,-116,-57,40),
(E'resource-native-1985-1298-90901',1,27,-116,-56,40),
(E'resource-native-1985-1298-90901',1,28,-116,-55,40),
(E'resource-native-1985-1298-90901',1,29,-116,-54,44),
(E'resource-native-1985-1298-90901',1,30,-116,-53,44),
(E'resource-native-1985-1298-90901',1,31,-116,-51,40),
(E'resource-native-1985-1298-90901',1,32,-116,-50,42),
(E'resource-native-1985-1298-90901',1,33,-116,-48,40),
(E'resource-native-1985-1298-90901',1,34,-116,-47,40),
(E'resource-native-1985-1298-90901',1,35,-115,-61,40),
(E'resource-native-1985-1298-90901',1,36,-115,-60,40),
(E'resource-native-1985-1298-90901',1,37,-115,-57,40);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1948-1276-90001',1,-1948,0,394,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1948-1276-90001',1,E'proposed',0),
(E'resource-native-1948-1276-90001',1,E'active',1),
(E'resource-native-1948-1276-90001',1,E'completed',2),
(E'resource-native-1948-1276-90001',1,E'expired',2),
(E'resource-native-1948-1276-90001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',-1948,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1948-1276-90001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1948-1276-90001',1,0,72,-152,2),
(E'resource-native-1948-1276-90001',1,1,72,-151,2),
(E'resource-native-1948-1276-90001',1,2,72,-150,2),
(E'resource-native-1948-1276-90001',1,3,72,-149,1),
(E'resource-native-1948-1276-90001',1,4,72,-148,1),
(E'resource-native-1948-1276-90001',1,5,72,-147,1),
(E'resource-native-1948-1276-90001',1,6,72,-116,1),
(E'resource-native-1948-1276-90001',1,7,72,-115,1),
(E'resource-native-1948-1276-90001',1,8,72,-114,1),
(E'resource-native-1948-1276-90001',1,9,72,-113,2),
(E'resource-native-1948-1276-90001',1,10,72,-112,2),
(E'resource-native-1948-1276-90001',1,11,72,-111,2),
(E'resource-native-1948-1276-90001',1,12,72,-91,0),
(E'resource-native-1948-1276-90001',1,13,72,-90,0),
(E'resource-native-1948-1276-90001',1,14,72,-89,0),
(E'resource-native-1948-1276-90001',1,15,72,-83,0),
(E'resource-native-1948-1276-90001',1,16,72,-82,-2),
(E'resource-native-1948-1276-90001',1,17,72,-81,-2),
(E'resource-native-1948-1276-90001',1,18,73,-152,2),
(E'resource-native-1948-1276-90001',1,19,73,-151,2),
(E'resource-native-1948-1276-90001',1,20,73,-150,2),
(E'resource-native-1948-1276-90001',1,21,73,-149,1),
(E'resource-native-1948-1276-90001',1,22,73,-148,1),
(E'resource-native-1948-1276-90001',1,23,73,-147,1),
(E'resource-native-1948-1276-90001',1,24,73,-146,0),
(E'resource-native-1948-1276-90001',1,25,73,-140,1),
(E'resource-native-1948-1276-90001',1,26,73,-139,1),
(E'resource-native-1948-1276-90001',1,27,73,-138,1),
(E'resource-native-1948-1276-90001',1,28,73,-116,1),
(E'resource-native-1948-1276-90001',1,29,73,-115,1),
(E'resource-native-1948-1276-90001',1,30,73,-114,1),
(E'resource-native-1948-1276-90001',1,31,73,-113,2),
(E'resource-native-1948-1276-90001',1,32,73,-112,2),
(E'resource-native-1948-1276-90001',1,33,73,-111,2),
(E'resource-native-1948-1276-90001',1,34,73,-110,0),
(E'resource-native-1948-1276-90001',1,35,73,-103,0),
(E'resource-native-1948-1276-90001',1,36,73,-101,0),
(E'resource-native-1948-1276-90001',1,37,73,-100,-2);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1947-1276-90201',1,-1947,0,393,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1947-1276-90201',1,E'proposed',0),
(E'resource-native-1947-1276-90201',1,E'active',1),
(E'resource-native-1947-1276-90201',1,E'completed',2),
(E'resource-native-1947-1276-90201',1,E'expired',2),
(E'resource-native-1947-1276-90201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',-1947,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1947-1276-90201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1947-1276-90201',1,0,-72,-211,-1),
(E'resource-native-1947-1276-90201',1,1,-72,-210,-1),
(E'resource-native-1947-1276-90201',1,2,-72,-209,-1),
(E'resource-native-1947-1276-90201',1,3,-71,-211,-2),
(E'resource-native-1947-1276-90201',1,4,-71,-210,-2),
(E'resource-native-1947-1276-90201',1,5,-71,-209,-2),
(E'resource-native-1947-1276-90201',1,6,-70,-211,-2),
(E'resource-native-1947-1276-90201',1,7,-70,-210,-2),
(E'resource-native-1947-1276-90201',1,8,-70,-209,-2),
(E'resource-native-1947-1276-90201',1,9,-69,-211,-3),
(E'resource-native-1947-1276-90201',1,10,-69,-210,-3),
(E'resource-native-1947-1276-90201',1,11,-69,-209,-3),
(E'resource-native-1947-1276-90201',1,12,-68,-211,-3),
(E'resource-native-1947-1276-90201',1,13,-68,-210,-3),
(E'resource-native-1947-1276-90201',1,14,-68,-209,-3),
(E'resource-native-1947-1276-90201',1,15,-67,-211,-3),
(E'resource-native-1947-1276-90201',1,16,-67,-210,-3),
(E'resource-native-1947-1276-90201',1,17,-67,-209,-3),
(E'resource-native-1947-1276-90201',1,18,-66,-211,-3),
(E'resource-native-1947-1276-90201',1,19,-66,-210,-3),
(E'resource-native-1947-1276-90201',1,20,-66,-209,-3),
(E'resource-native-1947-1276-90201',1,21,-65,-211,-3),
(E'resource-native-1947-1276-90201',1,22,-65,-210,-3),
(E'resource-native-1947-1276-90201',1,23,-65,-209,-3),
(E'resource-native-1947-1276-90201',1,24,-64,-211,-3),
(E'resource-native-1947-1276-90201',1,25,-64,-210,-3),
(E'resource-native-1947-1276-90201',1,26,-64,-209,-3),
(E'resource-native-1947-1276-90201',1,27,-63,-211,-2),
(E'resource-native-1947-1276-90201',1,28,-63,-210,-2),
(E'resource-native-1947-1276-90201',1,29,-63,-209,-2),
(E'resource-native-1947-1276-90201',1,30,-62,-211,-2),
(E'resource-native-1947-1276-90201',1,31,-62,-210,-2),
(E'resource-native-1947-1276-90201',1,32,-62,-209,-2),
(E'resource-native-1947-1276-90201',1,33,-61,-211,-1),
(E'resource-native-1947-1276-90201',1,34,-61,-210,-1),
(E'resource-native-1947-1276-90201',1,35,-61,-209,-1),
(E'resource-native-1947-1276-90201',1,36,-60,-211,0),
(E'resource-native-1947-1276-90201',1,37,-60,-210,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1946-1276-90101',1,-1946,0,392,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1946-1276-90101',1,E'proposed',0),
(E'resource-native-1946-1276-90101',1,E'active',1),
(E'resource-native-1946-1276-90101',1,E'completed',2),
(E'resource-native-1946-1276-90101',1,E'expired',2),
(E'resource-native-1946-1276-90101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',201,NULL,NULL),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',-1946,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1946-1276-90101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1946-1276-90101',1,0,-144,-147,1),
(E'resource-native-1946-1276-90101',1,1,-144,-146,1),
(E'resource-native-1946-1276-90101',1,2,-144,-145,1),
(E'resource-native-1946-1276-90101',1,3,-144,-132,1),
(E'resource-native-1946-1276-90101',1,4,-144,-131,1),
(E'resource-native-1946-1276-90101',1,5,-144,-130,1),
(E'resource-native-1946-1276-90101',1,6,-144,-113,0),
(E'resource-native-1946-1276-90101',1,7,-144,-104,-13),
(E'resource-native-1946-1276-90101',1,8,-143,-197,30),
(E'resource-native-1946-1276-90101',1,9,-143,-196,30),
(E'resource-native-1946-1276-90101',1,10,-143,-195,30),
(E'resource-native-1946-1276-90101',1,11,-143,-191,30),
(E'resource-native-1946-1276-90101',1,12,-143,-190,30),
(E'resource-native-1946-1276-90101',1,13,-143,-189,30),
(E'resource-native-1946-1276-90101',1,14,-143,-157,2),
(E'resource-native-1946-1276-90101',1,15,-143,-156,2),
(E'resource-native-1946-1276-90101',1,16,-143,-155,2),
(E'resource-native-1946-1276-90101',1,17,-143,-154,0),
(E'resource-native-1946-1276-90101',1,18,-143,-153,0),
(E'resource-native-1946-1276-90101',1,19,-143,-152,0),
(E'resource-native-1946-1276-90101',1,20,-143,-148,0),
(E'resource-native-1946-1276-90101',1,21,-143,-147,1),
(E'resource-native-1946-1276-90101',1,22,-143,-146,1),
(E'resource-native-1946-1276-90101',1,23,-143,-145,1),
(E'resource-native-1946-1276-90101',1,24,-143,-135,2),
(E'resource-native-1946-1276-90101',1,25,-143,-134,2),
(E'resource-native-1946-1276-90101',1,26,-143,-133,2),
(E'resource-native-1946-1276-90101',1,27,-143,-131,1),
(E'resource-native-1946-1276-90101',1,28,-143,-130,1),
(E'resource-native-1946-1276-90101',1,29,-143,-129,0),
(E'resource-native-1946-1276-90101',1,30,-143,-121,1),
(E'resource-native-1946-1276-90101',1,31,-143,-120,1),
(E'resource-native-1946-1276-90101',1,32,-143,-119,1),
(E'resource-native-1946-1276-90101',1,33,-143,-118,0),
(E'resource-native-1946-1276-90101',1,34,-143,-117,0),
(E'resource-native-1946-1276-90101',1,35,-143,-116,0),
(E'resource-native-1946-1276-90101',1,36,-143,-115,0),
(E'resource-native-1946-1276-90101',1,37,-143,-114,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1887-1252-88701',1,-1887,0,375,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1887-1252-88701',1,E'proposed',0),
(E'resource-native-1887-1252-88701',1,E'active',1),
(E'resource-native-1887-1252-88701',1,E'completed',2),
(E'resource-native-1887-1252-88701',1,E'expired',2),
(E'resource-native-1887-1252-88701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',-1887,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1887-1252-88701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1887-1252-88701',1,0,18,-217,-20),
(E'resource-native-1887-1252-88701',1,1,18,-216,-20),
(E'resource-native-1887-1252-88701',1,2,18,-207,-20),
(E'resource-native-1887-1252-88701',1,3,18,-206,-20),
(E'resource-native-1887-1252-88701',1,4,18,-202,-20),
(E'resource-native-1887-1252-88701',1,5,18,-201,-20),
(E'resource-native-1887-1252-88701',1,6,18,-200,-20),
(E'resource-native-1887-1252-88701',1,7,18,-199,-20),
(E'resource-native-1887-1252-88701',1,8,18,-198,-20),
(E'resource-native-1887-1252-88701',1,9,18,-197,-20),
(E'resource-native-1887-1252-88701',1,10,18,-196,-20),
(E'resource-native-1887-1252-88701',1,11,18,-195,-20),
(E'resource-native-1887-1252-88701',1,12,18,-194,-20),
(E'resource-native-1887-1252-88701',1,13,18,-193,-20),
(E'resource-native-1887-1252-88701',1,14,18,-192,-20),
(E'resource-native-1887-1252-88701',1,15,18,-191,-20),
(E'resource-native-1887-1252-88701',1,16,18,-190,-20),
(E'resource-native-1887-1252-88701',1,17,18,-189,-20),
(E'resource-native-1887-1252-88701',1,18,18,-188,-20),
(E'resource-native-1887-1252-88701',1,19,18,-183,-60),
(E'resource-native-1887-1252-88701',1,20,18,-174,-60),
(E'resource-native-1887-1252-88701',1,21,18,-170,-59),
(E'resource-native-1887-1252-88701',1,22,18,-169,-59),
(E'resource-native-1887-1252-88701',1,23,18,-168,-59),
(E'resource-native-1887-1252-88701',1,24,19,-233,-40),
(E'resource-native-1887-1252-88701',1,25,19,-232,-40),
(E'resource-native-1887-1252-88701',1,26,19,-228,-40),
(E'resource-native-1887-1252-88701',1,27,19,-226,-38),
(E'resource-native-1887-1252-88701',1,28,19,-217,-20),
(E'resource-native-1887-1252-88701',1,29,19,-216,-20),
(E'resource-native-1887-1252-88701',1,30,19,-207,-20),
(E'resource-native-1887-1252-88701',1,31,19,-206,-20),
(E'resource-native-1887-1252-88701',1,32,19,-205,-20),
(E'resource-native-1887-1252-88701',1,33,19,-204,-20),
(E'resource-native-1887-1252-88701',1,34,19,-203,-20),
(E'resource-native-1887-1252-88701',1,35,19,-202,-20),
(E'resource-native-1887-1252-88701',1,36,19,-201,-20),
(E'resource-native-1887-1252-88701',1,37,19,-200,-20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1883-1252-88801',1,-1883,0,373,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1883-1252-88801',1,E'proposed',0),
(E'resource-native-1883-1252-88801',1,E'active',1),
(E'resource-native-1883-1252-88801',1,E'completed',2),
(E'resource-native-1883-1252-88801',1,E'expired',2),
(E'resource-native-1883-1252-88801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',-1883,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1883-1252-88801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1883-1252-88801',1,0,-169,-155,-12),
(E'resource-native-1883-1252-88801',1,1,-169,-154,-15),
(E'resource-native-1883-1252-88801',1,2,-168,-156,-50),
(E'resource-native-1883-1252-88801',1,3,-168,-155,-50),
(E'resource-native-1883-1252-88801',1,4,-167,-156,-50),
(E'resource-native-1883-1252-88801',1,5,-167,-155,-50),
(E'resource-native-1883-1252-88801',1,6,-166,-157,-50),
(E'resource-native-1883-1252-88801',1,7,-166,-156,-50),
(E'resource-native-1883-1252-88801',1,8,-166,-155,-50),
(E'resource-native-1883-1252-88801',1,9,-166,-154,-50),
(E'resource-native-1883-1252-88801',1,10,-165,-159,-30),
(E'resource-native-1883-1252-88801',1,11,-165,-157,-50),
(E'resource-native-1883-1252-88801',1,12,-165,-156,-50),
(E'resource-native-1883-1252-88801',1,13,-165,-155,-50),
(E'resource-native-1883-1252-88801',1,14,-165,-154,-50),
(E'resource-native-1883-1252-88801',1,15,-164,-157,-50),
(E'resource-native-1883-1252-88801',1,16,-164,-156,-50),
(E'resource-native-1883-1252-88801',1,17,-164,-155,-50),
(E'resource-native-1883-1252-88801',1,18,-164,-154,-48),
(E'resource-native-1883-1252-88801',1,19,-163,-157,-50),
(E'resource-native-1883-1252-88801',1,20,-163,-156,-50),
(E'resource-native-1883-1252-88801',1,21,-163,-155,-50),
(E'resource-native-1883-1252-88801',1,22,-163,-154,-50),
(E'resource-native-1883-1252-88801',1,23,-162,-158,-50),
(E'resource-native-1883-1252-88801',1,24,-162,-157,-50),
(E'resource-native-1883-1252-88801',1,25,-162,-156,-50),
(E'resource-native-1883-1252-88801',1,26,-162,-155,-50),
(E'resource-native-1883-1252-88801',1,27,-162,-154,-50),
(E'resource-native-1883-1252-88801',1,28,-162,-153,-49),
(E'resource-native-1883-1252-88801',1,29,-161,-157,-50),
(E'resource-native-1883-1252-88801',1,30,-161,-156,-50),
(E'resource-native-1883-1252-88801',1,31,-161,-155,-50),
(E'resource-native-1883-1252-88801',1,32,-161,-154,-50),
(E'resource-native-1883-1252-88801',1,33,-161,-153,-50),
(E'resource-native-1883-1252-88801',1,34,-160,-160,-48),
(E'resource-native-1883-1252-88801',1,35,-160,-159,-49),
(E'resource-native-1883-1252-88801',1,36,-160,-158,-50),
(E'resource-native-1883-1252-88801',1,37,-160,-157,-50);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1875-1252-88501',1,-1875,0,371,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1875-1252-88501',1,E'proposed',0),
(E'resource-native-1875-1252-88501',1,E'active',1),
(E'resource-native-1875-1252-88501',1,E'completed',2),
(E'resource-native-1875-1252-88501',1,E'expired',2),
(E'resource-native-1875-1252-88501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',-1875,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1875-1252-88501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1875-1252-88501',1,0,-35,-62,-76),
(E'resource-native-1875-1252-88501',1,1,-35,-60,-78),
(E'resource-native-1875-1252-88501',1,2,-35,-55,-80),
(E'resource-native-1875-1252-88501',1,3,-35,-54,-80),
(E'resource-native-1875-1252-88501',1,4,-35,-53,-80),
(E'resource-native-1875-1252-88501',1,5,-35,-52,-80),
(E'resource-native-1875-1252-88501',1,6,-35,-51,-80),
(E'resource-native-1875-1252-88501',1,7,-34,-62,-76),
(E'resource-native-1875-1252-88501',1,8,-34,-61,-76),
(E'resource-native-1875-1252-88501',1,9,-34,-60,-76),
(E'resource-native-1875-1252-88501',1,10,-34,-55,-80),
(E'resource-native-1875-1252-88501',1,11,-34,-54,-80),
(E'resource-native-1875-1252-88501',1,12,-34,-53,-80),
(E'resource-native-1875-1252-88501',1,13,-34,-52,-80),
(E'resource-native-1875-1252-88501',1,14,-34,-51,-80),
(E'resource-native-1875-1252-88501',1,15,-34,-50,-80),
(E'resource-native-1875-1252-88501',1,16,-33,-62,-76),
(E'resource-native-1875-1252-88501',1,17,-33,-61,-76),
(E'resource-native-1875-1252-88501',1,18,-33,-60,-76),
(E'resource-native-1875-1252-88501',1,19,-33,-56,-80),
(E'resource-native-1875-1252-88501',1,20,-33,-55,-80),
(E'resource-native-1875-1252-88501',1,21,-33,-54,-80),
(E'resource-native-1875-1252-88501',1,22,-33,-53,-80),
(E'resource-native-1875-1252-88501',1,23,-33,-52,-80),
(E'resource-native-1875-1252-88501',1,24,-33,-51,-80),
(E'resource-native-1875-1252-88501',1,25,-33,-50,-80),
(E'resource-native-1875-1252-88501',1,26,-32,-71,-76),
(E'resource-native-1875-1252-88501',1,27,-32,-70,-76),
(E'resource-native-1875-1252-88501',1,28,-32,-63,-76),
(E'resource-native-1875-1252-88501',1,29,-32,-62,-76),
(E'resource-native-1875-1252-88501',1,30,-32,-61,-76),
(E'resource-native-1875-1252-88501',1,31,-32,-60,-74),
(E'resource-native-1875-1252-88501',1,32,-32,-56,-80),
(E'resource-native-1875-1252-88501',1,33,-32,-55,-80),
(E'resource-native-1875-1252-88501',1,34,-32,-54,-80),
(E'resource-native-1875-1252-88501',1,35,-32,-53,-80),
(E'resource-native-1875-1252-88501',1,36,-32,-52,-80),
(E'resource-native-1875-1252-88501',1,37,-32,-51,-80);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1723-1136-84301',1,-1723,0,360,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1723-1136-84301',1,E'proposed',0),
(E'resource-native-1723-1136-84301',1,E'active',1),
(E'resource-native-1723-1136-84301',1,E'completed',2),
(E'resource-native-1723-1136-84301',1,E'expired',2),
(E'resource-native-1723-1136-84301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',-1723,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1723-1136-84301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1723-1136-84301',1,0,72,-36,-80),
(E'resource-native-1723-1136-84301',1,1,72,-35,-80),
(E'resource-native-1723-1136-84301',1,2,72,-34,-80),
(E'resource-native-1723-1136-84301',1,3,72,-32,-80),
(E'resource-native-1723-1136-84301',1,4,72,-31,-80),
(E'resource-native-1723-1136-84301',1,5,72,-30,-80),
(E'resource-native-1723-1136-84301',1,6,72,-29,-76),
(E'resource-native-1723-1136-84301',1,7,72,-28,-78),
(E'resource-native-1723-1136-84301',1,8,72,-27,-80),
(E'resource-native-1723-1136-84301',1,9,72,-26,-80),
(E'resource-native-1723-1136-84301',1,10,72,-24,-80),
(E'resource-native-1723-1136-84301',1,11,72,-23,-78),
(E'resource-native-1723-1136-84301',1,12,72,-21,-80),
(E'resource-native-1723-1136-84301',1,13,72,-18,-67),
(E'resource-native-1723-1136-84301',1,14,72,-17,-67),
(E'resource-native-1723-1136-84301',1,15,72,-16,-67),
(E'resource-native-1723-1136-84301',1,16,72,-15,-67),
(E'resource-native-1723-1136-84301',1,17,72,-14,-67),
(E'resource-native-1723-1136-84301',1,18,72,-13,-67),
(E'resource-native-1723-1136-84301',1,19,72,-12,-67),
(E'resource-native-1723-1136-84301',1,20,72,-11,-67),
(E'resource-native-1723-1136-84301',1,21,72,-10,-67),
(E'resource-native-1723-1136-84301',1,22,72,-9,-67),
(E'resource-native-1723-1136-84301',1,23,72,-8,-67),
(E'resource-native-1723-1136-84301',1,24,72,-7,-78),
(E'resource-native-1723-1136-84301',1,25,72,-6,-80),
(E'resource-native-1723-1136-84301',1,26,72,-5,-80),
(E'resource-native-1723-1136-84301',1,27,72,-4,-80),
(E'resource-native-1723-1136-84301',1,28,72,-3,-80),
(E'resource-native-1723-1136-84301',1,29,72,-2,-80),
(E'resource-native-1723-1136-84301',1,30,72,0,-80),
(E'resource-native-1723-1136-84301',1,31,72,1,-80),
(E'resource-native-1723-1136-84301',1,32,72,2,-78),
(E'resource-native-1723-1136-84301',1,33,72,3,-78),
(E'resource-native-1723-1136-84301',1,34,72,4,-80),
(E'resource-native-1723-1136-84301',1,35,72,7,-80),
(E'resource-native-1723-1136-84301',1,36,72,8,-80),
(E'resource-native-1723-1136-84301',1,37,72,9,-80);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1720-1136-84401',1,-1720,0,361,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1720-1136-84401',1,E'proposed',0),
(E'resource-native-1720-1136-84401',1,E'active',1),
(E'resource-native-1720-1136-84401',1,E'completed',2),
(E'resource-native-1720-1136-84401',1,E'expired',2),
(E'resource-native-1720-1136-84401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',-1720,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1720-1136-84401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1720-1136-84401',1,0,-35,114,-78),
(E'resource-native-1720-1136-84401',1,1,-35,115,-80),
(E'resource-native-1720-1136-84401',1,2,-35,128,-80),
(E'resource-native-1720-1136-84401',1,3,-35,129,-80),
(E'resource-native-1720-1136-84401',1,4,-35,135,-80),
(E'resource-native-1720-1136-84401',1,5,-35,136,-80),
(E'resource-native-1720-1136-84401',1,6,-35,137,-80),
(E'resource-native-1720-1136-84401',1,7,-34,115,-80),
(E'resource-native-1720-1136-84401',1,8,-34,116,-80),
(E'resource-native-1720-1136-84401',1,9,-34,117,-80),
(E'resource-native-1720-1136-84401',1,10,-34,118,-80),
(E'resource-native-1720-1136-84401',1,11,-34,119,-78),
(E'resource-native-1720-1136-84401',1,12,-34,120,-82),
(E'resource-native-1720-1136-84401',1,13,-34,129,-80),
(E'resource-native-1720-1136-84401',1,14,-34,134,-80),
(E'resource-native-1720-1136-84401',1,15,-34,135,-80),
(E'resource-native-1720-1136-84401',1,16,-34,136,-80),
(E'resource-native-1720-1136-84401',1,17,-34,137,-80),
(E'resource-native-1720-1136-84401',1,18,-33,115,-80),
(E'resource-native-1720-1136-84401',1,19,-33,116,-80),
(E'resource-native-1720-1136-84401',1,20,-33,117,-80),
(E'resource-native-1720-1136-84401',1,21,-33,118,-80),
(E'resource-native-1720-1136-84401',1,22,-33,119,-80),
(E'resource-native-1720-1136-84401',1,23,-33,120,-80),
(E'resource-native-1720-1136-84401',1,24,-33,124,-78),
(E'resource-native-1720-1136-84401',1,25,-33,125,-80),
(E'resource-native-1720-1136-84401',1,26,-33,126,-80),
(E'resource-native-1720-1136-84401',1,27,-33,128,-80),
(E'resource-native-1720-1136-84401',1,28,-33,129,-80),
(E'resource-native-1720-1136-84401',1,29,-33,130,-80),
(E'resource-native-1720-1136-84401',1,30,-33,131,-80),
(E'resource-native-1720-1136-84401',1,31,-33,132,-80),
(E'resource-native-1720-1136-84401',1,32,-33,133,-80),
(E'resource-native-1720-1136-84401',1,33,-33,134,-80),
(E'resource-native-1720-1136-84401',1,34,-33,135,-80),
(E'resource-native-1720-1136-84401',1,35,-33,136,-80),
(E'resource-native-1720-1136-84401',1,36,-33,137,-80),
(E'resource-native-1720-1136-84401',1,37,-33,138,-80);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1716-1136-84501',1,-1716,0,362,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1716-1136-84501',1,E'proposed',0),
(E'resource-native-1716-1136-84501',1,E'active',1),
(E'resource-native-1716-1136-84501',1,E'completed',2),
(E'resource-native-1716-1136-84501',1,E'expired',2),
(E'resource-native-1716-1136-84501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',-1716,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1716-1136-84501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1716-1136-84501',1,0,-107,95,11),
(E'resource-native-1716-1136-84501',1,1,-107,96,11),
(E'resource-native-1716-1136-84501',1,2,-107,97,11),
(E'resource-native-1716-1136-84501',1,3,-107,98,12),
(E'resource-native-1716-1136-84501',1,4,-107,99,10),
(E'resource-native-1716-1136-84501',1,5,-107,100,10),
(E'resource-native-1716-1136-84501',1,6,-107,105,14),
(E'resource-native-1716-1136-84501',1,7,-107,106,12),
(E'resource-native-1716-1136-84501',1,8,-107,107,-32),
(E'resource-native-1716-1136-84501',1,9,-106,95,11),
(E'resource-native-1716-1136-84501',1,10,-106,97,11),
(E'resource-native-1716-1136-84501',1,11,-106,98,10),
(E'resource-native-1716-1136-84501',1,12,-106,99,10),
(E'resource-native-1716-1136-84501',1,13,-106,100,10),
(E'resource-native-1716-1136-84501',1,14,-106,101,10),
(E'resource-native-1716-1136-84501',1,15,-106,102,10),
(E'resource-native-1716-1136-84501',1,16,-106,103,10),
(E'resource-native-1716-1136-84501',1,17,-106,104,10),
(E'resource-native-1716-1136-84501',1,18,-106,105,12),
(E'resource-native-1716-1136-84501',1,19,-106,106,10),
(E'resource-native-1716-1136-84501',1,20,-106,107,-32),
(E'resource-native-1716-1136-84501',1,21,-105,91,10),
(E'resource-native-1716-1136-84501',1,22,-105,92,12),
(E'resource-native-1716-1136-84501',1,23,-105,93,14),
(E'resource-native-1716-1136-84501',1,24,-105,94,12),
(E'resource-native-1716-1136-84501',1,25,-105,95,11),
(E'resource-native-1716-1136-84501',1,26,-105,96,11),
(E'resource-native-1716-1136-84501',1,27,-105,97,11),
(E'resource-native-1716-1136-84501',1,28,-105,98,10),
(E'resource-native-1716-1136-84501',1,29,-105,99,10),
(E'resource-native-1716-1136-84501',1,30,-105,100,10),
(E'resource-native-1716-1136-84501',1,31,-105,101,10),
(E'resource-native-1716-1136-84501',1,32,-105,102,10),
(E'resource-native-1716-1136-84501',1,33,-105,103,10),
(E'resource-native-1716-1136-84501',1,34,-105,104,10),
(E'resource-native-1716-1136-84501',1,35,-105,105,10),
(E'resource-native-1716-1136-84501',1,36,-105,106,10),
(E'resource-native-1716-1136-84501',1,37,-105,107,-32);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1711-1209-86701',1,-1711,0,367,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1711-1209-86701',1,E'proposed',0),
(E'resource-native-1711-1209-86701',1,E'active',1),
(E'resource-native-1711-1209-86701',1,E'completed',2),
(E'resource-native-1711-1209-86701',1,E'expired',2),
(E'resource-native-1711-1209-86701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',-1711,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1711-1209-86701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1711-1209-86701',1,0,-71,-68,20),
(E'resource-native-1711-1209-86701',1,1,-71,-53,20),
(E'resource-native-1711-1209-86701',1,2,-71,-52,20),
(E'resource-native-1711-1209-86701',1,3,-71,-51,21),
(E'resource-native-1711-1209-86701',1,4,-71,-50,20),
(E'resource-native-1711-1209-86701',1,5,-71,-45,23),
(E'resource-native-1711-1209-86701',1,6,-71,-43,22),
(E'resource-native-1711-1209-86701',1,7,-71,-41,20),
(E'resource-native-1711-1209-86701',1,8,-71,-40,20),
(E'resource-native-1711-1209-86701',1,9,-70,-82,23),
(E'resource-native-1711-1209-86701',1,10,-70,-68,20),
(E'resource-native-1711-1209-86701',1,11,-70,-67,20),
(E'resource-native-1711-1209-86701',1,12,-70,-66,20),
(E'resource-native-1711-1209-86701',1,13,-70,-65,20),
(E'resource-native-1711-1209-86701',1,14,-70,-58,24),
(E'resource-native-1711-1209-86701',1,15,-70,-52,20),
(E'resource-native-1711-1209-86701',1,16,-70,-51,21),
(E'resource-native-1711-1209-86701',1,17,-70,-50,20),
(E'resource-native-1711-1209-86701',1,18,-70,-49,20),
(E'resource-native-1711-1209-86701',1,19,-70,-46,20),
(E'resource-native-1711-1209-86701',1,20,-70,-45,20),
(E'resource-native-1711-1209-86701',1,21,-70,-44,20),
(E'resource-native-1711-1209-86701',1,22,-70,-43,20),
(E'resource-native-1711-1209-86701',1,23,-70,-40,20),
(E'resource-native-1711-1209-86701',1,24,-69,-86,20),
(E'resource-native-1711-1209-86701',1,25,-69,-84,20),
(E'resource-native-1711-1209-86701',1,26,-69,-83,20),
(E'resource-native-1711-1209-86701',1,27,-69,-82,20),
(E'resource-native-1711-1209-86701',1,28,-69,-69,20),
(E'resource-native-1711-1209-86701',1,29,-69,-68,20),
(E'resource-native-1711-1209-86701',1,30,-69,-67,20),
(E'resource-native-1711-1209-86701',1,31,-69,-66,20),
(E'resource-native-1711-1209-86701',1,32,-69,-65,20),
(E'resource-native-1711-1209-86701',1,33,-69,-58,20),
(E'resource-native-1711-1209-86701',1,34,-69,-55,20),
(E'resource-native-1711-1209-86701',1,35,-69,-54,20),
(E'resource-native-1711-1209-86701',1,36,-69,-53,20),
(E'resource-native-1711-1209-86701',1,37,-69,-52,20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1707-1137-85901',1,-1707,0,358,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1707-1137-85901',1,E'proposed',0),
(E'resource-native-1707-1137-85901',1,E'active',1),
(E'resource-native-1707-1137-85901',1,E'completed',2),
(E'resource-native-1707-1137-85901',1,E'expired',2),
(E'resource-native-1707-1137-85901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',-1707,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1707-1137-85901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1707-1137-85901',1,0,9,-269,33),
(E'resource-native-1707-1137-85901',1,1,10,-269,33),
(E'resource-native-1707-1137-85901',1,2,12,-270,0),
(E'resource-native-1707-1137-85901',1,3,12,-269,6),
(E'resource-native-1707-1137-85901',1,4,12,-268,6),
(E'resource-native-1707-1137-85901',1,5,12,-267,0),
(E'resource-native-1707-1137-85901',1,6,13,-270,1),
(E'resource-native-1707-1137-85901',1,7,13,-269,6),
(E'resource-native-1707-1137-85901',1,8,13,-268,6),
(E'resource-native-1707-1137-85901',1,9,13,-267,6),
(E'resource-native-1707-1137-85901',1,10,13,-266,6),
(E'resource-native-1707-1137-85901',1,11,13,-265,0),
(E'resource-native-1707-1137-85901',1,12,13,-263,0),
(E'resource-native-1707-1137-85901',1,13,13,-262,0),
(E'resource-native-1707-1137-85901',1,14,14,-270,6),
(E'resource-native-1707-1137-85901',1,15,14,-269,6),
(E'resource-native-1707-1137-85901',1,16,14,-268,6),
(E'resource-native-1707-1137-85901',1,17,14,-267,6),
(E'resource-native-1707-1137-85901',1,18,14,-266,3),
(E'resource-native-1707-1137-85901',1,19,14,-265,0),
(E'resource-native-1707-1137-85901',1,20,14,-264,0),
(E'resource-native-1707-1137-85901',1,21,14,-263,0),
(E'resource-native-1707-1137-85901',1,22,14,-262,0),
(E'resource-native-1707-1137-85901',1,23,14,-260,4),
(E'resource-native-1707-1137-85901',1,24,15,-270,6),
(E'resource-native-1707-1137-85901',1,25,15,-269,6),
(E'resource-native-1707-1137-85901',1,26,15,-268,6),
(E'resource-native-1707-1137-85901',1,27,15,-267,6),
(E'resource-native-1707-1137-85901',1,28,15,-266,1),
(E'resource-native-1707-1137-85901',1,29,15,-265,0),
(E'resource-native-1707-1137-85901',1,30,15,-264,0),
(E'resource-native-1707-1137-85901',1,31,15,-263,0),
(E'resource-native-1707-1137-85901',1,32,15,-262,0),
(E'resource-native-1707-1137-85901',1,33,15,-261,0),
(E'resource-native-1707-1137-85901',1,34,15,-260,0),
(E'resource-native-1707-1137-85901',1,35,15,-259,0),
(E'resource-native-1707-1137-85901',1,36,15,-257,0),
(E'resource-native-1707-1137-85901',1,37,15,-238,4);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1704-1210-84001',1,-1704,0,365,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1704-1210-84001',1,E'proposed',0),
(E'resource-native-1704-1210-84001',1,E'active',1),
(E'resource-native-1704-1210-84001',1,E'completed',2),
(E'resource-native-1704-1210-84001',1,E'expired',2),
(E'resource-native-1704-1210-84001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',-1704,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1704-1210-84001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1704-1210-84001',1,0,-18,-121,40),
(E'resource-native-1704-1210-84001',1,1,-18,-120,40),
(E'resource-native-1704-1210-84001',1,2,-18,-119,40),
(E'resource-native-1704-1210-84001',1,3,-18,-118,41),
(E'resource-native-1704-1210-84001',1,4,-18,-117,40),
(E'resource-native-1704-1210-84001',1,5,-18,-116,40),
(E'resource-native-1704-1210-84001',1,6,-18,-86,-22),
(E'resource-native-1704-1210-84001',1,7,-18,-85,-20),
(E'resource-native-1704-1210-84001',1,8,-18,-84,-20),
(E'resource-native-1704-1210-84001',1,9,-18,-83,-20),
(E'resource-native-1704-1210-84001',1,10,-18,-82,1),
(E'resource-native-1704-1210-84001',1,11,-18,-81,1),
(E'resource-native-1704-1210-84001',1,12,-18,-80,2),
(E'resource-native-1704-1210-84001',1,13,-18,-79,6),
(E'resource-native-1704-1210-84001',1,14,-18,-78,9),
(E'resource-native-1704-1210-84001',1,15,-18,-77,10),
(E'resource-native-1704-1210-84001',1,16,-18,-76,11),
(E'resource-native-1704-1210-84001',1,17,-17,-121,40),
(E'resource-native-1704-1210-84001',1,18,-17,-120,40),
(E'resource-native-1704-1210-84001',1,19,-17,-119,40),
(E'resource-native-1704-1210-84001',1,20,-17,-118,41),
(E'resource-native-1704-1210-84001',1,21,-17,-117,40),
(E'resource-native-1704-1210-84001',1,22,-17,-116,40),
(E'resource-native-1704-1210-84001',1,23,-17,-86,-20),
(E'resource-native-1704-1210-84001',1,24,-17,-85,-17),
(E'resource-native-1704-1210-84001',1,25,-17,-84,-20),
(E'resource-native-1704-1210-84001',1,26,-17,-83,-20),
(E'resource-native-1704-1210-84001',1,27,-17,-82,1),
(E'resource-native-1704-1210-84001',1,28,-17,-81,1),
(E'resource-native-1704-1210-84001',1,29,-17,-80,-1),
(E'resource-native-1704-1210-84001',1,30,-17,-79,-4),
(E'resource-native-1704-1210-84001',1,31,-17,-78,-7),
(E'resource-native-1704-1210-84001',1,32,-17,-77,-9),
(E'resource-native-1704-1210-84001',1,33,-17,-76,-9),
(E'resource-native-1704-1210-84001',1,34,-16,-129,28),
(E'resource-native-1704-1210-84001',1,35,-16,-128,28),
(E'resource-native-1704-1210-84001',1,36,-16,-127,29),
(E'resource-native-1704-1210-84001',1,37,-16,-126,33);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1699-1137-82001',1,-1699,0,357,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1699-1137-82001',1,E'proposed',0),
(E'resource-native-1699-1137-82001',1,E'active',1),
(E'resource-native-1699-1137-82001',1,E'completed',2),
(E'resource-native-1699-1137-82001',1,E'expired',2),
(E'resource-native-1699-1137-82001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',-1699,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1699-1137-82001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1699-1137-82001',1,0,36,-72,-11),
(E'resource-native-1699-1137-82001',1,1,36,-71,-11),
(E'resource-native-1699-1137-82001',1,2,36,-70,-33),
(E'resource-native-1699-1137-82001',1,3,36,-69,-31),
(E'resource-native-1699-1137-82001',1,4,36,-68,-27),
(E'resource-native-1699-1137-82001',1,5,36,-67,-24),
(E'resource-native-1699-1137-82001',1,6,36,-65,-50),
(E'resource-native-1699-1137-82001',1,7,36,-64,-50),
(E'resource-native-1699-1137-82001',1,8,36,-63,-50),
(E'resource-native-1699-1137-82001',1,9,36,-62,-50),
(E'resource-native-1699-1137-82001',1,10,36,-61,-24),
(E'resource-native-1699-1137-82001',1,11,36,-60,-24),
(E'resource-native-1699-1137-82001',1,12,36,-59,-24),
(E'resource-native-1699-1137-82001',1,13,36,-58,-50),
(E'resource-native-1699-1137-82001',1,14,36,-57,-50),
(E'resource-native-1699-1137-82001',1,15,36,-56,-50),
(E'resource-native-1699-1137-82001',1,16,36,-55,-50),
(E'resource-native-1699-1137-82001',1,17,36,-53,-50),
(E'resource-native-1699-1137-82001',1,18,36,-52,-50),
(E'resource-native-1699-1137-82001',1,19,36,-51,-50),
(E'resource-native-1699-1137-82001',1,20,36,-50,-50),
(E'resource-native-1699-1137-82001',1,21,36,-49,-24),
(E'resource-native-1699-1137-82001',1,22,36,-48,-24),
(E'resource-native-1699-1137-82001',1,23,36,-47,-24),
(E'resource-native-1699-1137-82001',1,24,36,-45,-50),
(E'resource-native-1699-1137-82001',1,25,36,-44,-50),
(E'resource-native-1699-1137-82001',1,26,36,-43,-50),
(E'resource-native-1699-1137-82001',1,27,36,-40,-50),
(E'resource-native-1699-1137-82001',1,28,36,-39,-50),
(E'resource-native-1699-1137-82001',1,29,36,-38,-50),
(E'resource-native-1699-1137-82001',1,30,36,-37,-78),
(E'resource-native-1699-1137-82001',1,31,36,-35,-78),
(E'resource-native-1699-1137-82001',1,32,36,-34,-78),
(E'resource-native-1699-1137-82001',1,33,36,-33,-78),
(E'resource-native-1699-1137-82001',1,34,36,-32,-78),
(E'resource-native-1699-1137-82001',1,35,36,-31,-78),
(E'resource-native-1699-1137-82001',1,36,36,-30,-78),
(E'resource-native-1699-1137-82001',1,37,36,-29,-78);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1695-1210-86901',1,-1695,0,366,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1695-1210-86901',1,E'proposed',0),
(E'resource-native-1695-1210-86901',1,E'active',1),
(E'resource-native-1695-1210-86901',1,E'completed',2),
(E'resource-native-1695-1210-86901',1,E'expired',2),
(E'resource-native-1695-1210-86901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',-1695,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1695-1210-86901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1695-1210-86901',1,0,-73,-36,46),
(E'resource-native-1695-1210-86901',1,1,-70,-50,20),
(E'resource-native-1695-1210-86901',1,2,-70,-49,20),
(E'resource-native-1695-1210-86901',1,3,-70,-48,20),
(E'resource-native-1695-1210-86901',1,4,-70,-47,24),
(E'resource-native-1695-1210-86901',1,5,-70,-46,24),
(E'resource-native-1695-1210-86901',1,6,-69,-51,24),
(E'resource-native-1695-1210-86901',1,7,-69,-50,24),
(E'resource-native-1695-1210-86901',1,8,-69,-45,20),
(E'resource-native-1695-1210-86901',1,9,-69,-44,20),
(E'resource-native-1695-1210-86901',1,10,-69,-43,23),
(E'resource-native-1695-1210-86901',1,11,-69,-42,22),
(E'resource-native-1695-1210-86901',1,12,-68,-74,23),
(E'resource-native-1695-1210-86901',1,13,-68,-73,20),
(E'resource-native-1695-1210-86901',1,14,-68,-72,20),
(E'resource-native-1695-1210-86901',1,15,-68,-71,23),
(E'resource-native-1695-1210-86901',1,16,-68,-70,24),
(E'resource-native-1695-1210-86901',1,17,-68,-64,20),
(E'resource-native-1695-1210-86901',1,18,-68,-63,20),
(E'resource-native-1695-1210-86901',1,19,-68,-53,20),
(E'resource-native-1695-1210-86901',1,20,-68,-51,20),
(E'resource-native-1695-1210-86901',1,21,-68,-50,21),
(E'resource-native-1695-1210-86901',1,22,-68,-49,23),
(E'resource-native-1695-1210-86901',1,23,-68,-48,20),
(E'resource-native-1695-1210-86901',1,24,-68,-47,24),
(E'resource-native-1695-1210-86901',1,25,-68,-45,20),
(E'resource-native-1695-1210-86901',1,26,-68,-44,20),
(E'resource-native-1695-1210-86901',1,27,-68,-43,20),
(E'resource-native-1695-1210-86901',1,28,-68,-42,20),
(E'resource-native-1695-1210-86901',1,29,-67,-88,20),
(E'resource-native-1695-1210-86901',1,30,-67,-87,23),
(E'resource-native-1695-1210-86901',1,31,-67,-86,20),
(E'resource-native-1695-1210-86901',1,32,-67,-83,20),
(E'resource-native-1695-1210-86901',1,33,-67,-82,20),
(E'resource-native-1695-1210-86901',1,34,-67,-81,20),
(E'resource-native-1695-1210-86901',1,35,-67,-80,20),
(E'resource-native-1695-1210-86901',1,36,-67,-79,21),
(E'resource-native-1695-1210-86901',1,37,-67,-78,20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1692-1209-83901',1,-1692,0,368,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1692-1209-83901',1,E'proposed',0),
(E'resource-native-1692-1209-83901',1,E'active',1),
(E'resource-native-1692-1209-83901',1,E'completed',2),
(E'resource-native-1692-1209-83901',1,E'expired',2),
(E'resource-native-1692-1209-83901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',-1692,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1692-1209-83901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1692-1209-83901',1,0,-36,-162,100),
(E'resource-native-1692-1209-83901',1,1,-34,-149,43),
(E'resource-native-1692-1209-83901',1,2,-34,-144,43),
(E'resource-native-1692-1209-83901',1,3,-34,-142,40),
(E'resource-native-1692-1209-83901',1,4,-34,-141,40),
(E'resource-native-1692-1209-83901',1,5,-34,-140,41),
(E'resource-native-1692-1209-83901',1,6,-34,-139,40),
(E'resource-native-1692-1209-83901',1,7,-34,-137,40),
(E'resource-native-1692-1209-83901',1,8,-33,-156,43),
(E'resource-native-1692-1209-83901',1,9,-33,-155,40),
(E'resource-native-1692-1209-83901',1,10,-33,-151,40),
(E'resource-native-1692-1209-83901',1,11,-33,-149,40),
(E'resource-native-1692-1209-83901',1,12,-33,-148,40),
(E'resource-native-1692-1209-83901',1,13,-33,-146,40),
(E'resource-native-1692-1209-83901',1,14,-33,-145,40),
(E'resource-native-1692-1209-83901',1,15,-33,-144,40),
(E'resource-native-1692-1209-83901',1,16,-33,-143,42),
(E'resource-native-1692-1209-83901',1,17,-33,-142,40),
(E'resource-native-1692-1209-83901',1,18,-33,-141,40),
(E'resource-native-1692-1209-83901',1,19,-33,-140,41),
(E'resource-native-1692-1209-83901',1,20,-33,-139,40),
(E'resource-native-1692-1209-83901',1,21,-33,-138,40),
(E'resource-native-1692-1209-83901',1,22,-33,-137,40),
(E'resource-native-1692-1209-83901',1,23,-32,-156,40),
(E'resource-native-1692-1209-83901',1,24,-32,-155,40),
(E'resource-native-1692-1209-83901',1,25,-32,-153,40),
(E'resource-native-1692-1209-83901',1,26,-32,-152,40),
(E'resource-native-1692-1209-83901',1,27,-32,-151,40),
(E'resource-native-1692-1209-83901',1,28,-32,-150,40),
(E'resource-native-1692-1209-83901',1,29,-32,-149,40),
(E'resource-native-1692-1209-83901',1,30,-32,-148,40),
(E'resource-native-1692-1209-83901',1,31,-32,-147,40),
(E'resource-native-1692-1209-83901',1,32,-32,-146,40),
(E'resource-native-1692-1209-83901',1,33,-32,-145,40),
(E'resource-native-1692-1209-83901',1,34,-32,-144,40),
(E'resource-native-1692-1209-83901',1,35,-32,-143,40),
(E'resource-native-1692-1209-83901',1,36,-32,-142,40),
(E'resource-native-1692-1209-83901',1,37,-32,-141,40);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1688-1208-86801',1,-1688,0,364,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1688-1208-86801',1,E'proposed',0),
(E'resource-native-1688-1208-86801',1,E'active',1),
(E'resource-native-1688-1208-86801',1,E'completed',2),
(E'resource-native-1688-1208-86801',1,E'expired',2),
(E'resource-native-1688-1208-86801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',-1688,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1688-1208-86801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1688-1208-86801',1,0,-126,0,100),
(E'resource-native-1688-1208-86801',1,1,-124,16,2),
(E'resource-native-1688-1208-86801',1,2,-124,17,0),
(E'resource-native-1688-1208-86801',1,3,-124,18,0),
(E'resource-native-1688-1208-86801',1,4,-124,19,1),
(E'resource-native-1688-1208-86801',1,5,-124,20,0),
(E'resource-native-1688-1208-86801',1,6,-123,7,0),
(E'resource-native-1688-1208-86801',1,7,-123,10,0),
(E'resource-native-1688-1208-86801',1,8,-123,11,2),
(E'resource-native-1688-1208-86801',1,9,-123,12,0),
(E'resource-native-1688-1208-86801',1,10,-123,16,1),
(E'resource-native-1688-1208-86801',1,11,-123,17,0),
(E'resource-native-1688-1208-86801',1,12,-123,18,0),
(E'resource-native-1688-1208-86801',1,13,-123,19,1),
(E'resource-native-1688-1208-86801',1,14,-123,20,0),
(E'resource-native-1688-1208-86801',1,15,-123,21,0),
(E'resource-native-1688-1208-86801',1,16,-123,22,0),
(E'resource-native-1688-1208-86801',1,17,-123,23,2),
(E'resource-native-1688-1208-86801',1,18,-123,27,0),
(E'resource-native-1688-1208-86801',1,19,-123,28,3),
(E'resource-native-1688-1208-86801',1,20,-123,29,0),
(E'resource-native-1688-1208-86801',1,21,-123,30,0),
(E'resource-native-1688-1208-86801',1,22,-123,32,3),
(E'resource-native-1688-1208-86801',1,23,-122,4,3),
(E'resource-native-1688-1208-86801',1,24,-122,5,0),
(E'resource-native-1688-1208-86801',1,25,-122,6,3),
(E'resource-native-1688-1208-86801',1,26,-122,7,0),
(E'resource-native-1688-1208-86801',1,27,-122,8,0),
(E'resource-native-1688-1208-86801',1,28,-122,9,0),
(E'resource-native-1688-1208-86801',1,29,-122,10,0),
(E'resource-native-1688-1208-86801',1,30,-122,11,0),
(E'resource-native-1688-1208-86801',1,31,-122,12,0),
(E'resource-native-1688-1208-86801',1,32,-122,14,0),
(E'resource-native-1688-1208-86801',1,33,-122,15,0),
(E'resource-native-1688-1208-86801',1,34,-122,16,0),
(E'resource-native-1688-1208-86801',1,35,-122,17,0),
(E'resource-native-1688-1208-86801',1,36,-122,18,0),
(E'resource-native-1688-1208-86801',1,37,-122,19,1);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1683-1135-80901',1,-1683,0,349,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1683-1135-80901',1,E'proposed',0),
(E'resource-native-1683-1135-80901',1,E'active',1),
(E'resource-native-1683-1135-80901',1,E'completed',2),
(E'resource-native-1683-1135-80901',1,E'expired',2),
(E'resource-native-1683-1135-80901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',51,NULL,NULL),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',-1683,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1683-1135-80901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1683-1135-80901',1,0,18,-92,-30),
(E'resource-native-1683-1135-80901',1,1,18,-91,-29),
(E'resource-native-1683-1135-80901',1,2,18,-90,-29),
(E'resource-native-1683-1135-80901',1,3,18,-89,-29),
(E'resource-native-1683-1135-80901',1,4,18,-83,-44),
(E'resource-native-1683-1135-80901',1,5,18,-82,-44),
(E'resource-native-1683-1135-80901',1,6,18,-76,-44),
(E'resource-native-1683-1135-80901',1,7,18,-75,-44),
(E'resource-native-1683-1135-80901',1,8,18,-74,-44),
(E'resource-native-1683-1135-80901',1,9,18,-73,-44),
(E'resource-native-1683-1135-80901',1,10,19,-92,-30),
(E'resource-native-1683-1135-80901',1,11,19,-91,-30),
(E'resource-native-1683-1135-80901',1,12,19,-90,-30),
(E'resource-native-1683-1135-80901',1,13,19,-89,-30),
(E'resource-native-1683-1135-80901',1,14,19,-88,-32),
(E'resource-native-1683-1135-80901',1,15,19,-87,-35),
(E'resource-native-1683-1135-80901',1,16,19,-86,-39),
(E'resource-native-1683-1135-80901',1,17,19,-85,-43),
(E'resource-native-1683-1135-80901',1,18,19,-84,-44),
(E'resource-native-1683-1135-80901',1,19,19,-83,-44),
(E'resource-native-1683-1135-80901',1,20,19,-82,-44),
(E'resource-native-1683-1135-80901',1,21,19,-81,-44),
(E'resource-native-1683-1135-80901',1,22,19,-80,-44),
(E'resource-native-1683-1135-80901',1,23,19,-79,-44),
(E'resource-native-1683-1135-80901',1,24,19,-78,-44),
(E'resource-native-1683-1135-80901',1,25,19,-77,-44),
(E'resource-native-1683-1135-80901',1,26,19,-76,-44),
(E'resource-native-1683-1135-80901',1,27,19,-75,-44),
(E'resource-native-1683-1135-80901',1,28,19,-74,-44),
(E'resource-native-1683-1135-80901',1,29,19,-73,-44),
(E'resource-native-1683-1135-80901',1,30,20,-107,-41),
(E'resource-native-1683-1135-80901',1,31,20,-93,-30),
(E'resource-native-1683-1135-80901',1,32,20,-92,-30),
(E'resource-native-1683-1135-80901',1,33,20,-91,-30),
(E'resource-native-1683-1135-80901',1,34,20,-90,-30),
(E'resource-native-1683-1135-80901',1,35,20,-89,-30),
(E'resource-native-1683-1135-80901',1,36,20,-88,-30),
(E'resource-native-1683-1135-80901',1,37,20,-87,-30);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1680-1208-84101',1,-1680,0,363,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1680-1208-84101',1,E'proposed',0),
(E'resource-native-1680-1208-84101',1,E'active',1),
(E'resource-native-1680-1208-84101',1,E'completed',2),
(E'resource-native-1680-1208-84101',1,E'expired',2),
(E'resource-native-1680-1208-84101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',111,NULL,NULL),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',-1680,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1680-1208-84101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1680-1208-84101',1,0,-58,30,-1),
(E'resource-native-1680-1208-84101',1,1,-58,31,0),
(E'resource-native-1680-1208-84101',1,2,-58,32,3),
(E'resource-native-1680-1208-84101',1,3,-58,33,0),
(E'resource-native-1680-1208-84101',1,4,-58,34,-1),
(E'resource-native-1680-1208-84101',1,5,-58,35,-1),
(E'resource-native-1680-1208-84101',1,6,-58,36,0),
(E'resource-native-1680-1208-84101',1,7,-57,30,0),
(E'resource-native-1680-1208-84101',1,8,-57,31,0),
(E'resource-native-1680-1208-84101',1,9,-57,32,0),
(E'resource-native-1680-1208-84101',1,10,-57,33,0),
(E'resource-native-1680-1208-84101',1,11,-57,34,0),
(E'resource-native-1680-1208-84101',1,12,-57,35,0),
(E'resource-native-1680-1208-84101',1,13,-57,36,0),
(E'resource-native-1680-1208-84101',1,14,-56,30,3),
(E'resource-native-1680-1208-84101',1,15,-56,31,0),
(E'resource-native-1680-1208-84101',1,16,-56,32,0),
(E'resource-native-1680-1208-84101',1,17,-56,33,0),
(E'resource-native-1680-1208-84101',1,18,-56,34,0),
(E'resource-native-1680-1208-84101',1,19,-56,35,0),
(E'resource-native-1680-1208-84101',1,20,-56,36,0),
(E'resource-native-1680-1208-84101',1,21,-55,30,0),
(E'resource-native-1680-1208-84101',1,22,-55,31,0),
(E'resource-native-1680-1208-84101',1,23,-55,32,0),
(E'resource-native-1680-1208-84101',1,24,-55,33,0),
(E'resource-native-1680-1208-84101',1,25,-55,34,0),
(E'resource-native-1680-1208-84101',1,26,-55,35,0),
(E'resource-native-1680-1208-84101',1,27,-55,36,0),
(E'resource-native-1680-1208-84101',1,28,-54,2,1),
(E'resource-native-1680-1208-84101',1,29,-54,3,1),
(E'resource-native-1680-1208-84101',1,30,-54,4,1),
(E'resource-native-1680-1208-84101',1,31,-54,5,1),
(E'resource-native-1680-1208-84101',1,32,-54,6,1),
(E'resource-native-1680-1208-84101',1,33,-54,7,1),
(E'resource-native-1680-1208-84101',1,34,-54,9,0),
(E'resource-native-1680-1208-84101',1,35,-54,10,0),
(E'resource-native-1680-1208-84101',1,36,-54,11,0),
(E'resource-native-1680-1208-84101',1,37,-54,12,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1676-1135-80801',1,-1676,0,348,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1676-1135-80801',1,E'proposed',0),
(E'resource-native-1676-1135-80801',1,E'active',1),
(E'resource-native-1676-1135-80801',1,E'completed',2),
(E'resource-native-1676-1135-80801',1,E'expired',2),
(E'resource-native-1676-1135-80801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',111,NULL,NULL),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',-1676,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1676-1135-80801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1676-1135-80801',1,0,-108,-41,92),
(E'resource-native-1676-1135-80801',1,1,-108,-40,90),
(E'resource-native-1676-1135-80801',1,2,-108,-39,90),
(E'resource-native-1676-1135-80801',1,3,-108,-38,90),
(E'resource-native-1676-1135-80801',1,4,-108,-37,90),
(E'resource-native-1676-1135-80801',1,5,-108,-36,90),
(E'resource-native-1676-1135-80801',1,6,-108,-35,92),
(E'resource-native-1676-1135-80801',1,7,-108,-34,92),
(E'resource-native-1676-1135-80801',1,8,-107,-73,90),
(E'resource-native-1676-1135-80801',1,9,-107,-59,90),
(E'resource-native-1676-1135-80801',1,10,-107,-58,88),
(E'resource-native-1676-1135-80801',1,11,-107,-41,90),
(E'resource-native-1676-1135-80801',1,12,-107,-40,90),
(E'resource-native-1676-1135-80801',1,13,-107,-39,90),
(E'resource-native-1676-1135-80801',1,14,-107,-38,90),
(E'resource-native-1676-1135-80801',1,15,-107,-34,96),
(E'resource-native-1676-1135-80801',1,16,-106,-73,90),
(E'resource-native-1676-1135-80801',1,17,-106,-72,90),
(E'resource-native-1676-1135-80801',1,18,-106,-71,90),
(E'resource-native-1676-1135-80801',1,19,-106,-70,90),
(E'resource-native-1676-1135-80801',1,20,-106,-60,90),
(E'resource-native-1676-1135-80801',1,21,-106,-59,90),
(E'resource-native-1676-1135-80801',1,22,-106,-58,90),
(E'resource-native-1676-1135-80801',1,23,-106,-40,90),
(E'resource-native-1676-1135-80801',1,24,-106,-39,90),
(E'resource-native-1676-1135-80801',1,25,-106,-38,92),
(E'resource-native-1676-1135-80801',1,26,-106,-37,96),
(E'resource-native-1676-1135-80801',1,27,-106,-34,96),
(E'resource-native-1676-1135-80801',1,28,-106,-33,92),
(E'resource-native-1676-1135-80801',1,29,-106,-31,86),
(E'resource-native-1676-1135-80801',1,30,-106,-27,60),
(E'resource-native-1676-1135-80801',1,31,-106,-26,62),
(E'resource-native-1676-1135-80801',1,32,-105,-77,90),
(E'resource-native-1676-1135-80801',1,33,-105,-76,90),
(E'resource-native-1676-1135-80801',1,34,-105,-75,90),
(E'resource-native-1676-1135-80801',1,35,-105,-74,90),
(E'resource-native-1676-1135-80801',1,36,-105,-73,90),
(E'resource-native-1676-1135-80801',1,37,-105,-72,90);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1639-1207-86601',1,-1639,0,347,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1639-1207-86601',1,E'proposed',0),
(E'resource-native-1639-1207-86601',1,E'active',1),
(E'resource-native-1639-1207-86601',1,E'completed',2),
(E'resource-native-1639-1207-86601',1,E'expired',2),
(E'resource-native-1639-1207-86601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',-1639,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1639-1207-86601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1639-1207-86601',1,0,-126,-90,100),
(E'resource-native-1639-1207-86601',1,1,-124,-84,40),
(E'resource-native-1639-1207-86601',1,2,-124,-83,40),
(E'resource-native-1639-1207-86601',1,3,-124,-82,41),
(E'resource-native-1639-1207-86601',1,4,-124,-81,40),
(E'resource-native-1639-1207-86601',1,5,-124,-80,40),
(E'resource-native-1639-1207-86601',1,6,-124,-79,40),
(E'resource-native-1639-1207-86601',1,7,-123,-85,42),
(E'resource-native-1639-1207-86601',1,8,-123,-83,40),
(E'resource-native-1639-1207-86601',1,9,-123,-82,41),
(E'resource-native-1639-1207-86601',1,10,-123,-81,40),
(E'resource-native-1639-1207-86601',1,11,-123,-80,40),
(E'resource-native-1639-1207-86601',1,12,-123,-79,40),
(E'resource-native-1639-1207-86601',1,13,-122,-85,42),
(E'resource-native-1639-1207-86601',1,14,-122,-84,40),
(E'resource-native-1639-1207-86601',1,15,-122,-83,40),
(E'resource-native-1639-1207-86601',1,16,-122,-82,41),
(E'resource-native-1639-1207-86601',1,17,-122,-81,40),
(E'resource-native-1639-1207-86601',1,18,-122,-80,40),
(E'resource-native-1639-1207-86601',1,19,-122,-79,40),
(E'resource-native-1639-1207-86601',1,20,-122,-78,44),
(E'resource-native-1639-1207-86601',1,21,-122,-69,43),
(E'resource-native-1639-1207-86601',1,22,-121,-85,40),
(E'resource-native-1639-1207-86601',1,23,-121,-84,43),
(E'resource-native-1639-1207-86601',1,24,-121,-83,40),
(E'resource-native-1639-1207-86601',1,25,-121,-82,41),
(E'resource-native-1639-1207-86601',1,26,-121,-81,40),
(E'resource-native-1639-1207-86601',1,27,-121,-80,40),
(E'resource-native-1639-1207-86601',1,28,-121,-79,40),
(E'resource-native-1639-1207-86601',1,29,-121,-78,40),
(E'resource-native-1639-1207-86601',1,30,-121,-77,43),
(E'resource-native-1639-1207-86601',1,31,-121,-76,42),
(E'resource-native-1639-1207-86601',1,32,-121,-74,40),
(E'resource-native-1639-1207-86601',1,33,-121,-71,40),
(E'resource-native-1639-1207-86601',1,34,-121,-70,40),
(E'resource-native-1639-1207-86601',1,35,-121,-69,40),
(E'resource-native-1639-1207-86601',1,36,-121,-68,42),
(E'resource-native-1639-1207-86601',1,37,-121,-65,43);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1631-1207-83801',1,-1631,0,346,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1631-1207-83801',1,E'proposed',0),
(E'resource-native-1631-1207-83801',1,E'active',1),
(E'resource-native-1631-1207-83801',1,E'completed',2),
(E'resource-native-1631-1207-83801',1,E'expired',2),
(E'resource-native-1631-1207-83801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',36,NULL,NULL),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',-1631,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1631-1207-83801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1631-1207-83801',1,0,-117,-25,0),
(E'resource-native-1631-1207-83801',1,1,-116,-30,0),
(E'resource-native-1631-1207-83801',1,2,-116,-29,0),
(E'resource-native-1631-1207-83801',1,3,-116,-28,1),
(E'resource-native-1631-1207-83801',1,4,-116,-26,0),
(E'resource-native-1631-1207-83801',1,5,-116,-25,0),
(E'resource-native-1631-1207-83801',1,6,-115,-31,0),
(E'resource-native-1631-1207-83801',1,7,-115,-30,0),
(E'resource-native-1631-1207-83801',1,8,-115,-28,1),
(E'resource-native-1631-1207-83801',1,9,-115,-27,0),
(E'resource-native-1631-1207-83801',1,10,-115,-26,0),
(E'resource-native-1631-1207-83801',1,11,-115,-25,0),
(E'resource-native-1631-1207-83801',1,12,-114,-31,4),
(E'resource-native-1631-1207-83801',1,13,-114,-30,0),
(E'resource-native-1631-1207-83801',1,14,-114,-29,0),
(E'resource-native-1631-1207-83801',1,15,-114,-28,1),
(E'resource-native-1631-1207-83801',1,16,-114,-27,0),
(E'resource-native-1631-1207-83801',1,17,-114,-26,0),
(E'resource-native-1631-1207-83801',1,18,-114,-25,0),
(E'resource-native-1631-1207-83801',1,19,-113,-29,0),
(E'resource-native-1631-1207-83801',1,20,-113,-28,1),
(E'resource-native-1631-1207-83801',1,21,-113,-27,0),
(E'resource-native-1631-1207-83801',1,22,-113,-26,0),
(E'resource-native-1631-1207-83801',1,23,-113,-25,0),
(E'resource-native-1631-1207-83801',1,24,-112,-30,2),
(E'resource-native-1631-1207-83801',1,25,-112,-29,0),
(E'resource-native-1631-1207-83801',1,26,-112,-28,1),
(E'resource-native-1631-1207-83801',1,27,-112,-27,0),
(E'resource-native-1631-1207-83801',1,28,-112,-26,0),
(E'resource-native-1631-1207-83801',1,29,-112,-25,0),
(E'resource-native-1631-1207-83801',1,30,-112,-24,6),
(E'resource-native-1631-1207-83801',1,31,-112,-23,0),
(E'resource-native-1631-1207-83801',1,32,-111,-30,2),
(E'resource-native-1631-1207-83801',1,33,-111,-29,0),
(E'resource-native-1631-1207-83801',1,34,-111,-27,0),
(E'resource-native-1631-1207-83801',1,35,-111,-26,0),
(E'resource-native-1631-1207-83801',1,36,-111,-25,0),
(E'resource-native-1631-1207-83801',1,37,-111,-24,7);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1627-1134-79201',1,-1627,0,345,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1627-1134-79201',1,E'proposed',0),
(E'resource-native-1627-1134-79201',1,E'active',1),
(E'resource-native-1627-1134-79201',1,E'completed',2),
(E'resource-native-1627-1134-79201',1,E'expired',2),
(E'resource-native-1627-1134-79201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',36,NULL,NULL),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',-1627,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1627-1134-79201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1627-1134-79201',1,0,-56,-111,62),
(E'resource-native-1627-1134-79201',1,1,-56,-110,58),
(E'resource-native-1627-1134-79201',1,2,-56,-106,50),
(E'resource-native-1627-1134-79201',1,3,-55,-111,62),
(E'resource-native-1627-1134-79201',1,4,-55,-110,58),
(E'resource-native-1627-1134-79201',1,5,-55,-106,50),
(E'resource-native-1627-1134-79201',1,6,-53,-98,54),
(E'resource-native-1627-1134-79201',1,7,-53,-97,50),
(E'resource-native-1627-1134-79201',1,8,-53,-96,48),
(E'resource-native-1627-1134-79201',1,9,-53,-81,54),
(E'resource-native-1627-1134-79201',1,10,-53,-78,50),
(E'resource-native-1627-1134-79201',1,11,-53,-77,50),
(E'resource-native-1627-1134-79201',1,12,-52,-98,52),
(E'resource-native-1627-1134-79201',1,13,-52,-97,50),
(E'resource-native-1627-1134-79201',1,14,-52,-96,50),
(E'resource-native-1627-1134-79201',1,15,-52,-92,50),
(E'resource-native-1627-1134-79201',1,16,-52,-91,52),
(E'resource-native-1627-1134-79201',1,17,-52,-90,50),
(E'resource-native-1627-1134-79201',1,18,-52,-89,48),
(E'resource-native-1627-1134-79201',1,19,-52,-85,50),
(E'resource-native-1627-1134-79201',1,20,-52,-84,52),
(E'resource-native-1627-1134-79201',1,21,-52,-83,50),
(E'resource-native-1627-1134-79201',1,22,-52,-82,50),
(E'resource-native-1627-1134-79201',1,23,-52,-81,50),
(E'resource-native-1627-1134-79201',1,24,-52,-80,50),
(E'resource-native-1627-1134-79201',1,25,-52,-79,50),
(E'resource-native-1627-1134-79201',1,26,-52,-78,50),
(E'resource-native-1627-1134-79201',1,27,-52,-77,50),
(E'resource-native-1627-1134-79201',1,28,-51,-99,50),
(E'resource-native-1627-1134-79201',1,29,-51,-98,50),
(E'resource-native-1627-1134-79201',1,30,-51,-97,50),
(E'resource-native-1627-1134-79201',1,31,-51,-96,50),
(E'resource-native-1627-1134-79201',1,32,-51,-95,50),
(E'resource-native-1627-1134-79201',1,33,-51,-94,50),
(E'resource-native-1627-1134-79201',1,34,-51,-93,50),
(E'resource-native-1627-1134-79201',1,35,-51,-92,50),
(E'resource-native-1627-1134-79201',1,36,-51,-91,50),
(E'resource-native-1627-1134-79201',1,37,-51,-90,50);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1625-1137-81901',1,-1625,0,356,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1625-1137-81901',1,E'proposed',0),
(E'resource-native-1625-1137-81901',1,E'active',1),
(E'resource-native-1625-1137-81901',1,E'completed',2),
(E'resource-native-1625-1137-81901',1,E'expired',2),
(E'resource-native-1625-1137-81901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',-1625,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1625-1137-81901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1625-1137-81901',1,0,18,-133,30),
(E'resource-native-1625-1137-81901',1,1,18,-132,30),
(E'resource-native-1625-1137-81901',1,2,18,-131,30),
(E'resource-native-1625-1137-81901',1,3,18,-130,30),
(E'resource-native-1625-1137-81901',1,4,18,-129,30),
(E'resource-native-1625-1137-81901',1,5,18,-128,30),
(E'resource-native-1625-1137-81901',1,6,18,-127,30),
(E'resource-native-1625-1137-81901',1,7,18,-126,30),
(E'resource-native-1625-1137-81901',1,8,18,-125,30),
(E'resource-native-1625-1137-81901',1,9,18,-124,30),
(E'resource-native-1625-1137-81901',1,10,18,-123,30),
(E'resource-native-1625-1137-81901',1,11,18,-121,30),
(E'resource-native-1625-1137-81901',1,12,18,-120,30),
(E'resource-native-1625-1137-81901',1,13,18,-119,30),
(E'resource-native-1625-1137-81901',1,14,18,-118,30),
(E'resource-native-1625-1137-81901',1,15,18,-117,30),
(E'resource-native-1625-1137-81901',1,16,18,-116,30),
(E'resource-native-1625-1137-81901',1,17,18,-115,30),
(E'resource-native-1625-1137-81901',1,18,18,-114,30),
(E'resource-native-1625-1137-81901',1,19,18,-113,30),
(E'resource-native-1625-1137-81901',1,20,18,-112,30),
(E'resource-native-1625-1137-81901',1,21,18,-111,30),
(E'resource-native-1625-1137-81901',1,22,18,-110,27),
(E'resource-native-1625-1137-81901',1,23,18,-109,23),
(E'resource-native-1625-1137-81901',1,24,19,-135,30),
(E'resource-native-1625-1137-81901',1,25,19,-134,30),
(E'resource-native-1625-1137-81901',1,26,19,-133,30),
(E'resource-native-1625-1137-81901',1,27,19,-132,30),
(E'resource-native-1625-1137-81901',1,28,19,-131,30),
(E'resource-native-1625-1137-81901',1,29,19,-130,30),
(E'resource-native-1625-1137-81901',1,30,19,-129,30),
(E'resource-native-1625-1137-81901',1,31,19,-127,30),
(E'resource-native-1625-1137-81901',1,32,19,-126,30),
(E'resource-native-1625-1137-81901',1,33,19,-125,30),
(E'resource-native-1625-1137-81901',1,34,19,-124,30),
(E'resource-native-1625-1137-81901',1,35,19,-123,30),
(E'resource-native-1625-1137-81901',1,36,19,-122,30),
(E'resource-native-1625-1137-81901',1,37,19,-121,30);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1586-1053-73701',1,-1586,0,290,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1586-1053-73701',1,E'proposed',0),
(E'resource-native-1586-1053-73701',1,E'active',1),
(E'resource-native-1586-1053-73701',1,E'completed',2),
(E'resource-native-1586-1053-73701',1,E'expired',2),
(E'resource-native-1586-1053-73701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',171,NULL,NULL),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',-1586,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1586-1053-73701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1586-1053-73701',1,0,-43,-8,-10),
(E'resource-native-1586-1053-73701',1,1,-43,-3,-7),
(E'resource-native-1586-1053-73701',1,2,-43,-2,-10),
(E'resource-native-1586-1053-73701',1,3,-42,-10,-10),
(E'resource-native-1586-1053-73701',1,4,-42,-9,-10),
(E'resource-native-1586-1053-73701',1,5,-42,-8,-10),
(E'resource-native-1586-1053-73701',1,6,-42,-6,-7),
(E'resource-native-1586-1053-73701',1,7,-42,-5,-7),
(E'resource-native-1586-1053-73701',1,8,-42,-4,-7),
(E'resource-native-1586-1053-73701',1,9,-42,-3,-7),
(E'resource-native-1586-1053-73701',1,10,-42,-2,-10),
(E'resource-native-1586-1053-73701',1,11,-42,-1,-10),
(E'resource-native-1586-1053-73701',1,12,-42,0,-10),
(E'resource-native-1586-1053-73701',1,13,-42,1,-10),
(E'resource-native-1586-1053-73701',1,14,-42,2,-10),
(E'resource-native-1586-1053-73701',1,15,-42,3,-10),
(E'resource-native-1586-1053-73701',1,16,-42,4,-10),
(E'resource-native-1586-1053-73701',1,17,-42,5,-10),
(E'resource-native-1586-1053-73701',1,18,-41,-10,-10),
(E'resource-native-1586-1053-73701',1,19,-41,-9,-10),
(E'resource-native-1586-1053-73701',1,20,-41,-8,-10),
(E'resource-native-1586-1053-73701',1,21,-41,-6,-7),
(E'resource-native-1586-1053-73701',1,22,-41,-5,-7),
(E'resource-native-1586-1053-73701',1,23,-41,-4,-7),
(E'resource-native-1586-1053-73701',1,24,-41,-3,-7),
(E'resource-native-1586-1053-73701',1,25,-41,-2,-9),
(E'resource-native-1586-1053-73701',1,26,-41,-1,-10),
(E'resource-native-1586-1053-73701',1,27,-41,0,-10),
(E'resource-native-1586-1053-73701',1,28,-41,1,-10),
(E'resource-native-1586-1053-73701',1,29,-41,2,-10),
(E'resource-native-1586-1053-73701',1,30,-41,3,-10),
(E'resource-native-1586-1053-73701',1,31,-41,4,-10),
(E'resource-native-1586-1053-73701',1,32,-41,5,-10),
(E'resource-native-1586-1053-73701',1,33,-40,-9,-9),
(E'resource-native-1586-1053-73701',1,34,-40,-8,-9),
(E'resource-native-1586-1053-73701',1,35,-40,-6,-7),
(E'resource-native-1586-1053-73701',1,36,-40,-5,-7),
(E'resource-native-1586-1053-73701',1,37,-40,-4,-7);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1586-1264-89701',1,-1586,0,385,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1586-1264-89701',1,E'proposed',0),
(E'resource-native-1586-1264-89701',1,E'active',1),
(E'resource-native-1586-1264-89701',1,E'completed',2),
(E'resource-native-1586-1264-89701',1,E'expired',2),
(E'resource-native-1586-1264-89701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',171,NULL,NULL),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',-1586,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1586-1264-89701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1586-1264-89701',1,0,75,165,-20),
(E'resource-native-1586-1264-89701',1,1,75,166,-20),
(E'resource-native-1586-1264-89701',1,2,75,168,-20),
(E'resource-native-1586-1264-89701',1,3,75,169,-20),
(E'resource-native-1586-1264-89701',1,4,75,170,-20),
(E'resource-native-1586-1264-89701',1,5,75,171,-20),
(E'resource-native-1586-1264-89701',1,6,75,172,-20),
(E'resource-native-1586-1264-89701',1,7,76,163,-20),
(E'resource-native-1586-1264-89701',1,8,76,164,-20),
(E'resource-native-1586-1264-89701',1,9,76,165,-20),
(E'resource-native-1586-1264-89701',1,10,76,166,-20),
(E'resource-native-1586-1264-89701',1,11,76,167,-20),
(E'resource-native-1586-1264-89701',1,12,76,168,-20),
(E'resource-native-1586-1264-89701',1,13,76,169,-20),
(E'resource-native-1586-1264-89701',1,14,76,170,-20),
(E'resource-native-1586-1264-89701',1,15,76,171,-20),
(E'resource-native-1586-1264-89701',1,16,76,172,-20),
(E'resource-native-1586-1264-89701',1,17,77,163,-20),
(E'resource-native-1586-1264-89701',1,18,77,164,-20),
(E'resource-native-1586-1264-89701',1,19,77,165,-20),
(E'resource-native-1586-1264-89701',1,20,77,166,-20),
(E'resource-native-1586-1264-89701',1,21,77,167,-20),
(E'resource-native-1586-1264-89701',1,22,77,168,-20),
(E'resource-native-1586-1264-89701',1,23,77,169,-20),
(E'resource-native-1586-1264-89701',1,24,77,170,-20),
(E'resource-native-1586-1264-89701',1,25,77,171,-20),
(E'resource-native-1586-1264-89701',1,26,77,172,-20),
(E'resource-native-1586-1264-89701',1,27,77,173,-20),
(E'resource-native-1586-1264-89701',1,28,77,174,-20),
(E'resource-native-1586-1264-89701',1,29,77,175,-20),
(E'resource-native-1586-1264-89701',1,30,77,176,-20),
(E'resource-native-1586-1264-89701',1,31,78,162,-20),
(E'resource-native-1586-1264-89701',1,32,78,163,-20),
(E'resource-native-1586-1264-89701',1,33,78,164,-20),
(E'resource-native-1586-1264-89701',1,34,78,165,-20),
(E'resource-native-1586-1264-89701',1,35,78,166,-20),
(E'resource-native-1586-1264-89701',1,36,78,167,-20),
(E'resource-native-1586-1264-89701',1,37,78,168,-20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1582-999-71501',1,-1582,0,283,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1582-999-71501',1,E'proposed',0),
(E'resource-native-1582-999-71501',1,E'active',1),
(E'resource-native-1582-999-71501',1,E'completed',2),
(E'resource-native-1582-999-71501',1,E'expired',2),
(E'resource-native-1582-999-71501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',171,NULL,NULL),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',-1582,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1582-999-71501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1582-999-71501',1,0,-108,-127,-80),
(E'resource-native-1582-999-71501',1,1,-108,-126,-80),
(E'resource-native-1582-999-71501',1,2,-108,-95,-80),
(E'resource-native-1582-999-71501',1,3,-107,-127,-80),
(E'resource-native-1582-999-71501',1,4,-107,-126,-80),
(E'resource-native-1582-999-71501',1,5,-107,-98,-80),
(E'resource-native-1582-999-71501',1,6,-107,-97,-80),
(E'resource-native-1582-999-71501',1,7,-107,-95,-80),
(E'resource-native-1582-999-71501',1,8,-107,-93,-80),
(E'resource-native-1582-999-71501',1,9,-107,-92,-80),
(E'resource-native-1582-999-71501',1,10,-106,-127,-80),
(E'resource-native-1582-999-71501',1,11,-106,-126,-80),
(E'resource-native-1582-999-71501',1,12,-106,-124,-79),
(E'resource-native-1582-999-71501',1,13,-106,-123,-80),
(E'resource-native-1582-999-71501',1,14,-106,-115,-80),
(E'resource-native-1582-999-71501',1,15,-106,-114,-80),
(E'resource-native-1582-999-71501',1,16,-106,-113,-80),
(E'resource-native-1582-999-71501',1,17,-106,-112,-80),
(E'resource-native-1582-999-71501',1,18,-106,-111,-80),
(E'resource-native-1582-999-71501',1,19,-106,-98,-80),
(E'resource-native-1582-999-71501',1,20,-106,-97,-80),
(E'resource-native-1582-999-71501',1,21,-106,-96,-80),
(E'resource-native-1582-999-71501',1,22,-106,-95,-80),
(E'resource-native-1582-999-71501',1,23,-106,-94,-80),
(E'resource-native-1582-999-71501',1,24,-106,-93,-80),
(E'resource-native-1582-999-71501',1,25,-106,-92,-80),
(E'resource-native-1582-999-71501',1,26,-106,-89,-80),
(E'resource-native-1582-999-71501',1,27,-106,-88,-80),
(E'resource-native-1582-999-71501',1,28,-106,-87,-80),
(E'resource-native-1582-999-71501',1,29,-106,-86,-80),
(E'resource-native-1582-999-71501',1,30,-106,-85,-80),
(E'resource-native-1582-999-71501',1,31,-106,-84,-80),
(E'resource-native-1582-999-71501',1,32,-106,-83,-80),
(E'resource-native-1582-999-71501',1,33,-106,-82,-80),
(E'resource-native-1582-999-71501',1,34,-106,-81,-79),
(E'resource-native-1582-999-71501',1,35,-106,-80,-80),
(E'resource-native-1582-999-71501',1,36,-105,-127,-80),
(E'resource-native-1582-999-71501',1,37,-105,-126,-80);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1561-458-61501',1,-1561,0,204,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1561-458-61501',1,E'proposed',0),
(E'resource-native-1561-458-61501',1,E'active',1),
(E'resource-native-1561-458-61501',1,E'completed',2),
(E'resource-native-1561-458-61501',1,E'expired',2),
(E'resource-native-1561-458-61501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',-1561,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1561-458-61501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1561-458-61501',1,0,-74,5,3),
(E'resource-native-1561-458-61501',1,1,-73,5,3),
(E'resource-native-1561-458-61501',1,2,-72,0,0),
(E'resource-native-1561-458-61501',1,3,-72,5,3),
(E'resource-native-1561-458-61501',1,4,-71,-32,0),
(E'resource-native-1561-458-61501',1,5,-71,-31,0),
(E'resource-native-1561-458-61501',1,6,-71,-30,0),
(E'resource-native-1561-458-61501',1,7,-71,-29,0),
(E'resource-native-1561-458-61501',1,8,-71,-28,3),
(E'resource-native-1561-458-61501',1,9,-71,-27,1),
(E'resource-native-1561-458-61501',1,10,-71,-26,0),
(E'resource-native-1561-458-61501',1,11,-71,-25,0),
(E'resource-native-1561-458-61501',1,12,-71,-21,0),
(E'resource-native-1561-458-61501',1,13,-71,-20,0),
(E'resource-native-1561-458-61501',1,14,-71,-19,0),
(E'resource-native-1561-458-61501',1,15,-71,-11,0),
(E'resource-native-1561-458-61501',1,16,-71,-10,0),
(E'resource-native-1561-458-61501',1,17,-71,-9,0),
(E'resource-native-1561-458-61501',1,18,-71,-8,0),
(E'resource-native-1561-458-61501',1,19,-71,-7,1),
(E'resource-native-1561-458-61501',1,20,-71,-6,2),
(E'resource-native-1561-458-61501',1,21,-71,-5,0),
(E'resource-native-1561-458-61501',1,22,-71,-4,0),
(E'resource-native-1561-458-61501',1,23,-71,-3,0),
(E'resource-native-1561-458-61501',1,24,-71,0,0),
(E'resource-native-1561-458-61501',1,25,-71,5,3),
(E'resource-native-1561-458-61501',1,26,-71,7,0),
(E'resource-native-1561-458-61501',1,27,-71,8,0),
(E'resource-native-1561-458-61501',1,28,-71,9,0),
(E'resource-native-1561-458-61501',1,29,-71,10,1),
(E'resource-native-1561-458-61501',1,30,-70,-32,0),
(E'resource-native-1561-458-61501',1,31,-70,-31,0),
(E'resource-native-1561-458-61501',1,32,-70,-30,0),
(E'resource-native-1561-458-61501',1,33,-70,-29,0),
(E'resource-native-1561-458-61501',1,34,-70,-28,0),
(E'resource-native-1561-458-61501',1,35,-70,-27,0),
(E'resource-native-1561-458-61501',1,36,-70,-26,0),
(E'resource-native-1561-458-61501',1,37,-70,-25,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1544-323-56401',1,-1544,0,177,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1544-323-56401',1,E'proposed',0),
(E'resource-native-1544-323-56401',1,E'active',1),
(E'resource-native-1544-323-56401',1,E'completed',2),
(E'resource-native-1544-323-56401',1,E'expired',2),
(E'resource-native-1544-323-56401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',-1544,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1544-323-56401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1544-323-56401',1,0,-72,-62,0),
(E'resource-native-1544-323-56401',1,1,-72,-61,0),
(E'resource-native-1544-323-56401',1,2,-72,-60,0),
(E'resource-native-1544-323-56401',1,3,-72,-55,0),
(E'resource-native-1544-323-56401',1,4,-72,-54,0),
(E'resource-native-1544-323-56401',1,5,-72,-53,0),
(E'resource-native-1544-323-56401',1,6,-72,-52,-2),
(E'resource-native-1544-323-56401',1,7,-72,-44,0),
(E'resource-native-1544-323-56401',1,8,-72,-43,0),
(E'resource-native-1544-323-56401',1,9,-72,-42,0),
(E'resource-native-1544-323-56401',1,10,-72,-41,0),
(E'resource-native-1544-323-56401',1,11,-71,-62,0),
(E'resource-native-1544-323-56401',1,12,-71,-61,0),
(E'resource-native-1544-323-56401',1,13,-71,-60,0),
(E'resource-native-1544-323-56401',1,14,-71,-59,0),
(E'resource-native-1544-323-56401',1,15,-71,-58,0),
(E'resource-native-1544-323-56401',1,16,-71,-57,0),
(E'resource-native-1544-323-56401',1,17,-71,-56,0),
(E'resource-native-1544-323-56401',1,18,-71,-55,0),
(E'resource-native-1544-323-56401',1,19,-71,-54,0),
(E'resource-native-1544-323-56401',1,20,-71,-53,0),
(E'resource-native-1544-323-56401',1,21,-71,-52,0),
(E'resource-native-1544-323-56401',1,22,-71,-44,0),
(E'resource-native-1544-323-56401',1,23,-71,-43,0),
(E'resource-native-1544-323-56401',1,24,-71,-42,0),
(E'resource-native-1544-323-56401',1,25,-71,-41,0),
(E'resource-native-1544-323-56401',1,26,-70,-62,3),
(E'resource-native-1544-323-56401',1,27,-70,-61,0),
(E'resource-native-1544-323-56401',1,28,-70,-60,0),
(E'resource-native-1544-323-56401',1,29,-70,-59,0),
(E'resource-native-1544-323-56401',1,30,-70,-58,0),
(E'resource-native-1544-323-56401',1,31,-70,-57,0),
(E'resource-native-1544-323-56401',1,32,-70,-56,0),
(E'resource-native-1544-323-56401',1,33,-70,-55,0),
(E'resource-native-1544-323-56401',1,34,-70,-54,0),
(E'resource-native-1544-323-56401',1,35,-70,-53,0),
(E'resource-native-1544-323-56401',1,36,-70,-52,0),
(E'resource-native-1544-323-56401',1,37,-70,-48,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1515-793-64801',1,-1515,0,233,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1515-793-64801',1,E'proposed',0),
(E'resource-native-1515-793-64801',1,E'active',1),
(E'resource-native-1515-793-64801',1,E'completed',2),
(E'resource-native-1515-793-64801',1,E'expired',2),
(E'resource-native-1515-793-64801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',96,NULL,NULL),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',-1515,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1515-793-64801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1515-793-64801',1,0,-5,-76,61),
(E'resource-native-1515-793-64801',1,1,-5,-75,65),
(E'resource-native-1515-793-64801',1,2,-5,-69,47),
(E'resource-native-1515-793-64801',1,3,-5,-67,71),
(E'resource-native-1515-793-64801',1,4,-5,-66,70),
(E'resource-native-1515-793-64801',1,5,-5,-65,69),
(E'resource-native-1515-793-64801',1,6,-5,-64,66),
(E'resource-native-1515-793-64801',1,7,-3,-95,10),
(E'resource-native-1515-793-64801',1,8,-3,-71,32),
(E'resource-native-1515-793-64801',1,9,-3,-70,31),
(E'resource-native-1515-793-64801',1,10,-3,-69,32),
(E'resource-native-1515-793-64801',1,11,-2,-96,10),
(E'resource-native-1515-793-64801',1,12,-2,-95,10),
(E'resource-native-1515-793-64801',1,13,-2,-92,10),
(E'resource-native-1515-793-64801',1,14,-2,-91,10),
(E'resource-native-1515-793-64801',1,15,-2,-71,29),
(E'resource-native-1515-793-64801',1,16,-2,-70,29),
(E'resource-native-1515-793-64801',1,17,-2,-69,29),
(E'resource-native-1515-793-64801',1,18,-1,-97,10),
(E'resource-native-1515-793-64801',1,19,-1,-96,10),
(E'resource-native-1515-793-64801',1,20,-1,-92,9),
(E'resource-native-1515-793-64801',1,21,-1,-91,10),
(E'resource-native-1515-793-64801',1,22,-1,-71,26),
(E'resource-native-1515-793-64801',1,23,-1,-70,26),
(E'resource-native-1515-793-64801',1,24,-1,-69,26),
(E'resource-native-1515-793-64801',1,25,0,-98,10),
(E'resource-native-1515-793-64801',1,26,0,-97,10),
(E'resource-native-1515-793-64801',1,27,0,-96,10),
(E'resource-native-1515-793-64801',1,28,0,-95,10),
(E'resource-native-1515-793-64801',1,29,0,-92,10),
(E'resource-native-1515-793-64801',1,30,0,-91,10),
(E'resource-native-1515-793-64801',1,31,0,-89,11),
(E'resource-native-1515-793-64801',1,32,0,-71,23),
(E'resource-native-1515-793-64801',1,33,0,-70,23),
(E'resource-native-1515-793-64801',1,34,0,-69,23),
(E'resource-native-1515-793-64801',1,35,0,-3,7),
(E'resource-native-1515-793-64801',1,36,0,-2,7),
(E'resource-native-1515-793-64801',1,37,0,-1,7);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1509-1124-81001',1,-1509,0,316,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1509-1124-81001',1,E'proposed',0),
(E'resource-native-1509-1124-81001',1,E'active',1),
(E'resource-native-1509-1124-81001',1,E'completed',2),
(E'resource-native-1509-1124-81001',1,E'expired',2),
(E'resource-native-1509-1124-81001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',-1509,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1509-1124-81001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1509-1124-81001',1,0,-53,-83,24),
(E'resource-native-1509-1124-81001',1,1,-53,-82,22),
(E'resource-native-1509-1124-81001',1,2,-53,-81,20),
(E'resource-native-1509-1124-81001',1,3,-53,-80,23),
(E'resource-native-1509-1124-81001',1,4,-53,-79,22),
(E'resource-native-1509-1124-81001',1,5,-53,-78,20),
(E'resource-native-1509-1124-81001',1,6,-53,-68,20),
(E'resource-native-1509-1124-81001',1,7,-53,-67,20),
(E'resource-native-1509-1124-81001',1,8,-53,-66,20),
(E'resource-native-1509-1124-81001',1,9,-53,-63,20),
(E'resource-native-1509-1124-81001',1,10,-53,-62,20),
(E'resource-native-1509-1124-81001',1,11,-53,-61,20),
(E'resource-native-1509-1124-81001',1,12,-53,-60,20),
(E'resource-native-1509-1124-81001',1,13,-53,-59,23),
(E'resource-native-1509-1124-81001',1,14,-52,-89,24),
(E'resource-native-1509-1124-81001',1,15,-52,-88,21),
(E'resource-native-1509-1124-81001',1,16,-52,-87,23),
(E'resource-native-1509-1124-81001',1,17,-52,-86,20),
(E'resource-native-1509-1124-81001',1,18,-52,-85,20),
(E'resource-native-1509-1124-81001',1,19,-52,-83,24),
(E'resource-native-1509-1124-81001',1,20,-52,-82,22),
(E'resource-native-1509-1124-81001',1,21,-52,-81,22),
(E'resource-native-1509-1124-81001',1,22,-52,-80,20),
(E'resource-native-1509-1124-81001',1,23,-52,-79,20),
(E'resource-native-1509-1124-81001',1,24,-52,-78,20),
(E'resource-native-1509-1124-81001',1,25,-52,-70,20),
(E'resource-native-1509-1124-81001',1,26,-52,-69,20),
(E'resource-native-1509-1124-81001',1,27,-52,-68,20),
(E'resource-native-1509-1124-81001',1,28,-52,-67,20),
(E'resource-native-1509-1124-81001',1,29,-52,-66,20),
(E'resource-native-1509-1124-81001',1,30,-52,-65,20),
(E'resource-native-1509-1124-81001',1,31,-52,-64,20),
(E'resource-native-1509-1124-81001',1,32,-52,-63,20),
(E'resource-native-1509-1124-81001',1,33,-52,-62,20),
(E'resource-native-1509-1124-81001',1,34,-52,-61,20),
(E'resource-native-1509-1124-81001',1,35,-52,-60,20),
(E'resource-native-1509-1124-81001',1,36,-52,-59,20),
(E'resource-native-1509-1124-81001',1,37,-52,-58,20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1467-853-65401',1,-1467,0,241,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1467-853-65401',1,E'proposed',0),
(E'resource-native-1467-853-65401',1,E'active',1),
(E'resource-native-1467-853-65401',1,E'completed',2),
(E'resource-native-1467-853-65401',1,E'expired',2),
(E'resource-native-1467-853-65401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',-1467,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1467-853-65401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1467-853-65401',1,0,-54,-124,27),
(E'resource-native-1467-853-65401',1,1,-54,-123,27),
(E'resource-native-1467-853-65401',1,2,-54,-122,27),
(E'resource-native-1467-853-65401',1,3,-54,-117,27),
(E'resource-native-1467-853-65401',1,4,-54,-116,27),
(E'resource-native-1467-853-65401',1,5,-54,-98,27),
(E'resource-native-1467-853-65401',1,6,-54,-93,27),
(E'resource-native-1467-853-65401',1,7,-53,-114,1),
(E'resource-native-1467-853-65401',1,8,-53,-113,0),
(E'resource-native-1467-853-65401',1,9,-53,-112,0),
(E'resource-native-1467-853-65401',1,10,-53,-111,0),
(E'resource-native-1467-853-65401',1,11,-53,-110,0),
(E'resource-native-1467-853-65401',1,12,-53,-109,3),
(E'resource-native-1467-853-65401',1,13,-53,-107,2),
(E'resource-native-1467-853-65401',1,14,-53,-103,0),
(E'resource-native-1467-853-65401',1,15,-53,-102,0),
(E'resource-native-1467-853-65401',1,16,-53,-101,0),
(E'resource-native-1467-853-65401',1,17,-53,-100,1),
(E'resource-native-1467-853-65401',1,18,-53,-99,0),
(E'resource-native-1467-853-65401',1,19,-52,-126,27),
(E'resource-native-1467-853-65401',1,20,-52,-114,0),
(E'resource-native-1467-853-65401',1,21,-52,-113,0),
(E'resource-native-1467-853-65401',1,22,-52,-112,0),
(E'resource-native-1467-853-65401',1,23,-52,-111,0),
(E'resource-native-1467-853-65401',1,24,-52,-110,0),
(E'resource-native-1467-853-65401',1,25,-52,-109,0),
(E'resource-native-1467-853-65401',1,26,-52,-108,0),
(E'resource-native-1467-853-65401',1,27,-52,-107,0),
(E'resource-native-1467-853-65401',1,28,-52,-106,0),
(E'resource-native-1467-853-65401',1,29,-52,-105,0),
(E'resource-native-1467-853-65401',1,30,-52,-104,0),
(E'resource-native-1467-853-65401',1,31,-52,-103,0),
(E'resource-native-1467-853-65401',1,32,-52,-102,0),
(E'resource-native-1467-853-65401',1,33,-52,-101,0),
(E'resource-native-1467-853-65401',1,34,-52,-100,0),
(E'resource-native-1467-853-65401',1,35,-52,-99,0),
(E'resource-native-1467-853-65401',1,36,-51,-126,27),
(E'resource-native-1467-853-65401',1,37,-51,-114,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1463-843-65301',1,-1463,0,240,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1463-843-65301',1,E'proposed',0),
(E'resource-native-1463-843-65301',1,E'active',1),
(E'resource-native-1463-843-65301',1,E'completed',2),
(E'resource-native-1463-843-65301',1,E'expired',2),
(E'resource-native-1463-843-65301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',-1463,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1463-843-65301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1463-843-65301',1,0,-4,-4,48),
(E'resource-native-1463-843-65301',1,1,-4,-3,48),
(E'resource-native-1463-843-65301',1,2,-4,1,48),
(E'resource-native-1463-843-65301',1,3,-3,-5,48),
(E'resource-native-1463-843-65301',1,4,-3,-4,48),
(E'resource-native-1463-843-65301',1,5,-3,-3,48),
(E'resource-native-1463-843-65301',1,6,-3,-2,48),
(E'resource-native-1463-843-65301',1,7,-3,-1,48),
(E'resource-native-1463-843-65301',1,8,-3,0,48),
(E'resource-native-1463-843-65301',1,9,-3,1,48),
(E'resource-native-1463-843-65301',1,10,-3,2,48),
(E'resource-native-1463-843-65301',1,11,-2,-5,48),
(E'resource-native-1463-843-65301',1,12,-2,-4,48),
(E'resource-native-1463-843-65301',1,13,-2,-3,48),
(E'resource-native-1463-843-65301',1,14,-2,-2,48),
(E'resource-native-1463-843-65301',1,15,-2,-1,48),
(E'resource-native-1463-843-65301',1,16,-2,0,48),
(E'resource-native-1463-843-65301',1,17,-2,1,48),
(E'resource-native-1463-843-65301',1,18,-2,2,48),
(E'resource-native-1463-843-65301',1,19,-1,-6,48),
(E'resource-native-1463-843-65301',1,20,-1,-5,48),
(E'resource-native-1463-843-65301',1,21,-1,-4,48),
(E'resource-native-1463-843-65301',1,22,-1,-3,48),
(E'resource-native-1463-843-65301',1,23,-1,-2,48),
(E'resource-native-1463-843-65301',1,24,-1,-1,48),
(E'resource-native-1463-843-65301',1,25,-1,1,48),
(E'resource-native-1463-843-65301',1,26,-1,2,48),
(E'resource-native-1463-843-65301',1,27,0,-8,48),
(E'resource-native-1463-843-65301',1,28,0,-7,48),
(E'resource-native-1463-843-65301',1,29,0,-6,48),
(E'resource-native-1463-843-65301',1,30,0,-5,48),
(E'resource-native-1463-843-65301',1,31,0,-4,48),
(E'resource-native-1463-843-65301',1,32,0,-3,48),
(E'resource-native-1463-843-65301',1,33,0,-2,48),
(E'resource-native-1463-843-65301',1,34,0,-1,48),
(E'resource-native-1463-843-65301',1,35,0,0,48),
(E'resource-native-1463-843-65301',1,36,0,1,48),
(E'resource-native-1463-843-65301',1,37,0,2,48);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1437-1384-93801',1,-1437,0,435,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1437-1384-93801',1,E'proposed',0),
(E'resource-native-1437-1384-93801',1,E'active',1),
(E'resource-native-1437-1384-93801',1,E'completed',2),
(E'resource-native-1437-1384-93801',1,E'expired',2),
(E'resource-native-1437-1384-93801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',141,NULL,NULL),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',-1437,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1437-1384-93801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1437-1384-93801',1,0,-180,-306,-3),
(E'resource-native-1437-1384-93801',1,1,-180,-305,-3),
(E'resource-native-1437-1384-93801',1,2,-180,-304,-3),
(E'resource-native-1437-1384-93801',1,3,-180,-303,-3),
(E'resource-native-1437-1384-93801',1,4,-180,-302,-3),
(E'resource-native-1437-1384-93801',1,5,-180,-300,-2),
(E'resource-native-1437-1384-93801',1,6,-180,-299,0),
(E'resource-native-1437-1384-93801',1,7,-180,-298,0),
(E'resource-native-1437-1384-93801',1,8,-180,-297,-2),
(E'resource-native-1437-1384-93801',1,9,-180,-296,-3),
(E'resource-native-1437-1384-93801',1,10,-180,-295,-3),
(E'resource-native-1437-1384-93801',1,11,-180,-294,-3),
(E'resource-native-1437-1384-93801',1,12,-180,-292,-3),
(E'resource-native-1437-1384-93801',1,13,-180,-291,-3),
(E'resource-native-1437-1384-93801',1,14,-180,-290,-2),
(E'resource-native-1437-1384-93801',1,15,-180,-289,0),
(E'resource-native-1437-1384-93801',1,16,-180,-288,-2),
(E'resource-native-1437-1384-93801',1,17,-180,-287,-2),
(E'resource-native-1437-1384-93801',1,18,-180,-286,-3),
(E'resource-native-1437-1384-93801',1,19,-180,-285,-3),
(E'resource-native-1437-1384-93801',1,20,-180,-284,-3),
(E'resource-native-1437-1384-93801',1,21,-180,-283,-3),
(E'resource-native-1437-1384-93801',1,22,-180,-282,-3),
(E'resource-native-1437-1384-93801',1,23,-180,-281,-3),
(E'resource-native-1437-1384-93801',1,24,-180,-280,-3),
(E'resource-native-1437-1384-93801',1,25,-180,-279,-3),
(E'resource-native-1437-1384-93801',1,26,-180,-278,-3),
(E'resource-native-1437-1384-93801',1,27,-180,-277,-3),
(E'resource-native-1437-1384-93801',1,28,-180,-276,-3),
(E'resource-native-1437-1384-93801',1,29,-180,-274,-3),
(E'resource-native-1437-1384-93801',1,30,-180,-273,-3),
(E'resource-native-1437-1384-93801',1,31,-180,-272,-2),
(E'resource-native-1437-1384-93801',1,32,-180,-271,0),
(E'resource-native-1437-1384-93801',1,33,-180,-252,-3),
(E'resource-native-1437-1384-93801',1,34,-180,-251,-3),
(E'resource-native-1437-1384-93801',1,35,-180,-249,-3),
(E'resource-native-1437-1384-93801',1,36,-180,-248,-3),
(E'resource-native-1437-1384-93801',1,37,-180,-246,-3);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1429-1384-93501',1,-1429,0,431,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1429-1384-93501',1,E'proposed',0),
(E'resource-native-1429-1384-93501',1,E'active',1),
(E'resource-native-1429-1384-93501',1,E'completed',2),
(E'resource-native-1429-1384-93501',1,E'expired',2),
(E'resource-native-1429-1384-93501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',-1429,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1429-1384-93501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1429-1384-93501',1,0,-216,-155,0),
(E'resource-native-1429-1384-93501',1,1,-216,-151,0),
(E'resource-native-1429-1384-93501',1,2,-216,-150,0),
(E'resource-native-1429-1384-93501',1,3,-215,-157,6),
(E'resource-native-1429-1384-93501',1,4,-215,-156,6),
(E'resource-native-1429-1384-93501',1,5,-215,-155,3),
(E'resource-native-1429-1384-93501',1,6,-215,-154,0),
(E'resource-native-1429-1384-93501',1,7,-215,-153,0),
(E'resource-native-1429-1384-93501',1,8,-215,-152,0),
(E'resource-native-1429-1384-93501',1,9,-215,-151,0),
(E'resource-native-1429-1384-93501',1,10,-215,-150,0),
(E'resource-native-1429-1384-93501',1,11,-215,-149,0),
(E'resource-native-1429-1384-93501',1,12,-214,-159,2),
(E'resource-native-1429-1384-93501',1,13,-214,-158,0),
(E'resource-native-1429-1384-93501',1,14,-214,-155,0),
(E'resource-native-1429-1384-93501',1,15,-214,-154,0),
(E'resource-native-1429-1384-93501',1,16,-214,-153,0),
(E'resource-native-1429-1384-93501',1,17,-214,-152,0),
(E'resource-native-1429-1384-93501',1,18,-214,-151,0),
(E'resource-native-1429-1384-93501',1,19,-214,-150,0),
(E'resource-native-1429-1384-93501',1,20,-214,-149,0),
(E'resource-native-1429-1384-93501',1,21,-213,-159,0),
(E'resource-native-1429-1384-93501',1,22,-213,-158,0),
(E'resource-native-1429-1384-93501',1,23,-213,-157,0),
(E'resource-native-1429-1384-93501',1,24,-213,-156,0),
(E'resource-native-1429-1384-93501',1,25,-213,-155,0),
(E'resource-native-1429-1384-93501',1,26,-213,-154,0),
(E'resource-native-1429-1384-93501',1,27,-213,-153,0),
(E'resource-native-1429-1384-93501',1,28,-213,-152,0),
(E'resource-native-1429-1384-93501',1,29,-213,-151,0),
(E'resource-native-1429-1384-93501',1,30,-213,-150,0),
(E'resource-native-1429-1384-93501',1,31,-213,-149,0),
(E'resource-native-1429-1384-93501',1,32,-213,-148,0),
(E'resource-native-1429-1384-93501',1,33,-212,-161,0),
(E'resource-native-1429-1384-93501',1,34,-212,-160,0),
(E'resource-native-1429-1384-93501',1,35,-212,-159,0),
(E'resource-native-1429-1384-93501',1,36,-212,-158,0),
(E'resource-native-1429-1384-93501',1,37,-212,-157,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1412-796-64701',1,-1412,0,232,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1412-796-64701',1,E'proposed',0),
(E'resource-native-1412-796-64701',1,E'active',1),
(E'resource-native-1412-796-64701',1,E'completed',2),
(E'resource-native-1412-796-64701',1,E'expired',2),
(E'resource-native-1412-796-64701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',-1412,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1412-796-64701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1412-796-64701',1,0,-81,19,20),
(E'resource-native-1412-796-64701',1,1,-81,20,20),
(E'resource-native-1412-796-64701',1,2,-81,21,20),
(E'resource-native-1412-796-64701',1,3,-81,22,20),
(E'resource-native-1412-796-64701',1,4,-81,23,20),
(E'resource-native-1412-796-64701',1,5,-81,24,20),
(E'resource-native-1412-796-64701',1,6,-80,19,22),
(E'resource-native-1412-796-64701',1,7,-80,20,20),
(E'resource-native-1412-796-64701',1,8,-80,21,23),
(E'resource-native-1412-796-64701',1,9,-80,22,20),
(E'resource-native-1412-796-64701',1,10,-80,23,20),
(E'resource-native-1412-796-64701',1,11,-80,24,20),
(E'resource-native-1412-796-64701',1,12,-79,19,20),
(E'resource-native-1412-796-64701',1,13,-79,20,20),
(E'resource-native-1412-796-64701',1,14,-79,21,20),
(E'resource-native-1412-796-64701',1,15,-79,22,20),
(E'resource-native-1412-796-64701',1,16,-79,23,20),
(E'resource-native-1412-796-64701',1,17,-79,24,20),
(E'resource-native-1412-796-64701',1,18,-78,18,20),
(E'resource-native-1412-796-64701',1,19,-78,19,20),
(E'resource-native-1412-796-64701',1,20,-78,20,20),
(E'resource-native-1412-796-64701',1,21,-78,21,20),
(E'resource-native-1412-796-64701',1,22,-78,22,20),
(E'resource-native-1412-796-64701',1,23,-78,23,20),
(E'resource-native-1412-796-64701',1,24,-78,24,20),
(E'resource-native-1412-796-64701',1,25,-78,43,20),
(E'resource-native-1412-796-64701',1,26,-77,18,20),
(E'resource-native-1412-796-64701',1,27,-77,19,23),
(E'resource-native-1412-796-64701',1,28,-77,20,20),
(E'resource-native-1412-796-64701',1,29,-77,21,20),
(E'resource-native-1412-796-64701',1,30,-77,22,20),
(E'resource-native-1412-796-64701',1,31,-77,23,20),
(E'resource-native-1412-796-64701',1,32,-77,24,20),
(E'resource-native-1412-796-64701',1,33,-77,27,15),
(E'resource-native-1412-796-64701',1,34,-77,28,13),
(E'resource-native-1412-796-64701',1,35,-77,29,11),
(E'resource-native-1412-796-64701',1,36,-77,30,9),
(E'resource-native-1412-796-64701',1,37,-77,31,7);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1397-792-64601',1,-1397,0,231,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1397-792-64601',1,E'proposed',0),
(E'resource-native-1397-792-64601',1,E'active',1),
(E'resource-native-1397-792-64601',1,E'completed',2),
(E'resource-native-1397-792-64601',1,E'expired',2),
(E'resource-native-1397-792-64601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',111,NULL,NULL),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',-1397,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1397-792-64601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1397-792-64601',1,0,-144,-55,21),
(E'resource-native-1397-792-64601',1,1,-144,-54,20),
(E'resource-native-1397-792-64601',1,2,-144,-53,20),
(E'resource-native-1397-792-64601',1,3,-144,-52,22),
(E'resource-native-1397-792-64601',1,4,-144,-51,20),
(E'resource-native-1397-792-64601',1,5,-144,-50,20),
(E'resource-native-1397-792-64601',1,6,-144,-49,16),
(E'resource-native-1397-792-64601',1,7,-144,-48,4),
(E'resource-native-1397-792-64601',1,8,-144,-45,0),
(E'resource-native-1397-792-64601',1,9,-144,-44,0),
(E'resource-native-1397-792-64601',1,10,-144,-43,4),
(E'resource-native-1397-792-64601',1,11,-144,-42,-2),
(E'resource-native-1397-792-64601',1,12,-143,-62,20),
(E'resource-native-1397-792-64601',1,13,-143,-55,21),
(E'resource-native-1397-792-64601',1,14,-143,-54,20),
(E'resource-native-1397-792-64601',1,15,-143,-53,20),
(E'resource-native-1397-792-64601',1,16,-143,-52,20),
(E'resource-native-1397-792-64601',1,17,-143,-51,20),
(E'resource-native-1397-792-64601',1,18,-143,-50,20),
(E'resource-native-1397-792-64601',1,19,-143,-49,20),
(E'resource-native-1397-792-64601',1,20,-143,-48,0),
(E'resource-native-1397-792-64601',1,21,-143,-47,0),
(E'resource-native-1397-792-64601',1,22,-143,-46,2),
(E'resource-native-1397-792-64601',1,23,-143,-45,0),
(E'resource-native-1397-792-64601',1,24,-143,-44,0),
(E'resource-native-1397-792-64601',1,25,-143,-43,2),
(E'resource-native-1397-792-64601',1,26,-143,-42,0),
(E'resource-native-1397-792-64601',1,27,-142,-71,22),
(E'resource-native-1397-792-64601',1,28,-142,-70,20),
(E'resource-native-1397-792-64601',1,29,-142,-69,21),
(E'resource-native-1397-792-64601',1,30,-142,-68,20),
(E'resource-native-1397-792-64601',1,31,-142,-67,20),
(E'resource-native-1397-792-64601',1,32,-142,-66,20),
(E'resource-native-1397-792-64601',1,33,-142,-65,20),
(E'resource-native-1397-792-64601',1,34,-142,-64,20),
(E'resource-native-1397-792-64601',1,35,-142,-63,20),
(E'resource-native-1397-792-64601',1,36,-142,-62,20),
(E'resource-native-1397-792-64601',1,37,-142,-61,20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1382-508-60801',1,-1382,0,202,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1382-508-60801',1,E'proposed',0),
(E'resource-native-1382-508-60801',1,E'active',1),
(E'resource-native-1382-508-60801',1,E'completed',2),
(E'resource-native-1382-508-60801',1,E'expired',2),
(E'resource-native-1382-508-60801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',111,NULL,NULL),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',-1382,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1382-508-60801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1382-508-60801',1,0,-56,10,0),
(E'resource-native-1382-508-60801',1,1,-56,11,0),
(E'resource-native-1382-508-60801',1,2,-56,12,0),
(E'resource-native-1382-508-60801',1,3,-56,13,0),
(E'resource-native-1382-508-60801',1,4,-56,14,0),
(E'resource-native-1382-508-60801',1,5,-55,4,0),
(E'resource-native-1382-508-60801',1,6,-55,5,0),
(E'resource-native-1382-508-60801',1,7,-55,6,0),
(E'resource-native-1382-508-60801',1,8,-55,7,0),
(E'resource-native-1382-508-60801',1,9,-55,8,0),
(E'resource-native-1382-508-60801',1,10,-55,9,0),
(E'resource-native-1382-508-60801',1,11,-55,10,0),
(E'resource-native-1382-508-60801',1,12,-55,11,0),
(E'resource-native-1382-508-60801',1,13,-55,12,0),
(E'resource-native-1382-508-60801',1,14,-55,13,0),
(E'resource-native-1382-508-60801',1,15,-55,14,0),
(E'resource-native-1382-508-60801',1,16,-54,3,0),
(E'resource-native-1382-508-60801',1,17,-54,4,0),
(E'resource-native-1382-508-60801',1,18,-54,5,0),
(E'resource-native-1382-508-60801',1,19,-54,6,0),
(E'resource-native-1382-508-60801',1,20,-54,7,0),
(E'resource-native-1382-508-60801',1,21,-54,8,0),
(E'resource-native-1382-508-60801',1,22,-54,9,0),
(E'resource-native-1382-508-60801',1,23,-54,10,0),
(E'resource-native-1382-508-60801',1,24,-54,11,0),
(E'resource-native-1382-508-60801',1,25,-54,12,0),
(E'resource-native-1382-508-60801',1,26,-54,13,0),
(E'resource-native-1382-508-60801',1,27,-54,14,0),
(E'resource-native-1382-508-60801',1,28,-54,23,0),
(E'resource-native-1382-508-60801',1,29,-53,2,0),
(E'resource-native-1382-508-60801',1,30,-53,3,0),
(E'resource-native-1382-508-60801',1,31,-53,4,0),
(E'resource-native-1382-508-60801',1,32,-53,5,0),
(E'resource-native-1382-508-60801',1,33,-53,6,0),
(E'resource-native-1382-508-60801',1,34,-53,7,0),
(E'resource-native-1382-508-60801',1,35,-53,11,0),
(E'resource-native-1382-508-60801',1,36,-53,12,0),
(E'resource-native-1382-508-60801',1,37,-53,13,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1367-507-60701',1,-1367,0,200,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1367-507-60701',1,E'proposed',0),
(E'resource-native-1367-507-60701',1,E'active',1),
(E'resource-native-1367-507-60701',1,E'completed',2),
(E'resource-native-1367-507-60701',1,E'expired',2),
(E'resource-native-1367-507-60701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',96,NULL,NULL),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',-1367,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1367-507-60701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1367-507-60701',1,0,-22,-118,20),
(E'resource-native-1367-507-60701',1,1,-22,-117,25),
(E'resource-native-1367-507-60701',1,2,-22,-116,25),
(E'resource-native-1367-507-60701',1,3,-22,-115,25),
(E'resource-native-1367-507-60701',1,4,-22,-114,25),
(E'resource-native-1367-507-60701',1,5,-22,-113,25),
(E'resource-native-1367-507-60701',1,6,-22,-112,25),
(E'resource-native-1367-507-60701',1,7,-22,-111,24),
(E'resource-native-1367-507-60701',1,8,-22,-110,25),
(E'resource-native-1367-507-60701',1,9,-22,-79,30),
(E'resource-native-1367-507-60701',1,10,-22,-78,28),
(E'resource-native-1367-507-60701',1,11,-22,-77,28),
(E'resource-native-1367-507-60701',1,12,-22,-76,30),
(E'resource-native-1367-507-60701',1,13,-22,-75,30),
(E'resource-native-1367-507-60701',1,14,-22,-74,30),
(E'resource-native-1367-507-60701',1,15,-22,-73,30),
(E'resource-native-1367-507-60701',1,16,-22,-53,27),
(E'resource-native-1367-507-60701',1,17,-22,-52,26),
(E'resource-native-1367-507-60701',1,18,-22,-51,26),
(E'resource-native-1367-507-60701',1,19,-22,-50,28),
(E'resource-native-1367-507-60701',1,20,-22,-49,27),
(E'resource-native-1367-507-60701',1,21,-22,-48,28),
(E'resource-native-1367-507-60701',1,22,-22,-47,28),
(E'resource-native-1367-507-60701',1,23,-22,-46,28),
(E'resource-native-1367-507-60701',1,24,-21,-120,21),
(E'resource-native-1367-507-60701',1,25,-21,-119,21),
(E'resource-native-1367-507-60701',1,26,-21,-118,21),
(E'resource-native-1367-507-60701',1,27,-21,-116,25),
(E'resource-native-1367-507-60701',1,28,-21,-115,25),
(E'resource-native-1367-507-60701',1,29,-21,-112,21),
(E'resource-native-1367-507-60701',1,30,-21,-111,20),
(E'resource-native-1367-507-60701',1,31,-21,-110,21),
(E'resource-native-1367-507-60701',1,32,-21,-79,25),
(E'resource-native-1367-507-60701',1,33,-21,-78,25),
(E'resource-native-1367-507-60701',1,34,-21,-77,25),
(E'resource-native-1367-507-60701',1,35,-21,-76,25),
(E'resource-native-1367-507-60701',1,36,-21,-75,27),
(E'resource-native-1367-507-60701',1,37,-21,-74,29);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1352-504-60601',1,-1352,0,198,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1352-504-60601',1,E'proposed',0),
(E'resource-native-1352-504-60601',1,E'active',1),
(E'resource-native-1352-504-60601',1,E'completed',2),
(E'resource-native-1352-504-60601',1,E'expired',2),
(E'resource-native-1352-504-60601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',-1352,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1352-504-60601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1352-504-60601',1,0,-45,-94,6),
(E'resource-native-1352-504-60601',1,1,-45,-93,6),
(E'resource-native-1352-504-60601',1,2,-45,-92,6),
(E'resource-native-1352-504-60601',1,3,-45,-91,6),
(E'resource-native-1352-504-60601',1,4,-44,-94,4),
(E'resource-native-1352-504-60601',1,5,-44,-91,6),
(E'resource-native-1352-504-60601',1,6,-43,-94,6),
(E'resource-native-1352-504-60601',1,7,-43,-91,6),
(E'resource-native-1352-504-60601',1,8,-42,-94,6),
(E'resource-native-1352-504-60601',1,9,-41,-94,5),
(E'resource-native-1352-504-60601',1,10,-40,-94,6),
(E'resource-native-1352-504-60601',1,11,-39,-94,6),
(E'resource-native-1352-504-60601',1,12,-39,-93,6),
(E'resource-native-1352-504-60601',1,13,-39,-92,4),
(E'resource-native-1352-504-60601',1,14,-38,-92,6),
(E'resource-native-1352-504-60601',1,15,-37,-92,6),
(E'resource-native-1352-504-60601',1,16,-36,-92,6),
(E'resource-native-1352-504-60601',1,17,-36,-34,0),
(E'resource-native-1352-504-60601',1,18,-36,-33,0),
(E'resource-native-1352-504-60601',1,19,-36,-32,0),
(E'resource-native-1352-504-60601',1,20,-36,-31,3),
(E'resource-native-1352-504-60601',1,21,-35,-92,5),
(E'resource-native-1352-504-60601',1,22,-35,-65,20),
(E'resource-native-1352-504-60601',1,23,-35,-64,17),
(E'resource-native-1352-504-60601',1,24,-35,-63,0),
(E'resource-native-1352-504-60601',1,25,-35,-62,0),
(E'resource-native-1352-504-60601',1,26,-35,-61,0),
(E'resource-native-1352-504-60601',1,27,-35,-60,0),
(E'resource-native-1352-504-60601',1,28,-35,-57,0),
(E'resource-native-1352-504-60601',1,29,-35,-56,0),
(E'resource-native-1352-504-60601',1,30,-35,-55,0),
(E'resource-native-1352-504-60601',1,31,-35,-54,0),
(E'resource-native-1352-504-60601',1,32,-35,-53,0),
(E'resource-native-1352-504-60601',1,33,-35,-49,0),
(E'resource-native-1352-504-60601',1,34,-35,-48,0),
(E'resource-native-1352-504-60601',1,35,-35,-37,0),
(E'resource-native-1352-504-60601',1,36,-35,-36,0),
(E'resource-native-1352-504-60601',1,37,-35,-35,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1337-1295-90601',1,-1337,0,412,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1337-1295-90601',1,E'proposed',0),
(E'resource-native-1337-1295-90601',1,E'active',1),
(E'resource-native-1337-1295-90601',1,E'completed',2),
(E'resource-native-1337-1295-90601',1,E'expired',2),
(E'resource-native-1337-1295-90601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',96,NULL,NULL),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',-1337,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1337-1295-90601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1337-1295-90601',1,0,-198,-17,-42),
(E'resource-native-1337-1295-90601',1,1,-198,-16,-42),
(E'resource-native-1337-1295-90601',1,2,-198,-15,-42),
(E'resource-native-1337-1295-90601',1,3,-198,-14,-44),
(E'resource-native-1337-1295-90601',1,4,-198,-13,-48),
(E'resource-native-1337-1295-90601',1,5,-198,-12,-50),
(E'resource-native-1337-1295-90601',1,6,-198,-11,-50),
(E'resource-native-1337-1295-90601',1,7,-198,-10,-50),
(E'resource-native-1337-1295-90601',1,8,-198,-9,-52),
(E'resource-native-1337-1295-90601',1,9,-198,-7,-60),
(E'resource-native-1337-1295-90601',1,10,-198,-6,-62),
(E'resource-native-1337-1295-90601',1,11,-198,-5,-62),
(E'resource-native-1337-1295-90601',1,12,-198,-4,-62),
(E'resource-native-1337-1295-90601',1,13,-198,-3,-64),
(E'resource-native-1337-1295-90601',1,14,-198,-2,-68),
(E'resource-native-1337-1295-90601',1,15,-198,-1,-72),
(E'resource-native-1337-1295-90601',1,16,-197,-18,-42),
(E'resource-native-1337-1295-90601',1,17,-197,-17,-42),
(E'resource-native-1337-1295-90601',1,18,-197,-16,-42),
(E'resource-native-1337-1295-90601',1,19,-197,-15,-42),
(E'resource-native-1337-1295-90601',1,20,-197,-14,-44),
(E'resource-native-1337-1295-90601',1,21,-197,-13,-48),
(E'resource-native-1337-1295-90601',1,22,-197,-12,-50),
(E'resource-native-1337-1295-90601',1,23,-197,-11,-50),
(E'resource-native-1337-1295-90601',1,24,-197,-10,-50),
(E'resource-native-1337-1295-90601',1,25,-197,-9,-52),
(E'resource-native-1337-1295-90601',1,26,-197,-8,-56),
(E'resource-native-1337-1295-90601',1,27,-197,-7,-60),
(E'resource-native-1337-1295-90601',1,28,-197,-6,-62),
(E'resource-native-1337-1295-90601',1,29,-197,-5,-62),
(E'resource-native-1337-1295-90601',1,30,-197,-4,-62),
(E'resource-native-1337-1295-90601',1,31,-197,-3,-64),
(E'resource-native-1337-1295-90601',1,32,-197,-2,-68),
(E'resource-native-1337-1295-90601',1,33,-197,-1,-72),
(E'resource-native-1337-1295-90601',1,34,-196,-18,-42),
(E'resource-native-1337-1295-90601',1,35,-196,-17,-42),
(E'resource-native-1337-1295-90601',1,36,-196,-16,-42),
(E'resource-native-1337-1295-90601',1,37,-196,-15,-42);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1322-327-56601',1,-1322,0,180,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1322-327-56601',1,E'proposed',0),
(E'resource-native-1322-327-56601',1,E'active',1),
(E'resource-native-1322-327-56601',1,E'completed',2),
(E'resource-native-1322-327-56601',1,E'expired',2),
(E'resource-native-1322-327-56601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',-1322,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1322-327-56601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1322-327-56601',1,0,-107,-30,-20),
(E'resource-native-1322-327-56601',1,1,-107,-29,-20),
(E'resource-native-1322-327-56601',1,2,-107,-28,-20),
(E'resource-native-1322-327-56601',1,3,-107,-27,-20),
(E'resource-native-1322-327-56601',1,4,-107,-20,-20),
(E'resource-native-1322-327-56601',1,5,-107,-19,-20),
(E'resource-native-1322-327-56601',1,6,-106,-30,-20),
(E'resource-native-1322-327-56601',1,7,-106,-29,-20),
(E'resource-native-1322-327-56601',1,8,-106,-28,-20),
(E'resource-native-1322-327-56601',1,9,-106,-27,-20),
(E'resource-native-1322-327-56601',1,10,-106,-23,-20),
(E'resource-native-1322-327-56601',1,11,-106,-22,-20),
(E'resource-native-1322-327-56601',1,12,-106,-21,-20),
(E'resource-native-1322-327-56601',1,13,-106,-20,-20),
(E'resource-native-1322-327-56601',1,14,-106,-19,-20),
(E'resource-native-1322-327-56601',1,15,-105,-29,-20),
(E'resource-native-1322-327-56601',1,16,-105,-28,-20),
(E'resource-native-1322-327-56601',1,17,-105,-27,-20),
(E'resource-native-1322-327-56601',1,18,-105,-26,-20),
(E'resource-native-1322-327-56601',1,19,-105,-25,-19),
(E'resource-native-1322-327-56601',1,20,-105,-24,-20),
(E'resource-native-1322-327-56601',1,21,-105,-23,-20),
(E'resource-native-1322-327-56601',1,22,-105,-22,-20),
(E'resource-native-1322-327-56601',1,23,-105,-21,-20),
(E'resource-native-1322-327-56601',1,24,-105,-20,-20),
(E'resource-native-1322-327-56601',1,25,-105,-19,-20),
(E'resource-native-1322-327-56601',1,26,-104,-29,-20),
(E'resource-native-1322-327-56601',1,27,-104,-28,-20),
(E'resource-native-1322-327-56601',1,28,-104,-27,-20),
(E'resource-native-1322-327-56601',1,29,-104,-26,-20),
(E'resource-native-1322-327-56601',1,30,-104,-25,-20),
(E'resource-native-1322-327-56601',1,31,-104,-24,-20),
(E'resource-native-1322-327-56601',1,32,-104,-23,-20),
(E'resource-native-1322-327-56601',1,33,-104,-22,-20),
(E'resource-native-1322-327-56601',1,34,-104,-21,-20),
(E'resource-native-1322-327-56601',1,35,-104,-20,-20),
(E'resource-native-1322-327-56601',1,36,-104,-19,-17),
(E'resource-native-1322-327-56601',1,37,-103,-27,-20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1307-1134-79101',1,-1307,0,343,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1307-1134-79101',1,E'proposed',0),
(E'resource-native-1307-1134-79101',1,E'active',1),
(E'resource-native-1307-1134-79101',1,E'completed',2),
(E'resource-native-1307-1134-79101',1,E'expired',2),
(E'resource-native-1307-1134-79101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',36,NULL,NULL),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',-1307,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1307-1134-79101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1307-1134-79101',1,0,72,-54,47),
(E'resource-native-1307-1134-79101',1,1,72,-53,47),
(E'resource-native-1307-1134-79101',1,2,72,-52,26),
(E'resource-native-1307-1134-79101',1,3,72,-51,26),
(E'resource-native-1307-1134-79101',1,4,72,-50,26),
(E'resource-native-1307-1134-79101',1,5,72,-49,26),
(E'resource-native-1307-1134-79101',1,6,72,-48,30),
(E'resource-native-1307-1134-79101',1,7,72,-47,34),
(E'resource-native-1307-1134-79101',1,8,72,-46,26),
(E'resource-native-1307-1134-79101',1,9,72,-45,26),
(E'resource-native-1307-1134-79101',1,10,72,-44,26),
(E'resource-native-1307-1134-79101',1,11,72,-43,26),
(E'resource-native-1307-1134-79101',1,12,72,-42,26),
(E'resource-native-1307-1134-79101',1,13,72,-41,26),
(E'resource-native-1307-1134-79101',1,14,72,-40,26),
(E'resource-native-1307-1134-79101',1,15,72,-39,26),
(E'resource-native-1307-1134-79101',1,16,72,-38,26),
(E'resource-native-1307-1134-79101',1,17,72,-37,26),
(E'resource-native-1307-1134-79101',1,18,72,-35,30),
(E'resource-native-1307-1134-79101',1,19,72,-33,26),
(E'resource-native-1307-1134-79101',1,20,72,-32,26),
(E'resource-native-1307-1134-79101',1,21,72,-31,26),
(E'resource-native-1307-1134-79101',1,22,72,-30,26),
(E'resource-native-1307-1134-79101',1,23,72,-29,26),
(E'resource-native-1307-1134-79101',1,24,72,-28,26),
(E'resource-native-1307-1134-79101',1,25,72,-27,26),
(E'resource-native-1307-1134-79101',1,26,72,-26,26),
(E'resource-native-1307-1134-79101',1,27,72,-25,26),
(E'resource-native-1307-1134-79101',1,28,72,-24,26),
(E'resource-native-1307-1134-79101',1,29,72,-23,47),
(E'resource-native-1307-1134-79101',1,30,72,-22,47),
(E'resource-native-1307-1134-79101',1,31,72,-21,47),
(E'resource-native-1307-1134-79101',1,32,72,-20,47),
(E'resource-native-1307-1134-79101',1,33,72,-19,47),
(E'resource-native-1307-1134-79101',1,34,72,-17,0),
(E'resource-native-1307-1134-79101',1,35,72,-16,4),
(E'resource-native-1307-1134-79101',1,36,72,-15,0),
(E'resource-native-1307-1134-79101',1,37,72,-14,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1286-711-63401',1,-1286,0,226,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1286-711-63401',1,E'proposed',0),
(E'resource-native-1286-711-63401',1,E'active',1),
(E'resource-native-1286-711-63401',1,E'completed',2),
(E'resource-native-1286-711-63401',1,E'expired',2),
(E'resource-native-1286-711-63401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',51,NULL,NULL),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',-1286,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1286-711-63401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1286-711-63401',1,0,-109,-138,45),
(E'resource-native-1286-711-63401',1,1,-108,-159,40),
(E'resource-native-1286-711-63401',1,2,-108,-156,40),
(E'resource-native-1286-711-63401',1,3,-108,-155,40),
(E'resource-native-1286-711-63401',1,4,-108,-154,40),
(E'resource-native-1286-711-63401',1,5,-108,-153,38),
(E'resource-native-1286-711-63401',1,6,-108,-141,40),
(E'resource-native-1286-711-63401',1,7,-108,-140,40),
(E'resource-native-1286-711-63401',1,8,-108,-139,40),
(E'resource-native-1286-711-63401',1,9,-108,-138,42),
(E'resource-native-1286-711-63401',1,10,-108,-137,40),
(E'resource-native-1286-711-63401',1,11,-108,-136,40),
(E'resource-native-1286-711-63401',1,12,-108,-135,40),
(E'resource-native-1286-711-63401',1,13,-108,-134,40),
(E'resource-native-1286-711-63401',1,14,-108,-131,40),
(E'resource-native-1286-711-63401',1,15,-108,-130,40),
(E'resource-native-1286-711-63401',1,16,-108,-129,38),
(E'resource-native-1286-711-63401',1,17,-108,-128,34),
(E'resource-native-1286-711-63401',1,18,-108,-127,30),
(E'resource-native-1286-711-63401',1,19,-108,-126,26),
(E'resource-native-1286-711-63401',1,20,-108,-125,22),
(E'resource-native-1286-711-63401',1,21,-108,-124,18),
(E'resource-native-1286-711-63401',1,22,-108,-123,16),
(E'resource-native-1286-711-63401',1,23,-108,-122,16),
(E'resource-native-1286-711-63401',1,24,-108,-108,-40),
(E'resource-native-1286-711-63401',1,25,-108,-107,-40),
(E'resource-native-1286-711-63401',1,26,-108,-106,-40),
(E'resource-native-1286-711-63401',1,27,-108,-105,-40),
(E'resource-native-1286-711-63401',1,28,-108,-104,-40),
(E'resource-native-1286-711-63401',1,29,-108,-101,-40),
(E'resource-native-1286-711-63401',1,30,-108,-100,-37),
(E'resource-native-1286-711-63401',1,31,-108,-99,-40),
(E'resource-native-1286-711-63401',1,32,-108,-98,-40),
(E'resource-native-1286-711-63401',1,33,-108,-97,-40),
(E'resource-native-1286-711-63401',1,34,-108,-77,-40),
(E'resource-native-1286-711-63401',1,35,-108,-76,-40),
(E'resource-native-1286-711-63401',1,36,-108,-75,-40),
(E'resource-native-1286-711-63401',1,37,-108,-74,-40);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1234-943-69601',1,-1234,0,282,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1234-943-69601',1,E'proposed',0),
(E'resource-native-1234-943-69601',1,E'active',1),
(E'resource-native-1234-943-69601',1,E'completed',2),
(E'resource-native-1234-943-69601',1,E'expired',2),
(E'resource-native-1234-943-69601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',-1234,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1234-943-69601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1234-943-69601',1,0,-224,-31,0),
(E'resource-native-1234-943-69601',1,1,-224,-30,0),
(E'resource-native-1234-943-69601',1,2,-224,-29,0),
(E'resource-native-1234-943-69601',1,3,-224,-28,0),
(E'resource-native-1234-943-69601',1,4,-223,-30,0),
(E'resource-native-1234-943-69601',1,5,-222,-30,0),
(E'resource-native-1234-943-69601',1,6,-221,-30,0),
(E'resource-native-1234-943-69601',1,7,-220,-30,0),
(E'resource-native-1234-943-69601',1,8,-219,-30,0),
(E'resource-native-1234-943-69601',1,9,-218,-30,0),
(E'resource-native-1234-943-69601',1,10,-217,-30,0),
(E'resource-native-1234-943-69601',1,11,-216,-30,0),
(E'resource-native-1234-943-69601',1,12,-215,-31,0),
(E'resource-native-1234-943-69601',1,13,-215,-30,0),
(E'resource-native-1234-943-69601',1,14,-215,-29,0),
(E'resource-native-1234-943-69601',1,15,-214,-32,0),
(E'resource-native-1234-943-69601',1,16,-214,-31,0),
(E'resource-native-1234-943-69601',1,17,-214,-30,0),
(E'resource-native-1234-943-69601',1,18,-214,-29,0),
(E'resource-native-1234-943-69601',1,19,-213,-50,16),
(E'resource-native-1234-943-69601',1,20,-213,-46,0),
(E'resource-native-1234-943-69601',1,21,-213,-45,0),
(E'resource-native-1234-943-69601',1,22,-213,-33,0),
(E'resource-native-1234-943-69601',1,23,-213,-32,0),
(E'resource-native-1234-943-69601',1,24,-213,-31,0),
(E'resource-native-1234-943-69601',1,25,-213,-30,0),
(E'resource-native-1234-943-69601',1,26,-213,-29,0),
(E'resource-native-1234-943-69601',1,27,-213,-28,0),
(E'resource-native-1234-943-69601',1,28,-213,-27,0),
(E'resource-native-1234-943-69601',1,29,-213,-26,2),
(E'resource-native-1234-943-69601',1,30,-212,-54,2),
(E'resource-native-1234-943-69601',1,31,-212,-53,0),
(E'resource-native-1234-943-69601',1,32,-212,-52,0),
(E'resource-native-1234-943-69601',1,33,-212,-46,0),
(E'resource-native-1234-943-69601',1,34,-212,-45,0),
(E'resource-native-1234-943-69601',1,35,-212,-44,0),
(E'resource-native-1234-943-69601',1,36,-212,-43,0),
(E'resource-native-1234-943-69601',1,37,-212,-33,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1230-943-69501',1,-1230,0,281,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1230-943-69501',1,E'proposed',0),
(E'resource-native-1230-943-69501',1,E'active',1),
(E'resource-native-1230-943-69501',1,E'completed',2),
(E'resource-native-1230-943-69501',1,E'expired',2),
(E'resource-native-1230-943-69501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',-1230,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1230-943-69501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1230-943-69501',1,0,-160,43,-30),
(E'resource-native-1230-943-69501',1,1,-160,44,-30),
(E'resource-native-1230-943-69501',1,2,-159,43,-30),
(E'resource-native-1230-943-69501',1,3,-159,44,-30),
(E'resource-native-1230-943-69501',1,4,-159,50,-30),
(E'resource-native-1230-943-69501',1,5,-159,51,-30),
(E'resource-native-1230-943-69501',1,6,-159,52,-30),
(E'resource-native-1230-943-69501',1,7,-159,53,-28),
(E'resource-native-1230-943-69501',1,8,-158,43,-30),
(E'resource-native-1230-943-69501',1,9,-158,44,-30),
(E'resource-native-1230-943-69501',1,10,-158,45,-30),
(E'resource-native-1230-943-69501',1,11,-158,47,-28),
(E'resource-native-1230-943-69501',1,12,-158,48,-30),
(E'resource-native-1230-943-69501',1,13,-158,49,-30),
(E'resource-native-1230-943-69501',1,14,-158,50,-30),
(E'resource-native-1230-943-69501',1,15,-158,51,-30),
(E'resource-native-1230-943-69501',1,16,-158,52,-30),
(E'resource-native-1230-943-69501',1,17,-158,53,-30),
(E'resource-native-1230-943-69501',1,18,-157,43,-30),
(E'resource-native-1230-943-69501',1,19,-157,44,-30),
(E'resource-native-1230-943-69501',1,20,-157,45,-30),
(E'resource-native-1230-943-69501',1,21,-157,46,-30),
(E'resource-native-1230-943-69501',1,22,-157,47,-30),
(E'resource-native-1230-943-69501',1,23,-157,48,-30),
(E'resource-native-1230-943-69501',1,24,-157,49,-30),
(E'resource-native-1230-943-69501',1,25,-157,50,-30),
(E'resource-native-1230-943-69501',1,26,-157,51,-30),
(E'resource-native-1230-943-69501',1,27,-157,52,-30),
(E'resource-native-1230-943-69501',1,28,-157,53,-30),
(E'resource-native-1230-943-69501',1,29,-156,43,-30),
(E'resource-native-1230-943-69501',1,30,-156,44,-30),
(E'resource-native-1230-943-69501',1,31,-156,45,-30),
(E'resource-native-1230-943-69501',1,32,-156,46,-30),
(E'resource-native-1230-943-69501',1,33,-156,47,-30),
(E'resource-native-1230-943-69501',1,34,-156,48,-30),
(E'resource-native-1230-943-69501',1,35,-156,49,-30),
(E'resource-native-1230-943-69501',1,36,-156,50,-30),
(E'resource-native-1230-943-69501',1,37,-156,51,-30);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1219-1264-89301',1,-1219,0,379,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1219-1264-89301',1,E'proposed',0),
(E'resource-native-1219-1264-89301',1,E'active',1),
(E'resource-native-1219-1264-89301',1,E'completed',2),
(E'resource-native-1219-1264-89301',1,E'expired',2),
(E'resource-native-1219-1264-89301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',-1219,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1219-1264-89301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1219-1264-89301',1,0,36,-24,0),
(E'resource-native-1219-1264-89301',1,1,36,-10,0),
(E'resource-native-1219-1264-89301',1,2,36,-9,0),
(E'resource-native-1219-1264-89301',1,3,36,-7,0),
(E'resource-native-1219-1264-89301',1,4,36,-6,0),
(E'resource-native-1219-1264-89301',1,5,36,-3,0),
(E'resource-native-1219-1264-89301',1,6,36,-2,0),
(E'resource-native-1219-1264-89301',1,7,36,-1,0),
(E'resource-native-1219-1264-89301',1,8,36,0,0),
(E'resource-native-1219-1264-89301',1,9,36,1,0),
(E'resource-native-1219-1264-89301',1,10,36,2,0),
(E'resource-native-1219-1264-89301',1,11,36,3,0),
(E'resource-native-1219-1264-89301',1,12,36,6,0),
(E'resource-native-1219-1264-89301',1,13,36,11,0),
(E'resource-native-1219-1264-89301',1,14,37,-25,0),
(E'resource-native-1219-1264-89301',1,15,37,-24,0),
(E'resource-native-1219-1264-89301',1,16,37,-23,0),
(E'resource-native-1219-1264-89301',1,17,37,-21,0),
(E'resource-native-1219-1264-89301',1,18,37,-13,16),
(E'resource-native-1219-1264-89301',1,19,37,-10,2),
(E'resource-native-1219-1264-89301',1,20,37,-9,2),
(E'resource-native-1219-1264-89301',1,21,37,-7,0),
(E'resource-native-1219-1264-89301',1,22,37,-6,0),
(E'resource-native-1219-1264-89301',1,23,37,-4,16),
(E'resource-native-1219-1264-89301',1,24,37,-2,0),
(E'resource-native-1219-1264-89301',1,25,37,-1,0),
(E'resource-native-1219-1264-89301',1,26,37,0,0),
(E'resource-native-1219-1264-89301',1,27,37,1,0),
(E'resource-native-1219-1264-89301',1,28,37,2,0),
(E'resource-native-1219-1264-89301',1,29,37,5,16),
(E'resource-native-1219-1264-89301',1,30,37,6,0),
(E'resource-native-1219-1264-89301',1,31,37,10,0),
(E'resource-native-1219-1264-89301',1,32,37,11,2),
(E'resource-native-1219-1264-89301',1,33,37,12,2),
(E'resource-native-1219-1264-89301',1,34,37,14,16),
(E'resource-native-1219-1264-89301',1,35,37,16,2),
(E'resource-native-1219-1264-89301',1,36,37,18,0),
(E'resource-native-1219-1264-89301',1,37,37,19,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1219-1264-89501',1,-1219,0,382,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1219-1264-89501',1,E'proposed',0),
(E'resource-native-1219-1264-89501',1,E'active',1),
(E'resource-native-1219-1264-89501',1,E'completed',2),
(E'resource-native-1219-1264-89501',1,E'expired',2),
(E'resource-native-1219-1264-89501',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',66,NULL,NULL),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',-1219,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1219-1264-89501',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1219-1264-89501',1,0,-126,-33,60),
(E'resource-native-1219-1264-89501',1,1,-126,-32,62),
(E'resource-native-1219-1264-89501',1,2,-126,-24,60),
(E'resource-native-1219-1264-89501',1,3,-126,-22,58),
(E'resource-native-1219-1264-89501',1,4,-126,-13,60),
(E'resource-native-1219-1264-89501',1,5,-126,-12,56),
(E'resource-native-1219-1264-89501',1,6,-126,19,60),
(E'resource-native-1219-1264-89501',1,7,-126,20,60),
(E'resource-native-1219-1264-89501',1,8,-126,21,64),
(E'resource-native-1219-1264-89501',1,9,-126,29,60),
(E'resource-native-1219-1264-89501',1,10,-126,30,60),
(E'resource-native-1219-1264-89501',1,11,-125,-33,60),
(E'resource-native-1219-1264-89501',1,12,-125,-32,60),
(E'resource-native-1219-1264-89501',1,13,-125,-31,60),
(E'resource-native-1219-1264-89501',1,14,-125,-30,60),
(E'resource-native-1219-1264-89501',1,15,-125,-29,60),
(E'resource-native-1219-1264-89501',1,16,-125,-24,60),
(E'resource-native-1219-1264-89501',1,17,-125,-23,60),
(E'resource-native-1219-1264-89501',1,18,-125,-22,60),
(E'resource-native-1219-1264-89501',1,19,-125,-16,60),
(E'resource-native-1219-1264-89501',1,20,-125,-15,62),
(E'resource-native-1219-1264-89501',1,21,-125,-14,60),
(E'resource-native-1219-1264-89501',1,22,-125,-13,60),
(E'resource-native-1219-1264-89501',1,23,-125,9,60),
(E'resource-native-1219-1264-89501',1,24,-125,10,62),
(E'resource-native-1219-1264-89501',1,25,-125,19,60),
(E'resource-native-1219-1264-89501',1,26,-125,20,60),
(E'resource-native-1219-1264-89501',1,27,-125,21,60),
(E'resource-native-1219-1264-89501',1,28,-125,22,60),
(E'resource-native-1219-1264-89501',1,29,-125,23,60),
(E'resource-native-1219-1264-89501',1,30,-125,24,64),
(E'resource-native-1219-1264-89501',1,31,-125,25,60),
(E'resource-native-1219-1264-89501',1,32,-125,26,60),
(E'resource-native-1219-1264-89501',1,33,-125,27,60),
(E'resource-native-1219-1264-89501',1,34,-125,28,60),
(E'resource-native-1219-1264-89501',1,35,-125,29,60),
(E'resource-native-1219-1264-89501',1,36,-125,30,60),
(E'resource-native-1219-1264-89501',1,37,-124,-33,60);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1203-923-69401',1,-1203,0,279,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1203-923-69401',1,E'proposed',0),
(E'resource-native-1203-923-69401',1,E'active',1),
(E'resource-native-1203-923-69401',1,E'completed',2),
(E'resource-native-1203-923-69401',1,E'expired',2),
(E'resource-native-1203-923-69401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',-1203,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1203-923-69401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1203-923-69401',1,0,-36,60,-20),
(E'resource-native-1203-923-69401',1,1,-36,61,-20),
(E'resource-native-1203-923-69401',1,2,-36,62,-20),
(E'resource-native-1203-923-69401',1,3,-36,63,-20),
(E'resource-native-1203-923-69401',1,4,-36,66,-20),
(E'resource-native-1203-923-69401',1,5,-36,67,-20),
(E'resource-native-1203-923-69401',1,6,-36,68,-16),
(E'resource-native-1203-923-69401',1,7,-36,83,-70),
(E'resource-native-1203-923-69401',1,8,-36,84,-70),
(E'resource-native-1203-923-69401',1,9,-36,85,-70),
(E'resource-native-1203-923-69401',1,10,-36,86,-69),
(E'resource-native-1203-923-69401',1,11,-36,87,-67),
(E'resource-native-1203-923-69401',1,12,-36,88,-64),
(E'resource-native-1203-923-69401',1,13,-36,89,-70),
(E'resource-native-1203-923-69401',1,14,-35,60,-20),
(E'resource-native-1203-923-69401',1,15,-35,61,-20),
(E'resource-native-1203-923-69401',1,16,-35,62,-20),
(E'resource-native-1203-923-69401',1,17,-35,63,-20),
(E'resource-native-1203-923-69401',1,18,-35,64,-19),
(E'resource-native-1203-923-69401',1,19,-35,65,-20),
(E'resource-native-1203-923-69401',1,20,-35,66,-20),
(E'resource-native-1203-923-69401',1,21,-35,67,-20),
(E'resource-native-1203-923-69401',1,22,-35,68,-20),
(E'resource-native-1203-923-69401',1,23,-35,83,-70),
(E'resource-native-1203-923-69401',1,24,-35,84,-70),
(E'resource-native-1203-923-69401',1,25,-35,85,-70),
(E'resource-native-1203-923-69401',1,26,-35,86,-70),
(E'resource-native-1203-923-69401',1,27,-35,87,-70),
(E'resource-native-1203-923-69401',1,28,-35,88,-70),
(E'resource-native-1203-923-69401',1,29,-35,89,-70),
(E'resource-native-1203-923-69401',1,30,-34,48,-32),
(E'resource-native-1203-923-69401',1,31,-34,49,-36),
(E'resource-native-1203-923-69401',1,32,-34,51,-39),
(E'resource-native-1203-923-69401',1,33,-34,52,-39),
(E'resource-native-1203-923-69401',1,34,-34,53,-39),
(E'resource-native-1203-923-69401',1,35,-34,60,-20),
(E'resource-native-1203-923-69401',1,36,-34,61,-20),
(E'resource-native-1203-923-69401',1,37,-34,62,-20);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1191-922-69301',1,-1191,0,277,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1191-922-69301',1,E'proposed',0),
(E'resource-native-1191-922-69301',1,E'active',1),
(E'resource-native-1191-922-69301',1,E'completed',2),
(E'resource-native-1191-922-69301',1,E'expired',2),
(E'resource-native-1191-922-69301',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',-1191,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1191-922-69301',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1191-922-69301',1,0,-36,60,-20),
(E'resource-native-1191-922-69301',1,1,-36,61,-20),
(E'resource-native-1191-922-69301',1,2,-36,62,-20),
(E'resource-native-1191-922-69301',1,3,-36,63,-20),
(E'resource-native-1191-922-69301',1,4,-36,66,-20),
(E'resource-native-1191-922-69301',1,5,-36,67,-20),
(E'resource-native-1191-922-69301',1,6,-36,68,-16),
(E'resource-native-1191-922-69301',1,7,-36,83,-70),
(E'resource-native-1191-922-69301',1,8,-36,84,-70),
(E'resource-native-1191-922-69301',1,9,-36,85,-70),
(E'resource-native-1191-922-69301',1,10,-36,86,-69),
(E'resource-native-1191-922-69301',1,11,-36,87,-67),
(E'resource-native-1191-922-69301',1,12,-36,88,-64),
(E'resource-native-1191-922-69301',1,13,-36,89,-70),
(E'resource-native-1191-922-69301',1,14,-36,90,-77),
(E'resource-native-1191-922-69301',1,15,-36,91,-76),
(E'resource-native-1191-922-69301',1,16,-36,92,-77),
(E'resource-native-1191-922-69301',1,17,-36,93,-76),
(E'resource-native-1191-922-69301',1,18,-36,94,-76),
(E'resource-native-1191-922-69301',1,19,-36,95,-76),
(E'resource-native-1191-922-69301',1,20,-36,96,-77),
(E'resource-native-1191-922-69301',1,21,-36,97,-77),
(E'resource-native-1191-922-69301',1,22,-36,106,-77),
(E'resource-native-1191-922-69301',1,23,-36,107,-77),
(E'resource-native-1191-922-69301',1,24,-35,60,-20),
(E'resource-native-1191-922-69301',1,25,-35,61,-20),
(E'resource-native-1191-922-69301',1,26,-35,62,-20),
(E'resource-native-1191-922-69301',1,27,-35,63,-20),
(E'resource-native-1191-922-69301',1,28,-35,64,-19),
(E'resource-native-1191-922-69301',1,29,-35,65,-20),
(E'resource-native-1191-922-69301',1,30,-35,66,-20),
(E'resource-native-1191-922-69301',1,31,-35,67,-20),
(E'resource-native-1191-922-69301',1,32,-35,68,-20),
(E'resource-native-1191-922-69301',1,33,-35,83,-70),
(E'resource-native-1191-922-69301',1,34,-35,84,-70),
(E'resource-native-1191-922-69301',1,35,-35,85,-70),
(E'resource-native-1191-922-69301',1,36,-35,86,-70),
(E'resource-native-1191-922-69301',1,37,-35,87,-70);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1179-999-82201',1,-1179,0,330,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1179-999-82201',1,E'proposed',0),
(E'resource-native-1179-999-82201',1,E'active',1),
(E'resource-native-1179-999-82201',1,E'completed',2),
(E'resource-native-1179-999-82201',1,E'expired',2),
(E'resource-native-1179-999-82201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',171,NULL,NULL),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',-1179,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1179-999-82201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1179-999-82201',1,0,-96,-62,-49),
(E'resource-native-1179-999-82201',1,1,-96,-61,-50),
(E'resource-native-1179-999-82201',1,2,-96,-60,-50),
(E'resource-native-1179-999-82201',1,3,-96,-59,-50),
(E'resource-native-1179-999-82201',1,4,-96,-58,-50),
(E'resource-native-1179-999-82201',1,5,-96,-57,-50),
(E'resource-native-1179-999-82201',1,6,-96,-56,-50),
(E'resource-native-1179-999-82201',1,7,-95,-62,-50),
(E'resource-native-1179-999-82201',1,8,-95,-61,-50),
(E'resource-native-1179-999-82201',1,9,-95,-60,-50),
(E'resource-native-1179-999-82201',1,10,-95,-59,-50),
(E'resource-native-1179-999-82201',1,11,-95,-58,-50),
(E'resource-native-1179-999-82201',1,12,-95,-57,-50),
(E'resource-native-1179-999-82201',1,13,-95,-56,-50),
(E'resource-native-1179-999-82201',1,14,-94,-68,-42),
(E'resource-native-1179-999-82201',1,15,-94,-67,-42),
(E'resource-native-1179-999-82201',1,16,-94,-66,-42),
(E'resource-native-1179-999-82201',1,17,-94,-65,-42),
(E'resource-native-1179-999-82201',1,18,-94,-64,-42),
(E'resource-native-1179-999-82201',1,19,-94,-60,-50),
(E'resource-native-1179-999-82201',1,20,-94,-59,-50),
(E'resource-native-1179-999-82201',1,21,-94,-57,-50),
(E'resource-native-1179-999-82201',1,22,-94,-56,-50),
(E'resource-native-1179-999-82201',1,23,-94,-52,100),
(E'resource-native-1179-999-82201',1,24,-93,-68,-42),
(E'resource-native-1179-999-82201',1,25,-93,-67,-42),
(E'resource-native-1179-999-82201',1,26,-93,-66,-42),
(E'resource-native-1179-999-82201',1,27,-93,-65,-42),
(E'resource-native-1179-999-82201',1,28,-93,-64,-44),
(E'resource-native-1179-999-82201',1,29,-93,-63,-50),
(E'resource-native-1179-999-82201',1,30,-93,-62,-50),
(E'resource-native-1179-999-82201',1,31,-93,-60,-50),
(E'resource-native-1179-999-82201',1,32,-93,-59,-50),
(E'resource-native-1179-999-82201',1,33,-93,-58,-50),
(E'resource-native-1179-999-82201',1,34,-93,-57,-50),
(E'resource-native-1179-999-82201',1,35,-93,-56,-50),
(E'resource-native-1179-999-82201',1,36,-92,-68,-46),
(E'resource-native-1179-999-82201',1,37,-92,-67,-46);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1145-1123-80101',1,-1145,0,311,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1145-1123-80101',1,E'proposed',0),
(E'resource-native-1145-1123-80101',1,E'active',1),
(E'resource-native-1145-1123-80101',1,E'completed',2),
(E'resource-native-1145-1123-80101',1,E'expired',2),
(E'resource-native-1145-1123-80101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',-1145,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1145-1123-80101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1145-1123-80101',1,0,-89,-6,40),
(E'resource-native-1145-1123-80101',1,1,-89,3,44),
(E'resource-native-1145-1123-80101',1,2,-89,4,40),
(E'resource-native-1145-1123-80101',1,3,-89,5,40),
(E'resource-native-1145-1123-80101',1,4,-88,-7,46),
(E'resource-native-1145-1123-80101',1,5,-88,-6,40),
(E'resource-native-1145-1123-80101',1,6,-88,-5,42),
(E'resource-native-1145-1123-80101',1,7,-88,-4,40),
(E'resource-native-1145-1123-80101',1,8,-88,3,40),
(E'resource-native-1145-1123-80101',1,9,-88,4,40),
(E'resource-native-1145-1123-80101',1,10,-88,5,40),
(E'resource-native-1145-1123-80101',1,11,-88,6,42),
(E'resource-native-1145-1123-80101',1,12,-88,7,44),
(E'resource-native-1145-1123-80101',1,13,-88,8,40),
(E'resource-native-1145-1123-80101',1,14,-88,9,41),
(E'resource-native-1145-1123-80101',1,15,-88,10,43),
(E'resource-native-1145-1123-80101',1,16,-88,11,40),
(E'resource-native-1145-1123-80101',1,17,-88,17,43),
(E'resource-native-1145-1123-80101',1,18,-88,21,40),
(E'resource-native-1145-1123-80101',1,19,-87,-7,42),
(E'resource-native-1145-1123-80101',1,20,-87,-6,40),
(E'resource-native-1145-1123-80101',1,21,-87,-5,40),
(E'resource-native-1145-1123-80101',1,22,-87,-4,40),
(E'resource-native-1145-1123-80101',1,23,-87,-3,40),
(E'resource-native-1145-1123-80101',1,24,-87,-2,44),
(E'resource-native-1145-1123-80101',1,25,-87,-1,42),
(E'resource-native-1145-1123-80101',1,26,-87,2,40),
(E'resource-native-1145-1123-80101',1,27,-87,3,40),
(E'resource-native-1145-1123-80101',1,28,-87,4,40),
(E'resource-native-1145-1123-80101',1,29,-87,5,40),
(E'resource-native-1145-1123-80101',1,30,-87,6,40),
(E'resource-native-1145-1123-80101',1,31,-87,7,41),
(E'resource-native-1145-1123-80101',1,32,-87,8,40),
(E'resource-native-1145-1123-80101',1,33,-87,9,40),
(E'resource-native-1145-1123-80101',1,34,-87,10,40),
(E'resource-native-1145-1123-80101',1,35,-87,11,40),
(E'resource-native-1145-1123-80101',1,36,-87,12,40),
(E'resource-native-1145-1123-80101',1,37,-87,17,41);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1144-1122-80001',1,-1144,0,310,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1144-1122-80001',1,E'proposed',0),
(E'resource-native-1144-1122-80001',1,E'active',1),
(E'resource-native-1144-1122-80001',1,E'completed',2),
(E'resource-native-1144-1122-80001',1,E'expired',2),
(E'resource-native-1144-1122-80001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',-1144,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1144-1122-80001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1144-1122-80001',1,0,36,-72,50),
(E'resource-native-1144-1122-80001',1,1,36,-71,50),
(E'resource-native-1144-1122-80001',1,2,36,-69,51),
(E'resource-native-1144-1122-80001',1,3,36,-61,54),
(E'resource-native-1144-1122-80001',1,4,36,-60,54),
(E'resource-native-1144-1122-80001',1,5,36,-58,50),
(E'resource-native-1144-1122-80001',1,6,36,-57,50),
(E'resource-native-1144-1122-80001',1,7,37,-143,60),
(E'resource-native-1144-1122-80001',1,8,37,-142,63),
(E'resource-native-1144-1122-80001',1,9,37,-141,57),
(E'resource-native-1144-1122-80001',1,10,37,-140,53),
(E'resource-native-1144-1122-80001',1,11,37,-139,50),
(E'resource-native-1144-1122-80001',1,12,37,-133,53),
(E'resource-native-1144-1122-80001',1,13,37,-132,50),
(E'resource-native-1144-1122-80001',1,14,37,-130,52),
(E'resource-native-1144-1122-80001',1,15,37,-102,55),
(E'resource-native-1144-1122-80001',1,16,37,-101,52),
(E'resource-native-1144-1122-80001',1,17,37,-97,50),
(E'resource-native-1144-1122-80001',1,18,37,-94,57),
(E'resource-native-1144-1122-80001',1,19,37,-91,54),
(E'resource-native-1144-1122-80001',1,20,37,-90,56),
(E'resource-native-1144-1122-80001',1,21,37,-88,50),
(E'resource-native-1144-1122-80001',1,22,37,-87,53),
(E'resource-native-1144-1122-80001',1,23,37,-77,50),
(E'resource-native-1144-1122-80001',1,24,37,-76,50),
(E'resource-native-1144-1122-80001',1,25,37,-71,50),
(E'resource-native-1144-1122-80001',1,26,37,-70,54),
(E'resource-native-1144-1122-80001',1,27,37,-69,54),
(E'resource-native-1144-1122-80001',1,28,37,-68,50),
(E'resource-native-1144-1122-80001',1,29,37,-67,50),
(E'resource-native-1144-1122-80001',1,30,37,-66,50),
(E'resource-native-1144-1122-80001',1,31,37,-65,50),
(E'resource-native-1144-1122-80001',1,32,37,-61,54),
(E'resource-native-1144-1122-80001',1,33,37,-60,54),
(E'resource-native-1144-1122-80001',1,34,37,-59,50),
(E'resource-native-1144-1122-80001',1,35,37,-58,50),
(E'resource-native-1144-1122-80001',1,36,37,-57,50),
(E'resource-native-1144-1122-80001',1,37,38,-142,60);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1144-1264-89401',1,-1144,0,386,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1144-1264-89401',1,E'proposed',0),
(E'resource-native-1144-1264-89401',1,E'active',1),
(E'resource-native-1144-1264-89401',1,E'completed',2),
(E'resource-native-1144-1264-89401',1,E'expired',2),
(E'resource-native-1144-1264-89401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',-1144,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1144-1264-89401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1144-1264-89401',1,0,-54,80,2),
(E'resource-native-1144-1264-89401',1,1,-54,81,2),
(E'resource-native-1144-1264-89401',1,2,-54,82,2),
(E'resource-native-1144-1264-89401',1,3,-53,80,1),
(E'resource-native-1144-1264-89401',1,4,-53,81,1),
(E'resource-native-1144-1264-89401',1,5,-53,82,1),
(E'resource-native-1144-1264-89401',1,6,-52,80,0),
(E'resource-native-1144-1264-89401',1,7,-52,81,0),
(E'resource-native-1144-1264-89401',1,8,-52,82,0),
(E'resource-native-1144-1264-89401',1,9,-51,80,0),
(E'resource-native-1144-1264-89401',1,10,-51,81,0),
(E'resource-native-1144-1264-89401',1,11,-51,82,0),
(E'resource-native-1144-1264-89401',1,12,-51,88,0),
(E'resource-native-1144-1264-89401',1,13,-51,92,0),
(E'resource-native-1144-1264-89401',1,14,-51,93,0),
(E'resource-native-1144-1264-89401',1,15,-51,94,2),
(E'resource-native-1144-1264-89401',1,16,-50,76,0),
(E'resource-native-1144-1264-89401',1,17,-50,77,0),
(E'resource-native-1144-1264-89401',1,18,-50,78,0),
(E'resource-native-1144-1264-89401',1,19,-50,79,0),
(E'resource-native-1144-1264-89401',1,20,-50,80,0),
(E'resource-native-1144-1264-89401',1,21,-50,81,0),
(E'resource-native-1144-1264-89401',1,22,-50,82,0),
(E'resource-native-1144-1264-89401',1,23,-50,84,0),
(E'resource-native-1144-1264-89401',1,24,-50,85,0),
(E'resource-native-1144-1264-89401',1,25,-50,86,2),
(E'resource-native-1144-1264-89401',1,26,-50,88,0),
(E'resource-native-1144-1264-89401',1,27,-50,92,0),
(E'resource-native-1144-1264-89401',1,28,-50,94,0),
(E'resource-native-1144-1264-89401',1,29,-50,95,0),
(E'resource-native-1144-1264-89401',1,30,-50,96,0),
(E'resource-native-1144-1264-89401',1,31,-49,76,0),
(E'resource-native-1144-1264-89401',1,32,-49,77,0),
(E'resource-native-1144-1264-89401',1,33,-49,78,0),
(E'resource-native-1144-1264-89401',1,34,-49,79,0),
(E'resource-native-1144-1264-89401',1,35,-49,80,0),
(E'resource-native-1144-1264-89401',1,36,-49,81,0),
(E'resource-native-1144-1264-89401',1,37,-49,82,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1143-1122-79801',1,-1143,0,309,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1143-1122-79801',1,E'proposed',0),
(E'resource-native-1143-1122-79801',1,E'active',1),
(E'resource-native-1143-1122-79801',1,E'completed',2),
(E'resource-native-1143-1122-79801',1,E'expired',2),
(E'resource-native-1143-1122-79801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',156,NULL,NULL),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',-1143,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1143-1122-79801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1143-1122-79801',1,0,-35,-33,0),
(E'resource-native-1143-1122-79801',1,1,-35,-32,0),
(E'resource-native-1143-1122-79801',1,2,-35,-31,-2),
(E'resource-native-1143-1122-79801',1,3,-35,-30,-2),
(E'resource-native-1143-1122-79801',1,4,-35,-29,-2),
(E'resource-native-1143-1122-79801',1,5,-35,-28,4),
(E'resource-native-1143-1122-79801',1,6,-35,-27,2),
(E'resource-native-1143-1122-79801',1,7,-35,-26,0),
(E'resource-native-1143-1122-79801',1,8,-35,-25,0),
(E'resource-native-1143-1122-79801',1,9,-35,-17,7),
(E'resource-native-1143-1122-79801',1,10,-35,-15,4),
(E'resource-native-1143-1122-79801',1,11,-35,-14,4),
(E'resource-native-1143-1122-79801',1,12,-35,-12,0),
(E'resource-native-1143-1122-79801',1,13,-35,-5,3),
(E'resource-native-1143-1122-79801',1,14,-35,-4,0),
(E'resource-native-1143-1122-79801',1,15,-34,-32,0),
(E'resource-native-1143-1122-79801',1,16,-34,-31,0),
(E'resource-native-1143-1122-79801',1,17,-34,-30,0),
(E'resource-native-1143-1122-79801',1,18,-34,-29,0),
(E'resource-native-1143-1122-79801',1,19,-34,-28,4),
(E'resource-native-1143-1122-79801',1,20,-34,-27,4),
(E'resource-native-1143-1122-79801',1,21,-34,-26,0),
(E'resource-native-1143-1122-79801',1,22,-34,-25,0),
(E'resource-native-1143-1122-79801',1,23,-34,-17,4),
(E'resource-native-1143-1122-79801',1,24,-34,-16,4),
(E'resource-native-1143-1122-79801',1,25,-34,-15,4),
(E'resource-native-1143-1122-79801',1,26,-34,-14,4),
(E'resource-native-1143-1122-79801',1,27,-34,-13,0),
(E'resource-native-1143-1122-79801',1,28,-34,-12,0),
(E'resource-native-1143-1122-79801',1,29,-34,-6,0),
(E'resource-native-1143-1122-79801',1,30,-34,-5,0),
(E'resource-native-1143-1122-79801',1,31,-34,-4,0),
(E'resource-native-1143-1122-79801',1,32,-34,-3,0),
(E'resource-native-1143-1122-79801',1,33,-33,-31,0),
(E'resource-native-1143-1122-79801',1,34,-33,-30,0),
(E'resource-native-1143-1122-79801',1,35,-33,-29,0),
(E'resource-native-1143-1122-79801',1,36,-33,-28,1),
(E'resource-native-1143-1122-79801',1,37,-33,-27,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1116-1124-81101',1,-1116,0,317,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1116-1124-81101',1,E'proposed',0),
(E'resource-native-1116-1124-81101',1,E'active',1),
(E'resource-native-1116-1124-81101',1,E'completed',2),
(E'resource-native-1116-1124-81101',1,E'expired',2),
(E'resource-native-1116-1124-81101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',186,NULL,NULL),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',-1116,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1116-1124-81101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1116-1124-81101',1,0,-53,-98,61),
(E'resource-native-1116-1124-81101',1,1,-52,-98,64),
(E'resource-native-1116-1124-81101',1,2,-52,-97,60),
(E'resource-native-1116-1124-81101',1,3,-52,-96,60),
(E'resource-native-1116-1124-81101',1,4,-52,-95,64),
(E'resource-native-1116-1124-81101',1,5,-52,-94,63),
(E'resource-native-1116-1124-81101',1,6,-52,-93,60),
(E'resource-native-1116-1124-81101',1,7,-52,-92,60),
(E'resource-native-1116-1124-81101',1,8,-51,-97,60),
(E'resource-native-1116-1124-81101',1,9,-51,-96,60),
(E'resource-native-1116-1124-81101',1,10,-51,-95,60),
(E'resource-native-1116-1124-81101',1,11,-51,-94,60),
(E'resource-native-1116-1124-81101',1,12,-51,-93,60),
(E'resource-native-1116-1124-81101',1,13,-51,-92,60),
(E'resource-native-1116-1124-81101',1,14,-51,-91,60),
(E'resource-native-1116-1124-81101',1,15,-50,-103,60),
(E'resource-native-1116-1124-81101',1,16,-50,-102,60),
(E'resource-native-1116-1124-81101',1,17,-50,-101,60),
(E'resource-native-1116-1124-81101',1,18,-50,-100,60),
(E'resource-native-1116-1124-81101',1,19,-50,-96,60),
(E'resource-native-1116-1124-81101',1,20,-50,-95,60),
(E'resource-native-1116-1124-81101',1,21,-50,-94,60),
(E'resource-native-1116-1124-81101',1,22,-50,-93,60),
(E'resource-native-1116-1124-81101',1,23,-50,-92,60),
(E'resource-native-1116-1124-81101',1,24,-49,-103,60),
(E'resource-native-1116-1124-81101',1,25,-49,-102,60),
(E'resource-native-1116-1124-81101',1,26,-49,-101,60),
(E'resource-native-1116-1124-81101',1,27,-49,-100,60),
(E'resource-native-1116-1124-81101',1,28,-49,-99,60),
(E'resource-native-1116-1124-81101',1,29,-49,-96,60),
(E'resource-native-1116-1124-81101',1,30,-49,-95,60),
(E'resource-native-1116-1124-81101',1,31,-49,-94,60),
(E'resource-native-1116-1124-81101',1,32,-49,-93,60),
(E'resource-native-1116-1124-81101',1,33,-49,-92,60),
(E'resource-native-1116-1124-81101',1,34,-48,-105,60),
(E'resource-native-1116-1124-81101',1,35,-48,-104,60),
(E'resource-native-1116-1124-81101',1,36,-48,-103,60),
(E'resource-native-1116-1124-81101',1,37,-48,-102,60);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1097-1120-80601',1,-1097,0,314,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1097-1120-80601',1,E'proposed',0),
(E'resource-native-1097-1120-80601',1,E'active',1),
(E'resource-native-1097-1120-80601',1,E'completed',2),
(E'resource-native-1097-1120-80601',1,E'expired',2),
(E'resource-native-1097-1120-80601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',126,NULL,NULL),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',-1097,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1097-1120-80601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1097-1120-80601',1,0,-197,19,4),
(E'resource-native-1097-1120-80601',1,1,-197,20,4),
(E'resource-native-1097-1120-80601',1,2,-197,21,4),
(E'resource-native-1097-1120-80601',1,3,-197,22,0),
(E'resource-native-1097-1120-80601',1,4,-197,23,0),
(E'resource-native-1097-1120-80601',1,5,-197,24,0),
(E'resource-native-1097-1120-80601',1,6,-197,25,0),
(E'resource-native-1097-1120-80601',1,7,-197,26,0),
(E'resource-native-1097-1120-80601',1,8,-196,7,8),
(E'resource-native-1097-1120-80601',1,9,-196,8,4),
(E'resource-native-1097-1120-80601',1,10,-196,9,0),
(E'resource-native-1097-1120-80601',1,11,-196,10,0),
(E'resource-native-1097-1120-80601',1,12,-196,20,4),
(E'resource-native-1097-1120-80601',1,13,-196,21,2),
(E'resource-native-1097-1120-80601',1,14,-196,22,0),
(E'resource-native-1097-1120-80601',1,15,-196,23,0),
(E'resource-native-1097-1120-80601',1,16,-196,24,0),
(E'resource-native-1097-1120-80601',1,17,-196,25,0),
(E'resource-native-1097-1120-80601',1,18,-196,26,0),
(E'resource-native-1097-1120-80601',1,19,-195,7,8),
(E'resource-native-1097-1120-80601',1,20,-195,8,8),
(E'resource-native-1097-1120-80601',1,21,-195,9,0),
(E'resource-native-1097-1120-80601',1,22,-195,11,0),
(E'resource-native-1097-1120-80601',1,23,-195,12,0),
(E'resource-native-1097-1120-80601',1,24,-195,13,0),
(E'resource-native-1097-1120-80601',1,25,-195,14,0),
(E'resource-native-1097-1120-80601',1,26,-195,15,0),
(E'resource-native-1097-1120-80601',1,27,-195,20,0),
(E'resource-native-1097-1120-80601',1,28,-195,21,0),
(E'resource-native-1097-1120-80601',1,29,-195,22,0),
(E'resource-native-1097-1120-80601',1,30,-195,23,0),
(E'resource-native-1097-1120-80601',1,31,-195,24,0),
(E'resource-native-1097-1120-80601',1,32,-195,25,0),
(E'resource-native-1097-1120-80601',1,33,-195,26,0),
(E'resource-native-1097-1120-80601',1,34,-194,2,16),
(E'resource-native-1097-1120-80601',1,35,-194,3,12),
(E'resource-native-1097-1120-80601',1,36,-194,4,8),
(E'resource-native-1097-1120-80601',1,37,-194,5,8);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1096-1120-79401',1,-1096,0,308,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1096-1120-79401',1,E'proposed',0),
(E'resource-native-1096-1120-79401',1,E'active',1),
(E'resource-native-1096-1120-79401',1,E'completed',2),
(E'resource-native-1096-1120-79401',1,E'expired',2),
(E'resource-native-1096-1120-79401',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',111,NULL,NULL),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',-1096,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1096-1120-79401',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1096-1120-79401',1,0,-88,-11,0),
(E'resource-native-1096-1120-79401',1,1,-88,-10,0),
(E'resource-native-1096-1120-79401',1,2,-88,-9,0),
(E'resource-native-1096-1120-79401',1,3,-88,-8,0),
(E'resource-native-1096-1120-79401',1,4,-88,-7,0),
(E'resource-native-1096-1120-79401',1,5,-88,-6,0),
(E'resource-native-1096-1120-79401',1,6,-88,-5,4),
(E'resource-native-1096-1120-79401',1,7,-88,-4,2),
(E'resource-native-1096-1120-79401',1,8,-87,-33,8),
(E'resource-native-1096-1120-79401',1,9,-87,-32,8),
(E'resource-native-1096-1120-79401',1,10,-87,-31,6),
(E'resource-native-1096-1120-79401',1,11,-87,-30,5),
(E'resource-native-1096-1120-79401',1,12,-87,-17,6),
(E'resource-native-1096-1120-79401',1,13,-87,-16,4),
(E'resource-native-1096-1120-79401',1,14,-87,-15,4),
(E'resource-native-1096-1120-79401',1,15,-87,-14,2),
(E'resource-native-1096-1120-79401',1,16,-87,-11,0),
(E'resource-native-1096-1120-79401',1,17,-87,-10,0),
(E'resource-native-1096-1120-79401',1,18,-87,-9,0),
(E'resource-native-1096-1120-79401',1,19,-87,-8,0),
(E'resource-native-1096-1120-79401',1,20,-87,-7,0),
(E'resource-native-1096-1120-79401',1,21,-87,-6,0),
(E'resource-native-1096-1120-79401',1,22,-87,-5,4),
(E'resource-native-1096-1120-79401',1,23,-87,-4,4),
(E'resource-native-1096-1120-79401',1,24,-86,-34,8),
(E'resource-native-1096-1120-79401',1,25,-86,-33,8),
(E'resource-native-1096-1120-79401',1,26,-86,-32,8),
(E'resource-native-1096-1120-79401',1,27,-86,-31,8),
(E'resource-native-1096-1120-79401',1,28,-86,-30,5),
(E'resource-native-1096-1120-79401',1,29,-86,-17,4),
(E'resource-native-1096-1120-79401',1,30,-86,-16,4),
(E'resource-native-1096-1120-79401',1,31,-86,-15,4),
(E'resource-native-1096-1120-79401',1,32,-86,-14,4),
(E'resource-native-1096-1120-79401',1,33,-86,-12,0),
(E'resource-native-1096-1120-79401',1,34,-86,-11,0),
(E'resource-native-1096-1120-79401',1,35,-86,-10,0),
(E'resource-native-1096-1120-79401',1,36,-86,-9,0),
(E'resource-native-1096-1120-79401',1,37,-86,-8,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1095-1119-78701',1,-1095,0,306,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1095-1119-78701',1,E'proposed',0),
(E'resource-native-1095-1119-78701',1,E'active',1),
(E'resource-native-1095-1119-78701',1,E'completed',2),
(E'resource-native-1095-1119-78701',1,E'expired',2),
(E'resource-native-1095-1119-78701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',81,NULL,NULL),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',-1095,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1095-1119-78701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1095-1119-78701',1,0,-108,5,8),
(E'resource-native-1095-1119-78701',1,1,-108,6,11),
(E'resource-native-1095-1119-78701',1,2,-108,7,8),
(E'resource-native-1095-1119-78701',1,3,-107,-12,8),
(E'resource-native-1095-1119-78701',1,4,-107,-10,10),
(E'resource-native-1095-1119-78701',1,5,-107,-9,10),
(E'resource-native-1095-1119-78701',1,6,-107,-8,8),
(E'resource-native-1095-1119-78701',1,7,-107,-7,8),
(E'resource-native-1095-1119-78701',1,8,-107,3,8),
(E'resource-native-1095-1119-78701',1,9,-107,4,8),
(E'resource-native-1095-1119-78701',1,10,-107,5,8),
(E'resource-native-1095-1119-78701',1,11,-107,6,8),
(E'resource-native-1095-1119-78701',1,12,-107,7,8),
(E'resource-native-1095-1119-78701',1,13,-107,8,8),
(E'resource-native-1095-1119-78701',1,14,-107,9,9),
(E'resource-native-1095-1119-78701',1,15,-107,10,4),
(E'resource-native-1095-1119-78701',1,16,-106,-12,8),
(E'resource-native-1095-1119-78701',1,17,-106,-11,8),
(E'resource-native-1095-1119-78701',1,18,-106,-10,8),
(E'resource-native-1095-1119-78701',1,19,-106,-8,8),
(E'resource-native-1095-1119-78701',1,20,-106,-6,8),
(E'resource-native-1095-1119-78701',1,21,-106,-3,8),
(E'resource-native-1095-1119-78701',1,22,-106,2,8),
(E'resource-native-1095-1119-78701',1,23,-106,3,8),
(E'resource-native-1095-1119-78701',1,24,-106,4,8),
(E'resource-native-1095-1119-78701',1,25,-106,5,8),
(E'resource-native-1095-1119-78701',1,26,-106,6,8),
(E'resource-native-1095-1119-78701',1,27,-106,7,8),
(E'resource-native-1095-1119-78701',1,28,-106,9,5),
(E'resource-native-1095-1119-78701',1,29,-106,10,4),
(E'resource-native-1095-1119-78701',1,30,-105,-12,8),
(E'resource-native-1095-1119-78701',1,31,-105,-10,8),
(E'resource-native-1095-1119-78701',1,32,-105,-9,8),
(E'resource-native-1095-1119-78701',1,33,-105,-8,8),
(E'resource-native-1095-1119-78701',1,34,-105,-7,8),
(E'resource-native-1095-1119-78701',1,35,-105,-6,8),
(E'resource-native-1095-1119-78701',1,36,-105,-4,8),
(E'resource-native-1095-1119-78701',1,37,-105,-3,8);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-1094-1118-78601',1,-1094,0,304,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-1094-1118-78601',1,E'proposed',0),
(E'resource-native-1094-1118-78601',1,E'active',1),
(E'resource-native-1094-1118-78601',1,E'completed',2),
(E'resource-native-1094-1118-78601',1,E'expired',2),
(E'resource-native-1094-1118-78601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',51,NULL,NULL),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',-1094,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-1094-1118-78601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-1094-1118-78601',1,0,-37,-20,69),
(E'resource-native-1094-1118-78601',1,1,-36,-35,69),
(E'resource-native-1094-1118-78601',1,2,-36,3,69),
(E'resource-native-1094-1118-78601',1,3,-35,-66,69),
(E'resource-native-1094-1118-78601',1,4,-35,-64,69),
(E'resource-native-1094-1118-78601',1,5,-35,-35,69),
(E'resource-native-1094-1118-78601',1,6,-35,-29,0),
(E'resource-native-1094-1118-78601',1,7,-35,-28,0),
(E'resource-native-1094-1118-78601',1,8,-35,-24,0),
(E'resource-native-1094-1118-78601',1,9,-35,4,69),
(E'resource-native-1094-1118-78601',1,10,-34,-67,69),
(E'resource-native-1094-1118-78601',1,11,-34,-66,69),
(E'resource-native-1094-1118-78601',1,12,-34,-62,69),
(E'resource-native-1094-1118-78601',1,13,-34,-58,69),
(E'resource-native-1094-1118-78601',1,14,-34,-35,69),
(E'resource-native-1094-1118-78601',1,15,-34,-30,0),
(E'resource-native-1094-1118-78601',1,16,-34,-29,0),
(E'resource-native-1094-1118-78601',1,17,-34,-28,0),
(E'resource-native-1094-1118-78601',1,18,-34,-27,0),
(E'resource-native-1094-1118-78601',1,19,-34,-24,0),
(E'resource-native-1094-1118-78601',1,20,-34,4,69),
(E'resource-native-1094-1118-78601',1,21,-33,-68,69),
(E'resource-native-1094-1118-78601',1,22,-33,-60,69),
(E'resource-native-1094-1118-78601',1,23,-33,-57,0),
(E'resource-native-1094-1118-78601',1,24,-33,-56,0),
(E'resource-native-1094-1118-78601',1,25,-33,-55,0),
(E'resource-native-1094-1118-78601',1,26,-33,-50,0),
(E'resource-native-1094-1118-78601',1,27,-33,-49,0),
(E'resource-native-1094-1118-78601',1,28,-33,-48,0),
(E'resource-native-1094-1118-78601',1,29,-33,-45,69),
(E'resource-native-1094-1118-78601',1,30,-33,-35,69),
(E'resource-native-1094-1118-78601',1,31,-33,-30,0),
(E'resource-native-1094-1118-78601',1,32,-33,-29,0),
(E'resource-native-1094-1118-78601',1,33,-33,-28,0),
(E'resource-native-1094-1118-78601',1,34,-33,-27,0),
(E'resource-native-1094-1118-78601',1,35,-33,-26,0),
(E'resource-native-1094-1118-78601',1,36,-33,-25,0),
(E'resource-native-1094-1118-78601',1,37,-33,-24,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-991-527-75601',1,-991,0,299,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-991-527-75601',1,E'proposed',0),
(E'resource-native-991-527-75601',1,E'active',1),
(E'resource-native-991-527-75601',1,E'completed',2),
(E'resource-native-991-527-75601',1,E'expired',2),
(E'resource-native-991-527-75601',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',21,NULL,NULL),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',-991,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-991-527-75601',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-991-527-75601',1,0,-89,-122,20),
(E'resource-native-991-527-75601',1,1,-89,-121,20),
(E'resource-native-991-527-75601',1,2,-89,-120,20),
(E'resource-native-991-527-75601',1,3,-89,-119,24),
(E'resource-native-991-527-75601',1,4,-89,-118,20),
(E'resource-native-991-527-75601',1,5,-89,-117,18),
(E'resource-native-991-527-75601',1,6,-89,-111,20),
(E'resource-native-991-527-75601',1,7,-89,-110,20),
(E'resource-native-991-527-75601',1,8,-89,-109,18),
(E'resource-native-991-527-75601',1,9,-88,-125,20),
(E'resource-native-991-527-75601',1,10,-88,-124,20),
(E'resource-native-991-527-75601',1,11,-88,-123,20),
(E'resource-native-991-527-75601',1,12,-88,-122,20),
(E'resource-native-991-527-75601',1,13,-88,-121,20),
(E'resource-native-991-527-75601',1,14,-88,-120,20),
(E'resource-native-991-527-75601',1,15,-88,-118,20),
(E'resource-native-991-527-75601',1,16,-88,-117,20),
(E'resource-native-991-527-75601',1,17,-88,-114,20),
(E'resource-native-991-527-75601',1,18,-88,-113,20),
(E'resource-native-991-527-75601',1,19,-88,-112,24),
(E'resource-native-991-527-75601',1,20,-88,-110,20),
(E'resource-native-991-527-75601',1,21,-88,-109,20),
(E'resource-native-991-527-75601',1,22,-87,-125,20),
(E'resource-native-991-527-75601',1,23,-87,-124,20),
(E'resource-native-991-527-75601',1,24,-87,-123,20),
(E'resource-native-991-527-75601',1,25,-87,-122,20),
(E'resource-native-991-527-75601',1,26,-87,-121,20),
(E'resource-native-991-527-75601',1,27,-87,-120,20),
(E'resource-native-991-527-75601',1,28,-87,-119,20),
(E'resource-native-991-527-75601',1,29,-87,-118,20),
(E'resource-native-991-527-75601',1,30,-87,-117,20),
(E'resource-native-991-527-75601',1,31,-87,-116,20),
(E'resource-native-991-527-75601',1,32,-87,-115,20),
(E'resource-native-991-527-75601',1,33,-87,-114,20),
(E'resource-native-991-527-75601',1,34,-87,-113,20),
(E'resource-native-991-527-75601',1,35,-87,-112,20),
(E'resource-native-991-527-75601',1,36,-87,-111,20),
(E'resource-native-991-527-75601',1,37,-87,-110,24);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-991-527-75901',1,-991,0,301,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-991-527-75901',1,E'proposed',0),
(E'resource-native-991-527-75901',1,E'active',1),
(E'resource-native-991-527-75901',1,E'completed',2),
(E'resource-native-991-527-75901',1,E'expired',2),
(E'resource-native-991-527-75901',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',21,NULL,NULL),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',-991,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-991-527-75901',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-991-527-75901',1,0,18,73,0),
(E'resource-native-991-527-75901',1,1,18,74,0),
(E'resource-native-991-527-75901',1,2,18,75,0),
(E'resource-native-991-527-75901',1,3,18,76,0),
(E'resource-native-991-527-75901',1,4,18,77,0),
(E'resource-native-991-527-75901',1,5,18,78,0),
(E'resource-native-991-527-75901',1,6,18,79,0),
(E'resource-native-991-527-75901',1,7,18,80,0),
(E'resource-native-991-527-75901',1,8,18,81,0),
(E'resource-native-991-527-75901',1,9,18,82,0),
(E'resource-native-991-527-75901',1,10,18,83,0),
(E'resource-native-991-527-75901',1,11,18,84,0),
(E'resource-native-991-527-75901',1,12,18,85,0),
(E'resource-native-991-527-75901',1,13,18,86,0),
(E'resource-native-991-527-75901',1,14,18,87,0),
(E'resource-native-991-527-75901',1,15,18,88,0),
(E'resource-native-991-527-75901',1,16,18,89,0),
(E'resource-native-991-527-75901',1,17,18,90,0),
(E'resource-native-991-527-75901',1,18,18,92,0),
(E'resource-native-991-527-75901',1,19,18,93,0),
(E'resource-native-991-527-75901',1,20,18,94,0),
(E'resource-native-991-527-75901',1,21,18,95,0),
(E'resource-native-991-527-75901',1,22,18,96,0),
(E'resource-native-991-527-75901',1,23,18,97,0),
(E'resource-native-991-527-75901',1,24,18,98,0),
(E'resource-native-991-527-75901',1,25,18,99,0),
(E'resource-native-991-527-75901',1,26,18,100,0),
(E'resource-native-991-527-75901',1,27,18,101,0),
(E'resource-native-991-527-75901',1,28,18,102,0),
(E'resource-native-991-527-75901',1,29,18,103,0),
(E'resource-native-991-527-75901',1,30,18,104,0),
(E'resource-native-991-527-75901',1,31,18,105,0),
(E'resource-native-991-527-75901',1,32,18,106,0),
(E'resource-native-991-527-75901',1,33,18,107,3),
(E'resource-native-991-527-75901',1,34,18,108,0),
(E'resource-native-991-527-75901',1,35,18,109,0),
(E'resource-native-991-527-75901',1,36,18,110,0),
(E'resource-native-991-527-75901',1,37,18,111,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-991-527-76001',1,-991,0,293,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-991-527-76001',1,E'proposed',0),
(E'resource-native-991-527-76001',1,E'active',1),
(E'resource-native-991-527-76001',1,E'completed',2),
(E'resource-native-991-527-76001',1,E'expired',2),
(E'resource-native-991-527-76001',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',21,NULL,NULL),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',-991,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-991-527-76001',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-991-527-76001',1,0,-233,45,0),
(E'resource-native-991-527-76001',1,1,-233,46,0),
(E'resource-native-991-527-76001',1,2,-233,47,0),
(E'resource-native-991-527-76001',1,3,-233,48,0),
(E'resource-native-991-527-76001',1,4,-232,37,0),
(E'resource-native-991-527-76001',1,5,-232,38,0),
(E'resource-native-991-527-76001',1,6,-232,39,0),
(E'resource-native-991-527-76001',1,7,-232,40,0),
(E'resource-native-991-527-76001',1,8,-232,41,0),
(E'resource-native-991-527-76001',1,9,-232,42,0),
(E'resource-native-991-527-76001',1,10,-232,45,0),
(E'resource-native-991-527-76001',1,11,-232,47,0),
(E'resource-native-991-527-76001',1,12,-232,48,0),
(E'resource-native-991-527-76001',1,13,-231,37,0),
(E'resource-native-991-527-76001',1,14,-231,38,0),
(E'resource-native-991-527-76001',1,15,-231,39,0),
(E'resource-native-991-527-76001',1,16,-231,40,0),
(E'resource-native-991-527-76001',1,17,-231,41,0),
(E'resource-native-991-527-76001',1,18,-231,42,0),
(E'resource-native-991-527-76001',1,19,-231,43,0),
(E'resource-native-991-527-76001',1,20,-231,44,0),
(E'resource-native-991-527-76001',1,21,-231,45,0),
(E'resource-native-991-527-76001',1,22,-231,46,0),
(E'resource-native-991-527-76001',1,23,-231,47,0),
(E'resource-native-991-527-76001',1,24,-231,48,0),
(E'resource-native-991-527-76001',1,25,-230,37,0),
(E'resource-native-991-527-76001',1,26,-230,38,0),
(E'resource-native-991-527-76001',1,27,-230,39,0),
(E'resource-native-991-527-76001',1,28,-230,40,0),
(E'resource-native-991-527-76001',1,29,-230,43,0),
(E'resource-native-991-527-76001',1,30,-230,44,0),
(E'resource-native-991-527-76001',1,31,-230,45,0),
(E'resource-native-991-527-76001',1,32,-230,46,0),
(E'resource-native-991-527-76001',1,33,-230,47,0),
(E'resource-native-991-527-76001',1,34,-230,48,0),
(E'resource-native-991-527-76001',1,35,-229,38,0),
(E'resource-native-991-527-76001',1,36,-229,39,0),
(E'resource-native-991-527-76001',1,37,-229,40,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-954-527-75701',1,-954,0,292,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-954-527-75701',1,E'proposed',0),
(E'resource-native-954-527-75701',1,E'active',1),
(E'resource-native-954-527-75701',1,E'completed',2),
(E'resource-native-954-527-75701',1,E'expired',2),
(E'resource-native-954-527-75701',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',1,NULL,NULL),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',-954,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-954-527-75701',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-954-527-75701',1,0,-162,-126,-4),
(E'resource-native-954-527-75701',1,1,-162,-125,-4),
(E'resource-native-954-527-75701',1,2,-162,-124,-4),
(E'resource-native-954-527-75701',1,3,-162,-123,-4),
(E'resource-native-954-527-75701',1,4,-162,-122,-4),
(E'resource-native-954-527-75701',1,5,-162,-121,-4),
(E'resource-native-954-527-75701',1,6,-162,-120,-4),
(E'resource-native-954-527-75701',1,7,-162,-119,-4),
(E'resource-native-954-527-75701',1,8,-162,-118,-4),
(E'resource-native-954-527-75701',1,9,-162,-117,-4),
(E'resource-native-954-527-75701',1,10,-162,-116,-4),
(E'resource-native-954-527-75701',1,11,-162,-115,-4),
(E'resource-native-954-527-75701',1,12,-162,-114,-4),
(E'resource-native-954-527-75701',1,13,-162,-113,-4),
(E'resource-native-954-527-75701',1,14,-162,-112,-4),
(E'resource-native-954-527-75701',1,15,-162,-111,-4),
(E'resource-native-954-527-75701',1,16,-162,-110,-4),
(E'resource-native-954-527-75701',1,17,-162,-109,-4),
(E'resource-native-954-527-75701',1,18,-162,-108,-4),
(E'resource-native-954-527-75701',1,19,-162,-107,-4),
(E'resource-native-954-527-75701',1,20,-162,-106,-4),
(E'resource-native-954-527-75701',1,21,-162,-105,-4),
(E'resource-native-954-527-75701',1,22,-162,-104,-4),
(E'resource-native-954-527-75701',1,23,-162,-89,0),
(E'resource-native-954-527-75701',1,24,-162,-88,0),
(E'resource-native-954-527-75701',1,25,-162,-87,0),
(E'resource-native-954-527-75701',1,26,-162,-86,0),
(E'resource-native-954-527-75701',1,27,-162,-85,0),
(E'resource-native-954-527-75701',1,28,-162,-84,0),
(E'resource-native-954-527-75701',1,29,-162,-83,0),
(E'resource-native-954-527-75701',1,30,-162,-82,0),
(E'resource-native-954-527-75701',1,31,-162,-81,0),
(E'resource-native-954-527-75701',1,32,-162,-80,0),
(E'resource-native-954-527-75701',1,33,-162,-79,0),
(E'resource-native-954-527-75701',1,34,-162,-78,0),
(E'resource-native-954-527-75701',1,35,-162,-77,0),
(E'resource-native-954-527-75701',1,36,-162,-76,0),
(E'resource-native-954-527-75701',1,37,-162,-75,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-954-527-75801',1,-954,0,300,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-954-527-75801',1,E'proposed',0),
(E'resource-native-954-527-75801',1,E'active',1),
(E'resource-native-954-527-75801',1,E'completed',2),
(E'resource-native-954-527-75801',1,E'expired',2),
(E'resource-native-954-527-75801',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',1,NULL,NULL),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',-954,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-954-527-75801',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-954-527-75801',1,0,-126,2,0),
(E'resource-native-954-527-75801',1,1,-126,3,0),
(E'resource-native-954-527-75801',1,2,-126,4,0),
(E'resource-native-954-527-75801',1,3,-126,5,0),
(E'resource-native-954-527-75801',1,4,-126,6,0),
(E'resource-native-954-527-75801',1,5,-126,7,0),
(E'resource-native-954-527-75801',1,6,-126,8,0),
(E'resource-native-954-527-75801',1,7,-126,9,0),
(E'resource-native-954-527-75801',1,8,-126,10,0),
(E'resource-native-954-527-75801',1,9,-126,11,0),
(E'resource-native-954-527-75801',1,10,-126,12,0),
(E'resource-native-954-527-75801',1,11,-126,13,0),
(E'resource-native-954-527-75801',1,12,-126,14,0),
(E'resource-native-954-527-75801',1,13,-126,15,0),
(E'resource-native-954-527-75801',1,14,-126,18,4),
(E'resource-native-954-527-75801',1,15,-126,19,3),
(E'resource-native-954-527-75801',1,16,-126,23,4),
(E'resource-native-954-527-75801',1,17,-126,24,6),
(E'resource-native-954-527-75801',1,18,-126,25,3),
(E'resource-native-954-527-75801',1,19,-126,26,4),
(E'resource-native-954-527-75801',1,20,-126,29,0),
(E'resource-native-954-527-75801',1,21,-126,30,-2),
(E'resource-native-954-527-75801',1,22,-126,34,0),
(E'resource-native-954-527-75801',1,23,-126,35,0),
(E'resource-native-954-527-75801',1,24,-126,42,0),
(E'resource-native-954-527-75801',1,25,-126,43,0),
(E'resource-native-954-527-75801',1,26,-125,2,0),
(E'resource-native-954-527-75801',1,27,-125,3,0),
(E'resource-native-954-527-75801',1,28,-125,4,0),
(E'resource-native-954-527-75801',1,29,-125,5,0),
(E'resource-native-954-527-75801',1,30,-125,6,0),
(E'resource-native-954-527-75801',1,31,-125,7,0),
(E'resource-native-954-527-75801',1,32,-125,8,0),
(E'resource-native-954-527-75801',1,33,-125,9,0),
(E'resource-native-954-527-75801',1,34,-125,10,0),
(E'resource-native-954-527-75801',1,35,-125,11,0),
(E'resource-native-954-527-75801',1,36,-125,12,0),
(E'resource-native-954-527-75801',1,37,-125,13,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-954-527-76101',1,-954,0,303,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-954-527-76101',1,E'proposed',0),
(E'resource-native-954-527-76101',1,E'active',1),
(E'resource-native-954-527-76101',1,E'completed',2),
(E'resource-native-954-527-76101',1,E'expired',2),
(E'resource-native-954-527-76101',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',1,NULL,NULL),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',-954,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-954-527-76101',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-954-527-76101',1,0,-266,-41,0),
(E'resource-native-954-527-76101',1,1,-266,-40,0),
(E'resource-native-954-527-76101',1,2,-266,-38,0),
(E'resource-native-954-527-76101',1,3,-265,-44,0),
(E'resource-native-954-527-76101',1,4,-265,-43,0),
(E'resource-native-954-527-76101',1,5,-265,-41,0),
(E'resource-native-954-527-76101',1,6,-265,-40,0),
(E'resource-native-954-527-76101',1,7,-265,-39,0),
(E'resource-native-954-527-76101',1,8,-265,-38,0),
(E'resource-native-954-527-76101',1,9,-264,-45,0),
(E'resource-native-954-527-76101',1,10,-264,-44,0),
(E'resource-native-954-527-76101',1,11,-264,-43,0),
(E'resource-native-954-527-76101',1,12,-264,-42,0),
(E'resource-native-954-527-76101',1,13,-264,-41,0),
(E'resource-native-954-527-76101',1,14,-264,-40,0),
(E'resource-native-954-527-76101',1,15,-264,-39,0),
(E'resource-native-954-527-76101',1,16,-264,-38,0),
(E'resource-native-954-527-76101',1,17,-264,-37,0),
(E'resource-native-954-527-76101',1,18,-264,-36,0),
(E'resource-native-954-527-76101',1,19,-264,-35,0),
(E'resource-native-954-527-76101',1,20,-263,-45,0),
(E'resource-native-954-527-76101',1,21,-263,-44,0),
(E'resource-native-954-527-76101',1,22,-263,-43,0),
(E'resource-native-954-527-76101',1,23,-263,-42,0),
(E'resource-native-954-527-76101',1,24,-263,-41,0),
(E'resource-native-954-527-76101',1,25,-263,-40,0),
(E'resource-native-954-527-76101',1,26,-263,-39,-2),
(E'resource-native-954-527-76101',1,27,-263,-35,0),
(E'resource-native-954-527-76101',1,28,-262,-40,0),
(E'resource-native-954-527-76101',1,29,-262,-39,-2),
(E'resource-native-954-527-76101',1,30,-262,-35,0),
(E'resource-native-954-527-76101',1,31,-261,-51,0),
(E'resource-native-954-527-76101',1,32,-261,-43,0),
(E'resource-native-954-527-76101',1,33,-261,-41,0),
(E'resource-native-954-527-76101',1,34,-261,-40,0),
(E'resource-native-954-527-76101',1,35,-261,-39,0),
(E'resource-native-954-527-76101',1,36,-261,-35,0),
(E'resource-native-954-527-76101',1,37,-260,-44,0);
INSERT INTO environmental_profile_publication (profile_key,version,challenge_id,secondary_id,protector_id,native_time,time_mode,source_authority) VALUES
(E'resource-native-954-546-62201',1,-954,0,211,0,E'constant',E'wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero');
INSERT INTO environmental_profile_publication_states (profile_key,version,lifecycle_state,state_ordinal) VALUES
(E'resource-native-954-546-62201',1,E'proposed',0),
(E'resource-native-954-546-62201',1,E'active',1),
(E'resource-native-954-546-62201',1,E'completed',2),
(E'resource-native-954-546-62201',1,E'expired',2),
(E'resource-native-954-546-62201',1,E'cancelled',3);
INSERT INTO environmental_profile_native_variable_policy (profile_key,version,source_key,native_scenario_id,policy_contract,source_authority) VALUES
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,E'wakemu.durable-native-variable-projection.v1',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_native_variable_bindings (profile_key,version,source_key,native_scenario_id,variable_index,native_name,binding_kind,objective_key,configuration_key,constant_value,source_authority,entity_kind) VALUES
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,0,E'challengeLevelMax',E'configconstant',NULL,E'challengelevelmax',245,NULL,NULL),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,1,E'challengeLevelMin',E'configconstant',NULL,E'challengelevelmin',1,NULL,NULL),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,2,E'nbResourceForReward',E'configconstant',NULL,E'nbresourceforreward',1,NULL,NULL),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,3,E'nbResourceGlobal',E'global_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,4,E'nbResourceLeft',E'remaining',NULL,NULL,NULL,NULL,E'resource'),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,5,E'nbResourcePlayer',E'personal_progress',E'resource',NULL,NULL,NULL,NULL),
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',-954,6,E'nbResourceSpawned',E'spawned',NULL,NULL,NULL,NULL,E'resource');
INSERT INTO environmental_profile_resource_population (profile_key,version,source_key,placement_policy,transition_policy,source_authority) VALUES
(E'resource-native-954-546-62201',1,E'installed-environmental-source-v1',E'declared_native_cells',E'catalog_cvF',E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282');
INSERT INTO environmental_profile_resource_cells (profile_key,version,ordinal,x,y,z) VALUES
(E'resource-native-954-546-62201',1,0,-49,15,-1),
(E'resource-native-954-546-62201',1,1,-49,16,-1),
(E'resource-native-954-546-62201',1,2,-49,17,-1),
(E'resource-native-954-546-62201',1,3,-49,18,-1),
(E'resource-native-954-546-62201',1,4,-48,14,4),
(E'resource-native-954-546-62201',1,5,-48,15,0),
(E'resource-native-954-546-62201',1,6,-48,16,0),
(E'resource-native-954-546-62201',1,7,-48,17,0),
(E'resource-native-954-546-62201',1,8,-48,18,0),
(E'resource-native-954-546-62201',1,9,-48,41,8),
(E'resource-native-954-546-62201',1,10,-48,42,4),
(E'resource-native-954-546-62201',1,11,-48,45,0),
(E'resource-native-954-546-62201',1,12,-48,46,0),
(E'resource-native-954-546-62201',1,13,-48,47,0),
(E'resource-native-954-546-62201',1,14,-48,48,0),
(E'resource-native-954-546-62201',1,15,-48,49,0),
(E'resource-native-954-546-62201',1,16,-47,14,0),
(E'resource-native-954-546-62201',1,17,-47,15,0),
(E'resource-native-954-546-62201',1,18,-47,16,0),
(E'resource-native-954-546-62201',1,19,-47,17,0),
(E'resource-native-954-546-62201',1,20,-47,18,0),
(E'resource-native-954-546-62201',1,21,-47,19,0),
(E'resource-native-954-546-62201',1,22,-47,41,0),
(E'resource-native-954-546-62201',1,23,-47,42,0),
(E'resource-native-954-546-62201',1,24,-47,43,0),
(E'resource-native-954-546-62201',1,25,-47,44,0),
(E'resource-native-954-546-62201',1,26,-47,45,0),
(E'resource-native-954-546-62201',1,27,-47,46,0),
(E'resource-native-954-546-62201',1,28,-47,47,0),
(E'resource-native-954-546-62201',1,29,-47,48,0),
(E'resource-native-954-546-62201',1,30,-47,49,0),
(E'resource-native-954-546-62201',1,31,-46,13,0),
(E'resource-native-954-546-62201',1,32,-46,14,0),
(E'resource-native-954-546-62201',1,33,-46,15,0),
(E'resource-native-954-546-62201',1,34,-46,16,0),
(E'resource-native-954-546-62201',1,35,-46,17,0),
(E'resource-native-954-546-62201',1,36,-46,18,0),
(E'resource-native-954-546-62201',1,37,-46,19,0);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-323-56401',2,323,56401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c2120a4766f416e76e231d98865b8db5535a695c8c12422179f8c3fde4e8907e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-323-56401',2,0,E'resource-native-1542-323-56401',1),
(E'wakemu-native-resources-323-56401',2,1,E'resource-native-1544-323-56401',1),
(E'wakemu-native-resources-323-56401',2,2,E'resource-native-1545-323-56401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-327-56601',2,327,56601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2d4b706256242e3601fcf182375245b87aae49f4a06296bf86e183699cb35360',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-327-56601',2,0,E'resource-native-1320-327-56601',1),
(E'wakemu-native-resources-327-56601',2,1,E'resource-native-1322-327-56601',1),
(E'wakemu-native-resources-327-56601',2,2,E'resource-native-1323-327-56601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-458-61501',2,458,61501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'119d803753d16a89c131f7440bcdf15b49e581330055ca3a5ac42643f1c270ad',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-458-61501',2,0,E'resource-native-1559-458-61501',1),
(E'wakemu-native-resources-458-61501',2,1,E'resource-native-1561-458-61501',1),
(E'wakemu-native-resources-458-61501',2,2,E'resource-native-1562-458-61501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-504-60601',2,504,60601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7d95330b533edf73cdd2f093b296ad89aa5e4c8d8c1dea4f09513d95375ea71c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-504-60601',2,0,E'resource-native-1350-504-60601',1),
(E'wakemu-native-resources-504-60601',2,1,E'resource-native-1352-504-60601',1),
(E'wakemu-native-resources-504-60601',2,2,E'resource-native-1353-504-60601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-507-60701',2,507,60701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5043d0a6b3457c761aff3485bec36d8143a1b37e9b35f6702d272154dce2214c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-507-60701',2,0,E'resource-native-1365-507-60701',1),
(E'wakemu-native-resources-507-60701',2,1,E'resource-native-1367-507-60701',1),
(E'wakemu-native-resources-507-60701',2,2,E'resource-native-1368-507-60701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-508-60801',2,508,60801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'cdd6c4f6307b79d45760db3c2d740411d0ff91cd5dcecc7d7d12aef56d733b2c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-508-60801',2,0,E'resource-native-1380-508-60801',1),
(E'wakemu-native-resources-508-60801',2,1,E'resource-native-1382-508-60801',1),
(E'wakemu-native-resources-508-60801',2,2,E'resource-native-1383-508-60801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75601',2,527,75601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2efa6c903fc085cedfa6d53f45cb3ac0d4c4f8555a307e1587bc553721ca4608',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75601',2,0,E'resource-native-989-527-75601',1),
(E'wakemu-native-resources-527-75601',2,1,E'resource-native-991-527-75601',1),
(E'wakemu-native-resources-527-75601',2,2,E'resource-native-992-527-75601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75701',2,527,75701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'623add05e3b61c81049877abc5214e55f98493b8aba4291fc4b84800015076dc',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75701',2,0,E'resource-native-950-527-75701',1),
(E'wakemu-native-resources-527-75701',2,1,E'resource-native-953-527-75701',1),
(E'wakemu-native-resources-527-75701',2,2,E'resource-native-954-527-75701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75801',2,527,75801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'9a0a0e29d4d82c8ace291817d56b8e13ea253d4552946d7c3c6a5a60362c34c5',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75801',2,0,E'resource-native-950-527-75801',1),
(E'wakemu-native-resources-527-75801',2,1,E'resource-native-953-527-75801',1),
(E'wakemu-native-resources-527-75801',2,2,E'resource-native-954-527-75801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-75901',2,527,75901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd1fe31ebdd51e539cf6961c471adbc04275508fac33649b447abe35bbfcddeba',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-75901',2,0,E'resource-native-989-527-75901',1),
(E'wakemu-native-resources-527-75901',2,1,E'resource-native-991-527-75901',1),
(E'wakemu-native-resources-527-75901',2,2,E'resource-native-992-527-75901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76001',2,527,76001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0a51ccf624a2f51d4af7e20fd41880772a2d5e7e307f85a55e560dcb15d7c8d0',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76001',2,0,E'resource-native-989-527-76001',1),
(E'wakemu-native-resources-527-76001',2,1,E'resource-native-991-527-76001',1),
(E'wakemu-native-resources-527-76001',2,2,E'resource-native-992-527-76001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-527-76101',2,527,76101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'edbb34af61ceeefd6f09040f1b35e421ccd648743cd4a8afb39cfc9ed931b94e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-527-76101',2,0,E'resource-native-950-527-76101',1),
(E'wakemu-native-resources-527-76101',2,1,E'resource-native-953-527-76101',1),
(E'wakemu-native-resources-527-76101',2,2,E'resource-native-954-527-76101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-546-62201',2,546,62201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ee10d4bbb7c0dfc794de3867c164b61b57fec1faf6e9674153f124eeaea8cd98',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-546-62201',2,0,E'resource-native-950-546-62201',1),
(E'wakemu-native-resources-546-62201',2,1,E'resource-native-953-546-62201',1),
(E'wakemu-native-resources-546-62201',2,2,E'resource-native-954-546-62201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-711-63401',2,711,63401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1ee1435b3aa7f2a2e6b679c9d1af39f3c4b5f472dc19f09751f905f97088c603',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-711-63401',2,0,E'resource-native-1284-711-63401',1),
(E'wakemu-native-resources-711-63401',2,1,E'resource-native-1286-711-63401',1),
(E'wakemu-native-resources-711-63401',2,2,E'resource-native-1287-711-63401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-792-64601',2,792,64601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'3d5666b0c78ec86dfe17b4d32b3ecf026e6994b3bfe1a30231430994f3e7e3c4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-792-64601',2,0,E'resource-native-1395-792-64601',1),
(E'wakemu-native-resources-792-64601',2,1,E'resource-native-1397-792-64601',1),
(E'wakemu-native-resources-792-64601',2,2,E'resource-native-1398-792-64601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-793-64801',2,793,64801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5145016fa858f2ca7cc1722af02ffe1854b9e6d5255a66df20a44ff79f17832b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-793-64801',2,0,E'resource-native-1513-793-64801',1),
(E'wakemu-native-resources-793-64801',2,1,E'resource-native-1515-793-64801',1),
(E'wakemu-native-resources-793-64801',2,2,E'resource-native-1516-793-64801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-796-64701',2,796,64701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'2e88dd84a2fb5af620dca3278b9fb6685cb316b7c4025f0b8e98e2bb63bbce6f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-796-64701',2,0,E'resource-native-1410-796-64701',1),
(E'wakemu-native-resources-796-64701',2,1,E'resource-native-1412-796-64701',1),
(E'wakemu-native-resources-796-64701',2,2,E'resource-native-1413-796-64701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-843-65301',2,843,65301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a12024ad396049e42bc2534cd8f11c8292c921357ed124bb278fa92aa11bf38c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-843-65301',2,0,E'resource-native-1461-843-65301',1),
(E'wakemu-native-resources-843-65301',2,1,E'resource-native-1463-843-65301',1),
(E'wakemu-native-resources-843-65301',2,2,E'resource-native-1464-843-65301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-853-65401',2,853,65401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'bcccd87e631cf1986795356498a1b29165afd0bb60ce6846df6b34d4add8f783',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-853-65401',2,0,E'resource-native-1465-853-65401',1),
(E'wakemu-native-resources-853-65401',2,1,E'resource-native-1467-853-65401',1),
(E'wakemu-native-resources-853-65401',2,2,E'resource-native-1468-853-65401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-922-69301',2,922,69301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'37db054d1fca0c76bccbae09caec349f101990db29ffb1fd8a7549f001b6c4c6',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-922-69301',2,0,E'resource-native-1190-922-69301',1),
(E'wakemu-native-resources-922-69301',2,1,E'resource-native-1191-922-69301',1),
(E'wakemu-native-resources-922-69301',2,2,E'resource-native-1193-922-69301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-923-69401',2,923,69401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6a01f3f05266d015fd03cb162e05b29eeb152c689aaecff3bde0c768ec1aec47',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-923-69401',2,0,E'resource-native-1202-923-69401',1),
(E'wakemu-native-resources-923-69401',2,1,E'resource-native-1203-923-69401',1),
(E'wakemu-native-resources-923-69401',2,2,E'resource-native-1205-923-69401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69501',2,943,69501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c17544581630010c91d820bbdd008092875de99d1c3e462847211d50cf178e80',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69501',2,0,E'resource-native-1228-943-69501',1),
(E'wakemu-native-resources-943-69501',2,1,E'resource-native-1230-943-69501',1),
(E'wakemu-native-resources-943-69501',2,2,E'resource-native-1231-943-69501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-943-69601',2,943,69601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'145f4eae29208f24f6cd6896a54749febf27a381b000b67d68428f7d331c97ea',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-943-69601',2,0,E'resource-native-1232-943-69601',1),
(E'wakemu-native-resources-943-69601',2,1,E'resource-native-1234-943-69601',1),
(E'wakemu-native-resources-943-69601',2,2,E'resource-native-1235-943-69601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-71501',2,999,71501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c8f36c81d2a076d810b163754e13106a949c9a34a1a833326d13d1cd7355fedc',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-71501',2,0,E'resource-native-1581-999-71501',1),
(E'wakemu-native-resources-999-71501',2,1,E'resource-native-1582-999-71501',1),
(E'wakemu-native-resources-999-71501',2,2,E'resource-native-1584-999-71501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-999-82201',2,999,82201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7623652f49f450e93f6b58519ef5e2d5527ce5816dfabed980c3baaf2004ddc4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-999-82201',2,0,E'resource-native-1178-999-82201',1),
(E'wakemu-native-resources-999-82201',2,1,E'resource-native-1179-999-82201',1),
(E'wakemu-native-resources-999-82201',2,2,E'resource-native-1181-999-82201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1053-73701',2,1053,73701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd8398e03a85b036fdd55d5ef1a0d0017bca4ea765f50fc216d01a6f9fd1826bf',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1053-73701',2,0,E'resource-native-1585-1053-73701',1),
(E'wakemu-native-resources-1053-73701',2,1,E'resource-native-1586-1053-73701',1),
(E'wakemu-native-resources-1053-73701',2,2,E'resource-native-1588-1053-73701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1118-78601',2,1118,78601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'986e049b80a3e1710ba46c4ef809ff99749be2dfba563b9ac8486110379ef806',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1118-78601',2,0,E'resource-native-1086-1118-78601',1),
(E'wakemu-native-resources-1118-78601',2,1,E'resource-native-1094-1118-78601',1),
(E'wakemu-native-resources-1118-78601',2,2,E'resource-native-1098-1118-78601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1119-78701',2,1119,78701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1d4a59d85e848d55c6fce6273f4509ec308150c886af55657499d3db6b3562db',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1119-78701',2,0,E'resource-native-1087-1119-78701',1),
(E'wakemu-native-resources-1119-78701',2,1,E'resource-native-1095-1119-78701',1),
(E'wakemu-native-resources-1119-78701',2,2,E'resource-native-1099-1119-78701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-79401',2,1120,79401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'887431efde3f8058d5beee5f4f83d4921a6b4faca0a05d7a2606a5757df49151',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-79401',2,0,E'resource-native-1088-1120-79401',1),
(E'wakemu-native-resources-1120-79401',2,1,E'resource-native-1096-1120-79401',1),
(E'wakemu-native-resources-1120-79401',2,2,E'resource-native-1100-1120-79401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1120-80601',2,1120,80601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'96f336d213e78f151000be84cd844c71271e7356a493daa5caa030f303625780',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1120-80601',2,0,E'resource-native-1089-1120-80601',1),
(E'wakemu-native-resources-1120-80601',2,1,E'resource-native-1097-1120-80601',1),
(E'wakemu-native-resources-1120-80601',2,2,E'resource-native-1101-1120-80601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-79801',2,1122,79801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f273261a95d893637a8febe792653f2b8f77f5aeff19998166d3da9510553d52',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-79801',2,0,E'resource-native-1140-1122-79801',1),
(E'wakemu-native-resources-1122-79801',2,1,E'resource-native-1143-1122-79801',1),
(E'wakemu-native-resources-1122-79801',2,2,E'resource-native-1149-1122-79801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1122-80001',2,1122,80001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'596c7318c9607f2e4028c5430953196b44c806589aa92d09ba6e2f447b905b10',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1122-80001',2,0,E'resource-native-1141-1122-80001',1),
(E'wakemu-native-resources-1122-80001',2,1,E'resource-native-1144-1122-80001',1),
(E'wakemu-native-resources-1122-80001',2,2,E'resource-native-1150-1122-80001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1123-80101',2,1123,80101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'07ed824c891e883941756bf16a3672b48e930e0d2a01fc92b6b963eb5e870ea6',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1123-80101',2,0,E'resource-native-1142-1123-80101',1),
(E'wakemu-native-resources-1123-80101',2,1,E'resource-native-1145-1123-80101',1),
(E'wakemu-native-resources-1123-80101',2,2,E'resource-native-1151-1123-80101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81001',2,1124,81001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8d126efa267828990561bb25dcec708913cf87b4c128318686dad6976122f19b',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81001',2,0,E'resource-native-1508-1124-81001',1),
(E'wakemu-native-resources-1124-81001',2,1,E'resource-native-1509-1124-81001',1),
(E'wakemu-native-resources-1124-81001',2,2,E'resource-native-1511-1124-81001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1124-81101',2,1124,81101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd4a5383d5ba4a97b06d0a4e114584ae9611f9863eedb89558006855d1b60f783',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1124-81101',2,0,E'resource-native-1114-1124-81101',1),
(E'wakemu-native-resources-1124-81101',2,1,E'resource-native-1116-1124-81101',1),
(E'wakemu-native-resources-1124-81101',2,2,E'resource-native-1117-1124-81101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79101',2,1134,79101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6047eccb250b1e58f2d81b4a947064b79e6a4b64e85c125c8d869e8d915d08d7',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79101',2,0,E'resource-native-1305-1134-79101',1),
(E'wakemu-native-resources-1134-79101',2,1,E'resource-native-1307-1134-79101',1),
(E'wakemu-native-resources-1134-79101',2,2,E'resource-native-1308-1134-79101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1134-79201',2,1134,79201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'504b9adee407cc8ea089eb3f609b416d312fdc603aee25ab9197b5398641aa70',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1134-79201',2,0,E'resource-native-1626-1134-79201',1),
(E'wakemu-native-resources-1134-79201',2,1,E'resource-native-1627-1134-79201',1),
(E'wakemu-native-resources-1134-79201',2,2,E'resource-native-1629-1134-79201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80801',2,1135,80801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'269fd4b62936c44ad9b3c310e26b28101b472a290ddc2c4b4db5619c29670f95',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80801',2,0,E'resource-native-1674-1135-80801',1),
(E'wakemu-native-resources-1135-80801',2,1,E'resource-native-1675-1135-80801',1),
(E'wakemu-native-resources-1135-80801',2,2,E'resource-native-1676-1135-80801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1135-80901',2,1135,80901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0d3c5095b94fb6464d092238fcbf599d97740f7dd7d179df84f3d92412a958b7',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1135-80901',2,0,E'resource-native-1682-1135-80901',1),
(E'wakemu-native-resources-1135-80901',2,1,E'resource-native-1683-1135-80901',1),
(E'wakemu-native-resources-1135-80901',2,2,E'resource-native-1685-1135-80901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84301',2,1136,84301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd155cb352ec079db59dec2a5c4408e2f48f8f2542e43df84fe869bc2f9589501',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84301',2,0,E'resource-native-1722-1136-84301',1),
(E'wakemu-native-resources-1136-84301',2,1,E'resource-native-1723-1136-84301',1),
(E'wakemu-native-resources-1136-84301',2,2,E'resource-native-1725-1136-84301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84401',2,1136,84401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'b431501ab19f981375057f565e971c96700a9780de6072ab2d08d0ade0a15c2c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84401',2,0,E'resource-native-1718-1136-84401',1),
(E'wakemu-native-resources-1136-84401',2,1,E'resource-native-1720-1136-84401',1),
(E'wakemu-native-resources-1136-84401',2,2,E'resource-native-1721-1136-84401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1136-84501',2,1136,84501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5b58823a990d84f0310af4cf13c9103187169e4d1bd5fbbc188c2fb781f17fa1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1136-84501',2,0,E'resource-native-1714-1136-84501',1),
(E'wakemu-native-resources-1136-84501',2,1,E'resource-native-1716-1136-84501',1),
(E'wakemu-native-resources-1136-84501',2,2,E'resource-native-1717-1136-84501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-81901',2,1137,81901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a0009b5bf332a06c93fa44685fbdb9b930c239366e90b827faf77cb62b4ff23c',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-81901',2,0,E'resource-native-1622-1137-81901',1),
(E'wakemu-native-resources-1137-81901',2,1,E'resource-native-1623-1137-81901',1),
(E'wakemu-native-resources-1137-81901',2,2,E'resource-native-1625-1137-81901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-82001',2,1137,82001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'81abc66e00749717e95ca4ed58f19f7e02df949a0dfb682eb6af3e0a863bb980',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-82001',2,0,E'resource-native-1698-1137-82001',1),
(E'wakemu-native-resources-1137-82001',2,1,E'resource-native-1699-1137-82001',1),
(E'wakemu-native-resources-1137-82001',2,2,E'resource-native-1701-1137-82001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1137-85901',2,1137,85901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'8cd463541b6f08c485ba7ef0411e4a6574b302faff4e23fc82f0200aef970563',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1137-85901',2,0,E'resource-native-1706-1137-85901',1),
(E'wakemu-native-resources-1137-85901',2,1,E'resource-native-1707-1137-85901',1),
(E'wakemu-native-resources-1137-85901',2,2,E'resource-native-1709-1137-85901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-83801',2,1207,83801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f8f923563888f7ebc82d56cd8a9be159c749d3c548912f712cff9de17bee3095',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-83801',2,0,E'resource-native-1630-1207-83801',1),
(E'wakemu-native-resources-1207-83801',2,1,E'resource-native-1631-1207-83801',1),
(E'wakemu-native-resources-1207-83801',2,2,E'resource-native-1633-1207-83801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1207-86601',2,1207,86601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'94016cbe9a3b7c87996d0514de6bb2865a47e8b92df1118ac8a2494c96df89ae',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1207-86601',2,0,E'resource-native-1638-1207-86601',1),
(E'wakemu-native-resources-1207-86601',2,1,E'resource-native-1639-1207-86601',1),
(E'wakemu-native-resources-1207-86601',2,2,E'resource-native-1641-1207-86601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-84101',2,1208,84101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0c9e689b93a65510e9f0c724bb023bd090b1d419403598fbcee0a8cc6e657d1a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-84101',2,0,E'resource-native-1678-1208-84101',1),
(E'wakemu-native-resources-1208-84101',2,1,E'resource-native-1680-1208-84101',1),
(E'wakemu-native-resources-1208-84101',2,2,E'resource-native-1681-1208-84101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1208-86801',2,1208,86801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1de0d465d06bf923afee31b0ad18fb4431a23e5babc3a87cc26c6dd313e933f0',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1208-86801',2,0,E'resource-native-1686-1208-86801',1),
(E'wakemu-native-resources-1208-86801',2,1,E'resource-native-1687-1208-86801',1),
(E'wakemu-native-resources-1208-86801',2,2,E'resource-native-1688-1208-86801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-83901',2,1209,83901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'0f9fc8a5547f9d7ff4dc3b1de7429950543af72f31b92abed5fc72413160c15f',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-83901',2,0,E'resource-native-1690-1209-83901',1),
(E'wakemu-native-resources-1209-83901',2,1,E'resource-native-1692-1209-83901',1),
(E'wakemu-native-resources-1209-83901',2,2,E'resource-native-1693-1209-83901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1209-86701',2,1209,86701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'66826da06f02f1497bf5bef53754869bbb7c463134d6bca2fea6a4fc1e43348e',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1209-86701',2,0,E'resource-native-1710-1209-86701',1),
(E'wakemu-native-resources-1209-86701',2,1,E'resource-native-1711-1209-86701',1),
(E'wakemu-native-resources-1209-86701',2,2,E'resource-native-1713-1209-86701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-84001',2,1210,84001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'361814f16789350566e25a48fb9732a23d033118a9245cd5d115d547584082ce',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-84001',2,0,E'resource-native-1702-1210-84001',1),
(E'wakemu-native-resources-1210-84001',2,1,E'resource-native-1704-1210-84001',1),
(E'wakemu-native-resources-1210-84001',2,2,E'resource-native-1705-1210-84001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1210-86901',2,1210,86901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'f9713495e1cf187f68f89546f700b54adc167a98ddfd057732118c50325a8251',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1210-86901',2,0,E'resource-native-1694-1210-86901',1),
(E'wakemu-native-resources-1210-86901',2,1,E'resource-native-1695-1210-86901',1),
(E'wakemu-native-resources-1210-86901',2,2,E'resource-native-1697-1210-86901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88501',2,1252,88501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a41825605352eee5c3bcb3f2bb6dcf50d3da0ee162c6a0b924a1906ee3f8766d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88501',2,0,E'resource-native-1873-1252-88501',1),
(E'wakemu-native-resources-1252-88501',2,1,E'resource-native-1875-1252-88501',1),
(E'wakemu-native-resources-1252-88501',2,2,E'resource-native-1876-1252-88501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88701',2,1252,88701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'234c861b67dd735f90d15c114dfc90ad29a3d76f5ef15855532ee7b1855f3389',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88701',2,0,E'resource-native-1885-1252-88701',1),
(E'wakemu-native-resources-1252-88701',2,1,E'resource-native-1887-1252-88701',1),
(E'wakemu-native-resources-1252-88701',2,2,E'resource-native-1888-1252-88701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1252-88801',2,1252,88801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a35a68eb81c63ae3eb2a94884621e79d97b02a5e5e8af1f2cebf7a6940cfc824',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1252-88801',2,0,E'resource-native-1881-1252-88801',1),
(E'wakemu-native-resources-1252-88801',2,1,E'resource-native-1883-1252-88801',1),
(E'wakemu-native-resources-1252-88801',2,2,E'resource-native-1884-1252-88801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89301',2,1264,89301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'60355d6dc88564f12e3f69a19c15f2f268df675b435b616219fa38e1d26eb195',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89301',2,0,E'resource-native-1217-1264-89301',1),
(E'wakemu-native-resources-1264-89301',2,1,E'resource-native-1219-1264-89301',1),
(E'wakemu-native-resources-1264-89301',2,2,E'resource-native-1220-1264-89301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89401',2,1264,89401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'af9bb656dd384914bba91390a321dc0af48f10a777bfb589480536f12adc6626',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89401',2,0,E'resource-native-1141-1264-89401',1),
(E'wakemu-native-resources-1264-89401',2,1,E'resource-native-1144-1264-89401',1),
(E'wakemu-native-resources-1264-89401',2,2,E'resource-native-1150-1264-89401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89501',2,1264,89501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd38b27133021fb06fd4d9b2051aceedb6a7f6d8969208b0ff8abd85a6417e6a2',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89501',2,0,E'resource-native-1217-1264-89501',1),
(E'wakemu-native-resources-1264-89501',2,1,E'resource-native-1219-1264-89501',1),
(E'wakemu-native-resources-1264-89501',2,2,E'resource-native-1220-1264-89501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1264-89701',2,1264,89701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1664606a69b85fce147781311812bfd5d0d40cf4efa71055d16e43f38eaf5cb8',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1264-89701',2,0,E'resource-native-1585-1264-89701',1),
(E'wakemu-native-resources-1264-89701',2,1,E'resource-native-1586-1264-89701',1),
(E'wakemu-native-resources-1264-89701',2,2,E'resource-native-1588-1264-89701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90001',2,1276,90001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1234409b5bfa0fe15234a0354dc72aaa6469b57aaad567f79c081fb7f24abd0a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90001',2,0,E'resource-native-1944-1276-90001',1),
(E'wakemu-native-resources-1276-90001',2,1,E'resource-native-1948-1276-90001',1),
(E'wakemu-native-resources-1276-90001',2,2,E'resource-native-1956-1276-90001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90101',2,1276,90101,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd97d241c2703693c2c631ddad58db67628c213d4c2d3a939e40b3218f0010e11',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90101',2,0,E'resource-native-1942-1276-90101',1),
(E'wakemu-native-resources-1276-90101',2,1,E'resource-native-1946-1276-90101',1),
(E'wakemu-native-resources-1276-90101',2,2,E'resource-native-1954-1276-90101',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1276-90201',2,1276,90201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'441b66fac67fabc377800ef6728871006f20e7965ea4a8bc2401c6fb8de3a2cf',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1276-90201',2,0,E'resource-native-1943-1276-90201',1),
(E'wakemu-native-resources-1276-90201',2,1,E'resource-native-1947-1276-90201',1),
(E'wakemu-native-resources-1276-90201',2,2,E'resource-native-1955-1276-90201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90601',2,1295,90601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd010c321ab88dd54a36669bceecce146742df3460007648c225f8eef49120ef1',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90601',2,0,E'resource-native-1335-1295-90601',1),
(E'wakemu-native-resources-1295-90601',2,1,E'resource-native-1337-1295-90601',1),
(E'wakemu-native-resources-1295-90601',2,2,E'resource-native-1338-1295-90601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1295-90701',2,1295,90701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'954b1d09e13da4996e68a8f4ebbbd7d7172f624944be3202d62c393d99fe0e89',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1295-90701',2,0,E'resource-native-1983-1295-90701',1),
(E'wakemu-native-resources-1295-90701',2,1,E'resource-native-1986-1295-90701',1),
(E'wakemu-native-resources-1295-90701',2,2,E'resource-native-1992-1295-90701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1297-90801',2,1297,90801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'c1a0c0b7937fb0f1556f6890c95a5aaf14aed3a4465f983351f733d8d85e88e4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1297-90801',2,0,E'resource-native-1984-1297-90801',1),
(E'wakemu-native-resources-1297-90801',2,1,E'resource-native-1987-1297-90801',1),
(E'wakemu-native-resources-1297-90801',2,2,E'resource-native-1993-1297-90801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1298-90901',2,1298,90901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'924531df6858a32772cc569fdfbd4a887eb2446662f268e606704ce2eccac9c7',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1298-90901',2,0,E'resource-native-1982-1298-90901',1),
(E'wakemu-native-resources-1298-90901',2,1,E'resource-native-1985-1298-90901',1),
(E'wakemu-native-resources-1298-90901',2,2,E'resource-native-1991-1298-90901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1305-91201',2,1305,91201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'18b1bfce6fae6ebf61f25bbf2f4f730d8cffc03ce0bb2b1b8d1ce60263ccc046',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1305-91201',2,0,E'resource-native-2016-1305-91201',1),
(E'wakemu-native-resources-1305-91201',2,1,E'resource-native-2017-1305-91201',1),
(E'wakemu-native-resources-1305-91201',2,2,E'resource-native-2019-1305-91201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1309-91301',2,1309,91301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7ecf49a0bb661d27627b0c222034f69530ad9aeb5ab87c2884b19e95999affad',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1309-91301',2,0,E'resource-native-2016-1309-91301',1),
(E'wakemu-native-resources-1309-91301',2,1,E'resource-native-2017-1309-91301',1),
(E'wakemu-native-resources-1309-91301',2,2,E'resource-native-2019-1309-91301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1326-91401',2,1326,91401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6ddf6ec2915b19097277ef2fe17ce2ee234b89b1a7f0c2f540256cbeb75d67f3',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1326-91401',2,0,E'resource-native-2016-1326-91401',1),
(E'wakemu-native-resources-1326-91401',2,1,E'resource-native-2017-1326-91401',1),
(E'wakemu-native-resources-1326-91401',2,2,E'resource-native-2019-1326-91401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1333-91801',2,1333,91801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'015740e5c53c36b5e020a24be1c71793e695b26aad7f1ca8de4d5c5fef496c16',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1333-91801',2,0,E'resource-native-2016-1333-91801',1),
(E'wakemu-native-resources-1333-91801',2,1,E'resource-native-2017-1333-91801',1),
(E'wakemu-native-resources-1333-91801',2,2,E'resource-native-2019-1333-91801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1338-92001',2,1338,92001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'4dda9fe2c0db68656c8eea1ab5bde60bd758e950b08379e94275ceaf8b0bdbaf',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1338-92001',2,0,E'resource-native-2016-1338-92001',1),
(E'wakemu-native-resources-1338-92001',2,1,E'resource-native-2017-1338-92001',1),
(E'wakemu-native-resources-1338-92001',2,2,E'resource-native-2019-1338-92001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1358-92201',2,1358,92201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'27d8881462351d7a1f05d122be64cc14ebaed0fb92310d374abf855f0e5c67b6',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1358-92201',2,0,E'resource-native-2032-1358-92201',1),
(E'wakemu-native-resources-1358-92201',2,1,E'resource-native-2042-1358-92201',1),
(E'wakemu-native-resources-1358-92201',2,2,E'resource-native-2043-1358-92201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1359-92301',2,1359,92301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd230bb4e30a4ed648144cdc61f261fd0e88b6ba1121159e7f8a965076c820c92',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1359-92301',2,0,E'resource-native-2033-1359-92301',1),
(E'wakemu-native-resources-1359-92301',2,1,E'resource-native-2044-1359-92301',1),
(E'wakemu-native-resources-1359-92301',2,2,E'resource-native-2048-1359-92301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1364-93001',2,1364,93001,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd04cccbc7b0f981a769ce05e8d965371c294a9884ff97eaba29fd839aae9bad9',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1364-93001',2,0,E'resource-native-2034-1364-93001',1),
(E'wakemu-native-resources-1364-93001',2,1,E'resource-native-2045-1364-93001',1),
(E'wakemu-native-resources-1364-93001',2,2,E'resource-native-2049-1364-93001',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1365-92601',2,1365,92601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'12896ed92f3ea59571dca03efdb5439cdadba76062d6a40f0678f71e7273ac72',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1365-92601',2,0,E'resource-native-2036-1365-92601',1),
(E'wakemu-native-resources-1365-92601',2,1,E'resource-native-2047-1365-92601',1),
(E'wakemu-native-resources-1365-92601',2,2,E'resource-native-2051-1365-92601',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1368-92901',2,1368,92901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7760bd7a8228184ed4a06b6f557c132be92b0c250a4fc7be8efa98bd4c80a7d4',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1368-92901',2,0,E'resource-native-2035-1368-92901',1),
(E'wakemu-native-resources-1368-92901',2,1,E'resource-native-2046-1368-92901',1),
(E'wakemu-native-resources-1368-92901',2,2,E'resource-native-2050-1368-92901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93301',2,1384,93301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'a8edd72fed899a19f01a0e62a40f31e500a8cd9d6983353e10b32db6edb23686',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93301',2,0,E'resource-native-2112-1384-93301',1),
(E'wakemu-native-resources-1384-93301',2,1,E'resource-native-2120-1384-93301',1),
(E'wakemu-native-resources-1384-93301',2,2,E'resource-native-2124-1384-93301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93501',2,1384,93501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'1819b362e9fd72dfa5b0c702cb424e55b68eb02c426acc7719e1257fa13129d5',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93501',2,0,E'resource-native-1429-1384-93501',1),
(E'wakemu-native-resources-1384-93501',2,1,E'resource-native-1430-1384-93501',1),
(E'wakemu-native-resources-1384-93501',2,2,E'resource-native-2110-1384-93501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93801',2,1384,93801,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'7998225fa578415937919a4d08cedc63af341fe48005841a4c0dc5507e16cd40',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93801',2,0,E'resource-native-1437-1384-93801',1),
(E'wakemu-native-resources-1384-93801',2,1,E'resource-native-1438-1384-93801',1),
(E'wakemu-native-resources-1384-93801',2,2,E'resource-native-2109-1384-93801',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1384-93901',2,1384,93901,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'ea9e56626c7999f8154369bfc225577e5786b238df0d1ca2316d70c9fb0f5e88',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1384-93901',2,0,E'resource-native-2113-1384-93901',1),
(E'wakemu-native-resources-1384-93901',2,1,E'resource-native-2121-1384-93901',1),
(E'wakemu-native-resources-1384-93901',2,2,E'resource-native-2125-1384-93901',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1390-93701',2,1390,93701,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'62a652d32566bf72b3e4993a95822f9930524a51fef3a322e7e8b1593a1defa0',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1390-93701',2,0,E'resource-native-2114-1390-93701',1),
(E'wakemu-native-resources-1390-93701',2,1,E'resource-native-2122-1390-93701',1),
(E'wakemu-native-resources-1390-93701',2,2,E'resource-native-2126-1390-93701',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94201',2,1401,94201,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'd8affb540489c6357516862fc0d92dad4f64e0fa047b130f836844372538c27a',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94201',2,0,E'resource-native-2220-1401-94201',1),
(E'wakemu-native-resources-1401-94201',2,1,E'resource-native-2222-1401-94201',1),
(E'wakemu-native-resources-1401-94201',2,2,E'resource-native-2223-1401-94201',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94301',2,1401,94301,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'6efee33849f8915b6ce48a5425153a254d485240624dddf6d0528f875b2650d6',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94301',2,0,E'resource-native-2207-1401-94301',1),
(E'wakemu-native-resources-1401-94301',2,1,E'resource-native-2209-1401-94301',1),
(E'wakemu-native-resources-1401-94301',2,2,E'resource-native-2210-1401-94301',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94401',2,1401,94401,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'63435be9ca46224045fbc9b609e89828637f0bc82d9855790d875218bb60b351',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94401',2,0,E'resource-native-2194-1401-94401',1),
(E'wakemu-native-resources-1401-94401',2,1,E'resource-native-2196-1401-94401',1),
(E'wakemu-native-resources-1401-94401',2,2,E'resource-native-2197-1401-94401',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94501',2,1401,94501,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'5ab841d8ad8aabb45aadba765276fa5aabe85a4d7cf8ceb138f47f2e0caeec5d',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94501',2,0,E'resource-native-2233-1401-94501',1),
(E'wakemu-native-resources-1401-94501',2,1,E'resource-native-2235-1401-94501',1),
(E'wakemu-native-resources-1401-94501',2,2,E'resource-native-2236-1401-94501',1);
INSERT INTO environmental_regional_schedule_policies (policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256,sealed,enabled) VALUES
(E'wakemu-native-resources-1401-94601',2,1401,94601,E'wakemu_round_robin',E'occupied_sequential_windows',0,E'wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282',E'fa44b56cbe761d4f1e4236d17bd341dc3f3b635dd19a73ecb369ba3df1ee5208',FALSE,FALSE);
INSERT INTO environmental_regional_schedule_candidates (policy_key,version,ordinal,profile_key,profile_version) VALUES
(E'wakemu-native-resources-1401-94601',2,0,E'resource-native-2246-1401-94601',1),
(E'wakemu-native-resources-1401-94601',2,1,E'resource-native-2248-1401-94601',1),
(E'wakemu-native-resources-1401-94601',2,2,E'resource-native-2249-1401-94601',1);
COMMIT;
