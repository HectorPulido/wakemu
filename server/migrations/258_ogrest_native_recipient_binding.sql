-- Preserve original Qe.a(nonnull PV,aZX=false) recipients for reviewed Ivory leaves.
-- This is scoped server reconstruction, not a global change to native selectors.
CREATE TABLE encounter_recipient_binding_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference>0),
 carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
 effect_references INTEGER[] NOT NULL CHECK(cardinality(effect_references)>0),
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_recipient_binding_effects (
 policy TEXT NOT NULL REFERENCES encounter_recipient_binding_versions(policy),
 effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
 effect_family INTEGER NOT NULL CHECK(effect_family IN (82,83,84,85,304)),
 selector_mask BIGINT NOT NULL CHECK(selector_mask>=0),
 parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
 criterion TEXT NOT NULL,
 area_class TEXT NOT NULL CHECK(area_class IN ('anA','anD')),
 native_parameters DOUBLE PRECISION[] NOT NULL,
 listener_reference INTEGER NOT NULL CHECK(listener_reference>0),
 event_id INTEGER NOT NULL CHECK(event_id IN (5,6,7,8)),
 CHECK(cardinality(native_parameters)=2*parameter_count),
 PRIMARY KEY(policy,effect_reference)
);
CREATE TABLE encounter_recipient_binding_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_recipient_binding_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_recipient_binding_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_recipient_binding_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_recipient_binding_versions_no_truncate
 BEFORE TRUNCATE ON encounter_recipient_binding_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_recipient_binding_effects_immutable
 BEFORE UPDATE OR DELETE ON encounter_recipient_binding_effects
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_recipient_binding_effects_no_truncate
 BEFORE TRUNCATE ON encounter_recipient_binding_effects
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION validate_encounter_recipient_binding_member() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM encounter_recipient_binding_versions v
               WHERE v.policy=NEW.policy AND NEW.effect_reference=ANY(v.effect_references)) THEN
  RAISE EXCEPTION 'Effect is outside the immutable recipient binding inventory';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_recipient_binding_effects_inventory
 BEFORE INSERT ON encounter_recipient_binding_effects
 FOR EACH ROW EXECUTE FUNCTION validate_encounter_recipient_binding_member();
INSERT INTO encounter_recipient_binding_versions VALUES
('wakemu-ogrest-ivory-native-recipient-v1','wakemu-native-explicit-pv-event-child-binding',
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 1156,ARRAY[4378],4378,4984,ARRAY[238154,238155,240706,240707,240709,240710,240712,240713]);
INSERT INTO encounter_recipient_binding_effects VALUES
('wakemu-ogrest-ivory-native-recipient-v1',238154,304,2,3,'','anD',ARRAY[5072.0,0.0,1.0,0.0,-1.0,0.0]::double precision[],237875,5),
('wakemu-ogrest-ivory-native-recipient-v1',238155,82,1266637395197952,1,'HasState(5072, "target")','anA',ARRAY[0.0,5.0]::double precision[],237875,5),
('wakemu-ogrest-ivory-native-recipient-v1',240706,304,2,3,'','anD',ARRAY[5072.0,0.0,1.0,0.0,-1.0,0.0]::double precision[],237996,6),
('wakemu-ogrest-ivory-native-recipient-v1',240707,83,1266637395197952,1,'HasState(5072, "target")','anA',ARRAY[0.0,5.0]::double precision[],237996,6),
('wakemu-ogrest-ivory-native-recipient-v1',240709,304,2,3,'','anD',ARRAY[5072.0,0.0,1.0,0.0,-1.0,0.0]::double precision[],237999,7),
('wakemu-ogrest-ivory-native-recipient-v1',240710,85,1266637395197952,1,'HasState(5072, "target")','anA',ARRAY[0.0,5.0]::double precision[],237999,7),
('wakemu-ogrest-ivory-native-recipient-v1',240712,304,2,3,'','anD',ARRAY[5072.0,0.0,1.0,0.0,-1.0,0.0]::double precision[],238002,8),
('wakemu-ogrest-ivory-native-recipient-v1',240713,84,1266637395197952,1,'HasState(5072, "target")','anA',ARRAY[0.0,5.0]::double precision[],238002,8);
INSERT INTO encounter_recipient_binding_active VALUES
(1156,ARRAY[4378],'wakemu-ogrest-ivory-native-recipient-v1');
