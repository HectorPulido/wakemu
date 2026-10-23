-- Schema only. No profile, reward, scenario or publication is activated here.
-- Explicit Wakemu interpretation of native winnerScore for unranked resource
-- completion; original server parameter arithmetic was not recovered.
CREATE TABLE environmental_profile_simple_result_policy (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL,native_scenario_id integer NOT NULL,reward_id integer NOT NULL,
 policy_contract text NOT NULL CHECK(policy_contract='wakemu.original-resource-single-primary-base-result.v1'),
 primary_reward_index integer NOT NULL CHECK(primary_reward_index=0),
 parameter_mode text NOT NULL CHECK(parameter_mode IN ('personal_progress','global_progress')),
 source_authority text NOT NULL CHECK(length(btrim(source_authority))>0),
 mapping_authority text NOT NULL CHECK(length(btrim(mapping_authority))>0),
 parameter_authority text NOT NULL CHECK(length(btrim(parameter_authority))>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios,
 FOREIGN KEY(source_key,native_scenario_id,reward_id)
 REFERENCES environmental_native_rewards_raw(source_key,scenario_id,reward_id)
);
CREATE FUNCTION validate_environmental_simple_result_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;n bigint;primary_row record;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,f.native_scenario_id AS profile_scenario,f.family,f.mode INTO p
 FROM environmental_profile_simple_result_policy q
 JOIN environmental_runtime_profiles f USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR p.family<>'resource_collect'
   OR p.mode NOT IN ('solo','collaborative')
   OR p.parameter_mode<>(CASE WHEN p.mode='solo' THEN 'personal_progress' ELSE 'global_progress' END) THEN
  RAISE EXCEPTION 'Simple resource result differs from its declared profile';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM environmental_native_scenarios s WHERE s.source_key=p.source_key
   AND s.scenario_id=p.native_scenario_id AND s.family='resource_interaction'
   AND s.client_visible AND s.native_subtype=CASE WHEN p.mode='solo' THEN 1 ELSE 4 END) THEN
  RAISE EXCEPTION 'Simple result requires the original solo/collaborative resource source';
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
CREATE CONSTRAINT TRIGGER environmental_simple_result_policy_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_simple_result_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_simple_result_policy();
CREATE CONSTRAINT TRIGGER environmental_simple_result_profile_inventory AFTER INSERT OR UPDATE
 ON environmental_runtime_profiles DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_simple_result_policy();
CREATE TRIGGER environmental_simple_result_policy_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_simple_result_policy FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_simple_result_policy_no_truncate BEFORE TRUNCATE
 ON environmental_profile_simple_result_policy FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
