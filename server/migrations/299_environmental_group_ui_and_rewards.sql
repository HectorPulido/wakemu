-- Explicit Wakemu group counters and original primary reward mappings.
-- Schema only: no profile, scenario, population or reward is activated.
CREATE TABLE environmental_profile_group_ui (
 profile_key text NOT NULL,version integer NOT NULL,source_key text NOT NULL,native_scenario_id integer NOT NULL,
 authority text NOT NULL CHECK(length(btrim(authority))>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios
);
CREATE FUNCTION validate_environmental_group_ui() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF EXISTS(SELECT 1 FROM environmental_profile_group_ui q
  JOIN environmental_runtime_profiles p USING(profile_key,version)
  JOIN environmental_native_scenarios n ON n.source_key=q.source_key AND n.scenario_id=q.native_scenario_id
  WHERE q.profile_key=k AND q.version=v AND (
    p.native_scenario_id IS DISTINCT FROM q.native_scenario_id OR n.family<>'group_template'
    OR NOT n.client_visible OR n.native_type NOT IN (6,7,8) OR n.native_subtype<>CASE p.mode
      WHEN 'solo' THEN 1 WHEN 'race' THEN 2 WHEN 'competitive' THEN 3 WHEN 'collaborative' THEN 4 ELSE 0 END
    OR p.family<>CASE n.native_type WHEN 7 THEN 'group_defeat' ELSE 'monster_defeat' END)) THEN
  RAISE EXCEPTION 'Group UI differs from original scenario/profile';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_group_ui_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_group_ui DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_group_ui();
CREATE CONSTRAINT TRIGGER environmental_group_ui_profile_inventory AFTER INSERT OR UPDATE
 ON environmental_runtime_profiles DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_group_ui();
CREATE TRIGGER environmental_group_ui_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_group_ui FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_group_ui_no_truncate BEFORE TRUNCATE
 ON environmental_profile_group_ui FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='environmental_profile_ranked_reward_policy'::regclass
  AND contype='c' AND pg_get_constraintdef(oid) LIKE '%policy_contract%' LOOP
  EXECUTE format('ALTER TABLE environmental_profile_ranked_reward_policy DROP CONSTRAINT %I',c.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_profile_ranked_reward_policy ADD CONSTRAINT env_rank_reward_contract CHECK(policy_contract IN
 ('wakemu.original-resource-rank-bands-base-rewards.v1','wakemu.original-group-rank-bands-base-rewards.v1'));
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
DO $$ DECLARE c record; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='environmental_profile_simple_result_policy'::regclass
  AND contype='c' AND pg_get_constraintdef(oid) LIKE '%policy_contract%' LOOP
  EXECUTE format('ALTER TABLE environmental_profile_simple_result_policy DROP CONSTRAINT %I',c.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_profile_simple_result_policy ADD CONSTRAINT env_simple_result_contract CHECK(policy_contract IN
 ('wakemu.original-resource-single-primary-base-result.v1','wakemu.original-group-single-primary-base-result.v1'));
CREATE OR REPLACE FUNCTION validate_environmental_simple_result_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;n bigint;primary_row record;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,f.native_scenario_id AS profile_scenario,f.family,f.mode INTO p
 FROM environmental_profile_simple_result_policy q
 JOIN environmental_runtime_profiles f USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR p.family NOT IN ('resource_collect','monster_defeat','group_defeat')
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
DO $$ DECLARE r record; BEGIN
 FOR r IN SELECT conname FROM pg_constraint
   WHERE conrelid='environmental_profile_native_variable_bindings'::regclass
     AND contype='c' AND pg_get_constraintdef(oid) LIKE '%binding_kind%'
 LOOP
  EXECUTE format('ALTER TABLE environmental_profile_native_variable_bindings DROP CONSTRAINT %I',r.conname);
 END LOOP;
END $$;
ALTER TABLE environmental_profile_native_variable_bindings
 ADD CONSTRAINT env_native_variable_kind CHECK(binding_kind IN
 ('configconstant','declared_threshold','personal_progress','global_progress','spawned','remaining','leader_progress','entity_personal_progress','entity_global_progress')),
 ADD CONSTRAINT env_native_variable_shape CHECK(
   (binding_kind IN ('configconstant','declared_threshold') AND configuration_key IS NOT NULL AND constant_value IS NOT NULL
     AND objective_key IS NULL AND entity_kind IS NULL
     AND (binding_kind<>'declared_threshold' OR source_authority IS NOT NULL))
   OR (binding_kind IN ('personal_progress','global_progress','leader_progress') AND objective_key IS NOT NULL
     AND configuration_key IS NULL AND constant_value IS NULL AND entity_kind IS NULL
     AND (binding_kind<>'leader_progress' OR source_authority IS NOT NULL))
   OR (binding_kind IN ('entity_personal_progress','entity_global_progress') AND objective_key IS NOT NULL
     AND entity_kind IN ('monster','group') AND source_authority IS NOT NULL
     AND configuration_key IS NULL AND constant_value IS NULL)
   OR (binding_kind IN ('spawned','remaining') AND entity_kind IS NOT NULL
     AND objective_key IS NULL AND configuration_key IS NULL AND constant_value IS NULL));
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
 IF EXISTS(SELECT 1 FROM environmental_profile_group_ui q
  JOIN environmental_profile_native_variable_bindings x USING(profile_key,version)
  WHERE q.profile_key=k AND q.version=v AND x.native_name IN ('nbMobPlayer','nbGroupPlayer','nbMobGlobal','nbGroupGlobal')
    AND x.binding_kind<>CASE WHEN x.native_name LIKE '%Player' THEN 'entity_personal_progress' ELSE 'entity_global_progress' END) THEN
  RAISE EXCEPTION 'Group UI requires independent durable entity counters';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_native_variable_bindings x
  WHERE x.profile_key=k AND x.version=v AND NOT (
   (x.binding_kind IN ('entity_personal_progress','entity_global_progress') AND p.family IN ('monster_defeat','group_defeat')
     AND EXISTS(SELECT 1 FROM environmental_profile_group_ui q WHERE q.profile_key=k AND q.version=v
                AND q.source_key=p.source_key AND q.native_scenario_id=p.native_scenario_id)
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
-- Secondary physical counters only; objective and entitlement state is separate.
CREATE TABLE environmental_group_progress_facts (
 instance_id bigint NOT NULL REFERENCES environmental_event_instances(instance_id),
 character_id bigint NOT NULL, account_id bigint NOT NULL,
 entity_kind text NOT NULL CHECK(entity_kind IN ('monster','group')),
 entity_id bigint NOT NULL CHECK(entity_id<>0), reference integer NOT NULL CHECK(reference>0),
 source_key text NOT NULL CHECK(length(source_key) BETWEEN 1 AND 200),
 fact_kind text NOT NULL CHECK(fact_kind IN ('monster_defeated','group_defeated')),
 receipt_key text NOT NULL CHECK(length(receipt_key) BETWEEN 1 AND 160),
 fight_id bigint NOT NULL CHECK(fight_id>0), occurred_at_ms bigint NOT NULL CHECK(occurred_at_ms>=0),
 fact_digest text NOT NULL CHECK(fact_digest ~ '^[0-9a-f]{64}$'),
 physical_digest text NOT NULL CHECK(physical_digest ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(instance_id,character_id,entity_kind,entity_id),
 FOREIGN KEY(instance_id,character_id) REFERENCES environmental_participants(instance_id,character_id),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 FOREIGN KEY(instance_id,entity_kind,entity_id)
  REFERENCES environmental_event_memberships(instance_id,entity_kind,entity_id),
 CHECK((entity_kind='monster' AND fact_kind='monster_defeated' AND entity_id<0)
    OR (entity_kind='group' AND fact_kind='group_defeated' AND entity_id>0))
);
CREATE INDEX environmental_group_progress_physical
 ON environmental_group_progress_facts(instance_id,entity_kind,entity_id);
CREATE FUNCTION environmental_group_progress_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM environmental_event_instances e
  JOIN environmental_profile_group_ui u USING(profile_key,version)
  JOIN environmental_participants p ON p.instance_id=e.instance_id
  JOIN environmental_event_memberships m ON m.instance_id=e.instance_id
  WHERE e.instance_id=NEW.instance_id AND p.character_id=NEW.character_id
   AND p.account_id=NEW.account_id AND p.eligible AND p.completed_at_ms IS NULL
   AND e.state='active'
   AND p.joined_at_ms<=NEW.occurred_at_ms
   AND e.started_at_ms<=NEW.occurred_at_ms AND NEW.occurred_at_ms<e.deadline_ms
   AND m.entity_kind=NEW.entity_kind AND m.entity_id=NEW.entity_id
   AND m.reference=NEW.reference AND m.source_key=NEW.source_key AND m.spawn_owned
 ) THEN RAISE EXCEPTION 'Unqualified environmental secondary entity receipt'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_group_progress_qualified_insert BEFORE INSERT
 ON environmental_group_progress_facts FOR EACH ROW EXECUTE FUNCTION environmental_group_progress_insert_guard();
CREATE FUNCTION environmental_group_progress_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Environmental secondary entity receipts are immutable'; END $$;
CREATE TRIGGER environmental_group_progress_no_mutation BEFORE UPDATE OR DELETE
 ON environmental_group_progress_facts FOR EACH ROW EXECUTE FUNCTION environmental_group_progress_immutable();
CREATE TRIGGER environmental_group_progress_no_truncate BEFORE TRUNCATE
 ON environmental_group_progress_facts FOR EACH STATEMENT EXECUTE FUNCTION environmental_group_progress_immutable();
