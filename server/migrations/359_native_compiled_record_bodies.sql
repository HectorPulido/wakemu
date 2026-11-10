-- Exact byte bodies can be shared across immutable collections and variants.
-- Populated installations activate this schema through the online compactor.
CREATE TABLE native_compiled_record_bodies (
 body_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 sha256 bytea NOT NULL UNIQUE CHECK(octet_length(sha256)=32),
 raw bytea NOT NULL,
 source_bytes integer NOT NULL CHECK(source_bytes BETWEEN 0 AND 16777216 AND source_bytes=octet_length(raw)),
 CHECK(sha256=sha256(raw))
);

CREATE TABLE native_compiled_record_links (
 content_id bigint NOT NULL REFERENCES native_compiled_collection_contents(content_id),
 record_key text NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal>=0),
 body_id bigint NOT NULL REFERENCES native_compiled_record_bodies(body_id),
 PRIMARY KEY(content_id,record_key),
 UNIQUE(content_id,ordinal)
);
CREATE INDEX native_compiled_record_links_body ON native_compiled_record_links(body_id);

CREATE TRIGGER native_compiled_record_link_immutable
 BEFORE INSERT OR UPDATE OR DELETE ON native_compiled_record_links
 FOR EACH ROW EXECUTE FUNCTION guard_complete_native_compiled_content();

CREATE FUNCTION guard_native_compiled_record_body() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' AND
    current_setting('wakemu.compiled_catalog_maintenance',true)='on' AND
    NOT EXISTS(SELECT 1 FROM native_compiled_record_links WHERE body_id=OLD.body_id) THEN
  RETURN OLD;
 END IF;
 RAISE EXCEPTION 'A compiled record body is immutable';
END $$;
CREATE TRIGGER native_compiled_record_body_immutable
 BEFORE UPDATE OR DELETE ON native_compiled_record_bodies
 FOR EACH ROW EXECUTE FUNCTION guard_native_compiled_record_body();

CREATE FUNCTION intern_native_compiled_record_body(body bytea, checksum text)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE identity bytea; selected bigint; expected integer;
BEGIN
 IF checksum IS NULL OR checksum !~ '^[0-9a-f]{64}$' OR body IS NULL THEN
  RAISE EXCEPTION 'Invalid compiled record body identity';
 END IF;
 identity:=decode(checksum,'hex');
 expected:=octet_length(body);
 IF sha256(body)<>identity THEN RAISE EXCEPTION 'Compiled record checksum mismatch'; END IF;
 INSERT INTO native_compiled_record_bodies(sha256,raw,source_bytes)
 VALUES(identity,body,expected) ON CONFLICT(sha256) DO NOTHING
 RETURNING body_id INTO selected;
 IF selected IS NULL THEN
  SELECT body_id INTO selected FROM native_compiled_record_bodies
   WHERE sha256=identity AND source_bytes=expected AND raw=body;
  IF selected IS NULL THEN RAISE EXCEPTION 'Compiled body identity conflicts with stored bytes'; END IF;
 END IF;
 RETURN selected;
END $$;

CREATE FUNCTION write_native_compiled_content_record() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE selected bigint; storage_schema text;
BEGIN
 -- The function can only elevate writes originating from its own compatibility
 -- view. A caller cannot attach it to a view in another writable namespace.
 SELECT n.nspname INTO storage_schema
 FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
 JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE t.tgrelid=TG_RELID AND t.tgname=TG_NAME;
 IF storage_schema IS NULL OR TG_TABLE_SCHEMA<>storage_schema OR
    TG_RELID IS DISTINCT FROM to_regclass(format('%I.native_compiled_content_records',storage_schema)) THEN
  RAISE EXCEPTION 'Compiled record writer is attached to an unexpected relation';
 END IF;
 -- Builtins resolve in pg_catalog before the trusted storage namespace;
 -- pg_temp is last. The SET clause restores the caller on function exit.
 PERFORM set_config('search_path','pg_catalog,'||quote_ident(storage_schema)||',pg_temp',true);
 IF NOT pg_try_advisory_xact_lock_shared(hashtextextended(
  current_database()||':'||storage_schema||':compiled_catalog_maintenance',0)) THEN
  RAISE EXCEPTION 'Compiled catalog maintenance is active; retry this write'
   USING ERRCODE='40001';
 END IF;
 IF TG_OP='DELETE' THEN
  DELETE FROM native_compiled_record_links
   WHERE content_id=OLD.content_id AND record_key=OLD.record_key;
  RETURN OLD;
 END IF;
 selected:=intern_native_compiled_record_body(NEW.raw,NEW.sha256);
 IF TG_OP='INSERT' THEN
  INSERT INTO native_compiled_record_links(content_id,record_key,ordinal,body_id)
  VALUES(NEW.content_id,NEW.record_key,NEW.ordinal,selected);
 ELSE
  UPDATE native_compiled_record_links SET content_id=NEW.content_id,
   record_key=NEW.record_key,ordinal=NEW.ordinal,body_id=selected
   WHERE content_id=OLD.content_id AND record_key=OLD.record_key;
 END IF;
 RETURN NEW;
END $$;

-- Normal empty installs are immediately compact. Existing custom reader views
-- and grants are handled by the explicit compactor rather than dropped here.
DO $$
BEGIN
 IF (SELECT relkind='v' FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records'))
 AND NOT EXISTS(SELECT 1 FROM native_compiled_content_records LIMIT 1)
 AND (SELECT relacl IS NULL AND pg_get_userbyid(relowner)=current_user
      FROM pg_class WHERE oid=to_regclass('native_compiled_content_records'))
 AND NOT EXISTS(SELECT 1 FROM pg_attribute
                WHERE attrelid=to_regclass('native_compiled_content_records') AND attacl IS NOT NULL)
 AND NOT EXISTS(
  SELECT 1 FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid
   JOIN pg_class c ON c.oid=r.ev_class
   WHERE d.classid='pg_rewrite'::regclass AND d.refclassid='pg_class'::regclass
    AND d.refobjid=to_regclass('native_compiled_content_records')
    AND c.oid<>to_regclass('native_compiled_catalog_records')
 ) THEN
  ALTER TABLE native_compiled_content_records RENAME TO native_compiled_content_records_empty;
  CREATE VIEW native_compiled_content_records AS
   SELECT l.content_id,l.record_key,l.ordinal,b.raw,encode(b.sha256,'hex') AS sha256
   FROM native_compiled_record_links l JOIN native_compiled_record_bodies b USING(body_id);
  CREATE OR REPLACE VIEW native_compiled_catalog_records AS
   SELECT c.generation,c.collection,r.record_key,r.ordinal,r.raw,r.sha256
   FROM native_compiled_catalog_collections c
   JOIN native_compiled_content_records r USING(content_id);
  DROP TABLE native_compiled_content_records_empty;
  CREATE TRIGGER native_compiled_content_record_write
   INSTEAD OF INSERT OR UPDATE OR DELETE ON native_compiled_content_records
   FOR EACH ROW EXECUTE FUNCTION write_native_compiled_content_record();
 END IF;
END $$;
