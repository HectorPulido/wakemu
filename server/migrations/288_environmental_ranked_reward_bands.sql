-- Explicit Wakemu grants of original display base values, without boosters.
-- Schema only: no profile, event or reward activation.
CREATE TABLE environmental_profile_ranked_reward_policy (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL,native_scenario_id integer NOT NULL,
 policy_contract text NOT NULL CHECK(policy_contract='wakemu.original-resource-rank-bands-base-rewards.v1'),
 eligibility_contract text NOT NULL CHECK(eligibility_contract IN ('ranked_winners','all_eligible')),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 grant_authority text NOT NULL CHECK(length(grant_authority)>0),
 result_parameter_mode text NOT NULL CHECK(result_parameter_mode IN ('winner_score','declared_constant')),
 result_parameter integer,
 CHECK((result_parameter_mode='winner_score' AND result_parameter IS NULL) OR
       (result_parameter_mode='declared_constant' AND result_parameter IS NOT NULL)),
 parameter_authority text NOT NULL CHECK(length(parameter_authority)>0),
 PRIMARY KEY(profile_key,version),UNIQUE(profile_key,version,source_key,native_scenario_id),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_profile_ranked_reward_bands (
 profile_key text NOT NULL,version integer NOT NULL,source_key text NOT NULL,native_scenario_id integer NOT NULL,
 primary_reward_index integer NOT NULL CHECK(primary_reward_index>=0),
 reward_id integer NOT NULL,rank_min integer,rank_max integer,
 PRIMARY KEY(profile_key,version,primary_reward_index),UNIQUE(profile_key,version,reward_id),
 FOREIGN KEY(profile_key,version,source_key,native_scenario_id)
 REFERENCES environmental_profile_ranked_reward_policy(profile_key,version,source_key,native_scenario_id),
 FOREIGN KEY(source_key,native_scenario_id,reward_id)
 REFERENCES environmental_native_rewards_raw(source_key,scenario_id,reward_id),
 CHECK((rank_min IS NULL AND rank_max IS NULL) OR (rank_min IS NOT NULL AND rank_max IS NOT NULL AND rank_min>0 AND rank_max>=rank_min AND rank_max<=32767))
);
CREATE FUNCTION validate_environmental_ranked_reward_bands() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;p record;expected bigint;actual bigint;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 SELECT q.*,r.native_scenario_id AS profile_scenario,r.family,r.mode INTO p
 FROM environmental_profile_ranked_reward_policy q JOIN environmental_runtime_profiles r USING(profile_key,version)
 WHERE q.profile_key=k AND q.version=v;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF NOT EXISTS(SELECT 1 FROM environmental_native_scenarios n WHERE n.source_key=p.source_key
   AND n.scenario_id=p.native_scenario_id AND n.family='resource_interaction') THEN
  RAISE EXCEPTION 'Ranked resource policy requires original resource source';
 END IF;
 IF p.profile_scenario IS DISTINCT FROM p.native_scenario_id OR p.family<>'resource_collect'
   OR p.mode NOT IN ('competitive','race') THEN
  RAISE EXCEPTION 'Ranked resource rewards differ from their profile';
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
     r.native_text <> format('ListContains(GetUser(), GetPlayerInRankRange(%s, %s, "nbResourcePlayer", False))',b.rank_min,b.rank_max))))) THEN
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
CREATE CONSTRAINT TRIGGER environmental_ranked_reward_policy_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_ranked_reward_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_ranked_reward_bands();
CREATE CONSTRAINT TRIGGER environmental_ranked_reward_bands_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_ranked_reward_bands DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_ranked_reward_bands();
CREATE TRIGGER environmental_ranked_reward_policy_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_ranked_reward_policy FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_ranked_reward_bands_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_ranked_reward_bands FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_ranked_reward_policy_no_truncate BEFORE TRUNCATE
 ON environmental_profile_ranked_reward_policy FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
CREATE TRIGGER environmental_ranked_reward_bands_no_truncate BEFORE TRUNCATE
 ON environmental_profile_ranked_reward_bands FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();
