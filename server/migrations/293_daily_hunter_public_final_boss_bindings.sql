-- Explicit source-derived Wakemu daily targets, not original numeric selectors.
-- A normalized manifest avoids importing native documents into fresh test schemas;
-- consumers must compare it to actual native_catalog_documents before using it.
CREATE TABLE recurring_hunter_catalog_sources (
 native_catalog_revision text NOT NULL CHECK(native_catalog_revision ~ '^[0-9a-f]{64}$'),
 monsters_path text NOT NULL CHECK(monsters_path='monsters.json'),
 monsters_sha256 text NOT NULL CHECK(monsters_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(native_catalog_revision,monsters_path),
 UNIQUE(native_catalog_revision,monsters_path,monsters_sha256)
);
CREATE TABLE recurring_hunter_target_authority (
 definition_id integer NOT NULL, version integer NOT NULL,
 boss_reference integer NOT NULL CHECK(boss_reference>0),
 dungeon_definition_id integer NOT NULL CHECK(dungeon_definition_id>0),
 route_key text NOT NULL CHECK(length(route_key)>0),
 route_policy_version integer NOT NULL CHECK(route_policy_version>0),
 final_room_order integer NOT NULL CHECK(final_room_order>0),
 category_id integer NOT NULL CHECK(category_id>0),
 minimum_level integer NOT NULL CHECK(minimum_level>0),
 minimum_level_authority text NOT NULL CHECK(minimum_level_authority='wakemu-reconstruction:explicit-public-row-level+original-category-label'),
 native_catalog_revision text NOT NULL, monsters_path text NOT NULL, monsters_sha256 text NOT NULL,
 plan_sha256 text NOT NULL CHECK(plan_sha256 ~ '^[0-9a-f]{64}$'),
 public_url text NOT NULL CHECK(public_url='https://wakfu.wiki.gg/wiki/Guild_of_Hunters'),
 public_source_sha256 text NOT NULL CHECK(public_source_sha256 ~ '^[0-9a-f]{64}$'),
 interpretation_policy text NOT NULL CHECK(interpretation_policy='wakemu.daily-hunter-public-final-room-v1'),
 reward_policy text NOT NULL CHECK(reward_policy='fixed-native-parameter-no-booster'),
 native_reward_order integer[] NOT NULL CHECK(cardinality(native_reward_order)=2),
 PRIMARY KEY(definition_id,version,boss_reference), UNIQUE(definition_id,version),
 FOREIGN KEY(definition_id,version,boss_reference) REFERENCES recurring_hunter_targets,
 FOREIGN KEY(native_catalog_revision,monsters_path,monsters_sha256)
   REFERENCES recurring_hunter_catalog_sources(native_catalog_revision,monsters_path,monsters_sha256)
);
CREATE TRIGGER recurring_hunter_catalog_source_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_catalog_sources
FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TRIGGER recurring_hunter_target_authority_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_target_authority
FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
-- Deliberately no NPC/share acceptance binding and no server-wide daily choice.

INSERT INTO recurring_hunter_catalog_sources VALUES('b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4');
INSERT INTO recurring_hunter_contracts VALUES(4140,1,8627,6,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4140,1,44,'wakemu.daily.boss.44');
INSERT INTO recurring_hunter_rewards VALUES(4140,1,7737,6,NULL,33890,false);
INSERT INTO recurring_hunter_rewards VALUES(4140,1,7738,5,12686,20,false);
INSERT INTO recurring_hunter_target_authority VALUES(4140,1,44,90,'native_dungeon_90',2,3,701,6,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','1a66c99276a4dd19b49cb0d7063c74fea0ae6778947b69584a46f634ea100309','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7737,7738]);
INSERT INTO recurring_hunter_contracts VALUES(4141,1,8628,6,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4141,1,1259,'wakemu.daily.boss.1259');
INSERT INTO recurring_hunter_rewards VALUES(4141,1,7739,6,NULL,33890,false);
INSERT INTO recurring_hunter_rewards VALUES(4141,1,7740,5,12686,20,false);
INSERT INTO recurring_hunter_target_authority VALUES(4141,1,1259,27,'native_dungeon_27',3,3,701,6,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','a459541ceb4aaab4cf69ae2e483551cca9a9be8c05e32a57fe50a314fffacd95','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7739,7740]);
INSERT INTO recurring_hunter_contracts VALUES(4144,1,8631,21,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4144,1,1187,'wakemu.daily.boss.1187');
INSERT INTO recurring_hunter_rewards VALUES(4144,1,7745,6,NULL,121720,false);
INSERT INTO recurring_hunter_rewards VALUES(4144,1,7746,5,20672,20,false);
INSERT INTO recurring_hunter_target_authority VALUES(4144,1,1187,26,'native_dungeon_26',3,3,702,21,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','87c641dca1aa7e2770166dc1bd49c6d0182951494c91af0aa3fbbf5cca97b864','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7745,7746]);
INSERT INTO recurring_hunter_contracts VALUES(4145,1,8632,21,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4145,1,3216,'wakemu.daily.boss.3216');
INSERT INTO recurring_hunter_rewards VALUES(4145,1,7747,6,NULL,121720,false);
INSERT INTO recurring_hunter_rewards VALUES(4145,1,7748,5,20672,20,false);
INSERT INTO recurring_hunter_target_authority VALUES(4145,1,3216,89,'native_dungeon_89',3,3,702,21,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','7ead825c3ea84f4e1605e5d25a9f146a9e5e60dab88ed29f436aaabbdd368a4e','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7747,7748]);
INSERT INTO recurring_hunter_contracts VALUES(4146,1,8633,21,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4146,1,4107,'wakemu.daily.boss.4107');
INSERT INTO recurring_hunter_rewards VALUES(4146,1,7749,6,NULL,121720,false);
INSERT INTO recurring_hunter_rewards VALUES(4146,1,7750,5,20672,20,false);
INSERT INTO recurring_hunter_target_authority VALUES(4146,1,4107,125,'native_dungeon_125',3,3,702,21,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','38839c974c1eb451f42b0a20fb20a4f37ecabf76e161e14a2b72987615e49688','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7749,7750]);
INSERT INTO recurring_hunter_contracts VALUES(4163,1,8650,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4163,1,2768,'wakemu.daily.boss.2768');
INSERT INTO recurring_hunter_rewards VALUES(4163,1,7797,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4163,1,7798,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4163,1,2768,81,'native_dungeon_81',3,2,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','af13fbbe6539ffccee0808930df9710957658cd3104416278f5dc83ce51757ca','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7797,7798]);
INSERT INTO recurring_hunter_contracts VALUES(4164,1,8651,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4164,1,2774,'wakemu.daily.boss.2774');
INSERT INTO recurring_hunter_rewards VALUES(4164,1,7799,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4164,1,7800,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4164,1,2774,80,'native_dungeon_80',3,3,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','b365406962deb17bf6415b465128fab34201f6d3140178e620b3b5e2ae4c62bb','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7799,7800]);
INSERT INTO recurring_hunter_contracts VALUES(4167,1,8654,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4167,1,4240,'wakemu.daily.boss.4240');
INSERT INTO recurring_hunter_rewards VALUES(4167,1,7803,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4167,1,7804,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4167,1,4240,34,'native_dungeon_34',3,3,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','2f82d93f966e185ebc83378e5b5bf4be21b753817d721b57c23d95ee8be7c0c8','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7803,7804]);
INSERT INTO recurring_hunter_contracts VALUES(4168,1,8655,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4168,1,4244,'wakemu.daily.boss.4244');
INSERT INTO recurring_hunter_rewards VALUES(4168,1,7805,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4168,1,7806,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4168,1,4244,41,'native_dungeon_41',3,3,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','7df6b2394e6c8479be577081de92446c456670bb5b02029cefb98beadb6155c1','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7805,7806]);
INSERT INTO recurring_hunter_contracts VALUES(4174,1,8661,66,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4174,1,5107,'wakemu.daily.boss.5107');
INSERT INTO recurring_hunter_rewards VALUES(4174,1,7819,5,21002,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4174,1,7820,6,NULL,1201930,false);
INSERT INTO recurring_hunter_target_authority VALUES(4174,1,5107,46,'native_dungeon_46',3,3,692,66,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','db9155fc94279d733a5124bb9573a361e3d9ac0a5f59fe70ea2231a602589983','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7819,7820]);
INSERT INTO recurring_hunter_contracts VALUES(4175,1,8662,66,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4175,1,5114,'wakemu.daily.boss.5114');
INSERT INTO recurring_hunter_rewards VALUES(4175,1,7821,5,21002,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4175,1,7822,6,NULL,1201930,false);
INSERT INTO recurring_hunter_target_authority VALUES(4175,1,5114,47,'native_dungeon_47',3,4,692,66,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','959eee5fc10592b9c97827da176bcb811a6324893d87fd5bdc8f5adb37723fdc','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7821,7822]);
INSERT INTO recurring_hunter_contracts VALUES(4176,1,8663,66,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4176,1,3696,'wakemu.daily.boss.3696');
INSERT INTO recurring_hunter_rewards VALUES(4176,1,7823,5,21002,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4176,1,7824,6,NULL,1201930,false);
INSERT INTO recurring_hunter_target_authority VALUES(4176,1,3696,88,'native_dungeon_88',3,3,692,66,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','6685375ef510ab414b61b86c31b951aa7b82efaa277f932acd0cc01a287da80e','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7823,7824]);
INSERT INTO recurring_hunter_contracts VALUES(4178,1,8665,66,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4178,1,2313,'wakemu.daily.boss.2313');
INSERT INTO recurring_hunter_rewards VALUES(4178,1,7827,5,21002,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4178,1,7828,6,NULL,1201930,false);
INSERT INTO recurring_hunter_target_authority VALUES(4178,1,2313,12,'native_dungeon_12',3,2,692,66,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','3c058ca09ca69467f19ee425cb81d720537cb11118519a1edd06ee936b89b7e1','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7827,7828]);
INSERT INTO recurring_hunter_contracts VALUES(4183,1,8670,81,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:f9e96353e42a80b065c410dfcc45bf8d4bd8ca60c98460001f8d2ff1c41deb8a');
INSERT INTO recurring_hunter_targets VALUES(4183,1,1786,'wakemu.daily.boss.1786');
INSERT INTO recurring_hunter_rewards VALUES(4183,1,7837,5,21003,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4183,1,7838,6,NULL,1971970,false);
INSERT INTO recurring_hunter_target_authority VALUES(4183,1,1786,48,'native_dungeon_48',3,2,693,81,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','3c061ea38ad1f52e4792e2a6190fe2af4e9a3c404503725e5053f3cef7df29b5','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','f9e96353e42a80b065c410dfcc45bf8d4bd8ca60c98460001f8d2ff1c41deb8a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7837,7838]);
INSERT INTO recurring_hunter_contracts VALUES(4201,1,8688,126,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4201,1,5471,'wakemu.daily.boss.5471');
INSERT INTO recurring_hunter_rewards VALUES(4201,1,7875,5,21006,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4201,1,7876,6,NULL,8708950,false);
INSERT INTO recurring_hunter_target_authority VALUES(4201,1,5471,193,'native_dungeon_193',3,2,696,126,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','302203d3f4aa945acef48bbd794d3ede5ab5e63e417303b2f3852c0b8883e2f1','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7875,7876]);
INSERT INTO recurring_hunter_contracts VALUES(4210,1,8697,156,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4210,1,3398,'wakemu.daily.boss.3398');
INSERT INTO recurring_hunter_rewards VALUES(4210,1,7895,5,21008,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4210,1,7896,6,NULL,23442740,false);
INSERT INTO recurring_hunter_target_authority VALUES(4210,1,3398,95,'native_dungeon_95',3,4,698,156,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','05f25213552f63e0d45080adfd11e0589325f97ff1b7793d8275face3cc44113','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7895,7896]);
INSERT INTO recurring_hunter_contracts VALUES(4211,1,8698,156,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4211,1,3399,'wakemu.daily.boss.3399');
INSERT INTO recurring_hunter_rewards VALUES(4211,1,7897,5,21008,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4211,1,7898,6,NULL,23442740,false);
INSERT INTO recurring_hunter_target_authority VALUES(4211,1,3399,96,'native_dungeon_96',3,4,698,156,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','5b5ec10765c5c96cbbeb54757022a41d52273241493cf8c6df1279bd041f1fd6','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7897,7898]);
INSERT INTO recurring_hunter_contracts VALUES(4213,1,8700,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4213,1,3865,'wakemu.daily.boss.3865');
INSERT INTO recurring_hunter_rewards VALUES(4213,1,7901,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4213,1,7902,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4213,1,3865,104,'native_dungeon_104',3,2,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','57e8a3734e73f539d9ab8051ec6f123ca9394634d9de0c13cdb39f740980be37','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7901,7902]);
INSERT INTO recurring_hunter_contracts VALUES(4214,1,8701,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4214,1,3864,'wakemu.daily.boss.3864');
INSERT INTO recurring_hunter_rewards VALUES(4214,1,7903,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4214,1,7904,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4214,1,3864,106,'native_dungeon_106',3,2,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','f132b408bae5f106420fc8d15ead93a36f0a57cd7019a7e41601dfed5bceab75','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7903,7904]);
INSERT INTO recurring_hunter_contracts VALUES(4215,1,8702,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4215,1,3971,'wakemu.daily.boss.3971');
INSERT INTO recurring_hunter_rewards VALUES(4215,1,7905,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4215,1,7906,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4215,1,3971,110,'native_dungeon_110',3,3,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','164670fd1da7c99ab317aee19efed4f969a69a978e7d2697477542c1135408c3','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7905,7906]);
INSERT INTO recurring_hunter_contracts VALUES(4216,1,8703,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4216,1,3866,'wakemu.daily.boss.3866');
INSERT INTO recurring_hunter_rewards VALUES(4216,1,7907,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4216,1,7908,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4216,1,3866,109,'native_dungeon_109',3,2,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','719692397078360b8e3306f9eb036ce954104af06d851085e4c55f57c93a07d2','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7907,7908]);
INSERT INTO recurring_hunter_contracts VALUES(4218,1,8705,186,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4218,1,4327,'wakemu.daily.boss.4327');
INSERT INTO recurring_hunter_rewards VALUES(4218,1,7911,5,21010,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4218,1,7912,6,NULL,63103190,false);
INSERT INTO recurring_hunter_target_authority VALUES(4218,1,4327,127,'native_dungeon_127',3,3,700,186,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','d75bd37c93968b2b9ba3c278cf9905a99f70d511f817a439b33f75a33dd17cd7','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7911,7912]);
INSERT INTO recurring_hunter_contracts VALUES(4220,1,8707,186,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4220,1,4260,'wakemu.daily.boss.4260');
INSERT INTO recurring_hunter_rewards VALUES(4220,1,7915,5,21010,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4220,1,7916,6,NULL,63103190,false);
INSERT INTO recurring_hunter_target_authority VALUES(4220,1,4260,128,'native_dungeon_128',3,2,700,186,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','ad94cc4e58cf9bf3b8ff55e6e3c9218bef93c70e14d9fdffa5f08e0f9b97cf10','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[7915,7916]);
INSERT INTO recurring_hunter_contracts VALUES(4449,1,9140,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4449,1,4754,'wakemu.daily.boss.4754');
INSERT INTO recurring_hunter_rewards VALUES(4449,1,8300,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4449,1,8301,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4449,1,4754,140,'native_dungeon_140',3,4,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','81b62afe11909d927340fbe68a4761f9131dc7030b3522af404377f9081422a9','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8300,8301]);
INSERT INTO recurring_hunter_contracts VALUES(4450,1,9141,51,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4450,1,4731,'wakemu.daily.boss.4731');
INSERT INTO recurring_hunter_rewards VALUES(4450,1,8302,5,21001,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4450,1,8303,6,NULL,732590,false);
INSERT INTO recurring_hunter_target_authority VALUES(4450,1,4731,141,'native_dungeon_141',3,5,691,51,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','144fc7faed45824d466bd291d63a4581dd7b90825cac711e7cac8fe737adb21d','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8302,8303]);
INSERT INTO recurring_hunter_contracts VALUES(4455,1,9146,81,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4455,1,4913,'wakemu.daily.boss.4913');
INSERT INTO recurring_hunter_rewards VALUES(4455,1,8312,5,21003,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4455,1,8313,6,NULL,1971970,false);
INSERT INTO recurring_hunter_target_authority VALUES(4455,1,4913,151,'native_dungeon_151',2,3,693,81,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','123a1b0512a4d89af4aebd07bc79ee549f139cfbbe6adf40d08ac0a62b660dc0','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8312,8313]);
INSERT INTO recurring_hunter_contracts VALUES(4456,1,9147,96,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4456,1,4520,'wakemu.daily.boss.4520');
INSERT INTO recurring_hunter_rewards VALUES(4456,1,8314,5,21004,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4456,1,8315,6,NULL,3235360,false);
INSERT INTO recurring_hunter_target_authority VALUES(4456,1,4520,138,'native_dungeon_138',3,3,694,96,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','c1be121869559105e4efda28c33f7798f8babe8bbf6188e1eff94a4f9e46ec90','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8314,8315]);
INSERT INTO recurring_hunter_contracts VALUES(4457,1,9148,111,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4457,1,4720,'wakemu.daily.boss.4720');
INSERT INTO recurring_hunter_rewards VALUES(4457,1,8316,5,21005,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4457,1,8317,6,NULL,5308160,false);
INSERT INTO recurring_hunter_target_authority VALUES(4457,1,4720,142,'native_dungeon_142',3,2,695,111,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','4253c0cb5056166b656a51634b7475463aef34c7c6768cc8d88c59c432ad4f71','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8316,8317]);
INSERT INTO recurring_hunter_contracts VALUES(4460,1,9151,141,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4460,1,4780,'wakemu.daily.boss.4780');
INSERT INTO recurring_hunter_rewards VALUES(4460,1,8322,5,21007,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4460,1,8323,6,NULL,14288510,false);
INSERT INTO recurring_hunter_target_authority VALUES(4460,1,4780,152,'native_dungeon_152',3,4,697,141,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','863b8f0da80ca22adc61221977281ce5aa17d51c80f926712ae69667f6f7df7f','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8322,8323]);
INSERT INTO recurring_hunter_contracts VALUES(4461,1,9152,156,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4461,1,4538,'wakemu.daily.boss.4538');
INSERT INTO recurring_hunter_rewards VALUES(4461,1,8324,5,21008,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4461,1,8325,6,NULL,23442740,false);
INSERT INTO recurring_hunter_target_authority VALUES(4461,1,4538,139,'native_dungeon_139',2,4,698,156,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','21b2266795b0fb22f82a65f8202864f7b3b2454517587862995398611ca1ea0d','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8324,8325]);
INSERT INTO recurring_hunter_contracts VALUES(4463,1,9154,156,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4463,1,4924,'wakemu.daily.boss.4924');
INSERT INTO recurring_hunter_rewards VALUES(4463,1,8328,5,21008,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4463,1,8329,6,NULL,23442740,false);
INSERT INTO recurring_hunter_target_authority VALUES(4463,1,4924,149,'native_dungeon_149',3,8,698,156,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','563a79cc984fd3e556f2ba822b86af180e7ae47ebd6a12a906fca7f6c88ba577','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8328,8329]);
INSERT INTO recurring_hunter_contracts VALUES(4464,1,9155,156,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4464,1,4923,'wakemu.daily.boss.4923');
INSERT INTO recurring_hunter_rewards VALUES(4464,1,8330,5,21008,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4464,1,8331,6,NULL,23442740,false);
INSERT INTO recurring_hunter_target_authority VALUES(4464,1,4923,153,'native_dungeon_153',3,4,698,156,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','956692a4fbe68921f808ca22eb8787689956d18c73a4d9f2d9e4f2339cc6126e','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8330,8331]);
INSERT INTO recurring_hunter_contracts VALUES(4642,1,9557,141,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4642,1,5040,'wakemu.daily.boss.5040');
INSERT INTO recurring_hunter_rewards VALUES(4642,1,8706,5,21007,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4642,1,8707,6,NULL,14288510,false);
INSERT INTO recurring_hunter_target_authority VALUES(4642,1,5040,154,'native_dungeon_154',3,3,697,141,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','06d18b9815cc531b9ccba4db7bf5304c0649070d5a72a57d0b7d97e1043faae9','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8706,8707]);
INSERT INTO recurring_hunter_contracts VALUES(4645,1,9560,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4645,1,5046,'wakemu.daily.boss.5046');
INSERT INTO recurring_hunter_rewards VALUES(4645,1,8712,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4645,1,8713,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4645,1,5046,155,'native_dungeon_155',2,1,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','ac3e26af2a1b216d609a40483d5651816bb438157999b3b8395237a9c4fca0cb','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8712,8713]);
INSERT INTO recurring_hunter_contracts VALUES(4650,1,9565,186,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4650,1,5052,'wakemu.daily.boss.5052');
INSERT INTO recurring_hunter_rewards VALUES(4650,1,8722,5,21010,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4650,1,8723,6,NULL,63103190,false);
INSERT INTO recurring_hunter_target_authority VALUES(4650,1,5052,156,'native_dungeon_156',3,3,700,186,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','d99d45d5cdf8950b1a44bf0b8597c1eba23c5b4051f8eb277a324f6a07b0c2b7','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8722,8723]);
INSERT INTO recurring_hunter_contracts VALUES(4651,1,9566,186,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4651,1,5059,'wakemu.daily.boss.5059');
INSERT INTO recurring_hunter_rewards VALUES(4651,1,8724,5,21010,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4651,1,8725,6,NULL,63103190,false);
INSERT INTO recurring_hunter_target_authority VALUES(4651,1,5059,157,'native_dungeon_157',3,2,700,186,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','af1646ceaecb20145bfd738925aa80769096c83a82a1c75d27e7223c639a5554','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8724,8725]);
INSERT INTO recurring_hunter_contracts VALUES(4725,1,9827,171,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4725,1,5131,'wakemu.daily.boss.5131');
INSERT INTO recurring_hunter_rewards VALUES(4725,1,8864,5,19796,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4725,1,8865,6,NULL,38461820,false);
INSERT INTO recurring_hunter_target_authority VALUES(4725,1,5131,158,'native_dungeon_158',3,3,699,171,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','f3cf9348f36eaa48de48c3855ce3f8d48c1e1148370cbee568bf021807ba4946','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8864,8865]);
INSERT INTO recurring_hunter_contracts VALUES(4726,1,9828,186,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(4726,1,5137,'wakemu.daily.boss.5137');
INSERT INTO recurring_hunter_rewards VALUES(4726,1,8866,5,21010,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4726,1,8867,6,NULL,63103190,false);
INSERT INTO recurring_hunter_target_authority VALUES(4726,1,5137,159,'native_dungeon_159',3,3,700,186,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','6f3b9d14e5ff3855cc3d9d87ab5b09186314eceb863ae632c21556e154454e81','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8866,8867]);
INSERT INTO recurring_hunter_contracts VALUES(4774,1,9911,201,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4774,1,5170,'wakemu.daily.boss.5170');
INSERT INTO recurring_hunter_rewards VALUES(4774,1,8955,5,27888,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4774,1,8956,6,NULL,107005840,false);
INSERT INTO recurring_hunter_target_authority VALUES(4774,1,5170,160,'native_dungeon_160',3,2,809,201,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','4ddf74a386e1c31c246bf2907dc1c370033520ff8187a440d18dd307918f9fae','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8955,8956]);
INSERT INTO recurring_hunter_contracts VALUES(4776,1,9913,201,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a');
INSERT INTO recurring_hunter_targets VALUES(4776,1,5182,'wakemu.daily.boss.5182');
INSERT INTO recurring_hunter_rewards VALUES(4776,1,8959,5,27888,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4776,1,8960,6,NULL,107005840,false);
INSERT INTO recurring_hunter_target_authority VALUES(4776,1,5182,162,'native_dungeon_162',3,2,809,201,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','45ee9529fd0307fd8c2da8f829576456d573647ee916c11c00cce544dfca7bab','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','0b9e009afe6e5d42cc5c54631f0fafb998e5525fb403ff53ac0604071e56298a','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[8959,8960]);
INSERT INTO recurring_hunter_contracts VALUES(4869,1,10037,201,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4869,1,5241,'wakemu.daily.boss.5241');
INSERT INTO recurring_hunter_rewards VALUES(4869,1,9108,5,27888,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4869,1,9109,6,NULL,107005840,false);
INSERT INTO recurring_hunter_target_authority VALUES(4869,1,5241,166,'native_dungeon_166',3,2,809,201,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','b23998a4158278a855f57d4a565e21ef1dcb30e971e9592592a4567ccbe97bc5','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[9108,9109]);
INSERT INTO recurring_hunter_contracts VALUES(4870,1,10038,201,1,1475452800000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(4870,1,5247,'wakemu.daily.boss.5247');
INSERT INTO recurring_hunter_rewards VALUES(4870,1,9110,5,27888,20,false);
INSERT INTO recurring_hunter_rewards VALUES(4870,1,9111,6,NULL,107005840,false);
INSERT INTO recurring_hunter_target_authority VALUES(4870,1,5247,167,'native_dungeon_167',3,2,809,201,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','1f2d0ef9522e2da345aefdf42b1c9b7f50e8bdce275ded5b23925d2240fd5a7d','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[9110,9111]);
INSERT INTO recurring_hunter_contracts VALUES(5116,1,10503,216,1,1346457600000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe');
INSERT INTO recurring_hunter_targets VALUES(5116,1,5394,'wakemu.daily.boss.5394');
INSERT INTO recurring_hunter_rewards VALUES(5116,1,9631,5,29023,20,false);
INSERT INTO recurring_hunter_rewards VALUES(5116,1,9632,6,NULL,175561350,false);
INSERT INTO recurring_hunter_target_authority VALUES(5116,1,5394,187,'native_dungeon_187',2,3,853,216,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','37d0606781705537a3e1f01ae7bce19c00abd5cde053ffa5160fefa9c784630d','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','534a3c39ef33bc74ea78ddfc4afe045c9cd5cf5c6682dada7e329eb0b75dfdfe','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[9631,9632]);
INSERT INTO recurring_hunter_contracts VALUES(5395,1,11105,231,1,1346457600000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(5395,1,5626,'wakemu.daily.boss.5626');
INSERT INTO recurring_hunter_rewards VALUES(5395,1,10079,5,32303,20,false);
INSERT INTO recurring_hunter_rewards VALUES(5395,1,10080,6,NULL,288038370,false);
INSERT INTO recurring_hunter_target_authority VALUES(5395,1,5626,197,'native_dungeon_197',3,2,904,231,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','f1423dcc99c0d14fd679f7759b12319357271bc5fd9c1801fdcef5c576eedec2','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[10079,10080]);
INSERT INTO recurring_hunter_contracts VALUES(5396,1,11106,231,1,1346457600000,86400000,0,'wakemu.daily-hunter-public-final-room-v1','Wakemu-public-objective+native-bilingual+actual-final-role:cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301');
INSERT INTO recurring_hunter_targets VALUES(5396,1,5632,'wakemu.daily.boss.5632');
INSERT INTO recurring_hunter_rewards VALUES(5396,1,10081,5,32303,20,false);
INSERT INTO recurring_hunter_rewards VALUES(5396,1,10082,6,NULL,288038370,false);
INSERT INTO recurring_hunter_target_authority VALUES(5396,1,5632,198,'native_dungeon_198',3,2,904,231,'wakemu-reconstruction:explicit-public-row-level+original-category-label','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monsters.json','5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4','1718236c739506b19cc1aade0d623aed64e7fccb37973545edf32805783e4f8c','https://wakfu.wiki.gg/wiki/Guild_of_Hunters','cf674af9e5be48518923ce3beb11cce84f08084161538191884b139a8db6a301','wakemu.daily-hunter-public-final-room-v1','fixed-native-parameter-no-booster',ARRAY[10081,10082]);
