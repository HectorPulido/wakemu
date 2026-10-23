-- Additive original faJ identity authority; the active catalog release is unchanged.
CREATE TABLE native_health_ordering_authority_versions (
 authority_key TEXT PRIMARY KEY CHECK(length(authority_key)>0),
 catalog_revision TEXT NOT NULL UNIQUE CHECK(catalog_revision ~ '^[0-9a-f]{64}$'),
 ordering_contract TEXT NOT NULL CHECK(ordering_contract='faJ.PV.a.sgC.PA.aYS.aYU.float32.desc.v1'),
 source_proof_sha256 TEXT NOT NULL CHECK(source_proof_sha256 ~ '^[0-9a-f]{64}$'),
 definition_count INTEGER NOT NULL CHECK(definition_count>0)
);
CREATE TABLE native_health_ordering_authority_rows (
 authority_key TEXT NOT NULL REFERENCES native_health_ordering_authority_versions(authority_key),
 effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
 effect_class INTEGER NOT NULL CHECK(effect_class>0),
 native_effect_flags SMALLINT[] NOT NULL CHECK(25=ANY(native_effect_flags)),
 maximum_targets SMALLINT NOT NULL CHECK(maximum_targets BETWEEN -128 AND 127),
 PRIMARY KEY(authority_key,effect_reference)
);
CREATE FUNCTION reject_native_health_ordering_authority_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Native health ordering authority is append-only'; END;
$$;
CREATE TRIGGER native_health_ordering_versions_immutable BEFORE UPDATE OR DELETE ON native_health_ordering_authority_versions FOR EACH ROW EXECUTE FUNCTION reject_native_health_ordering_authority_mutation();
CREATE TRIGGER native_health_ordering_rows_immutable BEFORE UPDATE OR DELETE ON native_health_ordering_authority_rows FOR EACH ROW EXECUTE FUNCTION reject_native_health_ordering_authority_mutation();
INSERT INTO native_health_ordering_authority_versions VALUES ('native-faJ-descending-health-v1','b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450','faJ.PV.a.sgC.PA.aYS.aYU.float32.desc.v1','f0c2d6576b2c5cd2f9adcf41a884ecf656549a0b21b8fe7ca463aaeadca8fe77',9);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',179243,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',325710,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',335005,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',335210,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',351291,330,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',374497,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',376045,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',376049,345,ARRAY[25]::smallint[],-1);
INSERT INTO native_health_ordering_authority_rows VALUES ('native-faJ-descending-health-v1',380144,345,ARRAY[25]::smallint[],-1);
