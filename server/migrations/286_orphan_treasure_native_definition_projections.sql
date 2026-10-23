-- Complete85-row original table38 source, normalized rather than a rule JSON.
-- Hash-checked against the bounded original aLZ export in the shared reader.
CREATE TABLE native_loot_chest_prototypes (
 p integer PRIMARY KEY,"egY" integer NOT NULL,efm integer NOT NULL,ema integer NOT NULL,emb integer NOT NULL,emc integer NOT NULL,
 "ejK" boolean NOT NULL,emd integer NOT NULL,eme boolean NOT NULL,"ejL" integer NOT NULL,ehu text NOT NULL
);
INSERT INTO native_loot_chest_prototypes (p,"egY",efm,ema,emb,emc,"ejK",emd,eme,"ejL",ehu) VALUES
(31,87,0,0,0,0,true,1,true,0,''),
(32,88,0,1,0,0,true,0,true,0,''),
(53,98,5,0,0,0,false,1,true,5,'not IsHero()'),
(54,25,0,0,0,0,false,0,false,2,'not IsHero()'),
(55,113,0,0,0,0,false,0,false,2,'not IsHero()'),
(56,25,0,0,0,0,false,0,false,2,'not IsHero()'),
(57,19,2,0,0,0,true,999,true,0,''),
(58,19,2,0,0,0,true,999,true,0,''),
(59,115,0,0,0,0,false,0,true,2,''),
(60,86,-1,0,0,0,true,1,true,3,''),
(61,19,120,0,0,0,true,1,true,0,''),
(67,66,0,10,0,0,true,0,true,3,''),
(102,66,0,0,0,0,true,0,true,3,''),
(131,88,0,1,0,0,true,0,true,0,''),
(133,88,0,1,0,0,true,0,true,0,''),
(137,130,0,0,0,0,true,0,true,1,'IsAfter(25,12,2025,00,00,00)'),
(138,130,-1,0,0,0,true,1,true,1,''),
(161,135,-1,0,0,0,true,1,true,1,''),
(162,88,0,0,12231,1,true,0,true,0,''),
(163,88,0,0,11707,1,true,0,true,0,''),
(164,87,2,0,12324,5,true,1,false,2,'not IsHero()'),
(169,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(170,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(171,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(172,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(173,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(174,136,2,0,12324,2,true,1,false,2,'not IsHero()'),
(175,136,2,0,12324,3,true,1,false,2,'not IsHero()'),
(176,136,2,0,12324,3,true,1,false,2,'not IsHero()'),
(177,136,2,0,12324,3,true,1,false,2,'not IsHero()'),
(178,136,2,0,12324,3,true,1,false,2,'not IsHero()'),
(183,86,-1,0,0,0,true,1,true,0,''),
(184,88,0,0,12408,1,true,0,true,0,''),
(185,88,0,0,12409,1,true,0,true,0,''),
(187,88,0,1,0,0,true,0,true,0,''),
(190,151,0,0,16656,1,true,-1,true,0,''),
(191,151,0,0,16656,1,true,-1,true,0,''),
(192,151,0,0,16656,1,true,-1,true,0,''),
(193,151,0,0,16656,1,true,-1,true,0,''),
(194,151,0,0,0,0,true,-1,true,0,''),
(195,151,0,0,0,0,true,-1,true,0,''),
(199,178,0,500,0,0,true,-1,true,3,''),
(202,178,0,0,16656,1,true,-1,true,3,''),
(204,86,30,0,0,0,true,1,true,1,'not IsAchievementComplete(556)'),
(205,19,300,0,0,0,true,1,true,1,''),
(254,219,1,0,0,0,true,-1,true,0,''),
(257,87,0,0,15934,1,true,1,true,1,''),
(258,86,0,0,0,1,true,1,true,1,''),
(259,86,0,0,15993,1,true,-1,true,3,''),
(260,9,20,0,16073,1,true,1,false,1,''),
(261,87,-1,0,0,0,true,1,true,2,'!IsAchievementObjectiveComplete(2227)'),
(262,86,0,0,0,1,true,1,true,1,''),
(264,87,-1,0,0,0,true,1,true,5,''),
(265,87,-1,0,0,0,true,1,true,5,''),
(266,87,-1,0,0,0,true,1,true,5,''),
(267,87,-1,0,0,0,true,1,true,5,''),
(268,87,-1,0,0,0,true,1,true,5,''),
(269,87,-1,0,0,0,true,1,true,5,''),
(270,87,-1,0,0,0,true,1,true,5,''),
(271,87,-1,0,0,0,true,1,true,5,''),
(272,87,-1,0,0,0,true,1,true,5,''),
(273,87,-1,0,0,0,true,1,true,5,''),
(274,87,-1,0,0,0,true,1,true,5,''),
(275,87,-1,0,0,0,true,1,true,5,''),
(276,87,-1,0,0,0,true,1,true,5,''),
(277,87,-1,0,0,0,true,1,true,5,''),
(278,87,-1,0,0,0,true,1,true,5,''),
(279,87,-1,0,0,0,true,1,true,5,''),
(280,87,-1,0,0,0,true,1,true,5,''),
(309,237,-1,0,0,0,true,1,true,1,''),
(311,8,10,0,17537,1,true,1,false,1,''),
(313,209,20,0,0,0,true,1,false,1,''),
(314,86,20,0,0,0,true,1,false,1,'IsAchievementRunning(1646)'),
(315,8,5,0,17842,1,true,1,true,1,''),
(316,80,5,0,17844,1,true,1,true,1,''),
(317,86,1,0,0,0,false,1,true,0,''),
(318,86,15,0,18304,1,false,1,false,1,'IsAchievementRunning(1750)'),
(320,95,0,5,0,0,true,-1,true,0,''),
(321,86,20,0,0,0,true,1,false,1,''),
(348,206,-1,0,0,0,false,1,true,2,''),
(353,87,7200,0,0,0,false,1,false,0,'not IsHero()'),
(360,23,1800,0,14914,1,true,1,false,10,''),
(364,98,5,0,0,0,false,1,true,7,'not IsHero()'),
(374,87,-1,0,0,0,true,1,true,5,''),
(404,87,-1,0,0,0,true,1,true,5,'');
CREATE FUNCTION native_loot_chest_prototypes_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Original native loot-chest prototype source is immutable'; END $$;
CREATE TRIGGER native_loot_chest_prototypes_immutable BEFORE INSERT OR UPDATE OR DELETE ON native_loot_chest_prototypes
 FOR EACH ROW EXECUTE FUNCTION native_loot_chest_prototypes_immutable();
-- User-authorized reconstruction for the two placed, definition-less chests.
-- Native field1 refreshes bCI.dSG; original field2 is hydrated in the SAME13984.
-- No285 rewrite, asset/client edit, new object UID or original loot inheritance.
ALTER TABLE declared_treasure_locations ADD CONSTRAINT declared_treasure_original_identity
 UNIQUE(map_id,object_id,descriptor_id,catalog_revision);
CREATE TABLE declared_treasure_definition_overrides (
 map_id integer NOT NULL,object_id bigint NOT NULL,version integer NOT NULL CHECK(version>0),
 original_definition integer NOT NULL CHECK(original_definition>0),
 replacement_definition integer NOT NULL CHECK(replacement_definition>0),
 original_definition_missing boolean NOT NULL CHECK(original_definition_missing),
 native_action integer NOT NULL CHECK(native_action=22),native_mru integer NOT NULL CHECK(native_mru>0),
 required_item integer NOT NULL CHECK(required_item=0),required_quantity integer NOT NULL CHECK(required_quantity=0),
 required_kamas bigint NOT NULL CHECK(required_kamas=0),criterion text NOT NULL CHECK(criterion='not IsHero()'),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 definition_source_sha256 text NOT NULL CHECK(length(definition_source_sha256)=64),
 authority text NOT NULL CHECK(length(authority)>0),sealed boolean NOT NULL DEFAULT false,
 PRIMARY KEY(map_id,object_id),CHECK(original_definition<>replacement_definition),
 FOREIGN KEY(map_id,object_id,original_definition,catalog_revision)
 REFERENCES declared_treasure_locations(map_id,object_id,descriptor_id,catalog_revision)
);
CREATE FUNCTION declared_treasure_projection_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN RAISE EXCEPTION 'Sealed native treasure reconstruction is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER declared_treasure_projection_immutable BEFORE UPDATE OR DELETE ON declared_treasure_definition_overrides
 FOR EACH ROW EXECUTE FUNCTION declared_treasure_projection_immutable();
INSERT INTO declared_treasure_definition_overrides
(map_id,object_id,version,original_definition,replacement_definition,original_definition_missing,native_action,native_mru,
required_item,required_quantity,required_kamas,criterion,catalog_revision,definition_source_sha256,authority)
VALUES
(297,13819,1,179,353,true,22,87,0,0,0,'not IsHero()',
'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
'a95e2f1c0c3c9bd7ccfb59c42f329f7547235ef156826bb76d727b781f2f0ec8',
'Explicit user-approved reconstruction: preserve originalUID/location, use installed no-costLootChest353 menu via originalfg/bEH component1 plus state2 in one13984; custom100kamas once per character/chest remains the285 policy, not353 loot'),
(299,13821,1,181,353,true,22,87,0,0,0,'not IsHero()',
'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
'a95e2f1c0c3c9bd7ccfb59c42f329f7547235ef156826bb76d727b781f2f0ec8',
'Explicit user-approved reconstruction: preserve originalUID/location, use installed no-costLootChest353 menu via originalfg/bEH component1 plus state2 in one13984; custom100kamas once per character/chest remains the285 policy, not353 loot');
UPDATE declared_treasure_definition_overrides SET sealed=true;
