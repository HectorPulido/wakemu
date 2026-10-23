-- Explicit Wakemu marker placement reconstruction. Native faY prototypes and
-- original Nox roots own all subsequent summons, states, costs and effects.
CREATE TABLE encounter_marker_placement_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
    source_url TEXT NOT NULL,
    coordinate_authority TEXT NOT NULL,
    expected_count INTEGER NOT NULL CHECK(expected_count>0),
    placements_sha256 TEXT NOT NULL CHECK(length(placements_sha256)=64),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_marker_placements (
    policy TEXT NOT NULL REFERENCES encounter_marker_placement_versions(policy),
    ordinal INTEGER NOT NULL CHECK(ordinal>=0),
    area_reference INTEGER NOT NULL CHECK(area_reference>0),
    level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 32767),
    x INTEGER NOT NULL, y INTEGER NOT NULL, z SMALLINT NOT NULL,
    PRIMARY KEY(policy,ordinal), UNIQUE(policy,x,y)
);
CREATE TABLE encounter_marker_placement_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_marker_placement_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_marker_placement_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_marker_placement_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_marker_placement_versions_no_truncate
    BEFORE TRUNCATE ON encounter_marker_placement_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_marker_placements_immutable
    BEFORE UPDATE OR DELETE ON encounter_marker_placements
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_marker_placements_no_truncate
    BEFORE TRUNCATE ON encounter_marker_placements
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_marker_placement_versions VALUES
('wakemu.nox.initial-markers.native-floor-reconstruction.v2','authorized_wakemu_original_marker_placement_reconstruction',1435,ARRAY[5664],
'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
'https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/',
'guide_five_batteries_one_cube_schematic;world_xyz_explicit_reconstruction',17,'342a888dae39e4b914fb599f75aed6110e29d507976085cefa2e62de95ba6f7c');
INSERT INTO encounter_marker_placements VALUES
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',0,2057,0,-7,-10,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',1,2058,0,-4,-10,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',2,2059,0,2,-10,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',3,2060,0,5,-10,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',4,2061,0,-7,-12,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',5,2062,0,-4,-12,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',6,2063,0,-1,-12,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',7,2064,0,2,-12,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',8,2065,0,5,-12,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',9,2066,0,0,-14,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',10,2067,0,-1,-10,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',11,2050,0,-7,-19,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',12,2050,0,5,-19,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',13,2050,0,-8,-13,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',14,2050,0,6,-11,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',15,2050,0,-4,-6,0),
('wakemu.nox.initial-markers.native-floor-reconstruction.v2',16,2051,0,-5,-15,0);
INSERT INTO encounter_marker_placement_active VALUES
(1435,ARRAY[5664],'wakemu.nox.initial-markers.native-floor-reconstruction.v2');
