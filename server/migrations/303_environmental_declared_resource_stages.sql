-- Declared physical stage substitution; original280 source remains immutable.
CREATE TABLE environmental_resource_stage_actions (
 source_key text NOT NULL,resource_reference integer NOT NULL,native_step integer NOT NULL CHECK(native_step BETWEEN 0 AND 15),
 action_ordinal integer NOT NULL CHECK(action_ordinal>=0),action_id integer NOT NULL CHECK(action_id>0),
 original_action jsonb NOT NULL CHECK(jsonb_typeof(original_action)='object'),
 action_sha256 text NOT NULL CHECK(action_sha256 ~ '^[0-9a-f]{64}$'),
 record_sha256 text NOT NULL CHECK(record_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(source_key,resource_reference,native_step,action_ordinal),
 FOREIGN KEY(source_key,resource_reference) REFERENCES environmental_original_resources,
 CHECK((original_action->>'action_id')::integer=action_id)
);
CREATE TABLE environmental_resource_stage_mappings (
 source_key text NOT NULL,scenario_id integer NOT NULL,resource_reference integer NOT NULL,
 source_native_step integer NOT NULL,native_step integer NOT NULL,action_ordinal integer NOT NULL,
 authority text NOT NULL CHECK(length(btrim(authority))>0),
 PRIMARY KEY(source_key,scenario_id),CHECK(source_native_step<>native_step),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_scenario_resource_actions,
 FOREIGN KEY(source_key,resource_reference,native_step,action_ordinal) REFERENCES environmental_resource_stage_actions
);
CREATE FUNCTION validate_environmental_resource_stage_action() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE original environmental_original_resources%ROWTYPE;actual jsonb;
BEGIN
 SELECT * INTO STRICT original FROM environmental_original_resources
 WHERE source_key=NEW.source_key AND resource_reference=NEW.resource_reference;
 SELECT s->'actions'->NEW.action_ordinal INTO STRICT actual
 FROM jsonb_array_elements(original.original_record->'stage_definitions') s
 WHERE (s->>'stage_id')::integer=NEW.native_step;
 IF actual IS NULL OR actual<>NEW.original_action OR original.record_sha256<>NEW.record_sha256 THEN
  RAISE EXCEPTION 'Declared stage action differs from original resource record';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_stage_action_source BEFORE INSERT ON environmental_resource_stage_actions
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_resource_stage_action();
CREATE FUNCTION validate_environmental_resource_stage_mapping() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM environmental_scenario_resource_actions b WHERE
 (b.source_key,b.scenario_id,b.resource_reference,b.native_step)=
 (NEW.source_key,NEW.scenario_id,NEW.resource_reference,NEW.source_native_step)
 AND b.status='missing_original_stage') THEN
  RAISE EXCEPTION 'Stage declaration does not match original missing-stage source';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_stage_mapping_source BEFORE INSERT ON environmental_resource_stage_mappings
 FOR EACH ROW EXECUTE FUNCTION validate_environmental_resource_stage_mapping();
CREATE VIEW environmental_resolved_resource_actions AS
 SELECT b.source_key,b.scenario_id,b.resource_reference,b.native_step,b.native_step AS source_native_step,
 b.action_ordinal,a.action_id,a.original_action,a.action_sha256,a.native_criteria,
 'Original scenario stage and action'::text AS authority
 FROM environmental_scenario_resource_actions b JOIN environmental_original_resource_actions a
 USING(source_key,resource_reference,native_step,action_ordinal) WHERE b.status='matched_original_action'
 UNION ALL
 SELECT m.source_key,m.scenario_id,m.resource_reference,m.native_step,m.source_native_step,
 m.action_ordinal,a.action_id,a.original_action,a.action_sha256,a.original_action->>'criteria',m.authority
 FROM environmental_resource_stage_mappings m JOIN environmental_resource_stage_actions a
 USING(source_key,resource_reference,native_step,action_ordinal);
INSERT INTO environmental_resource_stage_actions VALUES('installed-environmental-source-v1','730','1','0','2091','{"action_id":2091,"criteria":"","duration_ms":1000,"item_reference":0,"minimum_level":0,"product_references":[],"profession_id":0,"raw_getters":{"bwX":0,"cmI":0.0,"csN":119,"csR":false,"cvF":0,"cvG":1,"cvH":0,"cvI":false,"cvK":0}}','21cad10556252c8f74e0963e43ec685875dc279bdfd147c219fd3cdb56c707b3','2fde678e8bb5b86f944ae96b266b1cdbc26a537af8bdfa38f01b30a97db00c9d');
INSERT INTO environmental_resource_stage_actions VALUES('installed-environmental-source-v1','744','1','0','2102','{"action_id":2102,"criteria":"","duration_ms":1000,"item_reference":0,"minimum_level":0,"product_references":[],"profession_id":0,"raw_getters":{"bwX":0,"cmI":0.0,"csN":119,"csR":false,"cvF":0,"cvG":1,"cvH":0,"cvI":false,"cvK":0}}','62bbc2643291e86e169e393445463cbfc512b6a265448eacdb2a4a42f3dd2c76','c74cabab124b15a80630b656db7dc85f951d815106401a3aa3b7c2c7fa27b305');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1880','744','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1879','744','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1878','744','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1877','744','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1637','730','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1636','730','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1635','730','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
INSERT INTO environmental_resource_stage_mappings VALUES('installed-environmental-source-v1','-1634','730','2','1','0','Wakemu reconstructed bomb interaction: original requested stage2 unavailable; original physical stage1 action; source bodies identify remove/defuse bombs');
CREATE TRIGGER immutable_stage_source BEFORE UPDATE OR DELETE ON environmental_resource_stage_actions FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();
CREATE TRIGGER immutable_stage_truncate BEFORE TRUNCATE ON environmental_resource_stage_actions FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_native_source_mutation();
CREATE TRIGGER immutable_stage_source BEFORE UPDATE OR DELETE ON environmental_resource_stage_mappings FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();
CREATE TRIGGER immutable_stage_truncate BEFORE TRUNCATE ON environmental_resource_stage_mappings FOR EACH STATEMENT EXECUTE FUNCTION reject_environmental_native_source_mutation();
CREATE OR REPLACE FUNCTION validate_environmental_resource_level_criterion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;original_criterion text;
BEGIN
 k:=COALESCE(NEW.profile_key,OLD.profile_key);v:=COALESCE(NEW.version,OLD.version);
 IF NOT EXISTS(SELECT 1 FROM environmental_profile_resource_population WHERE profile_key=k AND version=v) THEN
  RETURN NULL;
 END IF;
 SELECT a.native_criteria INTO original_criterion
 FROM environmental_profile_resource_population p
 JOIN environmental_runtime_profiles r USING(profile_key,version)
 JOIN environmental_resolved_resource_actions a ON a.source_key=p.source_key
  AND a.scenario_id=r.native_scenario_id
 WHERE p.profile_key=k AND p.version=v;
 IF NOT FOUND THEN RAISE EXCEPTION 'Environmental resource population lacks its exact original action'; END IF;
 PERFORM environmental_resource_criterion_minimum(original_criterion);
 RETURN NULL;
END $$;
