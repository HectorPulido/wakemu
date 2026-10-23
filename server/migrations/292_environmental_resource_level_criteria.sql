-- Qualify the recovered resource GetLevel() >= N fragment only.
-- No original source rows, runtime profiles or immutable historical migrations change.
CREATE FUNCTION environmental_resource_criterion_minimum(criterion text)
RETURNS integer LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE matched text[];minimum_value numeric;
BEGIN
 IF criterion IS NULL THEN RAISE EXCEPTION 'Missing native resource criterion'; END IF;
 IF criterion='' THEN RETURN NULL; END IF;
 matched:=regexp_match(criterion,E'^[ \\t\\r\\n]*GetLevel\\(\\)[ \\t\\r\\n]*>=[ \\t\\r\\n]*([0-9]+)[ \\t\\r\\n]*$');
 IF matched IS NULL THEN RAISE EXCEPTION 'Unsupported native resource criterion fragment'; END IF;
 minimum_value:=matched[1]::numeric;
 IF minimum_value<0 OR minimum_value>32767 THEN
  RAISE EXCEPTION 'Native resource minimum effective level is outside its bound';
 END IF;
 RETURN minimum_value::integer;
END $$;
CREATE FUNCTION validate_environmental_resource_level_criterion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;original_criterion text;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF NOT EXISTS(SELECT 1 FROM environmental_profile_resource_population WHERE profile_key=k AND version=v) THEN
  RETURN NULL;
 END IF;
 SELECT a.native_criteria INTO original_criterion
 FROM environmental_profile_resource_population p
 JOIN environmental_runtime_profiles r USING(profile_key,version)
 JOIN environmental_scenario_resource_actions s ON s.source_key=p.source_key
  AND s.scenario_id=r.native_scenario_id AND s.status='matched_original_action'
 JOIN environmental_original_resource_actions a ON a.source_key=s.source_key
  AND a.resource_reference=s.resource_reference AND a.native_step=s.native_step AND a.action_ordinal=s.action_ordinal
 WHERE p.profile_key=k AND p.version=v;
 IF NOT FOUND THEN RAISE EXCEPTION 'Environmental resource population lacks its exact original action'; END IF;
 PERFORM environmental_resource_criterion_minimum(original_criterion);
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER environmental_resource_level_criterion_population
 AFTER INSERT OR UPDATE OR DELETE ON environmental_profile_resource_population
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_environmental_resource_level_criterion();
CREATE CONSTRAINT TRIGGER environmental_resource_level_criterion_profile
 AFTER INSERT OR UPDATE ON environmental_runtime_profiles
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_environmental_resource_level_criterion();
