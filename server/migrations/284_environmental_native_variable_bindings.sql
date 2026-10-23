-- Explicit Wakemu projections of native variables, not recovered server formulas.
-- No profiles are created, enabled, or modified by this migration.
CREATE TABLE environmental_profile_native_variable_policy (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL,native_scenario_id integer NOT NULL,
 policy_contract text NOT NULL CHECK(policy_contract='wakemu.durable-native-variable-projection.v1'),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version),
 UNIQUE(profile_key,version,source_key,native_scenario_id),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_profile_native_variable_bindings (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL,native_scenario_id integer NOT NULL,
 variable_index smallint NOT NULL CHECK(variable_index BETWEEN 0 AND 127),
 native_name text NOT NULL CHECK(length(native_name)>0),
 binding_kind text NOT NULL CHECK(binding_kind IN
  ('configconstant','declared_threshold','personal_progress','global_progress','spawned','remaining')),
 objective_key text,configuration_key text,constant_value bigint,
 source_authority text CHECK(length(source_authority)>0),
 entity_kind text CHECK(entity_kind IN ('resource','group','monster')),
 PRIMARY KEY(profile_key,version,variable_index),UNIQUE(profile_key,version,native_name),
 FOREIGN KEY(profile_key,version,source_key,native_scenario_id)
 REFERENCES environmental_profile_native_variable_policy(profile_key,version,source_key,native_scenario_id),
 FOREIGN KEY(source_key,native_scenario_id,variable_index)
 REFERENCES environmental_native_variables(source_key,scenario_id,ordinal),
 FOREIGN KEY(source_key,native_scenario_id,configuration_key)
 REFERENCES environmental_native_configuration(source_key,scenario_id,native_key),
 FOREIGN KEY(profile_key,version,objective_key)
 REFERENCES environmental_profile_objectives(profile_key,version,objective_key),
 CHECK((binding_kind IN ('configconstant','declared_threshold') AND configuration_key IS NOT NULL AND constant_value IS NOT NULL
        AND objective_key IS NULL AND entity_kind IS NULL
        AND (binding_kind<>'declared_threshold' OR source_authority IS NOT NULL))
    OR (binding_kind IN ('personal_progress','global_progress') AND objective_key IS NOT NULL
        AND configuration_key IS NULL AND constant_value IS NULL AND entity_kind IS NULL)
    OR (binding_kind IN ('spawned','remaining') AND entity_kind IS NOT NULL
        AND objective_key IS NULL AND configuration_key IS NULL AND constant_value IS NULL))
);
CREATE FUNCTION validate_environmental_native_variable_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;n bigint;b bigint;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,r.native_scenario_id AS profile_scenario,r.family INTO p
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
CREATE CONSTRAINT TRIGGER environmental_native_variable_policy_inventory
 AFTER INSERT OR UPDATE OR DELETE ON environmental_profile_native_variable_policy
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_environmental_native_variable_policy();
CREATE CONSTRAINT TRIGGER environmental_native_variable_binding_inventory
 AFTER INSERT OR UPDATE OR DELETE ON environmental_profile_native_variable_bindings
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_environmental_native_variable_policy();
CREATE TRIGGER environmental_native_variable_policy_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_native_variable_policy FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_native_variable_binding_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_native_variable_bindings FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE FUNCTION reject_environmental_variable_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Environmental variable policy truncation is forbidden'; END $$;
CREATE TRIGGER environmental_native_variable_policy_no_truncate BEFORE TRUNCATE
 ON environmental_profile_native_variable_policy FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
CREATE TRIGGER environmental_native_variable_binding_no_truncate BEFORE TRUNCATE
 ON environmental_profile_native_variable_bindings FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
