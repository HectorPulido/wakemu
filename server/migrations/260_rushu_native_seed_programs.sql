-- Reconstructed initial layout executes original ordered349 programs at level1.
CREATE TABLE encounter_seed_program_versions (
 policy TEXT PRIMARY KEY CHECK(length(policy)>0),
 authority TEXT NOT NULL CHECK(length(authority)>0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
 boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
 boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
 initial_level INTEGER NOT NULL CHECK(initial_level BETWEEN 1 AND 32767),
 area_references INTEGER[] NOT NULL CHECK(cardinality(area_references)>0),
 UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_seed_program_rows (
 policy TEXT NOT NULL REFERENCES encounter_seed_program_versions(policy),
 area_reference INTEGER NOT NULL CHECK(area_reference>0),
 creator_reference INTEGER NOT NULL CHECK(creator_reference>0),
 program_reference INTEGER NOT NULL CHECK(program_reference>0),
 state_reference INTEGER NOT NULL CHECK(state_reference>0),
 state_effect_reference INTEGER NOT NULL CHECK(state_effect_reference>0),
 PRIMARY KEY(policy,area_reference),
 UNIQUE(policy,creator_reference), UNIQUE(policy,program_reference),
 UNIQUE(policy,state_effect_reference)
);
CREATE TABLE encounter_seed_program_active (
 map_id INTEGER NOT NULL,
 monster_references INTEGER[] NOT NULL,
 policy TEXT NOT NULL,
 PRIMARY KEY(map_id,monster_references),
 FOREIGN KEY(policy,map_id,monster_references)
 REFERENCES encounter_seed_program_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_seed_program_versions_immutable
 BEFORE UPDATE OR DELETE ON encounter_seed_program_versions
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_seed_program_versions_no_truncate
 BEFORE TRUNCATE ON encounter_seed_program_versions
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_seed_program_rows_immutable
 BEFORE UPDATE OR DELETE ON encounter_seed_program_rows
 FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_seed_program_rows_no_truncate
 BEFORE TRUNCATE ON encounter_seed_program_rows
 FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION validate_encounter_seed_program_member() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM encounter_seed_program_versions v
               WHERE v.policy=NEW.policy AND NEW.area_reference=ANY(v.area_references)) THEN
  RAISE EXCEPTION 'Area is outside the immutable encounter seed program inventory';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_seed_program_rows_inventory
 BEFORE INSERT ON encounter_seed_program_rows
 FOR EACH ROW EXECUTE FUNCTION validate_encounter_seed_program_member();
INSERT INTO encounter_seed_program_versions VALUES
('wakemu-rushu-initial-vestige-programs-v1','wakemu-reconstructed-initial-layout-original-programs',
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 1332,ARRAY[5306],5306,7000,1,ARRAY[1650,1652,1653,1654,1655,1656,1657,1658,1659,1660,1661,1662,1663,1664,1665,1666]);
INSERT INTO encounter_seed_program_rows VALUES
('wakemu-rushu-initial-vestige-programs-v1',1650,324354,324353,7001,324355),
('wakemu-rushu-initial-vestige-programs-v1',1652,324360,324359,7001,324361),
('wakemu-rushu-initial-vestige-programs-v1',1653,324365,324364,7001,324366),
('wakemu-rushu-initial-vestige-programs-v1',1654,324370,324369,7001,324371),
('wakemu-rushu-initial-vestige-programs-v1',1655,324375,324374,7001,324376),
('wakemu-rushu-initial-vestige-programs-v1',1656,324380,324379,7001,324381),
('wakemu-rushu-initial-vestige-programs-v1',1657,324385,324384,7001,324386),
('wakemu-rushu-initial-vestige-programs-v1',1658,324390,324389,7001,324391),
('wakemu-rushu-initial-vestige-programs-v1',1659,324395,324394,7001,324396),
('wakemu-rushu-initial-vestige-programs-v1',1660,324400,324399,7001,324401),
('wakemu-rushu-initial-vestige-programs-v1',1661,324405,324404,7001,324406),
('wakemu-rushu-initial-vestige-programs-v1',1662,324410,324409,7001,324411),
('wakemu-rushu-initial-vestige-programs-v1',1663,324415,324414,7001,324416),
('wakemu-rushu-initial-vestige-programs-v1',1664,324420,324419,7001,324421),
('wakemu-rushu-initial-vestige-programs-v1',1665,324425,324424,7001,324426),
('wakemu-rushu-initial-vestige-programs-v1',1666,324430,324429,7001,324431);
INSERT INTO encounter_seed_program_active VALUES
(1332,ARRAY[5306],'wakemu-rushu-initial-vestige-programs-v1');
