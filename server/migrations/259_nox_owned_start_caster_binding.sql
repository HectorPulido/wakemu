-- Explicit reconstruction of the missing server-owned START participant binding.
-- Native eZR.l/m(NULL), Qb/Qd, masks, criteria and child programs stay unchanged.
CREATE TABLE encounter_owned_start_binding_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
 carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
 listener_reference INTEGER NOT NULL CHECK(listener_reference>0),
 binding TEXT NOT NULL CHECK(binding='actual_owned_turn_manager_as_caster'),
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
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_owned_start_binding_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_owned_start_binding_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_owned_start_binding_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_owned_start_binding_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_owned_start_binding_versions_no_truncate
 BEFORE TRUNCATE ON encounter_owned_start_binding_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_owned_start_binding_versions VALUES
('wakemu-nox-faille-owned-start-caster-v1',
 'wakemu-reconstructed-external-owned-start-participant',
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 1435,ARRAY[5664],5664,8969,9028,402183,
 'actual_owned_turn_manager_as_caster',1001,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
 '(GetStateCountInRange(-1, "target", 8981) + GetStateCountInRange(-1, "target", 8982) + GetStateCountInRange(-1, "target", 8983) + GetStateCountInRange(-1, "target", 8984)) >= 1',
 ARRAY[]::double precision[],ARRAY[402184,402194]);
INSERT INTO encounter_owned_start_binding_active VALUES
(1435,ARRAY[5664],'wakemu-nox-faille-owned-start-caster-v1');
