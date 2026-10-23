-- Staged migration 263. No content is activated by this additive schema.
-- Historical starter cache was a Well, misclassified by the generic LootChest
-- Java type. Remove only its configuration; preserve all claims/player items.
DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM treasure_chest_rules WHERE map_id=527 AND object_id=25114
            AND content_id='wakemu.astrub.starter-cache.1') THEN
  DELETE FROM treasure_chest_rewards WHERE map_id=527 AND object_id=25114;
  DELETE FROM treasure_chest_approaches WHERE map_id=527 AND object_id=25114;
  DELETE FROM treasure_chest_rules WHERE map_id=527 AND object_id=25114
   AND content_id='wakemu.astrub.starter-cache.1';
 END IF;
END $$;

CREATE TABLE account_achievement_reward_claims (
 account_id bigint NOT NULL REFERENCES accounts(id),
 reward_id integer NOT NULL CHECK(reward_id>0),
 achievement_id integer NOT NULL CHECK(achievement_id>0),
 character_id bigint NOT NULL REFERENCES characters(id),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 claimed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(account_id,reward_id)
);

-- The server database is the realm boundary, exactly as for account_wallets.
-- Reviewed object/objective relations are independent of custom item claims.
-- The client Java LootChest family also contains wells/pebbles. Membership
-- below requires an independently reviewed positive original object identity.
CREATE TABLE achievement_chest_source_attestations (
 map_id integer NOT NULL,
 object_id bigint NOT NULL,
 native_definition integer NOT NULL,
 original_name_en text NOT NULL,
 object_kind text NOT NULL CHECK(object_kind IN ('chest','emote_chest','gemlock')),
 object_family text NOT NULL CHECK(object_family IN ('LootChest','GenericActivableInteractiveElement')),
 native_action integer NOT NULL CHECK(native_action BETWEEN 0 AND 65535),
 native_parameter integer NOT NULL CHECK(native_parameter BETWEEN 0 AND 65535),
 native_payload_hex text NOT NULL,
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 PRIMARY KEY(map_id,object_id,native_definition)
);

-- Original content85[353] Gemlockitup, matched to original object31733.
-- This attests object identity only. No item/repeat/journal rule is activated.
INSERT INTO achievement_chest_source_attestations VALUES
 (1207,31733,353,'Gemlockitup','gemlock','LootChest',22,0,
  '02000000000b010000000d00000104b7ffffff8bffffffe3000000010101010001000000033335330000007bc60101',
  'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
  'ef6d7a2986f5c69c57a928c6854ecf8a7775ad20b539af63e4d989216ee63553');

-- Original table31 programs, not activated world reward bindings.
CREATE TABLE native_generic_emote_effect_sources (
 descriptor_id integer NOT NULL,
 wire_action integer NOT NULL,
 effect_reference integer NOT NULL,
 native_action_id integer NOT NULL,
 native_group_id integer NOT NULL,
 effect_type integer NOT NULL CHECK(effect_type=7),
 action_criterion text NOT NULL,
 effect_criterion text NOT NULL,
 parameters text[] NOT NULL,
 group_cof boolean NOT NULL,
 group_cog integer NOT NULL,
 group_cnd integer NOT NULL,
 group_cod integer NOT NULL,
 group_coe integer NOT NULL,
 group_clx integer NOT NULL,
 raw_cob real NOT NULL,
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 PRIMARY KEY(descriptor_id,wire_action,effect_reference)
);
INSERT INTO native_generic_emote_effect_sources VALUES
(55,0,103,64,65,7,'','not HasEmote(20022)',ARRAY['20022']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(59,0,114,68,69,7,'','not HasEmote(20036)',ARRAY['20036']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(60,0,117,69,70,7,'','not HasEmote(20021)',ARRAY['20021']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(61,0,120,70,71,7,'','not HasEmote(20029)',ARRAY['20029']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(62,0,123,71,72,7,'','not HasEmote(20049)',ARRAY['20049']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(63,0,126,72,73,7,'','not HasEmote(20052)',ARRAY['20052']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(64,0,129,73,74,7,'','not HasEmote(20057)',ARRAY['20057']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(65,0,132,74,75,7,'','not HasEmote(20056)',ARRAY['20056']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(66,0,135,75,76,7,'','not HasEmote(20046)',ARRAY['20046']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(67,0,138,76,77,7,'','not HasEmote(20048)',ARRAY['20048']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(68,0,141,77,78,7,'','not HasEmote(20038)',ARRAY['20038']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(69,0,144,78,79,7,'','not HasEmote(20035)',ARRAY['20035']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(70,0,147,79,80,7,'','not HasEmote(20027)',ARRAY['20027']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(71,0,150,80,81,7,'','not HasEmote(20032)',ARRAY['20032']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(72,0,153,81,82,7,'','not HasEmote(20044)',ARRAY['20044']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(73,0,156,82,83,7,'','not HasEmote(20037)',ARRAY['20037']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(74,0,159,83,84,7,'','not HasEmote(20025)',ARRAY['20025']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(75,0,162,84,85,7,'','not HasEmote(20042)',ARRAY['20042']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(76,0,165,85,86,7,'','not HasEmote(20053)',ARRAY['20053']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(77,0,168,86,87,7,'','not HasEmote(20058)',ARRAY['20058']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(78,0,171,87,88,7,'','not HasEmote(20051)',ARRAY['20051']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(79,0,174,88,89,7,'','not HasEmote(20034)',ARRAY['20034']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(80,0,177,89,90,7,'','not HasEmote(20071)',ARRAY['20071']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(81,0,180,90,91,7,'','not HasEmote(20028)',ARRAY['20028']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(82,0,183,91,92,7,'','not HasEmote(20031)',ARRAY['20031']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(83,0,186,92,93,7,'','not HasEmote(20039)',ARRAY['20039']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(84,0,189,93,94,7,'','not HasEmote(20059)',ARRAY['20059']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(85,0,192,94,95,7,'','not HasEmote(20054)',ARRAY['20054']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(86,0,195,95,96,7,'','not HasEmote(20040)',ARRAY['20040']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(87,0,198,96,97,7,'','not HasEmote(20009)',ARRAY['20009']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(88,0,201,97,98,7,'','not HasEmote(20030)',ARRAY['20030']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(90,0,207,99,100,7,'','not HasEmote(20069)',ARRAY['20069']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(91,0,210,100,101,7,'','not HasEmote(20033)',ARRAY['20033']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(92,0,213,101,102,7,'','not HasEmote(20047)',ARRAY['20047']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(93,0,216,102,103,7,'','not HasEmote(20041)',ARRAY['20041']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(94,0,219,103,104,7,'','not HasEmote(20026)',ARRAY['20026']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(95,0,222,104,105,7,'','not HasEmote(20050)',ARRAY['20050']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(96,0,225,105,106,7,'','not HasEmote(20018)',ARRAY['20018']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(97,0,228,106,107,7,'','not HasEmote(20045)',ARRAY['20045']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(98,0,231,107,108,7,'','not HasEmote(20063)',ARRAY['20063']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(99,0,234,108,109,7,'','not HasEmote(20071)',ARRAY['20071']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(100,0,237,109,110,7,'','not HasEmote(20070)',ARRAY['20070']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(103,0,245,112,113,7,'','not HasEmote(20012)',ARRAY['20012']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(173,0,374,194,194,7,'','not HasEmote(20001)',ARRAY['20001']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(194,0,423,217,217,7,'','not HasEmote(20002)',ARRAY['20002']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(195,0,426,218,218,7,'','not HasEmote(20003)',ARRAY['20003']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(197,0,432,220,220,7,'','not HasEmote(20006)',ARRAY['20006']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(198,0,435,221,221,7,'','not HasEmote(20005)',ARRAY['20005']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(200,0,441,223,223,7,'','not HasEmote(20007)',ARRAY['20007']::text[],TRUE,0,0,0,0,87,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(1055,0,2586,1331,1298,7,'not IsAchievementObjectiveComplete(6020) or not HasEmote(20007)','not HasEmote(20007)',ARRAY['20007']::text[],FALSE,4000,0,0,0,308,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(1056,0,2589,1332,1299,7,'not IsAchievementObjectiveComplete(6021) or not HasEmote(20008)','not HasEmote(20008)',ARRAY['20008']::text[],FALSE,4000,0,0,0,308,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(1057,0,2592,1333,1300,7,'not IsAchievementObjectiveComplete(6022) or not HasEmote(20010)','not HasEmote(20010)',ARRAY['20010']::text[],FALSE,4000,0,0,0,308,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(1058,0,2595,1334,1301,7,'not IsAchievementObjectiveComplete(6023) or not HasEmote(20011)','not HasEmote(20011)',ARRAY['20011']::text[],FALSE,4000,0,0,0,308,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450'),
(1059,0,2598,1335,1302,7,'not IsAchievementObjectiveComplete(6024) or not HasEmote(20016)','not HasEmote(20016)',ARRAY['20016']::text[],FALSE,4000,0,0,0,308,1.0,'652fb00a5b38cfc2a90a4ca969f9b8c4086bfcdc2e3d5934f385402bd4335552','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450');

CREATE TABLE achievement_chest_bindings (
 binding_id integer PRIMARY KEY CHECK(binding_id>0),
 map_id integer NOT NULL CHECK(map_id>0),
 object_id bigint NOT NULL CHECK(object_id>0),
 definition_id integer CHECK(definition_id>0),
 objective_id integer CHECK(objective_id>0),
 emote_id integer REFERENCES native_emote_definitions(emote_id),
 effect_reference integer CHECK(effect_reference>0),
 effect_criterion text,
 native_definition integer NOT NULL CHECK(native_definition>0),
 native_action integer NOT NULL CHECK(native_action BETWEEN 0 AND 65535),
 native_criterion text NOT NULL,
 activation_criterion text NOT NULL,
 completion_criterion text NOT NULL,
 artifact_reference integer CHECK(artifact_reference>0),
 x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
 native_payload_hex text NOT NULL,
 native_state_payload_hex text,
 native_geometry_sha256 text NOT NULL CHECK(length(native_geometry_sha256)=64),
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 binding_authority text NOT NULL CHECK(binding_authority IN
   ('recovered_native_chest_objective_v1','reviewed_reconstructed_chest_objective_v1',
    'recovered_native_emote_effect7_v1')),
 CHECK((definition_id IS NOT NULL AND objective_id IS NOT NULL AND emote_id IS NULL
        AND effect_reference IS NULL AND effect_criterion IS NULL)
    OR (definition_id IS NULL AND objective_id IS NULL AND emote_id IS NOT NULL
        AND effect_reference IS NOT NULL AND effect_criterion IS NOT NULL
        AND effect_criterion='not HasEmote('||emote_id::text||')'
        AND binding_authority='recovered_native_emote_effect7_v1')),
 UNIQUE(map_id,object_id,objective_id),
 UNIQUE(map_id,object_id,effect_reference),
 FOREIGN KEY(map_id,object_id,native_definition) REFERENCES
  achievement_chest_source_attestations(map_id,object_id,native_definition)
);

CREATE TABLE achievement_chest_approaches (
 binding_id integer NOT NULL REFERENCES achievement_chest_bindings(binding_id),
 x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
 PRIMARY KEY(binding_id,x,y,z)
);

CREATE TABLE character_achievement_chest_opens (
 character_id bigint NOT NULL REFERENCES characters(id),
 binding_id integer NOT NULL REFERENCES achievement_chest_bindings(binding_id),
 account_id bigint NOT NULL REFERENCES accounts(id),
 rule_sha256 text NOT NULL CHECK(length(rule_sha256)=64),
 event_payload jsonb NOT NULL CHECK(jsonb_typeof(event_payload)='object'),
 opened_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(character_id,binding_id)
);
