-- STAGING ONLY: normalized original DROP programs; no state/cost overrides.
CREATE TABLE encounter_area_callback_program_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
 area_references INTEGER[] NOT NULL CHECK(cardinality(area_references)>0),
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_area_callback_programs (
 policy TEXT NOT NULL REFERENCES encounter_area_callback_program_versions(policy),
 area_reference INTEGER NOT NULL CHECK(area_reference>0),
 held_state_reference INTEGER NOT NULL CHECK(held_state_reference>0),
 drop_spell_reference INTEGER NOT NULL CHECK(drop_spell_reference>0),
 drop_root_reference INTEGER NOT NULL CHECK(drop_root_reference>0),
 drop_getter_reference INTEGER NOT NULL CHECK(drop_getter_reference>0),
 state_reference INTEGER NOT NULL CHECK(state_reference>0),
 getter_criterion TEXT NOT NULL,
 getter_parameter_count INTEGER NOT NULL CHECK(getter_parameter_count>=0),
 PRIMARY KEY(policy,area_reference),
 UNIQUE(policy,drop_getter_reference)
);
CREATE TABLE encounter_area_callback_program_steps (
 policy TEXT NOT NULL,
 area_reference INTEGER NOT NULL,
 ordinal SMALLINT NOT NULL CHECK(ordinal BETWEEN 0 AND 3),
 role TEXT NOT NULL CHECK(role IN ('constructor','event','state','lock_removal')),
 effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
 effect_family INTEGER NOT NULL CHECK(effect_family>0),
 area_class TEXT NOT NULL,
 native_definition_class TEXT NOT NULL,
 selector_mask BIGINT NOT NULL,
 minimum_level INTEGER NOT NULL,
 maximum_level INTEGER NOT NULL CHECK(maximum_level>=minimum_level),
 criterion TEXT NOT NULL,
 native_execution_mode INTEGER NOT NULL,
 native_effect_flags INTEGER[] NOT NULL,
 emitted_events INTEGER[] NOT NULL,
 parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
 PRIMARY KEY(policy,area_reference,ordinal),
 UNIQUE(policy,area_reference,role), UNIQUE(policy,effect_reference),
 FOREIGN KEY(policy,area_reference) REFERENCES encounter_area_callback_programs(policy,area_reference)
);
CREATE TABLE encounter_area_callback_program_parameters (
 policy TEXT NOT NULL,
 area_reference INTEGER NOT NULL,
 effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
 ordinal SMALLINT NOT NULL CHECK(ordinal>=0),
 base DOUBLE PRECISION NOT NULL,
 per_level DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(policy,effect_reference,ordinal),
 FOREIGN KEY(policy,area_reference) REFERENCES encounter_area_callback_programs(policy,area_reference)
);
CREATE TABLE encounter_area_callback_program_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_area_callback_program_versions(policy,map_id,monster_references)
);
CREATE FUNCTION validate_encounter_area_callback_program_member() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM encounter_area_callback_program_versions v
 WHERE v.policy=NEW.policy AND NEW.area_reference=ANY(v.area_references)) THEN
  RAISE EXCEPTION 'Area is outside the immutable callback program inventory';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_area_callback_program_inventory BEFORE INSERT
 ON encounter_area_callback_programs FOR EACH ROW
 EXECUTE FUNCTION validate_encounter_area_callback_program_member();
CREATE FUNCTION validate_encounter_area_callback_parameter() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE expected_count INTEGER;
BEGIN
 SELECT getter_parameter_count INTO expected_count FROM encounter_area_callback_programs
 WHERE policy=NEW.policy AND area_reference=NEW.area_reference AND drop_getter_reference=NEW.effect_reference;
 IF expected_count IS NULL THEN
  SELECT parameter_count INTO expected_count FROM encounter_area_callback_program_steps
  WHERE policy=NEW.policy AND area_reference=NEW.area_reference AND effect_reference=NEW.effect_reference;
 END IF;
 IF expected_count IS NULL OR NEW.ordinal>=expected_count THEN
  RAISE EXCEPTION 'Parameter is outside the immutable native callback effect';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_area_callback_parameter_inventory BEFORE INSERT
 ON encounter_area_callback_program_parameters FOR EACH ROW
 EXECUTE FUNCTION validate_encounter_area_callback_parameter();
CREATE TRIGGER encounter_area_callback_program_versions_immutable BEFORE UPDATE OR DELETE ON encounter_area_callback_program_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_program_versions_no_truncate BEFORE TRUNCATE ON encounter_area_callback_program_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_programs_immutable BEFORE UPDATE OR DELETE ON encounter_area_callback_programs
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_programs_no_truncate BEFORE TRUNCATE ON encounter_area_callback_programs
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_program_steps_immutable BEFORE UPDATE OR DELETE ON encounter_area_callback_program_steps
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_program_steps_no_truncate BEFORE TRUNCATE ON encounter_area_callback_program_steps
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_program_parameters_immutable BEFORE UPDATE OR DELETE ON encounter_area_callback_program_parameters
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_callback_program_parameters_no_truncate BEFORE TRUNCATE ON encounter_area_callback_program_parameters
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_area_callback_program_versions VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 'wakemu-reconstructed-native-area-container-state-level-operand', 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450', 1332, ARRAY[5306], 5306, 7000, ARRAY[1650,1652,1653,1654,1655,1656,1657,1658,1659,1660,1661,1662,1663,1664,1665,1666]);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 6998, 7271, 318819, 318821, 7001, 'HasEffectWithSpecificId("caster", 318811)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 0, 'constructor', 318822, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 1, 'event', 318823, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 2, 'state', 318827, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1650)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 3, 'lock_removal', 318829, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 6, 6998.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318821, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318822, 0, 1650.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318822, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318822, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318827, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318827, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318827, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1650, 318829, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 7011, 7271, 318819, 324497, 7001, 'HasEffectWithSpecificId("caster", 318884)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 0, 'constructor', 324498, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 1, 'event', 324499, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 2, 'state', 324500, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1652)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 3, 'lock_removal', 324501, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 6, 7011.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324497, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324498, 0, 1652.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324498, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324498, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324500, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324500, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324500, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1652, 324501, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 7012, 7271, 318819, 324502, 7001, 'HasEffectWithSpecificId("caster", 318926)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 0, 'constructor', 324503, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 1, 'event', 324504, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 2, 'state', 324505, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1653)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 3, 'lock_removal', 324506, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 6, 7012.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324502, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324503, 0, 1653.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324503, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324503, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324505, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324505, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324505, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1653, 324506, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 7013, 7271, 318819, 324507, 7001, 'HasEffectWithSpecificId("caster", 318938)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 0, 'constructor', 324508, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 1, 'event', 324509, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 2, 'state', 324510, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1654)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 3, 'lock_removal', 324511, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 6, 7013.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324507, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324508, 0, 1654.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324508, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324508, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324510, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324510, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324510, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1654, 324511, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 7014, 7271, 318819, 324512, 7001, 'HasEffectWithSpecificId("caster", 318949)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 0, 'constructor', 324513, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 1, 'event', 324514, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 2, 'state', 324515, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1655)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 3, 'lock_removal', 324516, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 6, 7014.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324512, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324513, 0, 1655.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324513, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324513, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324515, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324515, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324515, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1655, 324516, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 7015, 7271, 318819, 324517, 7001, 'HasEffectWithSpecificId("caster", 318960)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 0, 'constructor', 324518, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 1, 'event', 324519, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 2, 'state', 324520, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1656)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 3, 'lock_removal', 324521, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 6, 7015.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324517, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324518, 0, 1656.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324518, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324518, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324520, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324520, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324520, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1656, 324521, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 7016, 7271, 318819, 324522, 7001, 'HasEffectWithSpecificId("caster", 318971)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 0, 'constructor', 324523, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 1, 'event', 324524, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 2, 'state', 324525, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1657)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 3, 'lock_removal', 324526, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 6, 7016.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324522, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324523, 0, 1657.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324523, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324523, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324525, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324525, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324525, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1657, 324526, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 7017, 7271, 318819, 324527, 7001, 'HasEffectWithSpecificId("caster", 318982)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 0, 'constructor', 324528, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 1, 'event', 324529, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 2, 'state', 324530, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1658)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 3, 'lock_removal', 324531, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 6, 7017.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324527, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324528, 0, 1658.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324528, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324528, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324530, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324530, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324530, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1658, 324531, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 7018, 7271, 318819, 324532, 7001, 'HasEffectWithSpecificId("caster", 318993)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 0, 'constructor', 324533, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 1, 'event', 324534, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 2, 'state', 324535, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1659)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 3, 'lock_removal', 324536, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 6, 7018.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324532, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324533, 0, 1659.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324533, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324533, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324535, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324535, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324535, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1659, 324536, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 7019, 7271, 318819, 324537, 7001, 'HasEffectWithSpecificId("caster", 319004)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 0, 'constructor', 324538, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 1, 'event', 324539, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 2, 'state', 324540, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1660)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 3, 'lock_removal', 324541, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 6, 7019.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324537, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324538, 0, 1660.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324538, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324538, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324540, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324540, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324540, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1660, 324541, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 7020, 7271, 318819, 324542, 7001, 'HasEffectWithSpecificId("caster", 319015)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 0, 'constructor', 324543, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 1, 'event', 324544, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 2, 'state', 324545, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1661)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 3, 'lock_removal', 324546, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 6, 7020.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324542, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324543, 0, 1661.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324543, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324543, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324545, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324545, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324545, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1661, 324546, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 7021, 7271, 318819, 324547, 7001, 'HasEffectWithSpecificId("caster", 319334)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 0, 'constructor', 324548, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 1, 'event', 324549, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 2, 'state', 324550, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1662)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 3, 'lock_removal', 324551, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 6, 7021.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324547, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324548, 0, 1662.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324548, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324548, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324550, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324550, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324550, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1662, 324551, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 7022, 7271, 318819, 324552, 7001, 'HasEffectWithSpecificId("caster", 319347)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 0, 'constructor', 324553, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 1, 'event', 324554, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 2, 'state', 324555, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1663)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 3, 'lock_removal', 324556, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 6, 7022.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324552, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324553, 0, 1663.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324553, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324553, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324555, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324555, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324555, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1663, 324556, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 7023, 7271, 318819, 324557, 7001, 'HasEffectWithSpecificId("caster", 319048)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 0, 'constructor', 324558, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 1, 'event', 324559, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 2, 'state', 324560, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1664)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 3, 'lock_removal', 324561, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 6, 7023.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324557, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324558, 0, 1664.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324558, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324558, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324560, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324560, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324560, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1664, 324561, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 7024, 7271, 318819, 324562, 7001, 'HasEffectWithSpecificId("caster", 319059)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 0, 'constructor', 324563, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 1, 'event', 324564, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 2, 'state', 324565, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1665)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 3, 'lock_removal', 324566, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 6, 7024.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324562, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324563, 0, 1665.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324563, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324563, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324565, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324565, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324565, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1665, 324566, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_programs VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 7025, 7271, 318819, 324567, 7001, 'HasEffectWithSpecificId("caster", 319070)', 9);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 0, 'constructor', 324568, 315, 'anD', 'eVy', 1, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 1, 'event', 324569, 400, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[2172], 0);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 2, 'state', 324570, 304, 'anD', 'eVy', 2251799813685313, 0, 32767, 'IsSpecificArea(1666)', 2, ARRAY[]::integer[], ARRAY[]::integer[], 3);
INSERT INTO encounter_area_callback_program_steps VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 3, 'lock_removal', 324571, 321, 'anD', 'eVy', 8194, 0, 32767, '', 2, ARRAY[]::integer[], ARRAY[]::integer[], 1);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 0, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 1, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 2, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 3, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 4, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 5, 0.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 6, 7025.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 7, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324567, 8, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324568, 0, 1666.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324568, 1, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324568, 2, 1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324570, 0, 7001.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324570, 1, 0.0, 1.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324570, 2, -1.0, 0.0);
INSERT INTO encounter_area_callback_program_parameters VALUES ('wakemu-rushu-native-drop-callback-programs-v1', 1666, 324571, 0, 6999.0, 0.0);
INSERT INTO encounter_area_callback_program_active VALUES (1332, ARRAY[5306], 'wakemu-rushu-native-drop-callback-programs-v1');

-- Explicit reconstruction of four original NPC-owned START caster bindings.
-- Native NULL Qe, state producers, helper grades and callback programs stay unchanged.
CREATE TABLE encounter_npc_start_binding_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
 binding TEXT NOT NULL CHECK(binding='actual_owned_npc_turn_manager_as_caster'),
 effect_references INTEGER[] NOT NULL CHECK(cardinality(effect_references)>0),
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_npc_start_binding_effects (
 policy TEXT NOT NULL REFERENCES encounter_npc_start_binding_versions(policy),
 listener_reference INTEGER NOT NULL CHECK(listener_reference>0),
 carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
 owner_effect_reference INTEGER NOT NULL CHECK(owner_effect_reference>0),
 event_id INTEGER NOT NULL CHECK(event_id=1001),
 channel INTEGER NOT NULL CHECK(channel=60),
 caster_code INTEGER NOT NULL CHECK(caster_code=2),
 target_code INTEGER NOT NULL CHECK(target_code=2),
 effect_family INTEGER NOT NULL CHECK(effect_family=330),
 selector_mask BIGINT NOT NULL CHECK(selector_mask=1),
 area_class TEXT NOT NULL,
 native_execution_mode INTEGER NOT NULL,
 parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
 native_effect_flags INTEGER[] NOT NULL,
 criterion TEXT NOT NULL,
 native_parameters DOUBLE PRECISION[] NOT NULL,
 CHECK(cardinality(native_parameters)=2*parameter_count),
 native_children INTEGER[] NOT NULL CHECK(cardinality(native_children)>0),
 PRIMARY KEY(policy,listener_reference)
);
CREATE TABLE encounter_npc_start_binding_active (
 map_id INTEGER NOT NULL, monster_references INTEGER[] NOT NULL, policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_npc_start_binding_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_npc_start_binding_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_npc_start_binding_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_npc_start_binding_versions_no_truncate
 BEFORE TRUNCATE ON encounter_npc_start_binding_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_npc_start_binding_effects_immutable
 BEFORE UPDATE OR DELETE ON encounter_npc_start_binding_effects
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_npc_start_binding_effects_no_truncate
 BEFORE TRUNCATE ON encounter_npc_start_binding_effects
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION validate_npc_start_binding_effect_inventory() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM encounter_npc_start_binding_versions v
               WHERE v.policy=NEW.policy AND NEW.listener_reference=ANY(v.effect_references)) THEN
  RAISE EXCEPTION 'NPC START listener is outside immutable inventory';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER encounter_npc_start_binding_effect_inventory
 BEFORE INSERT ON encounter_npc_start_binding_effects
 FOR EACH ROW EXECUTE FUNCTION validate_npc_start_binding_effect_inventory();
INSERT INTO encounter_npc_start_binding_versions VALUES
('wakemu-rushu-held-owned-npc-start-caster-v1','wakemu-reconstructed-external-owned-npc-start-manager',
'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
1332,ARRAY[5306],5306,7000,'actual_owned_npc_turn_manager_as_caster',ARRAY[318946,318957,318968,325709]);
INSERT INTO encounter_npc_start_binding_effects VALUES
('wakemu-rushu-held-owned-npc-start-caster-v1',318946,7013,318945,1001,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
'',ARRAY[]::double precision[],ARRAY[324703,324705,318947]);
INSERT INTO encounter_npc_start_binding_effects VALUES
('wakemu-rushu-held-owned-npc-start-caster-v1',318957,7014,318956,1001,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
'',ARRAY[]::double precision[],ARRAY[318958,324706]);
INSERT INTO encounter_npc_start_binding_effects VALUES
('wakemu-rushu-held-owned-npc-start-caster-v1',318968,7015,318967,1001,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
'',ARRAY[]::double precision[],ARRAY[324707,324708,318969]);
INSERT INTO encounter_npc_start_binding_effects VALUES
('wakemu-rushu-held-owned-npc-start-caster-v1',325709,6998,319310,1001,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
'',ARRAY[]::double precision[],ARRAY[325710,325712]);
INSERT INTO encounter_npc_start_binding_active VALUES(1332,ARRAY[5306],'wakemu-rushu-held-owned-npc-start-caster-v1');
