-- Native chest placement and explicit Wakemu rewards are normalized data.
CREATE TABLE treasure_chest_rules (
 map_id INTEGER NOT NULL, object_id BIGINT NOT NULL, content_id TEXT NOT NULL UNIQUE,
 x INTEGER NOT NULL,y INTEGER NOT NULL,z INTEGER NOT NULL,
 native_definition INTEGER NOT NULL,native_criterion TEXT NOT NULL,native_action INTEGER NOT NULL,
 native_action_name TEXT NOT NULL,native_action_metadata INTEGER NOT NULL,
 native_required_tool_reference INTEGER,native_required_item INTEGER NOT NULL,
 native_required_quantity INTEGER NOT NULL,native_required_currency INTEGER NOT NULL,
 native_payload_hex TEXT NOT NULL,native_state_payload_hex TEXT NOT NULL,
 native_geometry_sha256 TEXT NOT NULL,approach_policy TEXT NOT NULL,
 placement_authority TEXT NOT NULL,claim_policy TEXT NOT NULL,reward_authority TEXT NOT NULL,
 PRIMARY KEY(map_id,object_id)
);
CREATE TABLE treasure_chest_approaches (
 map_id INTEGER NOT NULL,object_id BIGINT NOT NULL,x INTEGER NOT NULL,y INTEGER NOT NULL,z INTEGER NOT NULL,
 PRIMARY KEY(map_id,object_id,x,y,z),
 FOREIGN KEY(map_id,object_id) REFERENCES treasure_chest_rules(map_id,object_id)
);
CREATE TABLE treasure_chest_rewards (
 map_id INTEGER NOT NULL,object_id BIGINT NOT NULL,ordinal INTEGER NOT NULL,
 reference INTEGER NOT NULL CHECK(reference>0),quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 32767),
 PRIMARY KEY(map_id,object_id,ordinal),
 FOREIGN KEY(map_id,object_id) REFERENCES treasure_chest_rules(map_id,object_id)
);
INSERT INTO treasure_chest_rules(map_id,object_id,content_id,x,y,z,native_definition,native_criterion,native_action,native_action_name,native_action_metadata,native_required_tool_reference,native_required_item,native_required_quantity,native_required_currency,native_payload_hex,native_state_payload_hex,native_geometry_sha256,approach_policy,placement_authority,claim_policy,reward_authority) VALUES(527,25114,'wakemu.astrub.starter-cache.1',5,58,0,56,'not IsHero()',22,'CHALLENGE_ACTIVATE',25,NULL,0,0,0,'02000000000b010000000d000001020f000000050000003a00000001010101000d00000002353600000007f00101','01020000000602000101010001010000000000','0bfbbc314349dd929561c9a93dd65fed6c3d52a78a886cbabb28515893394cb0','wakemu.same-floor-cardinal-native-surface.v1','installed-client:527:0_3:25114','wakemu.once-per-account.v1','wakemu-custom-content-not-original-loot');
INSERT INTO treasure_chest_approaches VALUES(527,25114,5,57,0);
INSERT INTO treasure_chest_approaches VALUES(527,25114,6,58,0);
INSERT INTO treasure_chest_approaches VALUES(527,25114,5,59,0);
INSERT INTO treasure_chest_rewards VALUES(527,25114,0,1752,5);

