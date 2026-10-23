-- Explicit Wakemu reconstruction: the original encounter publisher is unrecovered.
-- Native team criteria are preserved. Existing fights pin the immutable policy key.
CREATE TABLE encounter_role_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(
        cardinality(monster_references)>0 AND array_ndims(monster_references)=1
        AND array_lower(monster_references,1)=1
        AND array_position(monster_references,NULL) IS NULL
        AND 0<ALL(monster_references)),
    player_team SMALLINT NOT NULL CHECK(player_team IN (0,1)),
    npc_team SMALLINT NOT NULL CHECK(npc_team IN (0,1)),
    CHECK(player_team<>npc_team),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_role_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_role_versions(policy,map_id,monster_references)
);
CREATE FUNCTION forbid_encounter_role_version_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Encounter role versions are immutable';
END;
$$;
CREATE TRIGGER encounter_role_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_role_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_role_versions_no_truncate
    BEFORE TRUNCATE ON encounter_role_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_role_versions VALUES
('wakemu-nox-player1-npc0-v1','wakemu-reconstructed-nox-artifact-role-contract',1435,ARRAY[5664],1,0),
('wakemu-rushu-player1-npc0-v1','wakemu-reconstructed-rushu-vestige-role-contract',1332,ARRAY[5306],1,0);
INSERT INTO encounter_role_active
    SELECT map_id,monster_references,policy FROM encounter_role_versions;
