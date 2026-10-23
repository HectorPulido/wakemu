-- Native component authority. Existing characters remain explicitly unknown.
CREATE TABLE native_national_progression_versions (
 version text PRIMARY KEY,source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 provenance text NOT NULL CHECK(length(provenance)>0)
);
INSERT INTO native_national_progression_versions VALUES
 ('native-national-component-20261020-v1',
  '89bff63987a7fce2806aa85d2851cefe96b08e24ee22e67d9a39ab63de9c4400',
  'Original installed ProbeNationScores: bVr constructor, signed scores and fxk rank matrix');
CREATE TABLE native_national_pvp_ranks (
 version text NOT NULL REFERENCES native_national_progression_versions(version),
 rank_id smallint NOT NULL CHECK(rank_id BETWEEN 0 AND 127),
 merit_threshold integer NOT NULL CHECK(merit_threshold>=0),
 PRIMARY KEY(version,rank_id),UNIQUE(version,merit_threshold)
);
INSERT INTO native_national_pvp_ranks VALUES
 ('native-national-component-20261020-v1',0,0),
 ('native-national-component-20261020-v1',1,2000),
 ('native-national-component-20261020-v1',2,4000),
 ('native-national-component-20261020-v1',3,6000),
 ('native-national-component-20261020-v1',4,8000),
 ('native-national-component-20261020-v1',5,10000),
 ('native-national-component-20261020-v1',6,12000),
 ('native-national-component-20261020-v1',7,14000),
 ('native-national-component-20261020-v1',8,16000),
 ('native-national-component-20261020-v1',9,18000);
CREATE FUNCTION native_national_source_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Native national authority is append-only'; END $$;
CREATE TRIGGER native_national_version_immutable BEFORE UPDATE OR DELETE ON native_national_progression_versions
 FOR EACH ROW EXECUTE FUNCTION native_national_source_immutable();
CREATE TRIGGER native_national_rank_immutable BEFORE UPDATE OR DELETE ON native_national_pvp_ranks
 FOR EACH ROW EXECUTE FUNCTION native_national_source_immutable();
CREATE TABLE character_national_authority (
 character_id bigint PRIMARY KEY,account_id bigint NOT NULL,
 version text NOT NULL,rank_id smallint NOT NULL,
 provenance text NOT NULL CHECK(provenance IN ('native_constructor','native_import')),
 revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 FOREIGN KEY(version,rank_id) REFERENCES native_national_pvp_ranks(version,rank_id),
 UNIQUE(character_id,account_id)
);
CREATE TABLE character_national_crime_scores (
 character_id bigint NOT NULL,account_id bigint NOT NULL,
 nation_id integer NOT NULL CHECK(nation_id>=0),score integer NOT NULL,
 PRIMARY KEY(character_id,nation_id),
 FOREIGN KEY(character_id,account_id) REFERENCES character_national_authority(character_id,account_id)
);
CREATE TABLE character_national_import_receipts (
 character_id bigint NOT NULL,account_id bigint NOT NULL,
 receipt_key text NOT NULL CHECK(length(receipt_key) BETWEEN 1 AND 160),
 source_digest text NOT NULL CHECK(length(source_digest)=64),
 PRIMARY KEY(character_id,receipt_key),
 FOREIGN KEY(character_id,account_id) REFERENCES character_national_authority(character_id,account_id)
);
