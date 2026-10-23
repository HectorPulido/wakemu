-- Explicit Wakemu reconstruction, not a change to native Qe.g chosen-PV replay.
CREATE TABLE encounter_group_population_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    effect_references INTEGER[] NOT NULL CHECK(cardinality(effect_references)>0),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_group_population_effects (
    policy TEXT NOT NULL REFERENCES encounter_group_population_versions(policy),
    effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
    effect_family INTEGER NOT NULL CHECK(effect_family IN (304,321,330)),
    selector_mask BIGINT NOT NULL CHECK(selector_mask=0),
    parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
    criterion TEXT NOT NULL CHECK(length(criterion)>0),
    native_parameters DOUBLE PRECISION[] NOT NULL,
    CHECK(cardinality(native_parameters)=2*parameter_count),
    PRIMARY KEY(policy,effect_reference)
);
CREATE TABLE encounter_group_population_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_group_population_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_group_population_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_group_population_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_group_population_versions_no_truncate
    BEFORE TRUNCATE ON encounter_group_population_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_group_population_effects_immutable
    BEFORE UPDATE OR DELETE ON encounter_group_population_effects
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_group_population_effects_no_truncate
    BEFORE TRUNCATE ON encounter_group_population_effects
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION validate_encounter_group_population_member() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM encounter_group_population_versions v
        WHERE v.policy=NEW.policy AND NEW.effect_reference=ANY(v.effect_references)
    ) THEN
        RAISE EXCEPTION 'Effect is outside the immutable group population inventory';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_group_population_effects_inventory
    BEFORE INSERT ON encounter_group_population_effects
    FOR EACH ROW EXECUTE FUNCTION validate_encounter_group_population_member();
INSERT INTO encounter_group_population_versions VALUES
('wakemu-tal-mirror-criterion-population-v1','wakemu-reconstructed-fresh-controller-population',
 1400,ARRAY[5500],ARRAY[379384,379386,379951,379954,394706,394707]);
INSERT INTO encounter_group_population_effects VALUES
('wakemu-tal-mirror-criterion-population-v1',379384,304,0,3,'HasState(8231, "target")',ARRAY[8250.0,0.0,1.0,0.0,-1.0,0.0]::double precision[]),
('wakemu-tal-mirror-criterion-population-v1',379386,321,0,1,'HasState(8231, "target")',ARRAY[8250.0,0.0]::double precision[]),
('wakemu-tal-mirror-criterion-population-v1',379951,330,0,0,'HasState(8237, "target")',ARRAY[]::double precision[]),
('wakemu-tal-mirror-criterion-population-v1',379954,330,0,0,'HasState(8237, "target")',ARRAY[]::double precision[]),
('wakemu-tal-mirror-criterion-population-v1',394706,321,0,1,'HasState(8231, "target")',ARRAY[8891.0,0.0]::double precision[]),
('wakemu-tal-mirror-criterion-population-v1',394707,304,0,3,'HasState(8231, "target") and HasState(8236)',ARRAY[8891.0,0.0,1.0,0.0,-1.0,0.0]::double precision[]);
INSERT INTO encounter_group_population_active VALUES
(1400,ARRAY[5500],'wakemu-tal-mirror-criterion-population-v1');
