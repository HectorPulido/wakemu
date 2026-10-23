-- Native action3 world-member lifecycle. No profile or service is enabled.
CREATE TABLE environmental_destroy_sources (
 source_key text NOT NULL,scenario_id integer NOT NULL,policy_version text NOT NULL,
 template_reference integer NOT NULL CHECK(template_reference>0),
 monster_reference integer NOT NULL CHECK(monster_reference>0),action_id integer NOT NULL CHECK(action_id>0),
 action_descriptor jsonb NOT NULL CHECK(jsonb_typeof(action_descriptor)='object'),
 descriptor_sha256 text NOT NULL CHECK(length(descriptor_sha256)=64),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 public_proof jsonb NOT NULL CHECK(jsonb_typeof(public_proof)='object'),
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 PRIMARY KEY(source_key,scenario_id,policy_version,monster_reference,action_id),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_profile_destroy_policy (
 profile_key text NOT NULL,version integer NOT NULL,source_key text NOT NULL,scenario_id integer NOT NULL,
 policy_version text NOT NULL,monster_reference integer NOT NULL,action_id integer NOT NULL,
 PRIMARY KEY(profile_key,version,monster_reference,action_id),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,scenario_id,policy_version,monster_reference,action_id) REFERENCES environmental_destroy_sources
);
CREATE TABLE environmental_destroy_rosters (
 instance_id bigint NOT NULL,group_ordinal integer NOT NULL,
 birth_members jsonb NOT NULL CHECK(jsonb_typeof(birth_members)='array' AND jsonb_array_length(birth_members)>0),
 roster_sha256 text NOT NULL CHECK(length(roster_sha256)=64),
 PRIMARY KEY(instance_id,group_ordinal),
 FOREIGN KEY(instance_id,group_ordinal) REFERENCES environmental_owned_groups
);
CREATE TABLE environmental_monster_destructions (
 instance_id bigint NOT NULL,monster_id bigint NOT NULL CHECK(monster_id<0),group_ordinal integer NOT NULL,
 account_id bigint NOT NULL,character_id bigint NOT NULL,
 action_id integer NOT NULL,monster_reference integer NOT NULL,policy_version text NOT NULL,
 target_snapshot jsonb NOT NULL CHECK(jsonb_typeof(target_snapshot)='object'),
 token text NOT NULL UNIQUE,occurred_at_ms bigint NOT NULL CHECK(occurred_at_ms>=0),
 group_revision bigint NOT NULL CHECK(group_revision>0),
 PRIMARY KEY(instance_id,monster_id),UNIQUE(instance_id,group_ordinal,group_revision),
 FOREIGN KEY(instance_id,monster_id) REFERENCES environmental_owned_group_members(instance_id,monster_id),
 FOREIGN KEY(instance_id,group_ordinal) REFERENCES environmental_destroy_rosters,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE TABLE environmental_destroy_publications (
 instance_id bigint NOT NULL,group_ordinal integer NOT NULL,group_revision bigint NOT NULL,
 created_at_ms bigint NOT NULL,published_at_ms bigint,
 PRIMARY KEY(instance_id,group_ordinal,group_revision),
 FOREIGN KEY(instance_id,group_ordinal,group_revision)
 REFERENCES environmental_monster_destructions(instance_id,group_ordinal,group_revision)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['environmental_destroy_sources','environmental_profile_destroy_policy',
 'environmental_destroy_rosters','environmental_monster_destructions'] LOOP
 EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION environmental_random_roster_immutable()',
 'immutable_'||t,t);
 END LOOP;
END $$;
-- A recovery/respawn UPDATE must not bring an already consumed UID back.
CREATE FUNCTION environmental_destroy_no_resurrection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM environmental_owned_groups o
   JOIN environmental_monster_destructions d USING(instance_id,group_ordinal)
   JOIN LATERAL jsonb_array_elements(NEW.members) m ON (m->>'id')::bigint=d.monster_id
   WHERE o.map_id=NEW.map_id AND o.world_instance_id=NEW.instance_id AND o.group_id=NEW.group_id)
 THEN RAISE EXCEPTION 'Destroyed environmental monster cannot reappear'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_destroy_no_resurrection BEFORE INSERT OR UPDATE OF members,status ON combat_groups
 FOR EACH ROW EXECUTE FUNCTION environmental_destroy_no_resurrection();

-- Eight explicit public target reconstructions; no enabled profile.
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1328,'wakemu.explicit-public-target-native-destroy-v1',1595,2253,265,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":265,"getDuration":0,"native_class":"aMg"}'::jsonb,'f9464b30778f432097f8a9646af38b9008dc7864402a601dcb8afad71445571d','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"2014-07-22","url":"https://wakfu.jeuxonline.info/actualite/45181/mise-jour-22-juillet-monture-simone"}'::jsonb,'f67797973f374f8b07e6103a71dfabe4acca59fea8222e59f0cc7d1d91de184b');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1327,'wakemu.explicit-public-target-native-destroy-v1',1595,2253,265,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":265,"getDuration":0,"native_class":"aMg"}'::jsonb,'f9464b30778f432097f8a9646af38b9008dc7864402a601dcb8afad71445571d','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"2014-07-22","url":"https://wakfu.jeuxonline.info/actualite/45181/mise-jour-22-juillet-monture-simone"}'::jsonb,'05af588a6cfa2a159573d2c9d4c9375714a21094f487f9bfc3b2502dd74beaf0');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1326,'wakemu.explicit-public-target-native-destroy-v1',1595,2253,265,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":265,"getDuration":0,"native_class":"aMg"}'::jsonb,'f9464b30778f432097f8a9646af38b9008dc7864402a601dcb8afad71445571d','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"2014-07-22","url":"https://wakfu.jeuxonline.info/actualite/45181/mise-jour-22-juillet-monture-simone"}'::jsonb,'81221f36969ca17caf780e107c9af968a9b0873ee356db79ffd88b09c3a9a97d');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1325,'wakemu.explicit-public-target-native-destroy-v1',1595,2253,265,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":265,"getDuration":0,"native_class":"aMg"}'::jsonb,'f9464b30778f432097f8a9646af38b9008dc7864402a601dcb8afad71445571d','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"2014-07-22","url":"https://wakfu.jeuxonline.info/actualite/45181/mise-jour-22-juillet-monture-simone"}'::jsonb,'0bdeabd84a7626197c9d290dd25f4d30882d32471aab806f1833cc38217857c4');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1225,'wakemu.explicit-public-target-native-destroy-v1',1581,2236,263,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":263,"getDuration":0,"native_class":"aMg"}'::jsonb,'d71fa2d56cd1a4dd87affc5d4597af876e815c8cf4439a22aec1d225e51988dd','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"indexed-retrieved-2026-10-22","url":"https://wakfu.wiki.gg/wiki/Environmental_Quests"}'::jsonb,'d1cce8cfc4d3721ed94c0d483246b049118899e2a377a5c84defb2b9f57d19c7');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1223,'wakemu.explicit-public-target-native-destroy-v1',1581,2236,263,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":263,"getDuration":0,"native_class":"aMg"}'::jsonb,'d71fa2d56cd1a4dd87affc5d4597af876e815c8cf4439a22aec1d225e51988dd','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"indexed-retrieved-2026-10-22","url":"https://wakfu.wiki.gg/wiki/Environmental_Quests"}'::jsonb,'0a3651bb4f81c14feb324c72975e15aa89a16928ea65e553a658556b27fa4a2b');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1222,'wakemu.explicit-public-target-native-destroy-v1',1581,2236,263,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":263,"getDuration":0,"native_class":"aMg"}'::jsonb,'d71fa2d56cd1a4dd87affc5d4597af876e815c8cf4439a22aec1d225e51988dd','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"indexed-retrieved-2026-10-22","url":"https://wakfu.wiki.gg/wiki/Environmental_Quests"}'::jsonb,'79abf8392bf081caf659950b44c8a1b2ae61200abdedd05b6e06bc58923a5756');
INSERT INTO environmental_destroy_sources (source_key,scenario_id,policy_version,template_reference,monster_reference,action_id,action_descriptor,descriptor_sha256,catalog_revision,public_proof,source_sha256) VALUES('installed-environmental-source-v1',-1221,'wakemu.explicit-public-target-native-destroy-v1',1581,2236,263,'{"aGJ":3,"cbH":0,"clT":"","clx":315,"csI":false,"csJ":true,"csK":false,"d":263,"getDuration":0,"native_class":"aMg"}'::jsonb,'d71fa2d56cd1a4dd87affc5d4597af876e815c8cf4439a22aec1d225e51988dd','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','{"kind":"EXPLICIT_PUBLIC_QUEST_TARGET_MULTILINGUAL_NATIVE_JOIN","source_date":"indexed-retrieved-2026-10-22","url":"https://wakfu.wiki.gg/wiki/Environmental_Quests"}'::jsonb,'62faeb08118f8b53f0b7dcb88228fd0450f0062ddec9550f90c0b201bc9f9084');

-- Projection facts are separate from the physical performer's one-time action.
CREATE TABLE environmental_destroy_progress_facts (
 instance_id bigint NOT NULL,character_id bigint NOT NULL,account_id bigint NOT NULL,
 monster_id bigint NOT NULL,receipt_key text NOT NULL,occurred_at_ms bigint NOT NULL,
 fact_digest text NOT NULL CHECK(length(fact_digest)=64),
 PRIMARY KEY(instance_id,character_id,monster_id),
 FOREIGN KEY(instance_id,monster_id) REFERENCES environmental_monster_destructions,
 FOREIGN KEY(instance_id,character_id,account_id) REFERENCES environmental_participants(instance_id,character_id,account_id)
);
CREATE TRIGGER immutable_environmental_destroy_progress_facts BEFORE UPDATE OR DELETE ON environmental_destroy_progress_facts
 FOR EACH ROW EXECUTE FUNCTION environmental_random_roster_immutable();

-- UI/result qualification for original type5 action3. No fight receipt reuse.
CREATE TABLE environmental_profile_destroy_ui (
 profile_key text NOT NULL,version integer NOT NULL,source_key text NOT NULL,native_scenario_id integer NOT NULL,
 authority text NOT NULL CHECK(length(btrim(authority))>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios
);
CREATE FUNCTION validate_environmental_destroy_ui() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF EXISTS(SELECT 1 FROM environmental_profile_destroy_ui q
  JOIN environmental_runtime_profiles p USING(profile_key,version)
  JOIN environmental_native_scenarios n ON n.source_key=q.source_key AND n.scenario_id=q.native_scenario_id
  WHERE q.profile_key=k AND q.version=v AND (
   p.family<>'monster_destroy' OR p.native_scenario_id IS DISTINCT FROM q.native_scenario_id
   OR n.native_type<>5 OR n.family<>'destroy_monster_action' OR NOT n.client_visible
   OR n.native_subtype<>CASE p.mode WHEN 'solo' THEN 1 WHEN 'race' THEN 2
       WHEN 'competitive' THEN 3 WHEN 'collaborative' THEN 4 ELSE 0 END
   OR NOT EXISTS(SELECT 1 FROM environmental_native_configuration c WHERE c.source_key=q.source_key
     AND c.scenario_id=q.native_scenario_id AND c.normalized_key='monsteractiontypeid' AND c.native_value='3')
   OR NOT EXISTS(SELECT 1 FROM environmental_profile_destroy_policy d
     WHERE d.profile_key=k AND d.version=v)
   OR EXISTS(SELECT 1 FROM environmental_profile_destroy_policy d
     JOIN environmental_destroy_sources s USING(source_key,scenario_id,policy_version,monster_reference,action_id)
     WHERE d.profile_key=k AND d.version=v AND (d.source_key<>q.source_key OR d.scenario_id<>q.native_scenario_id
       OR s.catalog_revision<>p.catalog_revision OR s.action_descriptor->>'aGJ' IS DISTINCT FROM '3'
       OR s.action_descriptor->>'d' IS DISTINCT FROM d.action_id::text)))) THEN
  RAISE EXCEPTION 'Destroy UI requires exact original scenario and qualified native action3';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_destroy_ui_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_destroy_ui DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_ui();
CREATE CONSTRAINT TRIGGER environmental_destroy_ui_profile_inventory AFTER INSERT OR UPDATE
 ON environmental_runtime_profiles DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_ui();
CREATE CONSTRAINT TRIGGER environmental_destroy_ui_source_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_destroy_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_ui();
CREATE TRIGGER environmental_destroy_ui_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_destroy_ui FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_destroy_ui_no_truncate BEFORE TRUNCATE
 ON environmental_profile_destroy_ui FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='environmental_profile_ranked_reward_policy'::regclass
  AND contype='c' AND pg_get_constraintdef(oid) LIKE '%policy_contract%' LOOP
  EXECUTE format('ALTER TABLE environmental_profile_ranked_reward_policy DROP CONSTRAINT %I',c.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_profile_ranked_reward_policy ADD CONSTRAINT env_destroy_ranked_reward_contract
 CHECK(policy_contract IN ('wakemu.original-resource-rank-bands-base-rewards.v1','wakemu.original-group-rank-bands-base-rewards.v1','wakemu.original-destroy-rank-bands-base-rewards.v1'));
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='environmental_profile_simple_result_policy'::regclass
  AND contype='c' AND pg_get_constraintdef(oid) LIKE '%policy_contract%' LOOP
  EXECUTE format('ALTER TABLE environmental_profile_simple_result_policy DROP CONSTRAINT %I',c.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_profile_simple_result_policy ADD CONSTRAINT env_destroy_simple_result_contract
 CHECK(policy_contract IN ('wakemu.original-resource-single-primary-base-result.v1','wakemu.original-group-single-primary-base-result.v1','wakemu.original-destroy-single-primary-base-result.v1'));
CREATE OR REPLACE FUNCTION validate_environmental_ranked_reward_bands() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;expected bigint;actual bigint;counter_name text;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,r.native_scenario_id AS profile_scenario,r.family,r.mode INTO p
 FROM environmental_profile_ranked_reward_policy q JOIN environmental_runtime_profiles r USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR p.mode NOT IN ('competitive','race') THEN
  RAISE EXCEPTION 'Ranked rewards differ from profile mode/source';
 END IF;
 IF p.family='resource_collect' AND p.policy_contract='wakemu.original-resource-rank-bands-base-rewards.v1' THEN
  counter_name:='nbResourcePlayer';
  IF NOT EXISTS(SELECT 1 FROM environmental_native_scenarios n WHERE n.source_key=p.source_key
    AND n.scenario_id=p.native_scenario_id AND n.family='resource_interaction') THEN
   RAISE EXCEPTION 'Ranked resource policy requires original resource source';
  END IF;
 ELSIF p.family IN ('monster_defeat','group_defeat') AND p.policy_contract='wakemu.original-group-rank-bands-base-rewards.v1' THEN
  counter_name:='nbMobPlayer';
  IF NOT EXISTS(SELECT 1 FROM environmental_profile_group_ui q
    WHERE q.profile_key=k AND q.version=v AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id) THEN
   RAISE EXCEPTION 'Ranked group policy requires qualified group UI';
  END IF;
 ELSIF p.family='monster_destroy' AND p.policy_contract='wakemu.original-destroy-rank-bands-base-rewards.v1' THEN
  counter_name:='nbMobPlayer';
  IF NOT EXISTS(SELECT 1 FROM environmental_profile_destroy_ui q WHERE q.profile_key=k AND q.version=v
    AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id) THEN
   RAISE EXCEPTION 'Ranked destroy policy requires qualified action3 UI';
  END IF;
 ELSE RAISE EXCEPTION 'Unsupported ranked reward family/contract';
 END IF;
 SELECT count(*) INTO expected FROM environmental_native_reward_display
 WHERE source_key=p.source_key AND scenario_id=p.native_scenario_id AND primary_reward_list;
 SELECT count(*) INTO actual FROM environmental_profile_ranked_reward_bands WHERE profile_key=k AND version=v;
 IF expected=0 OR actual<>expected THEN RAISE EXCEPTION 'Incomplete original primary reward list'; END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_ranked_reward_bands b
  JOIN environmental_native_rewards_raw r ON r.source_key=b.source_key AND r.scenario_id=b.native_scenario_id AND r.reward_id=b.reward_id
  JOIN environmental_native_reward_display d ON d.source_key=r.source_key AND d.scenario_id=r.scenario_id AND d.reward_id=r.reward_id
  WHERE b.profile_key=k AND b.version=v AND (
   NOT d.primary_reward_list OR d.primary_result_index IS DISTINCT FROM b.primary_reward_index OR
   (r.native_text='' AND (b.rank_min IS NOT NULL OR b.rank_max IS NOT NULL)) OR
   (r.native_text<>'' AND (b.rank_min IS NULL OR b.rank_max IS NULL OR
     r.native_text <> format('ListContains(GetUser(), GetPlayerInRankRange(%s, %s, "%s", False))',b.rank_min,b.rank_max,counter_name))))) THEN
  RAISE EXCEPTION 'Reward band differs from original predicate/index';
 END IF;
 IF (SELECT count(*) FROM environmental_profile_ranked_reward_bands WHERE profile_key=k AND version=v AND rank_min IS NULL)<>1 THEN
  RAISE EXCEPTION 'Exactly one original blank fallback is required';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_ranked_reward_bands a
  JOIN environmental_profile_ranked_reward_bands b USING(profile_key,version)
  WHERE a.profile_key=k AND a.version=v AND a.primary_reward_index<b.primary_reward_index
    AND a.rank_min<=b.rank_max AND b.rank_min<=a.rank_max) THEN
  RAISE EXCEPTION 'Overlapping environmental reward rank bands';
 END IF;
 RETURN NULL;
END $$;
CREATE OR REPLACE FUNCTION validate_environmental_simple_result_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;n bigint;primary_row record;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,f.native_scenario_id AS profile_scenario,f.family,f.mode INTO p
 FROM environmental_profile_simple_result_policy q
 JOIN environmental_runtime_profiles f USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR p.family NOT IN ('resource_collect','monster_defeat','group_defeat','monster_destroy')
   OR p.mode NOT IN ('solo','collaborative')
   OR p.parameter_mode<>(CASE WHEN p.mode='solo' THEN 'personal_progress' ELSE 'global_progress' END) THEN
  RAISE EXCEPTION 'Simple resource result differs from its declared profile';
 END IF;
 IF p.family='resource_collect' AND p.policy_contract='wakemu.original-resource-single-primary-base-result.v1' THEN
  IF NOT EXISTS(SELECT 1 FROM environmental_native_scenarios s WHERE s.source_key=p.source_key
    AND s.scenario_id=p.native_scenario_id AND s.family='resource_interaction' AND s.client_visible
    AND s.native_subtype=CASE WHEN p.mode='solo' THEN 1 ELSE 4 END) THEN
   RAISE EXCEPTION 'Simple result requires original resource mode/source';
  END IF;
 ELSIF p.family IN ('monster_defeat','group_defeat') AND p.policy_contract='wakemu.original-group-single-primary-base-result.v1' THEN
  IF NOT EXISTS(SELECT 1 FROM environmental_profile_group_ui q WHERE q.profile_key=k AND q.version=v
    AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id) THEN
   RAISE EXCEPTION 'Simple group result requires qualified group UI';
  END IF;
 ELSIF p.family='monster_destroy' AND p.policy_contract='wakemu.original-destroy-single-primary-base-result.v1' THEN
  IF NOT EXISTS(SELECT 1 FROM environmental_profile_destroy_ui q WHERE q.profile_key=k AND q.version=v
    AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id) THEN
   RAISE EXCEPTION 'Simple destroy result requires qualified action3 UI';
  END IF;
 ELSE RAISE EXCEPTION 'Unsupported simple result family/contract';
 END IF;
 SELECT count(*) INTO n FROM environmental_native_reward_display
 WHERE source_key=p.source_key AND scenario_id=p.native_scenario_id AND primary_reward_list;
 SELECT d.*,raw.native_text INTO primary_row FROM environmental_native_reward_display d
 JOIN environmental_native_rewards_raw raw USING(source_key,scenario_id,reward_id)
 WHERE d.source_key=p.source_key AND d.scenario_id=p.native_scenario_id AND d.reward_id=p.reward_id;
 IF n<>1 OR NOT FOUND OR primary_row.primary_reward_list IS DISTINCT FROM true
   OR primary_row.primary_result_index IS DISTINCT FROM 0 OR primary_row.native_text IS DISTINCT FROM '' THEN
  RAISE EXCEPTION 'Simple result requires exactly one original unconditional primary reward';
 END IF;
 RETURN NULL;
END $$;
CREATE OR REPLACE FUNCTION validate_environmental_native_variable_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;n bigint;b bigint;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,r.native_scenario_id AS profile_scenario,r.family,r.mode INTO p
 FROM environmental_profile_native_variable_policy q
 JOIN environmental_runtime_profiles r USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR
    p.family NOT IN ('resource_collect','resource_plant','monster_defeat','group_defeat','monster_destroy') THEN
  RAISE EXCEPTION 'Environmental variable policy differs from its profile';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_native_scenarios s WHERE s.source_key=p.source_key
           AND s.scenario_id=p.native_scenario_id AND s.family='portal_boss_chain') THEN
  RAISE EXCEPTION 'Portal variable projections are not supported';
 END IF;
 IF EXISTS(SELECT 1 FROM (SELECT profile_key,version FROM environmental_profile_group_ui UNION ALL SELECT profile_key,version FROM environmental_profile_destroy_ui) q
  JOIN environmental_profile_native_variable_bindings x USING(profile_key,version)
  WHERE q.profile_key=k AND q.version=v AND x.native_name IN ('nbMobPlayer','nbGroupPlayer','nbMobGlobal','nbGroupGlobal')
    AND x.binding_kind<>CASE WHEN x.native_name LIKE '%Player' THEN 'entity_personal_progress' ELSE 'entity_global_progress' END) THEN
  RAISE EXCEPTION 'Group UI requires independent durable entity counters';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_native_variable_bindings x
  WHERE x.profile_key=k AND x.version=v AND NOT (
   (x.binding_kind IN ('entity_personal_progress','entity_global_progress') AND ((p.family IN ('monster_defeat','group_defeat') AND EXISTS(SELECT 1 FROM environmental_profile_group_ui q
        WHERE q.profile_key=k AND q.version=v AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id))
      OR (p.family='monster_destroy' AND EXISTS(SELECT 1 FROM environmental_profile_destroy_ui q
        WHERE q.profile_key=k AND q.version=v AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id)))
     AND x.native_name='nb'||CASE x.entity_kind WHEN 'monster' THEN 'Mob' WHEN 'group' THEN 'Group' END
       ||CASE x.binding_kind WHEN 'entity_personal_progress' THEN 'Player' ELSE 'Global' END) OR
   (x.binding_kind='leader_progress' AND p.mode='competitive' AND x.native_name IN ('nbResourceMax','nbMobMax')) OR
   (x.binding_kind='declared_threshold' AND x.native_name IN ('nbResourceMin','nbMobMin')) OR
   (x.binding_kind='personal_progress' AND x.native_name IN ('nbResourcePlayer','nbGroupPlayer','nbMobPlayer')) OR
   (x.binding_kind='global_progress' AND x.native_name IN ('nbResourceGlobal','nbGroupGlobal','nbMobGlobal')) OR
   (x.binding_kind IN ('spawned','remaining') AND
     x.native_name='nb'||CASE x.entity_kind WHEN 'resource' THEN 'Resource' WHEN 'group' THEN 'Group' ELSE 'Mob' END
       ||CASE x.binding_kind WHEN 'spawned' THEN 'Spawned' ELSE 'Left' END) OR
   (x.binding_kind='configconstant' AND x.native_name IN
     ('challengeDuration','challengeLevelMin','challengeLevelMax','notificationIntervalDuration',
      'nbGroupForReward','nbMobForReward','nbResourceForReward')))) THEN
  RAISE EXCEPTION 'Unsupported environmental variable binding semantics';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_native_variable_bindings x
  JOIN environmental_native_configuration c ON c.source_key=x.source_key
   AND c.scenario_id=x.native_scenario_id AND c.native_key=x.configuration_key
  WHERE x.profile_key=k AND x.version=v AND c.normalized_key<>CASE WHEN x.binding_kind='declared_threshold'
    THEN CASE x.native_name WHEN 'nbResourceMin' THEN 'nbresourceforreward'
                           WHEN 'nbMobMin' THEN 'nbmobforreward' END
    ELSE lower(x.native_name) END) THEN
  RAISE EXCEPTION 'Environmental variable configuration key differs from its native name';
 END IF;
 SELECT count(*) INTO n FROM environmental_native_variables
 WHERE source_key=p.source_key AND scenario_id=p.native_scenario_id;
 SELECT count(*) INTO b FROM environmental_profile_native_variable_bindings WHERE profile_key=k AND version=v;
 IF n=0 OR n<>b OR EXISTS(
  SELECT 1 FROM environmental_profile_native_variable_bindings x
  JOIN environmental_native_variables y ON y.source_key=x.source_key AND y.scenario_id=x.native_scenario_id
   AND y.ordinal=x.variable_index
  WHERE x.profile_key=k AND x.version=v AND x.native_name<>y.native_name) THEN
  RAISE EXCEPTION 'Environmental variable bindings must match the complete original ordered array';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_native_variable_bindings x
  JOIN environmental_native_configuration c ON c.source_key=x.source_key
   AND c.scenario_id=x.native_scenario_id AND c.native_key=x.configuration_key
  WHERE x.profile_key=k AND x.version=v AND x.binding_kind IN ('configconstant','declared_threshold')
   AND (c.native_value !~ '^-?[0-9]+$' OR c.native_value::numeric<>x.constant_value)) THEN
  RAISE EXCEPTION 'Environmental constant differs from original configuration';
 END IF;
 RETURN NULL;
END $$;

-- Reuse the same frozen ordinary sizing/caps. Existing 518 pools are unchanged.
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint
 WHERE conrelid='environmental_random_roster_policies'::regclass AND contype='c'
 AND (pg_get_constraintdef(oid) LIKE '%native_type%' OR pg_get_constraintdef(oid) LIKE '%nb_group_for_reward%') LOOP
 EXECUTE format('ALTER TABLE environmental_random_roster_policies DROP CONSTRAINT %I',c.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_random_roster_policies ADD CONSTRAINT environmental_roster_native_types
 CHECK(native_type IN(5,6,7,8));
ALTER TABLE environmental_random_roster_policies ADD CONSTRAINT environmental_roster_typed_reward_minima
 CHECK((native_type=7 AND nb_group_for_reward>0 AND nb_mob_for_reward=0)
    OR(native_type IN(5,6,8) AND nb_mob_for_reward>0 AND nb_group_for_reward=0));
CREATE FUNCTION validate_environmental_destroy_random_roster() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s text;i integer;p record;c record;
BEGIN
 s:=COALESCE(NEW.source_key,OLD.source_key);i:=COALESCE(NEW.scenario_id,OLD.scenario_id);
 FOR p IN SELECT * FROM environmental_random_roster_policies WHERE source_key=s AND scenario_id=i AND native_type=5 LOOP
  IF NOT EXISTS(SELECT 1 FROM environmental_native_scenarios n WHERE n.source_key=s AND n.scenario_id=i
      AND n.native_type=5 AND n.family='destroy_monster_action'
      AND p.native_mode=CASE n.native_subtype WHEN 1 THEN 'SOLO' WHEN 2 THEN 'RACE'
       WHEN 3 THEN 'COMPETITIVE' WHEN 4 THEN 'COLLABORATIVE' END) THEN
   RAISE EXCEPTION 'Random interaction population requires original type5';
  END IF;
  SELECT max(native_value) FILTER(WHERE normalized_key='usergrouptemplateid') AS template,
   max(native_value) FILTER(WHERE normalized_key='usergroupquantitytospawn') AS quantity,
   max(native_value) FILTER(WHERE normalized_key='nbmobforreward') AS mobs,
   max(native_value) FILTER(WHERE normalized_key='nbgroupforreward') AS groups,
   max(native_value) FILTER(WHERE normalized_key='monsteractiontypeid') AS action,
   max(native_value) FILTER(WHERE normalized_key='challengeduration') AS duration,
   max(native_value) FILTER(WHERE normalized_key='challengelevelmin') AS minimum,
   max(native_value) FILTER(WHERE normalized_key='challengelevelmax') AS maximum
  INTO c FROM environmental_native_configuration WHERE source_key=s AND scenario_id=i;
  IF c.template IS DISTINCT FROM p.group_reference::text OR c.quantity IS DISTINCT FROM p.group_count::text
   OR c.mobs IS DISTINCT FROM p.nb_mob_for_reward::text OR c.groups IS DISTINCT FROM p.nb_group_for_reward::text
   OR c.action IS DISTINCT FROM '3' OR c.duration IS DISTINCT FROM (p.duration_ms/1000)::text
   OR p.duration_ms%1000<>0 OR c.minimum IS DISTINCT FROM p.challenge_level_min::text
   OR c.maximum IS DISTINCT FROM p.challenge_level_max::text THEN
   RAISE EXCEPTION 'Random interaction population changed original count/action/level fields';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM environmental_random_roster_species r WHERE r.source_key=s AND r.scenario_id=i
      AND r.policy_version=p.policy_version)
   OR EXISTS(SELECT 1 FROM environmental_random_roster_species r WHERE r.source_key=s AND r.scenario_id=i
      AND r.policy_version=p.policy_version AND NOT EXISTS(SELECT 1 FROM environmental_destroy_sources d
       WHERE d.source_key=s AND d.scenario_id=i AND d.template_reference=p.group_reference
        AND d.monster_reference=r.monster_reference AND d.action_descriptor->>'aGJ'='3'))
   OR EXISTS(SELECT 1 FROM environmental_destroy_sources d WHERE d.source_key=s AND d.scenario_id=i
      AND d.template_reference=p.group_reference AND NOT EXISTS(SELECT 1 FROM environmental_random_roster_species r
       WHERE r.source_key=s AND r.scenario_id=i AND r.policy_version=p.policy_version
        AND r.monster_reference=d.monster_reference)) THEN
   RAISE EXCEPTION 'Random interaction population must equal exact externally proven species pool';
  END IF;
 END LOOP;
 -- Every qualified profile binding must retain its exact source action and pool.
 IF EXISTS(SELECT 1 FROM environmental_profile_destroy_policy d
   JOIN environmental_runtime_profiles q USING(profile_key,version)
   WHERE d.source_key=s AND d.scenario_id=i AND (
    q.family<>'monster_destroy' OR q.native_scenario_id IS DISTINCT FROM i
    OR NOT EXISTS(SELECT 1 FROM environmental_random_roster_policies rp
       JOIN environmental_random_roster_species r USING(source_key,scenario_id,policy_version)
       JOIN environmental_random_roster_bindings b USING(source_key,scenario_id,policy_version)
       WHERE rp.source_key=s AND rp.scenario_id=i AND rp.native_type=5
        AND r.monster_reference=d.monster_reference AND b.map_id=q.map_id AND b.region_id=q.region_id))) THEN
  RAISE EXCEPTION 'Destroy profile requires its exact source-qualified random population';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_destroy_random_policy AFTER INSERT OR UPDATE OR DELETE
 ON environmental_random_roster_policies DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_random_roster();
CREATE CONSTRAINT TRIGGER environmental_destroy_random_species AFTER INSERT OR UPDATE OR DELETE
 ON environmental_random_roster_species DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_random_roster();
CREATE CONSTRAINT TRIGGER environmental_destroy_random_binding AFTER INSERT OR UPDATE OR DELETE
 ON environmental_random_roster_bindings DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_random_roster();
CREATE CONSTRAINT TRIGGER environmental_destroy_random_profile AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_destroy_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_destroy_random_roster();

-- Source301-owned exact target population; no activation or sizing version switch.
INSERT INTO environmental_random_native_species (monster_reference,native_min_level,native_max_level,catalog_revision,monsters_sha256) VALUES
(2253,1,1,E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1328 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1595 AND monster_reference=2253 AND action_id=265 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1328,E'wakemu.environmental-exact-species-genesis-v1',5,E'SOLO',1595,100,0,5,81,245,600000,E'bc46cfd6f8ead442c640e43abdf4c05a5f93108889ca43634af893eb5e9f4f34');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1328,E'wakemu.environmental-exact-species-genesis-v1',2253);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1328,E'wakemu.environmental-exact-species-genesis-v1',327,56601);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1327 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1595 AND monster_reference=2253 AND action_id=265 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1327,E'wakemu.environmental-exact-species-genesis-v1',5,E'RACE',1595,3,0,1,81,245,600000,E'42d5c421984ffcd16ddd624cefd9a588619eee249df6367ff20e52153c68b327');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1327,E'wakemu.environmental-exact-species-genesis-v1',2253);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1327,E'wakemu.environmental-exact-species-genesis-v1',327,56601);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1326 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1595 AND monster_reference=2253 AND action_id=265 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1326,E'wakemu.environmental-exact-species-genesis-v1',5,E'COMPETITIVE',1595,100,0,5,81,245,600000,E'35335d8198fe4d70b181c6f42c062869fcfbaef3bd1745ad4b3158fa49cdecad');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1326,E'wakemu.environmental-exact-species-genesis-v1',2253);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1326,E'wakemu.environmental-exact-species-genesis-v1',327,56601);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1325 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1595 AND monster_reference=2253 AND action_id=265 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1325,E'wakemu.environmental-exact-species-genesis-v1',5,E'COLLABORATIVE',1595,50,0,5,81,245,900000,E'0f078c62b95dbbdb23a95b2c6ec5960fa40a0253f0ceeac0864bb8874759e46e');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1325,E'wakemu.environmental-exact-species-genesis-v1',2253);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1325,E'wakemu.environmental-exact-species-genesis-v1',327,56601);
INSERT INTO environmental_random_native_species (monster_reference,native_min_level,native_max_level,catalog_revision,monsters_sha256) VALUES
(2236,1,1,E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',E'5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4');
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1225 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1581 AND monster_reference=2236 AND action_id=263 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1225,E'wakemu.environmental-exact-species-genesis-v1',5,E'SOLO',1581,100,0,5,66,245,600000,E'ab4e1bb492d2ccd5079a371da6d8dce4c4d3441dd8ee0055e4bae1605245a341');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1225,E'wakemu.environmental-exact-species-genesis-v1',2236);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1225,E'wakemu.environmental-exact-species-genesis-v1',1264,89301),
(E'installed-environmental-source-v1',-1225,E'wakemu.environmental-exact-species-genesis-v1',1264,89501);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1223 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1581 AND monster_reference=2236 AND action_id=263 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1223,E'wakemu.environmental-exact-species-genesis-v1',5,E'COMPETITIVE',1581,100,0,5,66,245,600000,E'48570fc9b4a3387ee73b6c81345ccd23ab32f73c58ee8691bef3a33da2161bd2');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1223,E'wakemu.environmental-exact-species-genesis-v1',2236);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1223,E'wakemu.environmental-exact-species-genesis-v1',1264,89301),
(E'installed-environmental-source-v1',-1223,E'wakemu.environmental-exact-species-genesis-v1',1264,89501);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1222 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1581 AND monster_reference=2236 AND action_id=263 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1222,E'wakemu.environmental-exact-species-genesis-v1',5,E'COLLABORATIVE',1581,50,0,5,66,245,900000,E'd4248fa304a7275d5a4368500c0cf83bf29733bfa6f443c3c2beea980b1b12b3');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1222,E'wakemu.environmental-exact-species-genesis-v1',2236);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1222,E'wakemu.environmental-exact-species-genesis-v1',1264,89301),
(E'installed-environmental-source-v1',-1222,E'wakemu.environmental-exact-species-genesis-v1',1264,89501);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM environmental_destroy_sources WHERE source_key=E'installed-environmental-source-v1' AND scenario_id=-1221 AND policy_version=E'wakemu.explicit-public-target-native-destroy-v1' AND template_reference=1581 AND monster_reference=2236 AND action_id=263 AND catalog_revision=E'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450') THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;
INSERT INTO environmental_random_roster_policies (source_key,scenario_id,policy_version,native_type,native_mode,group_reference,group_count,nb_group_for_reward,nb_mob_for_reward,challenge_level_min,challenge_level_max,duration_ms,source_sha256) VALUES
(E'installed-environmental-source-v1',-1221,E'wakemu.environmental-exact-species-genesis-v1',5,E'RACE',1581,3,0,1,66,245,600000,E'e8c3e294037390846c9a43fa6c284198caa3b0b2bcc99fbe68133b57d8ec7898');
INSERT INTO environmental_random_roster_species (source_key,scenario_id,policy_version,monster_reference) VALUES
(E'installed-environmental-source-v1',-1221,E'wakemu.environmental-exact-species-genesis-v1',2236);
INSERT INTO environmental_random_roster_bindings (source_key,scenario_id,policy_version,map_id,region_id) VALUES
(E'installed-environmental-source-v1',-1221,E'wakemu.environmental-exact-species-genesis-v1',1264,89301),
(E'installed-environmental-source-v1',-1221,E'wakemu.environmental-exact-species-genesis-v1',1264,89501);
