-- Sharing is activated by the explicit catalog compaction tool. Existing
-- publications remain readable throughout the staging/backfill phase.
CREATE TABLE native_compiled_collection_contents (
 content_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 collection text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('dict','list')),
 representation text NOT NULL CHECK(representation IN ('native_json','frozen_effect')),
 record_count integer NOT NULL CHECK(record_count>=0),
 ordered_keys_sha256 text NOT NULL CHECK(ordered_keys_sha256 ~ '^[0-9a-f]{64}$'),
 records_sha256 text NOT NULL CHECK(records_sha256 ~ '^[0-9a-f]{64}$'),
 complete boolean NOT NULL DEFAULT false,
 UNIQUE(collection,kind,representation,record_count,ordered_keys_sha256,records_sha256)
);

CREATE TABLE native_compiled_content_records (
 content_id bigint NOT NULL REFERENCES native_compiled_collection_contents(content_id),
 record_key text NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal>=0),
 raw bytea NOT NULL,
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(content_id,record_key),
 UNIQUE(content_id,ordinal)
);

ALTER TABLE native_compiled_catalog_collections ADD COLUMN content_id bigint
 REFERENCES native_compiled_collection_contents(content_id);
CREATE INDEX native_compiled_catalog_collections_content
 ON native_compiled_catalog_collections(content_id);

CREATE FUNCTION guard_complete_native_compiled_content() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE published boolean;
BEGIN
 IF TG_TABLE_NAME='native_compiled_collection_contents' THEN
  IF OLD.complete THEN
   -- Retention removes unreferenced content through an explicit maintenance
   -- transaction; the foreign keys still prevent removal of referenced data.
   IF TG_OP='DELETE' AND
      current_setting('wakemu.compiled_catalog_maintenance',true)='on' THEN
    RETURN OLD;
   END IF;
   RAISE EXCEPTION 'A complete compiled collection content is immutable';
  END IF;
 ELSE
  IF TG_OP='DELETE' AND
     current_setting('wakemu.compiled_catalog_maintenance',true)='on' AND
     NOT EXISTS(SELECT 1 FROM native_compiled_catalog_collections
                WHERE content_id=OLD.content_id) THEN
   RETURN OLD;
  END IF;
  IF TG_OP='UPDATE' THEN
   SELECT bool_or(complete) INTO published FROM native_compiled_collection_contents
    WHERE content_id IN (OLD.content_id,NEW.content_id);
  ELSE
   SELECT complete INTO published FROM native_compiled_collection_contents
    WHERE content_id=CASE WHEN TG_OP='DELETE' THEN OLD.content_id ELSE NEW.content_id END;
  END IF;
  IF published THEN
   RAISE EXCEPTION 'Complete compiled collection records are immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;

-- Empty installations start with sharing immediately. Populated databases
-- require the explicit compactor so no large copy runs inside migrations.
DO $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM native_compiled_catalog_records LIMIT 1) THEN
  DROP TABLE native_compiled_catalog_records;
  EXECUTE 'CREATE VIEW native_compiled_catalog_records AS
   SELECT c.generation,c.collection,r.record_key,r.ordinal,r.raw,r.sha256
   FROM native_compiled_catalog_collections c
   JOIN native_compiled_content_records r USING(content_id)';
 END IF;
END $$;

CREATE TRIGGER native_compiled_content_immutable
 BEFORE UPDATE OR DELETE ON native_compiled_collection_contents
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_content();
CREATE TRIGGER native_compiled_content_record_immutable
 BEFORE INSERT OR UPDATE OR DELETE ON native_compiled_content_records
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_content();

CREATE FUNCTION check_native_compiled_content_reference() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE valid boolean;
BEGIN
 IF NEW.content_id IS NULL THEN RETURN NEW; END IF;
 SELECT c.complete AND c.collection=NEW.collection AND c.kind=NEW.kind
        AND c.record_count=NEW.record_count
        AND c.ordered_keys_sha256=NEW.ordered_keys_sha256
        AND c.records_sha256=r.manifest->'collections'->NEW.collection->>'records_sha256'
        AND c.representation=r.manifest->'collections'->NEW.collection->>'representation'
 INTO valid
 FROM native_compiled_collection_contents c
 JOIN native_compiled_catalog_releases r ON r.generation=NEW.generation
 WHERE c.content_id=NEW.content_id;
 IF valid IS DISTINCT FROM true THEN
  RAISE EXCEPTION 'Compiled collection content differs from publication';
 END IF;
 RETURN NEW;
END $$;

CREATE TRIGGER native_compiled_content_reference
 BEFORE INSERT OR UPDATE ON native_compiled_catalog_collections
 FOR EACH ROW EXECUTE FUNCTION check_native_compiled_content_reference();

-- Retirement is explicit and transaction-scoped. Normal publication and
-- reader operations retain the original immutable-generation contract.
CREATE OR REPLACE FUNCTION guard_complete_native_compiled_catalog() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE published boolean;
BEGIN
 IF TG_OP='DELETE' AND
    current_setting('wakemu.compiled_catalog_maintenance',true)='on' THEN
  RETURN OLD;
 END IF;
 IF TG_TABLE_NAME='native_compiled_catalog_releases' THEN
  IF OLD.complete THEN
   RAISE EXCEPTION 'A complete compiled catalog publication is immutable';
  END IF;
 ELSE
  IF TG_OP='UPDATE' THEN
   SELECT bool_or(complete) INTO published FROM native_compiled_catalog_releases
    WHERE generation IN (OLD.generation,NEW.generation);
  ELSE
   SELECT complete INTO published FROM native_compiled_catalog_releases
    WHERE generation=CASE WHEN TG_OP='DELETE' THEN OLD.generation ELSE NEW.generation END;
  END IF;
  IF published THEN
   RAISE EXCEPTION 'A complete compiled catalog collection is immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
