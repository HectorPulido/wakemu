-- Reconstructed Nox table publisher; execute only the original owned Cube listener.
CREATE TABLE encounter_table_listener_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
    boss_reference INTEGER NOT NULL CHECK(boss_reference>0),
    boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
    owner_reference INTEGER NOT NULL CHECK(owner_reference>0),
    owner_constructor_state INTEGER NOT NULL CHECK(owner_constructor_state>0),
    effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
    event_id INTEGER NOT NULL CHECK(event_id=1003),
    channel INTEGER NOT NULL CHECK(channel=61),
    timing TEXT NOT NULL CHECK(timing='owned_boss_table_start'),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_table_listener_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_table_listener_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_table_listener_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_table_listener_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_table_listener_versions_no_truncate
    BEFORE TRUNCATE ON encounter_table_listener_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_table_listener_versions VALUES
('wakemu-nox-cube-table-listener-v1','wakemu-reconstructed-owned-cube-table-publication',
 1435,ARRAY[5664],'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 5664,8969,5786,8974,401548,1003,61,'owned_boss_table_start');
INSERT INTO encounter_table_listener_active VALUES
(1435,ARRAY[5664],'wakemu-nox-cube-table-listener-v1');
