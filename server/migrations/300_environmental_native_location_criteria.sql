-- Exact original location admission criteria. No profile activation, dynamic
-- ecology snapshot, event completion rule or cancellation policy is stored here.
CREATE TABLE environmental_profile_location_policy (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL,native_scenario_id integer NOT NULL,
 protector_id integer NOT NULL CHECK(protector_id>0),
 native_criteria text NOT NULL,
 criterion_kind text NOT NULL,
 source_authority text NOT NULL CHECK(length(btrim(source_authority))>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles,
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios,
 CHECK((native_criteria='' AND criterion_kind='always') OR
       (native_criteria='GetSatisfactionLevel() >= 3' AND criterion_kind='all_wishes') OR
       (native_criteria='IsNeoServer()' AND criterion_kind='neo_server'))
);
CREATE FUNCTION validate_environmental_profile_location_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF EXISTS(SELECT 1 FROM environmental_profile_location_policy q
  JOIN environmental_runtime_profiles r USING(profile_key,version)
  WHERE q.profile_key=k AND q.version=v AND (
   r.native_scenario_id IS DISTINCT FROM q.native_scenario_id OR NOT EXISTS(
    SELECT 1 FROM environmental_native_scenario_locations n
    WHERE n.source_key=q.source_key AND n.scenario_id=q.native_scenario_id
     AND n.protector_id=q.protector_id AND n.map_id=r.map_id AND n.region_id=r.region_id
     AND n.native_cells_present AND n.native_criteria=q.native_criteria))) THEN
  RAISE EXCEPTION 'Environmental admission criterion differs from exact original location';
 END IF;
 IF EXISTS(SELECT 1 FROM environmental_profile_location_policy q
  JOIN environmental_profile_publication p USING(profile_key,version)
  WHERE q.profile_key=k AND q.version=v AND
   (p.challenge_id IS DISTINCT FROM q.native_scenario_id OR p.protector_id IS DISTINCT FROM q.protector_id)) THEN
  RAISE EXCEPTION 'Environmental location policy differs from native publication';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_location_policy_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_location_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_profile_location_policy();
CREATE CONSTRAINT TRIGGER environmental_location_profile_inventory AFTER INSERT OR UPDATE
 ON environmental_runtime_profiles DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_profile_location_policy();
CREATE CONSTRAINT TRIGGER environmental_location_publication_inventory AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_publication DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_profile_location_policy();
CREATE TRIGGER environmental_location_policy_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_location_policy FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_location_policy_no_truncate BEFORE TRUNCATE
 ON environmental_profile_location_policy FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_variable_truncate();

-- Source admission authority is also mandatory for sealed profiles used
-- without a regional scheduler. Legacy blank-source profiles remain valid.
CREATE FUNCTION validate_environmental_group_profile_location() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF EXISTS(SELECT 1 FROM environmental_profile_group_ui u
  JOIN environmental_runtime_profiles r USING(profile_key,version)
  LEFT JOIN environmental_profile_location_policy q USING(profile_key,version)
  WHERE u.profile_key=k AND u.version=v AND r.sealed AND NOT EXISTS(
   SELECT 1 FROM environmental_native_scenario_locations n
   WHERE n.source_key=u.source_key AND n.scenario_id=u.native_scenario_id
    AND n.map_id=r.map_id AND n.region_id=r.region_id AND n.native_cells_present AND (
     (q.profile_key IS NULL AND n.native_criteria='') OR
     (q.source_key=n.source_key AND q.native_scenario_id=n.scenario_id
      AND q.protector_id=n.protector_id AND q.native_criteria=n.native_criteria)))) THEN
  RAISE EXCEPTION 'Sealed environmental group profile lacks exact location admission authority';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_group_location_profile AFTER INSERT OR UPDATE
 ON environmental_runtime_profiles DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_group_profile_location();
CREATE CONSTRAINT TRIGGER environmental_group_location_ui AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_group_ui DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_group_profile_location();
CREATE CONSTRAINT TRIGGER environmental_group_location_binding AFTER INSERT OR UPDATE OR DELETE
 ON environmental_profile_location_policy DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_group_profile_location();

-- Existing blank-location group candidates remain valid. A candidate whose
-- only original locations require criteria must carry the exact qualified child.
-- Resource policies are outside this additional group source validation.
CREATE FUNCTION validate_environmental_schedule_group_locations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;
BEGIN
 k:=COALESCE(NEW.policy_key,OLD.policy_key);v:=COALESCE(NEW.version,OLD.version);
 IF EXISTS(SELECT 1 FROM environmental_regional_schedule_candidates c
  JOIN environmental_regional_schedule_policies s USING(policy_key,version)
  JOIN environmental_runtime_profiles r ON r.profile_key=c.profile_key AND r.version=c.profile_version
  JOIN environmental_profile_group_ui u ON u.profile_key=r.profile_key AND u.version=r.version
  LEFT JOIN environmental_profile_location_policy q ON q.profile_key=r.profile_key AND q.version=r.version
  WHERE c.policy_key=k AND c.version=v AND (
   (s.map_id,s.region_id) IS DISTINCT FROM (r.map_id,r.region_id) OR NOT EXISTS(
    SELECT 1 FROM environmental_native_scenario_locations n WHERE n.source_key=u.source_key
     AND n.scenario_id=u.native_scenario_id AND n.map_id=r.map_id AND n.region_id=r.region_id
     AND n.native_cells_present AND (
      (q.profile_key IS NULL AND n.native_criteria='') OR
      (q.source_key=n.source_key AND q.native_scenario_id=n.scenario_id
       AND q.protector_id=n.protector_id AND q.native_criteria=n.native_criteria))))) THEN
  RAISE EXCEPTION 'Environmental group schedule lacks exact original location admission authority';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_schedule_group_location_candidates AFTER INSERT OR UPDATE OR DELETE
 ON environmental_regional_schedule_candidates DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_schedule_group_locations();
CREATE CONSTRAINT TRIGGER environmental_schedule_group_location_policies AFTER INSERT OR UPDATE
 ON environmental_regional_schedule_policies DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_schedule_group_locations();
