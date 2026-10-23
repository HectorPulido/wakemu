-- Extend the qualified271 shared engine; no per-container Python or new protocol.
-- Five explicitly custom Wakemu contextual policies / nine original locations.
-- Original item IDs and levels belong to the same dungeon's own breed drops.
-- One exclusive reward: gear NEVER also grants the common material.
-- No Slobber, Gemlockitup, story treasure, orphan definition or combat change.
ALTER TABLE paid_container_outcomes ADD CONSTRAINT paid_container_outcome_item_identity UNIQUE(policy_id,ordinal,itemref);
CREATE TABLE paid_container_contextual_item_sources (
 policy_id text NOT NULL,ordinal integer NOT NULL,dungeon_id integer NOT NULL,
 monster_reference integer NOT NULL,item_reference integer NOT NULL,
 item_equipment_level integer CHECK(item_equipment_level>0),
 native_probability numeric NOT NULL CHECK(native_probability>0 AND native_probability<=1),
 native_quantity_min integer NOT NULL CHECK(native_quantity_min>0),
 native_quantity_max integer NOT NULL CHECK(native_quantity_max>=native_quantity_min),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 native_document text NOT NULL,native_collection text NOT NULL,
 PRIMARY KEY(policy_id,ordinal),
 FOREIGN KEY(policy_id,ordinal,item_reference) REFERENCES paid_container_outcomes(policy_id,ordinal,itemref)
);
CREATE TRIGGER paid_container_contextual_sources_immutable BEFORE INSERT OR UPDATE OR DELETE ON paid_container_contextual_item_sources
 FOR EACH ROW EXECUTE FUNCTION paid_container_child_immutable();
INSERT INTO paid_container_policies (policy_id,version,authority_label,reconstruction_label,occupation_type,duration_ms,debit_timing,repetition) VALUES
('wakemu.contextual.dungeon301.v1',1,'Original dungeon139 member map301 and breed roster; same-dungeon direct NPC item drops and original equipment level164','Wakemu custom contextual chest binding: exactly one exclusive weighted outcome; gear does not also grant resource; common material quantity equals original input count; rare weight uses selected native NPC piece probability as a conservative basis, not recovered chest odds; occupation28/1000ms, debit at finish, cancel without debit, new paid attempt, grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.contextual.dungeon901.v1',1,'Original dungeon89 member map901 and breed roster; same-dungeon direct NPC item drops and original equipment level32','Wakemu custom contextual chest binding: exactly one exclusive weighted outcome; gear does not also grant resource; common material quantity equals original input count; rare weight uses selected native NPC piece probability as a conservative basis, not recovered chest odds; occupation28/1000ms, debit at finish, cancel without debit, new paid attempt, grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.contextual.dungeon909.v1',1,'Original dungeon151 member map909 and breed roster; same-dungeon direct NPC item drops and original equipment level89','Wakemu custom contextual chest binding: exactly one exclusive weighted outcome; gear does not also grant resource; common material quantity equals original input count; rare weight uses selected native NPC piece probability as a conservative basis, not recovered chest odds; occupation28/1000ms, debit at finish, cancel without debit, new paid attempt, grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.contextual.dungeon1458.v1',1,'Original dungeon211 member map1458 and breed roster; same-dungeon direct NPC item drops and original equipment level74','Wakemu custom contextual chest binding: exactly one exclusive weighted outcome; gear does not also grant resource; common material quantity equals original input count; rare weight uses selected native NPC piece probability as a conservative basis, not recovered chest odds; occupation28/1000ms, debit at finish, cancel without debit, new paid attempt, grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.contextual.dungeon1460.v1',1,'Original dungeon208 member map1460 and breed roster; same-dungeon direct NPC item drops and original equipment level32','Wakemu custom contextual chest binding: exactly one exclusive weighted outcome; gear does not also grant resource; common material quantity equals original input count; rare weight uses selected native NPC piece probability as a conservative basis, not recovered chest odds; occupation28/1000ms, debit at finish, cancel without debit, new paid attempt, grace30s',28,1000,'finish','new_paid_attempt');
INSERT INTO paid_container_outcomes (policy_id,ordinal,itemref,quantity,weight) VALUES
('wakemu.contextual.dungeon301.v1',0,26584,5,92),
('wakemu.contextual.dungeon301.v1',1,26037,1,8),
('wakemu.contextual.dungeon901.v1',0,20678,2,98),
('wakemu.contextual.dungeon901.v1',1,10787,1,2),
('wakemu.contextual.dungeon909.v1',0,26440,2,92),
('wakemu.contextual.dungeon909.v1',1,25523,1,8),
('wakemu.contextual.dungeon1458.v1',0,26416,2,92),
('wakemu.contextual.dungeon1458.v1',1,25439,1,8),
('wakemu.contextual.dungeon1460.v1',0,2702,2,98),
('wakemu.contextual.dungeon1460.v1',1,9552,1,2);
INSERT INTO paid_container_locations (policy_id,map_id,object_id,definition_id,x,y,z,payload_hex,ready_state,transient_state,action,parameter,requireditem,qty,kamas,criterion,mru,catalog_revision,native_state_payload_hex,geometry_sha256,approach_policy) VALUES
('wakemu.contextual.dungeon301.v1',301,13559,164,-1,-87,0,'02000000000b010000000d000001012dffffffffffffffa90000000100000300010000000331363400ffffffff0101',1,3,22,0,12324,5,0,'not IsHero()',87,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','599d4535611f0ba8f4689d21b81cb2770e2ef15a12646e7d9fb49e4b2be215b4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon301.v1',301,13556,164,-27,-11,0,'02000000000b010000000d000001012dffffffe5fffffff50000000100000100010000000331363400ffffffff0101',1,3,22,0,12324,5,0,'not IsHero()',87,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','599d4535611f0ba8f4689d21b81cb2770e2ef15a12646e7d9fb49e4b2be215b4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon301.v1',301,13560,164,-27,-80,0,'02000000000b010000000d000001012dffffffe5ffffffb00000000100000100010000000331363400ffffffff0101',1,3,22,0,12324,5,0,'not IsHero()',87,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','599d4535611f0ba8f4689d21b81cb2770e2ef15a12646e7d9fb49e4b2be215b4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon301.v1',301,13557,164,15,-17,0,'02000000000b010000000d000001012d0000000fffffffef0000000100000100010000000331363400ffffffff0101',1,3,22,0,12324,5,0,'not IsHero()',87,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','599d4535611f0ba8f4689d21b81cb2770e2ef15a12646e7d9fb49e4b2be215b4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon301.v1',301,13558,164,21,-87,0,'02000000000b010000000d000001012d00000015ffffffa90000000100000300010000000331363400ffffffff0101',1,3,22,0,12324,5,0,'not IsHero()',87,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','599d4535611f0ba8f4689d21b81cb2770e2ef15a12646e7d9fb49e4b2be215b4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon901.v1',901,26497,169,-24,-34,0,'02000000000b010000000d0000010385ffffffe8ffffffde0000000100000300010000000331363900000035f10101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','0caa9a71e626fb73ebc18015d134939e9906da5b7c9682b5bbdbb58ee3be2208','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon909.v1',909,26429,172,63,-40,0,'02000000000b010000000d000001038d0000003fffffffd80000000101010300010000000331373200000035f10101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','fb55b03f2e0845a38568549fd2792807612ca5fcda7fa666d469d5d8454a8b5a','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon1458.v1',1458,35365,173,63,-152,0,'02000000000b010000000d00000105b20000003fffffff680000000101010100010000000331373300000000000101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','baef325b37eb746f7caca15d467c852c1433c474c65f989673eaefd24d5d382d','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.contextual.dungeon1460.v1',1460,35288,170,26,21,-1,'02000000000b010000000d00000105b40000001a00000015ffff000101010100010000000331373000000000000001',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010000010000000000','4fa4808fbd5d8d61ede0da2c7b821e50e923b36e42c31a2acf000812c0ee91f5','wakemu.reconstructed-cardinal-native-walkable.v1');
INSERT INTO paid_container_approaches (map_id,object_id,x,y,z) VALUES
(301,13559,-2,-87,0),
(301,13559,0,-87,0),
(301,13559,-1,-86,0),
(301,13556,-27,-12,0),
(301,13556,-26,-11,0),
(301,13556,-27,-10,0),
(301,13560,-27,-81,0),
(301,13560,-27,-81,28),
(301,13560,-26,-80,0),
(301,13560,-27,-79,0),
(301,13557,15,-18,3),
(301,13557,16,-17,0),
(301,13557,15,-16,0),
(301,13558,21,-88,4),
(301,13558,20,-87,0),
(301,13558,22,-87,0),
(301,13558,21,-86,0),
(901,26497,-23,-34,0),
(901,26497,-24,-33,0),
(909,26429,64,-40,0),
(909,26429,63,-39,0),
(1458,35365,63,-153,0),
(1458,35365,64,-152,0),
(1458,35365,63,-151,0),
(1460,35288,27,21,-1),
(1460,35288,26,22,0);
INSERT INTO paid_container_contextual_item_sources (policy_id,ordinal,dungeon_id,monster_reference,item_reference,item_equipment_level,native_probability,native_quantity_min,native_quantity_max,catalog_revision,native_document,native_collection) VALUES
('wakemu.contextual.dungeon301.v1',0,139,4534,26584,NULL,'0.25',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon301.v1',1,139,4538,26037,164,'0.08',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon901.v1',0,89,3212,20678,NULL,'0.25',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon901.v1',1,89,3216,10787,32,'0.02',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon909.v1',0,151,4909,26440,NULL,'0.25',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon909.v1',1,151,4913,25523,89,'0.08',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon1458.v1',0,211,4760,26416,NULL,'0.25',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon1458.v1',1,211,5795,25439,74,'0.08',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon1460.v1',0,208,87,2702,NULL,'0.25',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters'),
('wakemu.contextual.dungeon1460.v1',1,208,5792,9552,32,'0.02',1,1,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','monster-encyclopedia 2.json','monsters');
UPDATE paid_container_policies SET sealed=true WHERE policy_id IN ('wakemu.contextual.dungeon301.v1','wakemu.contextual.dungeon901.v1','wakemu.contextual.dungeon909.v1','wakemu.contextual.dungeon1458.v1','wakemu.contextual.dungeon1460.v1');
