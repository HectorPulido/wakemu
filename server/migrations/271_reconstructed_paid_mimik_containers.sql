-- Original bCI source locations and input costs; no Gemlockitup or story seed.
-- Reward item identities: Methodwakfu seven-family observations, 2025-06-11.
-- RECONSTRUCTED Wakemu economics: sample-count weights, quantity1, occupation28/1000ms,
-- debit on completed attempt, cancel without debit, immediate new paid attempt.
-- Neither probability, quantity nor settlement timing is claimed original.
CREATE TABLE paid_container_policies (
 policy_id text PRIMARY KEY, version integer NOT NULL CHECK(version>0),
 authority_label text NOT NULL, reconstruction_label text NOT NULL,
 occupation_type smallint NOT NULL CHECK(occupation_type IN (13,28)),
 duration_ms bigint NOT NULL CHECK(duration_ms>=0),
 debit_timing text NOT NULL CHECK(debit_timing='finish'),
 repetition text NOT NULL CHECK(repetition='new_paid_attempt'),
 sealed boolean NOT NULL DEFAULT false
);
CREATE TABLE paid_container_locations (
 policy_id text NOT NULL REFERENCES paid_container_policies(policy_id),
 map_id integer NOT NULL, object_id bigint NOT NULL CHECK(object_id>0),
 definition_id integer NOT NULL CHECK(definition_id>0),
 x integer NOT NULL,y integer NOT NULL,z integer NOT NULL,
 payload_hex text NOT NULL CHECK(length(payload_hex)>0 AND length(payload_hex)%2=0),
 ready_state smallint NOT NULL,transient_state smallint NOT NULL,
 action integer NOT NULL,parameter integer NOT NULL,
 requireditem integer NOT NULL CHECK(requireditem>0),qty integer NOT NULL CHECK(qty>0),
 kamas bigint NOT NULL CHECK(kamas>=0),criterion text NOT NULL,mru integer NOT NULL,
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 native_state_payload_hex text,
 geometry_sha256 text NOT NULL CHECK(length(geometry_sha256)=64),
 approach_policy text NOT NULL,
 PRIMARY KEY(policy_id,map_id,object_id),UNIQUE(map_id,object_id)
);
CREATE TABLE paid_container_approaches (
 map_id integer NOT NULL,object_id bigint NOT NULL,
 x integer NOT NULL,y integer NOT NULL,z integer NOT NULL,
 PRIMARY KEY(map_id,object_id,x,y,z),
 FOREIGN KEY(map_id,object_id) REFERENCES paid_container_locations(map_id,object_id)
);
CREATE TABLE paid_container_outcomes (
 policy_id text NOT NULL REFERENCES paid_container_policies(policy_id),
 ordinal integer NOT NULL CHECK(ordinal>=0),itemref integer NOT NULL CHECK(itemref>0),
 quantity integer NOT NULL CHECK(quantity>0),weight integer NOT NULL CHECK(weight>0),
 PRIMARY KEY(policy_id,ordinal),UNIQUE(policy_id,itemref)
);
CREATE TABLE paid_container_attempts (
 token uuid PRIMARY KEY,account_id bigint NOT NULL REFERENCES accounts(id),
 generation text NOT NULL,character_id bigint NOT NULL,
 policy_id text NOT NULL REFERENCES paid_container_policies(policy_id),
 map_id integer NOT NULL,instance_id bigint NOT NULL,object_id bigint NOT NULL,
 origin_x integer NOT NULL,origin_y integer NOT NULL,origin_z integer NOT NULL,
 rule_digest text NOT NULL CHECK(length(rule_digest)=64),
 selected_ordinal integer NOT NULL,
 state text NOT NULL CHECK(state IN ('active','completed','canceled')),
 started_at timestamptz NOT NULL,due_at timestamptz NOT NULL,expires_at timestamptz NOT NULL,
 finished_at timestamptz,receipt jsonb,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 FOREIGN KEY(policy_id,map_id,object_id) REFERENCES paid_container_locations(policy_id,map_id,object_id),
 FOREIGN KEY(policy_id,selected_ordinal) REFERENCES paid_container_outcomes(policy_id,ordinal),
 CHECK(due_at>=started_at AND expires_at>=due_at),
 CHECK((state='active' AND finished_at IS NULL AND receipt IS NULL) OR
       (state<>'active' AND finished_at IS NOT NULL)),
 CHECK(state<>'completed' OR receipt IS NOT NULL)
);
CREATE UNIQUE INDEX paid_container_one_character_active ON paid_container_attempts(character_id) WHERE state='active';
CREATE UNIQUE INDEX paid_container_one_location_active ON paid_container_attempts(map_id,instance_id,object_id) WHERE state='active';
CREATE INDEX paid_container_attempt_history ON paid_container_attempts(account_id,character_id,started_at DESC);
INSERT INTO paid_container_policies (policy_id,version,authority_label,reconstruction_label,occupation_type,duration_ms,debit_timing,repetition) VALUES
('wakemu.mimik.piou_lahoupe.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.champs_pourchan.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.kokokolantha.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.domaine_petit_groin.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.palais_tsu.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.necropoil_morbax.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt'),
('wakemu.mimik.pichine.v1',1,'Original bCI placement/input and installed original item IDs; Methodwakfu https://methodwakfu.com/bien-debuter/mimics/ 2025-06-11 observations','Wakemu reconstruction: observed sample weights; one item per outcome; occupation28/1000ms; debit only at finish; cancel without debit; new paid attempt immediately after terminal; grace30s',28,1000,'finish','new_paid_attempt');
INSERT INTO paid_container_outcomes (policy_id,ordinal,itemref,quantity,weight) VALUES
('wakemu.mimik.piou_lahoupe.v1',0,12325,1,41),
('wakemu.mimik.piou_lahoupe.v1',1,8403,1,4),
('wakemu.mimik.piou_lahoupe.v1',2,9948,1,5),
('wakemu.mimik.champs_pourchan.v1',0,26550,1,17),
('wakemu.mimik.champs_pourchan.v1',1,7762,1,13),
('wakemu.mimik.champs_pourchan.v1',2,12325,1,11),
('wakemu.mimik.champs_pourchan.v1',3,8403,1,9),
('wakemu.mimik.kokokolantha.v1',0,26551,1,13),
('wakemu.mimik.kokokolantha.v1',1,7644,1,18),
('wakemu.mimik.kokokolantha.v1',2,12325,1,9),
('wakemu.mimik.kokokolantha.v1',3,8403,1,10),
('wakemu.mimik.domaine_petit_groin.v1',0,26552,1,12),
('wakemu.mimik.domaine_petit_groin.v1',1,7583,1,9),
('wakemu.mimik.domaine_petit_groin.v1',2,12325,1,8),
('wakemu.mimik.domaine_petit_groin.v1',3,11549,1,15),
('wakemu.mimik.domaine_petit_groin.v1',4,11550,1,6),
('wakemu.mimik.palais_tsu.v1',0,26552,1,13),
('wakemu.mimik.palais_tsu.v1',1,7765,1,14),
('wakemu.mimik.palais_tsu.v1',2,12325,1,14),
('wakemu.mimik.palais_tsu.v1',3,8403,1,9),
('wakemu.mimik.necropoil_morbax.v1',0,26553,1,9),
('wakemu.mimik.necropoil_morbax.v1',1,7451,1,7),
('wakemu.mimik.necropoil_morbax.v1',2,12325,1,19),
('wakemu.mimik.necropoil_morbax.v1',3,8403,1,15),
('wakemu.mimik.pichine.v1',0,26551,1,14),
('wakemu.mimik.pichine.v1',1,9708,1,16),
('wakemu.mimik.pichine.v1',2,12325,1,10),
('wakemu.mimik.pichine.v1',3,8403,1,10);
INSERT INTO paid_container_locations (policy_id,map_id,object_id,definition_id,x,y,z,payload_hex,ready_state,transient_state,action,parameter,requireditem,qty,kamas,criterion,mru,catalog_revision,native_state_payload_hex,geometry_sha256,approach_policy) VALUES
('wakemu.mimik.piou_lahoupe.v1',311,26903,170,16,23,-1,'02000000000b010000000d00000101370000001000000017ffff00010101010001000000033137300000004f5b0001',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010000010000000000','0398f5249d58964d58982514ef30cb1e10ee3b1baf7a1622f623838a6523fda2','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.champs_pourchan.v1',910,26489,174,32,41,0,'02000000000b010000000d000001038e00000020000000290000000101010300010000000331373400000035f10101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','b2f141bb019945ded95de974b544426ec5a8c783cb5939a9232c982865459613','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.kokokolantha.v1',295,13817,176,-31,-74,0,'02000000000b010000000d0000010127ffffffe1ffffffb60000000101010100010000000331373600ffffffff0101',1,3,22,0,12324,3,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','06e449dc04cfa10368875b37d4513de56c4cf319bc3e5806bc19b784bd477ff8','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.domaine_petit_groin.v1',911,26427,173,-64,-99,0,'02000000000b010000000d000001038fffffffc0ffffff9d0000000101010100010000000331373300000035f10101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','38b9bfc116c3830009031404a76aa397efdc19ace0b9e867942581bc65636ff4','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.palais_tsu.v1',165,13816,178,-59,28,0,'02000000000b010000000d00000100a5ffffffc50000001c0000000101010100010000000331373800ffffffff0101',1,3,22,0,12324,3,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','22d41e233612a81457a579f8fa6c120c4bf0ea4db70a90a32ad67ef39f68c486','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.necropoil_morbax.v1',296,13818,175,-36,-87,20,'02000000000b010000000d0000010128ffffffdcffffffa90014000101010300010000000331373500ffffffff0101',1,3,22,0,12324,3,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','8796edef430c9b72e9fa6ba2446d92c36c6b036477726525a791771c50712d4f','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.necropoil_morbax.v1',296,26493,175,64,9,0,'02000000000b010000000d000001012800000040000000090000000100000100010000000331373500000035f10101',1,3,22,0,12324,3,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000100000001010000000000','8796edef430c9b72e9fa6ba2446d92c36c6b036477726525a791771c50712d4f','wakemu.reconstructed-cardinal-native-walkable.v1'),
('wakemu.mimik.pichine.v1',912,26428,171,60,17,0,'02000000000b010000000d00000103900000003c000000110000000101010100010000000331373100000035f10101',1,3,22,0,12324,2,0,'not IsHero()',136,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','01020000000602000101010001010000000000','25bc770cf0c2616928c3a2243918845e813636f6840cebede8ac69374f088829','wakemu.reconstructed-cardinal-native-walkable.v1');
INSERT INTO paid_container_approaches (map_id,object_id,x,y,z) VALUES
(311,26903,17,23,-1),
(311,26903,16,24,0),
(910,26489,31,41,0),
(910,26489,33,41,0),
(910,26489,32,42,0),
(295,13817,-31,-75,0),
(295,13817,-32,-74,0),
(295,13817,-30,-74,0),
(295,13817,-31,-73,0),
(911,26427,-64,-100,0),
(911,26427,-63,-99,0),
(911,26427,-64,-98,0),
(165,13816,-58,28,0),
(165,13816,-59,29,0),
(296,13818,-37,-87,20),
(296,13818,-36,-86,20),
(296,26493,64,8,0),
(296,26493,65,9,0),
(296,26493,64,10,0),
(912,26428,60,16,0),
(912,26428,59,17,0),
(912,26428,61,17,0),
(912,26428,60,18,0);
UPDATE paid_container_policies SET sealed=true;
CREATE FUNCTION paid_container_policy_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN RAISE EXCEPTION 'Sealed paid-container policy is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER paid_container_policy_immutable BEFORE UPDATE OR DELETE ON paid_container_policies
 FOR EACH ROW EXECUTE FUNCTION paid_container_policy_immutable();
CREATE FUNCTION paid_container_child_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text; previous_k text;
BEGIN
 IF TG_TABLE_NAME='paid_container_approaches' THEN
  IF TG_OP<>'DELETE' THEN SELECT policy_id INTO k FROM paid_container_locations WHERE map_id=NEW.map_id AND object_id=NEW.object_id; END IF;
  IF TG_OP<>'INSERT' THEN SELECT policy_id INTO previous_k FROM paid_container_locations WHERE map_id=OLD.map_id AND object_id=OLD.object_id; END IF;
 ELSE
  IF TG_OP<>'DELETE' THEN k:=NEW.policy_id; END IF;
  IF TG_OP<>'INSERT' THEN previous_k:=OLD.policy_id; END IF;
 END IF;
 IF EXISTS(SELECT 1 FROM paid_container_policies WHERE sealed AND policy_id IN (k,previous_k)) THEN
  RAISE EXCEPTION 'Sealed paid-container content is immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER paid_container_locations_immutable BEFORE INSERT OR UPDATE OR DELETE ON paid_container_locations
 FOR EACH ROW EXECUTE FUNCTION paid_container_child_immutable();
CREATE TRIGGER paid_container_outcomes_immutable BEFORE INSERT OR UPDATE OR DELETE ON paid_container_outcomes
 FOR EACH ROW EXECUTE FUNCTION paid_container_child_immutable();
CREATE TRIGGER paid_container_approaches_immutable BEFORE INSERT OR UPDATE OR DELETE ON paid_container_approaches
 FOR EACH ROW EXECUTE FUNCTION paid_container_child_immutable();
