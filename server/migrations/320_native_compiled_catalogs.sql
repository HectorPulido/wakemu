-- Derived immutable combat publications; original native catalogs remain intact.
CREATE TABLE native_compiled_catalog_releases (
 generation text PRIMARY KEY CHECK(generation ~ '^[0-9a-f]{64}$'),
 policy text NOT NULL,
 source_revision text NOT NULL REFERENCES native_catalog_releases(revision),
 source_inventory_sha256 text NOT NULL CHECK(source_inventory_sha256 ~ '^[0-9a-f]{64}$'),
 compiler_contract_sha256 text NOT NULL CHECK(compiler_contract_sha256 ~ '^[0-9a-f]{64}$'),
 config_sha256 text NOT NULL CHECK(config_sha256 ~ '^[0-9a-f]{64}$'),
 manifest_raw bytea NOT NULL,
 manifest jsonb NOT NULL,
 complete boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz,
 UNIQUE(policy,source_revision,source_inventory_sha256,compiler_contract_sha256,config_sha256)
);

CREATE TABLE native_compiled_catalog_collections (
 generation text NOT NULL REFERENCES native_compiled_catalog_releases(generation),
 collection text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('dict','list')),
 record_count integer NOT NULL CHECK(record_count>=0),
 ordered_keys_raw bytea NOT NULL,
 ordered_keys_sha256 text NOT NULL CHECK(ordered_keys_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(generation,collection)
);

CREATE TABLE native_compiled_catalog_records (
 generation text NOT NULL,
 collection text NOT NULL,
 record_key text NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal>=0),
 raw bytea NOT NULL,
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(generation,collection,record_key),
 UNIQUE(generation,collection,ordinal),
 FOREIGN KEY(generation,collection)
 REFERENCES native_compiled_catalog_collections(generation,collection)
);

CREATE FUNCTION guard_complete_native_compiled_catalog() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE published boolean;
BEGIN
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

CREATE TRIGGER native_compiled_catalog_release_immutable
 BEFORE UPDATE OR DELETE ON native_compiled_catalog_releases
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_catalog();
CREATE TRIGGER native_compiled_catalog_collection_immutable
 BEFORE INSERT OR UPDATE OR DELETE ON native_compiled_catalog_collections
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_catalog();
CREATE TRIGGER native_compiled_catalog_record_immutable
 BEFORE INSERT OR UPDATE OR DELETE ON native_compiled_catalog_records
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_catalog();
