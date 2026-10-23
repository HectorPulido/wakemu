-- Original bBH item effects, original placements and criteria.
-- No mission achievement completion, Gemlockitup or global emote policy.
-- Four unguarded placements use reconstructed once-per-character lifecycle.
-- Two native inventory guards permit reacquisition after consumption/loss.
CREATE TABLE native_generic_reward_programs (
 policy_id text PRIMARY KEY,version integer NOT NULL CHECK(version>0),authority text NOT NULL,
 lifecycle_mode text NOT NULL CHECK(lifecycle_mode IN ('NATIVE_INVENTORY_GUARD','ONCE_PER_CHARACTER_RECONSTRUCTED')),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),descriptor_id integer NOT NULL,
 wire_action integer NOT NULL,native_action_id integer NOT NULL,group_id integer NOT NULL,mru integer NOT NULL,
 group_cof boolean NOT NULL,group_cog bigint NOT NULL,group_cnd bigint NOT NULL,group_cod bigint NOT NULL,group_coe bigint NOT NULL,
 raw_cob double precision NOT NULL,action_criterion text NOT NULL,sealed boolean NOT NULL DEFAULT false
);
CREATE TABLE native_generic_reward_effects (
 policy_id text REFERENCES native_generic_reward_programs NOT NULL,effect_order integer NOT NULL,
 effect_reference integer NOT NULL,effect_type integer NOT NULL CHECK(effect_type IN (1,4,12)),criterion text NOT NULL,
 parameters text[] NOT NULL,item_reference integer,item_quantity integer,loot_list_id integer,
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),loot_source_sha256 text CHECK(length(loot_source_sha256)=64),
 PRIMARY KEY(policy_id,effect_reference),UNIQUE(policy_id,effect_order),
 CHECK((effect_type=1 AND item_reference IS NULL AND item_quantity IS NULL AND loot_list_id IS NULL AND loot_source_sha256 IS NULL)
 OR (effect_type=12 AND item_reference IS NOT NULL AND item_quantity IS NOT NULL AND item_reference>0 AND item_quantity>0 AND loot_list_id IS NULL AND loot_source_sha256 IS NULL)
 OR (effect_type=4 AND item_reference IS NULL AND item_quantity IS NULL AND loot_list_id IS NOT NULL AND loot_list_id>0 AND loot_source_sha256 IS NOT NULL))
);
CREATE TABLE native_generic_reward_locations (
 policy_id text NOT NULL REFERENCES native_generic_reward_programs,map_id integer NOT NULL,object_id bigint NOT NULL,
 x integer NOT NULL,y integer NOT NULL,z integer NOT NULL,payload_hex text NOT NULL,state_payload_hex text,
 geometry_sha256 text NOT NULL CHECK(length(geometry_sha256)=64),approach_policy text NOT NULL,
 PRIMARY KEY(map_id,object_id),UNIQUE(policy_id,map_id,object_id)
);
CREATE TABLE native_generic_reward_approaches (
 map_id integer NOT NULL,object_id bigint NOT NULL,x integer NOT NULL,y integer NOT NULL,z integer NOT NULL,
 PRIMARY KEY(map_id,object_id,x,y,z),FOREIGN KEY(map_id,object_id) REFERENCES native_generic_reward_locations
);
CREATE TABLE native_generic_reward_attempts (
 token uuid PRIMARY KEY,account_id bigint NOT NULL REFERENCES accounts(id),character_id bigint NOT NULL,
 generation text NOT NULL,map_id integer NOT NULL,instance_id bigint NOT NULL,object_id bigint NOT NULL,
 policy_id text NOT NULL,rule_digest text NOT NULL CHECK(length(rule_digest)=64),granted jsonb NOT NULL,consumed jsonb NOT NULL DEFAULT '[]'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 FOREIGN KEY(policy_id,map_id,object_id) REFERENCES native_generic_reward_locations(policy_id,map_id,object_id)
);
CREATE TABLE native_generic_reward_claims (
 character_id bigint NOT NULL REFERENCES characters(id),policy_id text NOT NULL,object_id bigint NOT NULL,
 effect_reference integer NOT NULL,rule_digest text NOT NULL CHECK(length(rule_digest)=64),attempt_uuid uuid NOT NULL,
 PRIMARY KEY(character_id,policy_id,object_id,effect_reference),
 FOREIGN KEY(policy_id,effect_reference) REFERENCES native_generic_reward_effects,
 FOREIGN KEY(attempt_uuid) REFERENCES native_generic_reward_attempts(token) DEFERRABLE INITIALLY DEFERRED
);
CREATE FUNCTION native_generic_reward_program_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN RAISE EXCEPTION 'Sealed generic reward policy is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER native_generic_reward_program_immutable BEFORE UPDATE OR DELETE ON native_generic_reward_programs
 FOR EACH ROW EXECUTE FUNCTION native_generic_reward_program_immutable();
CREATE FUNCTION native_generic_reward_child_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p text;
BEGIN
 IF TG_TABLE_NAME='native_generic_reward_approaches' THEN
  IF TG_OP='UPDATE' AND (NEW.map_id<>OLD.map_id OR NEW.object_id<>OLD.object_id) THEN RAISE EXCEPTION 'Generic reward approach reassignment is forbidden'; END IF;
  SELECT policy_id INTO p FROM native_generic_reward_locations WHERE map_id=COALESCE(NEW.map_id,OLD.map_id) AND object_id=COALESCE(NEW.object_id,OLD.object_id);
 ELSE p:=COALESCE(NEW.policy_id,OLD.policy_id); END IF;
 IF EXISTS(SELECT 1 FROM native_generic_reward_programs WHERE policy_id=p AND sealed) THEN RAISE EXCEPTION 'Sealed generic reward content is immutable'; END IF;
 IF TG_OP='UPDATE' AND TG_TABLE_NAME<>'native_generic_reward_approaches' THEN
  IF NEW.policy_id<>OLD.policy_id THEN RAISE EXCEPTION 'Generic reward policy reassignment is forbidden'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER native_generic_reward_effects_immutable BEFORE INSERT OR UPDATE OR DELETE ON native_generic_reward_effects FOR EACH ROW EXECUTE FUNCTION native_generic_reward_child_immutable();
CREATE TRIGGER native_generic_reward_locations_immutable BEFORE INSERT OR UPDATE OR DELETE ON native_generic_reward_locations FOR EACH ROW EXECUTE FUNCTION native_generic_reward_child_immutable();
CREATE TRIGGER native_generic_reward_approaches_immutable BEFORE INSERT OR UPDATE OR DELETE ON native_generic_reward_approaches FOR EACH ROW EXECUTE FUNCTION native_generic_reward_child_immutable();
INSERT INTO native_generic_reward_programs (policy_id,version,authority,lifecycle_mode,catalog_revision,descriptor_id,wire_action,native_action_id,group_id,mru,group_cof,group_cog,group_cnd,group_cod,group_coe,raw_cob,action_criterion) VALUES
('native.generic.reward.1403.v1',1,'Original table31 aLl/aLn/aLm export SHA256 10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d; bBH action/effect and native world placement. Wakemu reconstruction: once per character/object/effect; original repetition unavailable.','ONCE_PER_CHARACTER_RECONSTRUCTED','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',1403,0,1747,1705,87,false,0,0,0,0,1.0,''),
('native.generic.reward.183.v1',1,'Original table31 aLl/aLn/aLm export SHA256 10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d; bBH action/effect and native world placement. Wakemu reconstruction: once per character/object/effect; original repetition unavailable.','ONCE_PER_CHARACTER_RECONSTRUCTED','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',183,0,204,204,147,true,0,0,17578,1,1.0,''),
('native.generic.reward.1163.v1',1,'Original table31 aLl/aLn/aLm export SHA256 10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d; bBH action/effect and native world placement. Native inventory eligibility retained.','NATIVE_INVENTORY_GUARD','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',1163,0,1451,1418,87,false,0,0,0,0,1.0,''),
('native.generic.reward.181.v1',1,'Original table31 aLl/aLn/aLm export SHA256 10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d; bBH action/effect and native world placement. Native inventory eligibility retained.','NATIVE_INVENTORY_GUARD','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',181,0,202,202,87,true,0,0,0,0,1.0,'');
INSERT INTO native_generic_reward_effects (policy_id,effect_order,effect_reference,effect_type,criterion,parameters,item_reference,item_quantity,loot_list_id,source_sha256,loot_source_sha256) VALUES
('native.generic.reward.1403.v1',0,3192,12,'',ARRAY['11423','1']::text[],11423,1,NULL,'10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d',NULL),
('native.generic.reward.183.v1',0,395,4,'',ARRAY['2344']::text[],NULL,NULL,2344,'10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d','46de9005d013140a048a2992d02ed2e31a798cb9b5ec0f35a44e64967aced305'),
('native.generic.reward.1163.v1',0,2819,12,'GetItemQuantity(21599) <= 0',ARRAY['21599','1']::text[],21599,1,NULL,'10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d',NULL),
('native.generic.reward.181.v1',0,393,1,'GetItemQuantity(17496) > 0',ARRAY['false']::text[],NULL,NULL,NULL,'10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d',NULL),
('native.generic.reward.181.v1',1,3443,12,'GetItemQuantity(17496) <= 0',ARRAY['17496','1']::text[],17496,1,NULL,'10bcd8da6eb87e67f94f48aab80ae08ade182d4603366f6704ee637bff6d9c3d',NULL);
INSERT INTO native_generic_reward_locations (policy_id,map_id,object_id,x,y,z,payload_hex,state_payload_hex,geometry_sha256,approach_policy) VALUES
('native.generic.reward.1403.v1',295,13564,-11,-2,0,'02000000000b010000000d0000010127fffffff5fffffffe000000030000010001000000043134303300ffffffff0101','01020000000602000300000001010000000000','06e449dc04cfa10368875b37d4513de56c4cf319bc3e5806bc19b784bd477ff8','wakemu.reconstructed-cardinal-native-walkable.v1'),
('native.generic.reward.1403.v1',295,13565,-32,-5,0,'02000000000b010000000d0000010127ffffffe0fffffffb000000030000030001000000043134303300ffffffff0101','01020000000602000300000001010000000000','06e449dc04cfa10368875b37d4513de56c4cf319bc3e5806bc19b784bd477ff8','wakemu.reconstructed-cardinal-native-walkable.v1'),
('native.generic.reward.1403.v1',295,13566,-44,-25,0,'02000000000b010000000d0000010127ffffffd4ffffffe7000000030000010001000000043134303300ffffffff0101','01020000000602000300000001010000000000','06e449dc04cfa10368875b37d4513de56c4cf319bc3e5806bc19b784bd477ff8','wakemu.reconstructed-cardinal-native-walkable.v1'),
('native.generic.reward.183.v1',510,20081,99,10,1,'02000000000b010000000d00000101fe000000630000000a0001000101010100010000000331383300000000000101','01020000000602000101010001010000000000','cdaa81e2e5e06491680f1dbda0decbe61a8a21f09415427025e08edf2131e2dd','wakemu.reconstructed-cardinal-native-walkable.v1'),
('native.generic.reward.1163.v1',554,27669,103,0,2,'02000000000b010000000d000001022a0000006700000000000200010000010001000000043131363300000000000101','01020000000602000100000001010000000000','c13cee9d8f1a9ddb5c5389e5cc9584dd6d87c1630a730d02a550da34d4789c13','wakemu.reconstructed-cardinal-native-walkable.v1'),
('native.generic.reward.181.v1',622,20060,-17,-46,3,'02000000000b010000000d000001026effffffefffffffd20003000101010100010000000331383100000016d20101','01020000000602000101010001010000000000','eeadfda096d537fa00bd74d70f35d00e895f67bbcdbf230c98f10e8507f7ee72','wakemu.reconstructed-cardinal-native-walkable.v1');
INSERT INTO native_generic_reward_approaches (map_id,object_id,x,y,z) VALUES
(295,13564,-11,-1,0),
(295,13564,-10,-2,0),
(295,13565,-32,-4,0),
(295,13565,-31,-5,0),
(295,13566,-44,-24,0),
(295,13566,-43,-25,0),
(510,20081,98,10,-2),
(510,20081,99,9,-2),
(510,20081,99,11,-2),
(510,20081,100,10,-2),
(554,27669,102,0,0),
(554,27669,102,0,2),
(554,27669,103,-1,0),
(554,27669,103,-1,2),
(554,27669,103,1,0),
(554,27669,103,1,2),
(554,27669,104,0,0),
(554,27669,104,0,2),
(622,20060,-18,-46,3),
(622,20060,-17,-47,3),
(622,20060,-17,-45,3),
(622,20060,-16,-46,3);
INSERT INTO native_random_item_tables (reference,payload,source_sha256) VALUES
(2344,'{"czg":1,"d":2344,"gBN":[{"aAi":17545,"bfh":1,"cmY":1.0,"cqA":false,"cqy":1,"cqz":1,"csE":1,"czk":"","czl":0,"d":2873,"gBO":[]}]}','46de9005d013140a048a2992d02ed2e31a798cb9b5ec0f35a44e64967aced305');
UPDATE native_generic_reward_programs SET sealed=true;
