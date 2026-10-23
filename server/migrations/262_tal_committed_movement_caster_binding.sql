-- Explicit reconstruction of the missing server-committed movement participant binding.
-- Native eZR.l/m(NULL), Qb/Qd, masks, criteria and child programs stay unchanged.
CREATE TABLE encounter_movement_binding_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
 carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
 listener_reference INTEGER NOT NULL CHECK(listener_reference>0),
 binding TEXT NOT NULL CHECK(binding='actual_committed_movement_manager_as_caster'),
 event_id INTEGER NOT NULL CHECK(event_id=1005),
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
CREATE TABLE encounter_movement_binding_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_movement_binding_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_movement_binding_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_movement_binding_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_movement_binding_versions_no_truncate
 BEFORE TRUNCATE ON encounter_movement_binding_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_movement_binding_versions VALUES
('wakemu-tal-committed-movement-caster-v1',
 'wakemu-reconstructed-external-committed-movement-manager',
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 1400,ARRAY[5500],5500,8231,8231,379830,
 'actual_committed_movement_manager_as_caster',1005,60,2,2,330,1,'anD',2,0,ARRAY[]::integer[],
 '',ARRAY[]::double precision[],ARRAY[379833,379834,379831,380304,379836,380104]);
INSERT INTO encounter_movement_binding_active VALUES
(1400,ARRAY[5500],'wakemu-tal-committed-movement-caster-v1');
