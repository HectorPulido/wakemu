-- Wakemu reconstruction: original external10006 publisher is unrecovered.
-- This policy is independent of encounter teams and never changes native masks.
CREATE TABLE encounter_area_activation_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    area_references INTEGER[] NOT NULL CHECK(cardinality(area_references)>0),
    event_id INTEGER NOT NULL CHECK(event_id=10006),
    timing TEXT NOT NULL CHECK(timing='post_registration'),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_area_activation_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_area_activation_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_area_activation_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_area_activation_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_area_activation_versions_no_truncate
    BEFORE TRUNCATE ON encounter_area_activation_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_area_activation_versions VALUES
('wakemu-tal-post-registration10006-v1','wakemu-reconstructed-external-area-activation',
 1400,ARRAY[5500],ARRAY[1839,1840,1841,1842],10006,'post_registration');
INSERT INTO encounter_area_activation_active VALUES
(1400,ARRAY[5500],'wakemu-tal-post-registration10006-v1');
