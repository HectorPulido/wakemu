-- Explicit Wakemu leader metric. No original server Max setter was recovered.
-- Schema only; no imported profile, activation or mutable source rows.
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
 ('configconstant','declared_threshold','personal_progress','global_progress','spawned','remaining','leader_progress')),
 ADD CONSTRAINT env_native_variable_shape CHECK(
   (binding_kind IN ('configconstant','declared_threshold') AND configuration_key IS NOT NULL AND constant_value IS NOT NULL
     AND objective_key IS NULL AND entity_kind IS NULL
     AND (binding_kind<>'declared_threshold' OR source_authority IS NOT NULL))
   OR (binding_kind IN ('personal_progress','global_progress','leader_progress') AND objective_key IS NOT NULL
     AND configuration_key IS NULL AND constant_value IS NULL AND entity_kind IS NULL
     AND (binding_kind<>'leader_progress' OR source_authority IS NOT NULL))
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
 IF EXISTS(SELECT 1 FROM environmental_profile_native_variable_bindings x
  WHERE x.profile_key=k AND x.version=v AND NOT (
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
