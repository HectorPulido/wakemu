-- Explicit guide/source-based reconstruction of owned cycle publications.
-- Native Qe IDs, table values, channels and subscriber programs stay intact.
CREATE TABLE encounter_turn_end_order_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    boss_reference INTEGER NOT NULL CHECK(boss_reference>0 AND boss_reference=ANY(monster_references)),
    boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
    table_turns INTEGER[] NOT NULL CHECK(cardinality(table_turns)>0 AND 0<ALL(table_turns)),
    event_ids INTEGER[] NOT NULL CHECK(event_ids=ARRAY[1002,1037] OR event_ids=ARRAY[1037,1002]),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_turn_end_order_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_turn_end_order_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_turn_end_order_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_turn_end_order_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_turn_end_order_versions_no_truncate
    BEFORE TRUNCATE ON encounter_turn_end_order_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_turn_end_order_versions VALUES
('wakemu-rushu-cycle-regeneration-before-end-v1',
 'wakemu-reconstructed-observed-rushu-cycle-end-order',
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 1332,ARRAY[5306],5306,7000,ARRAY[5,10,15,20],ARRAY[1037,1002]);
INSERT INTO encounter_turn_end_order_active VALUES
(1332,ARRAY[5306],'wakemu-rushu-cycle-regeneration-before-end-v1');
