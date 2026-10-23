-- Reconstructed original event-child criterion population for Tal's pyramids.
-- Native damage sources, chosen-PV replay, criteria and null-Qe rules remain intact.
CREATE TABLE encounter_event_population_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 effect_references INTEGER[] NOT NULL CHECK(cardinality(effect_references)>0),
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_event_population_effects (
 policy TEXT NOT NULL REFERENCES encounter_event_population_versions(policy),
 effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
 effect_family INTEGER NOT NULL CHECK(effect_family=330),
 selector_mask BIGINT NOT NULL CHECK(selector_mask=0),
 parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
 native_parameters JSONB NOT NULL CHECK(jsonb_typeof(native_parameters)='array'),
 criterion TEXT NOT NULL CHECK(length(criterion)>0),
 area_class TEXT NOT NULL CHECK(area_class='anD'),
 owner_effect_reference INTEGER NOT NULL CHECK(owner_effect_reference>0),
 listener_reference INTEGER NOT NULL CHECK(listener_reference>0),
 event_id INTEGER NOT NULL CHECK(event_id IN (5,6,7,8)),
 channel INTEGER NOT NULL CHECK(channel=2),
 CHECK(jsonb_array_length(native_parameters)=parameter_count*2),
 PRIMARY KEY(policy,effect_reference)
);
CREATE TABLE encounter_event_population_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_event_population_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_event_population_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_event_population_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_event_population_versions_no_truncate
 BEFORE TRUNCATE ON encounter_event_population_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_event_population_effects_immutable
 BEFORE UPDATE OR DELETE ON encounter_event_population_effects
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_event_population_effects_no_truncate
 BEFORE TRUNCATE ON encounter_event_population_effects
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION validate_encounter_event_population_member() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM encounter_event_population_versions v
               WHERE v.policy=NEW.policy AND NEW.effect_reference=ANY(v.effect_references)) THEN
  RAISE EXCEPTION 'Effect is outside the immutable event population inventory';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_event_population_effects_inventory
 BEFORE INSERT ON encounter_event_population_effects
 FOR EACH ROW EXECUTE FUNCTION validate_encounter_event_population_member();
INSERT INTO encounter_event_population_versions VALUES
('wakemu-tal-pyramid-element-event-population-v1','wakemu-reconstructed-original-event-child-pyramid-population',
 1400,ARRAY[5500],5500,8231,
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 ARRAY[379873,379882,379884,379886]);
INSERT INTO encounter_event_population_effects VALUES
('wakemu-tal-pyramid-element-event-population-v1',379873,330,0,0,'[]'::jsonb,E'GetStateCountInRange(-1, "caster", 8232, 2) >= 1\r\nand HasState(8232, 2, "target") and HasState(8236, "target")','anD',378826,378827,5,2),
('wakemu-tal-pyramid-element-event-population-v1',379882,330,0,0,'[]'::jsonb,E'GetStateCountInRange(-1, "caster", 8233, 2) >= 1\r\nand HasState(8233, 2, "target") and HasState(8236, "target")','anD',378826,378829,6,2),
('wakemu-tal-pyramid-element-event-population-v1',379884,330,0,0,'[]'::jsonb,E'GetStateCountInRange(-1, "caster", 8234, 2) >= 1\r\nand HasState(8234, 2, "target") and HasState(8236, "target")','anD',378826,378831,8,2),
('wakemu-tal-pyramid-element-event-population-v1',379886,330,0,0,'[]'::jsonb,E'GetStateCountInRange(-1, "caster", 8235, 2) >= 1\r\nand HasState(8235, 2, "target") and HasState(8236, "target")','anD',378826,378833,7,2);
INSERT INTO encounter_event_population_active VALUES
(1400,ARRAY[5500],'wakemu-tal-pyramid-element-event-population-v1');
